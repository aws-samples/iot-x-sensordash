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
import requests
import json

STACK_OUTPUT_PATH = "stack_output.json"
DASHBOARD_PATH = "dashboards/"


if len(sys.argv) < 2:
    print("Usage: python3 setup_dashboard.py <grafana_session_token>")
    exit()

session_token = sys.argv[1]



#1. load the config from the stack setup stage done previously
stack_output_file = open(STACK_OUTPUT_PATH, "r")
stack_output = stack_output_file.read()
stack_output_file.close() 
stack_output_json = json.loads(stack_output)

grafana_url = ""
db_name = ""
data_table_name = ""

for output in stack_output_json:
    if output['OutputKey'] == "GrafanaURL":
        grafana_url = "https://" + output['OutputValue']
    if output['OutputKey'] == "TimestreamDBName":
        db_name = output['OutputValue']
    if output['OutputKey'] == "TimestreamDataTableName":
        data_table_name = output['OutputValue'].split("|")[1]
  

if grafana_url == "":
    print("Grafana URL not found in stack outputs. Quitting now")
    exit()
if db_name == "":
    print("Timestream database name not found in stack outputs. Quitting now")
    exit()
if data_table_name == "":
    print("Timestream table name not found in stack outputs. Quitting now")
    exit()


#2. Check if there is a timestream datasource already
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


#3. Create the Timestream DataSource in Grafana if it is not already created

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

#4. Create the dashboards

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
        



        





