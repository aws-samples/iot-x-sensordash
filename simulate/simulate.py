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
from datetime import datetime, timedelta
import sys
import time
import requests
import json
import random
#this script writes random data in the given range for the given device to the sensor data table i timestream
# Usage: python3 simulate.py <Dev Eui> <measure name> <start date> <end date> <measure min> <measure max> <db name> <table name>

STACK_OUTPUT_PATH = "../stack_output.json"
WRITE_BATCH_SIZE = 100


if len(sys.argv) < 8:
    print("Usage: python3 simulate.py <Dev Eui> <measure name> <start date> <end date> <measure min> <measure max> <interval s> [db name] [table name]")
    print("\teg: python3 simulate.py 0102030405060708 temperature 2023-01-01T00:00:00 2023-01-01T01:00:00 20 30 600")
    exit()

dev_eui = sys.argv[1]
measure_name = sys.argv[2]
start_time = datetime.fromisoformat(sys.argv[3])
end_time = datetime.fromisoformat(sys.argv[4])
measure_min = sys.argv[5]
measure_max = sys.argv[6]
interval = sys.argv[7]
db_name = ""
table_name = ""

if len(sys.argv) >= 10:
    db_name = sys.argv[8]
    table_name = sys.argv[9]
else:
    stack_output_file = open(STACK_OUTPUT_PATH, "r")
    stack_output = stack_output_file.read()
    stack_output_file.close() 
    stack_output_json = json.loads(stack_output)

    for output in stack_output_json:
       
        if output['OutputKey'] == "TimestreamDBName":
            db_name = output['OutputValue']
        if output['OutputKey'] == "TimestreamDataTableName":
            table_name = output['OutputValue'].split("|")[1]


if db_name == "" or table_name == "":
    print("Db name and/or table name not found. Quitting now")
    exit()


next_time = start_time
db_client = boto3.client('timestream-write')

records = []

while next_time.timestamp() <= end_time.timestamp():

    measure_value = random.randint(int(measure_min), int(measure_max))
    record = {
                'Dimensions': [
                    {
                        'Name': 'DevEui',
                        'Value': dev_eui,
                        'DimensionValueType': 'VARCHAR'
                    },
                ],
                'Time': str(round(next_time.timestamp())),
                'TimeUnit': 'SECONDS',
                'MeasureName' : measure_name,
                'MeasureValue' : str(measure_value),
                'MeasureValueType' : 'DOUBLE'
                
            }
    records.append(record)
    next_time = next_time + timedelta(seconds = int(interval))

    if len(records) >= WRITE_BATCH_SIZE:

        response = db_client.write_records(
            DatabaseName = db_name,
            TableName = table_name,
            Records = records
        )
        print(response)
        records = []


if len(records) > 0:

    response = db_client.write_records(
        DatabaseName = db_name,
        TableName = table_name,
        Records = records
    )
    print(response)
