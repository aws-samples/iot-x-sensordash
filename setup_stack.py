# /*
#  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  * SPDX-License-Identifier: MIT-0
#  *
#  * Permission is hereby granted, free of charge, to any person obtaining a copy of this
#  * software and associated documentation files (the "Software"), to deal in the Software
#  * without restriction, including without limitation the rights to use, copy, modify,
#  * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  * permit persons to whom the Software is furnished to do so.
#  *
#  * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#  * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#  * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#  * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#  */
import os
import boto3
from datetime import datetime
import sys
import time
import json
import random
import requests


TEMPLATE_PATH = "cfn/stack.json"
STACK_CREATE_TIMEOUT = 600 #seconds
DECODER_FUNC_PATH = "lambda/decoder/"
LIST_FUNC_PATH = "lambda/list/"
STACK_OUTPUT_PATH = "stack_output.json"
DASHBOARD_PATH = "dashboards/"

stack_name = "sensordash"
if len(sys.argv) >= 2:
    stack_name = sys.argv[1]

skip_stack_create = False
skip_lambda_update = False

for arg in sys.argv:
    if arg == "--skip-stack-create":
        skip_stack_create = True
    if arg == "--skip-lambda-update":
        skip_lambda_update = True




grafana_url = ""
decoder_lambda_name = ""
list_lambda_name = ""
db_name = ""
data_table_name = ""

if skip_stack_create == False:

    #1. Create stack with cloudformation
    stack_file = open(TEMPLATE_PATH, "r")
    stack_json = stack_file.read()
    stack_file.close() 

    cfn = boto3.client('cloudformation')
    print("1. Creating stack : " + stack_name)
    create_ret = cfn.create_stack(StackName = stack_name, TemplateBody = stack_json, Capabilities=['CAPABILITY_IAM'])
    print(create_ret)
    if 'StackId' not in create_ret:
        print("Could not create stack!")
        exit()

    stack_id = create_ret['StackId']

    #2. Query stack creation state
    start_time = datetime.now().timestamp()
    create_complete = False
    outputs = {}
    last_stack_status = ""
    while datetime.now().timestamp() < start_time + STACK_CREATE_TIMEOUT:
        time.sleep(10)
        desc_ret = cfn.describe_stacks(StackName = stack_name)
        if 'Stacks' not in desc_ret:
            print("Stack description request failed!")
            exit()
        for stack in desc_ret['Stacks']:
            if stack['StackId'] == stack_id:
                stack_status = stack['StackStatus']
                if last_stack_status == stack_status:
                    print(".")
                else:
                    last_stack_status = stack_status
                    print(stack_status)

                if stack_status.endswith("_FAILED"):
                    print("Stack creation failed!")
                    exit()
                elif stack_status == "CREATE_COMPLETE":
                    create_complete = True
                    outputs = stack['Outputs']
                    print("2. Stack created")
                    break

        if create_complete == True:
            break

    if create_complete == False:
        print("Stack creation timed out!")
        exit()


    if outputs == {}:
        print("No stack creation outputs found. Quitting now")
        exit()

    

    for output in outputs:
        if output['OutputKey'] == "DecoderLambdaName":
            decoder_lambda_name = output['OutputValue']
        if output['OutputKey'] == "ListLambdaName":
            list_lambda_name = output['OutputValue']
        if output['OutputKey'] == "GrafanaURL":
            grafana_url = output['OutputValue']
        if output['OutputKey'] == "TimestreamDBName":
            db_name = output['OutputValue']
        if output['OutputKey'] == "TimestreamDataTableName":
            data_table_name = output['OutputValue'].split("|")[1]
        

    if decoder_lambda_name == "":
        print("Decoder lambda name not found. Quitting now")
        exit()
    if list_lambda_name == "":
        print("List lambda name not found. Quitting now")
        exit()
    if grafana_url == "":
        print("Grafana URL not found. Quitting now")
        exit()
    if db_name == "":
        print("Timestream database name not found in stack outputs. Quitting now")
        exit()
    if data_table_name == "":
        print("Timestream table name not found in stack outputs. Quitting now")
        exit()

    output_str = json.dumps(outputs)
    stack_output_file = open(STACK_OUTPUT_PATH, "w")
    stack_output_file.write(output_str)
    stack_output_file.close() 

else:
    # if we are skipping stack creation, load the outputs from the previous stack creation
    print("1. Loading stack information from previous creation")
    stack_output_file = open(STACK_OUTPUT_PATH, "r")
    stack_output = stack_output_file.read()
    stack_output_file.close() 
    stack_output_json = json.loads(stack_output)

    for output in stack_output_json:
        if output['OutputKey'] == "DecoderLambdaName":
            decoder_lambda_name = output['OutputValue']
        if output['OutputKey'] == "ListLambdaName":
            list_lambda_name = output['OutputValue']
        if output['OutputKey'] == "GrafanaURL":
            grafana_url = output['OutputValue']
        if output['OutputKey'] == "TimestreamDBName":
            db_name = output['OutputValue']
        if output['OutputKey'] == "TimestreamDataTableName":
            data_table_name = output['OutputValue'].split("|")[1]
        

    if decoder_lambda_name == "":
        print("Decoder lambda name not found. Quitting now")
        exit()
    if list_lambda_name == "":
        print("List lambda name not found. Quitting now")
        exit()
    if grafana_url == "":
        print("Grafana URL not found. Quitting now")
        exit()
    if db_name == "":
        print("Timestream database name not found in stack outputs. Quitting now")
        exit()
    if data_table_name == "":
        print("Timestream table name not found in stack outputs. Quitting now")
        exit()


#3. Update Lambda function

if skip_lambda_update == False:
    lmb = boto3.client('lambda')

    print("3.1 Updating decoder lambda function: " + decoder_lambda_name)
    print("Zipping source files")
    decoder_zip_ret = os.system('cd ' + DECODER_FUNC_PATH + " && zip -r code.zip *")
    print(decoder_zip_ret)

    decoder_zip_file = open(DECODER_FUNC_PATH + "code.zip", "rb")
    decoder_zip_body = decoder_zip_file.read()
    decoder_zip_file.close() 

    decoder_lmb_ret = lmb.update_function_code(FunctionName = decoder_lambda_name, ZipFile = decoder_zip_body)

    if 'FunctionName' in decoder_lmb_ret:
        print("Decoder lambda function updated successfully")
    else:
        print("Decoder lambda function update failed!")

    print("3.2 Updating list lambda function: " + list_lambda_name)
    print("Zipping source files")
    list_zip_ret = os.system('cd ' + LIST_FUNC_PATH + " && zip -r code.zip *")
    print(list_zip_ret)

    list_zip_file = open(LIST_FUNC_PATH + "code.zip", "rb")
    list_zip_body = list_zip_file.read()
    list_zip_file.close() 

    list_lmb_ret = lmb.update_function_code(FunctionName = list_lambda_name, ZipFile = list_zip_body)

    if 'FunctionName' in list_lmb_ret:
        print("List lambda function updated successfully")
    else:
        print("List lambda function update failed!")


#4. Enable IoT thing create notification

print("4. Enabling thing event notifications in IoT Core")
iot = boto3.client('iot')
event_response = iot.update_event_configurations(
    eventConfigurations={
        'THING': {
            'Enabled': True
        }
    }
)


#5. Create a API key for Grafana

print("5. Creating template dashboards")
grafana = boto3.client('grafana')
create_key_response = grafana.create_workspace_api_key(
    keyName = "key-" + str(random.randint(0,1000000)),
    keyRole = 'ADMIN',
    secondsToLive = 3600,
    workspaceId = grafana_url.split(".")[0]
)

session_token = create_key_response['key']
grafana_url = "https://" + grafana_url

#6. Create the Timestream DataSource in Grafana if it is not already created

get_ds_response = requests.get(grafana_url + "/api/datasources", headers = {"Authorization": "Bearer " + session_token}).text


if 'message' in get_ds_response:
    print(get_ds_response)
    exit()

get_ds_response_json = json.loads(get_ds_response)
ds_uid = ""

for ds in get_ds_response_json:
    if ds['type'] == 'grafana-timestream-datasource':
        ds_uid = ds['uid']
        print("Data source with uid = " + ds_uid + " already exists")

if ds_uid == "":
    create_ds_request = {

        "name":"Amazon Timestream",
        "type":"grafana-timestream-datasource",
        "typeName":"Amazon Timestream",
        "typeLogoUrl":"public/plugins/grafana-timestream-datasource/img/timestream.svg",
        "access":"proxy",
        "jsonData": {
            "authType" : "ec2_iam_role",
            "defaultDatabase" : "\""+ db_name +"\"",
            "defaultTable": "\""+ data_table_name +"\"",
            "defaultRegion": os.environ['AWS_REGION']
        }

    }
    create_ds_response = requests.post(
                                                grafana_url + '/api/datasources', 
                                                json = create_ds_request,
                                                headers = {"Authorization": "Bearer " + session_token}
                                            ).text

    create_ds_response_json = json.loads(create_ds_response)


    if create_ds_response_json['message'] != "Datasource added":
        print("Failed to create timestream datasource")
        print(create_ds_response)
        exit()
    else:
        print("Data source created")

    ds_uid = create_ds_response_json['datasource']['uid']

#7. Create the dashboards

#get a list of all the folders in Grafana
get_folder_response = requests.get(grafana_url + "/api/folders", headers = {"Authorization": "Bearer " + session_token}).text
get_folder_response_json = json.loads(get_folder_response)
grafana_folders = {}
for grafana_folder in get_folder_response_json:
    grafana_folders[grafana_folder['title']] = grafana_folder
#get a list of all the folders in the dashboards folder

dashboard_folders = os.listdir(DASHBOARD_PATH)
#iterate over the dashboard folders
for dashboard_folder in dashboard_folders:
    #check if it is actually a folder
    if os.path.isdir(DASHBOARD_PATH + dashboard_folder):
        folder_uid = ""
        #create a folder with the same name if it doesn't exist
        if dashboard_folder not in grafana_folders:
            create_folder_response = requests.post(grafana_url + '/api/folders',  json = {"title" : dashboard_folder}, headers = {"Authorization": "Bearer " + session_token})
            if create_folder_response.status_code != 200:
                print("Failed to create folder: " + dashboard_folder)
                exit()
            create_folder_response_json = json.loads(create_folder_response.text)
            folder_uid = create_folder_response_json['uid']
            print("Created folder " + dashboard_folder)

        else:
            folder_uid = grafana_folders[dashboard_folder]['uid']

        print("Creating dashboards in folder " + dashboard_folder)
        #list all the dashboard files in this local folder
        dashboard_filenames = os.listdir(DASHBOARD_PATH + dashboard_folder + "/")
        for dashboard_filename in dashboard_filenames:
            if dashboard_filename.endswith(".json"):
                dashboard_file = open(DASHBOARD_PATH + dashboard_folder + "/" + dashboard_filename, "r")
                dashboard_str = dashboard_file.read()
                dashboard_file.close()
                dashboard_json = json.loads(dashboard_str)

                #update the datasource uid in panels and templating
                for panel in dashboard_json['panels']:
                    if 'datasource' in panel:
                        if panel['datasource']['type'] == "grafana-timestream-datasource":
                            panel['datasource']['uid'] = ds_uid
                    if 'targets' in panel:
                        for target in panel['targets']:
                            if 'datasource' in target:
                                if target['datasource']['type'] == "grafana-timestream-datasource":
                                    target['datasource']['uid'] = ds_uid

                for item in dashboard_json['templating']['list']:
                    if 'datasource' in item:
                        if item['datasource']['type'] == "grafana-timestream-datasource":
                            item['datasource']['uid'] = ds_uid

                dashboard_uid = dashboard_json['uid']

                #check if a dashboard with the same uid exists
                get_dashboard_response = requests.get(grafana_url + "/api/dashboards/uid/" + dashboard_uid, headers = {"Authorization": "Bearer " + session_token})
                #create dashboard if it doesn't exist
                if get_dashboard_response.status_code == 404:
                    #id has to be null when creating new dashboard
                    dashboard_json.pop('id')
                    create_dashboard_request = {
                        "dashboard" : dashboard_json,
                        "folderUid" : folder_uid,
                        "message" : "",
                        "overwrite" : False
                    }
                    create_dashboard_response = requests.post(grafana_url + "/api/dashboards/db", json = create_dashboard_request, headers = {"Authorization": "Bearer " + session_token})
                    if create_dashboard_response.status_code == 200:
                        print("Created dashboard: " + dashboard_filename)
                    else:
                        print("Failed to create dashboard: " + dashboard_filename)
                        print(create_dashboard_response.text)

                else:
                    print("Dashboard exists: " + dashboard_filename)
        



print("")
print("Next steps: >>>>")
print("1. Navigate to the Amazon Managed Grafana page in the AWS console and click on the workspace name")
print("2. Assign a user under Authentication > AWS IAM Identity Center")
print("3. Make the user an Admin")
print("4. Login to your Grafana URL: " + grafana_url + " with the credentials for the assigned user and start exploring!")






