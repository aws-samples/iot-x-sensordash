/*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

const { TimestreamWriteClient, WriteRecordsCommand  } = require("@aws-sdk/client-timestream-write");
const { IoTWirelessClient, ListTagsForResourceCommand, GetWirelessDeviceCommand  } = require("@aws-sdk/client-iot-wireless");
const { TimestreamQueryClient, QueryCommand  } = require("@aws-sdk/client-timestream-query");

const dbWriteClient = new TimestreamWriteClient({ region: process.env.AWS_REGION  })
const wirelessClient = new IoTWirelessClient({ region: process.env.AWS_REGION  });
const dbReadClient = new TimestreamQueryClient({ region: process.env.AWS_REGION });

const sleepNow = (delay) => new Promise((resolve) => setTimeout(resolve, delay))

exports.handler = async (event) => {
  
  await sleepNow(5000)
  console.log(event)
  if(event.eventType === undefined || event.thingName === undefined || event.operation === undefined){
    return;
  }
  //find the ARN for the wireless device
  const getCommand = new GetWirelessDeviceCommand({ Identifier: event.thingName, IdentifierType: "ThingName"});
  var getResponse = {}
  try{
    getResponse = await wirelessClient.send(getCommand);  
  }catch(e){}
  
  console.log(getResponse);
  var deviceArn = "";
  var devEui = "";
  var deviceName = "";
  var vendor = "";
  var model = "";
  
  if(getResponse.Arn !== undefined){
     deviceArn = getResponse.Arn;
     devEui = getResponse.LoRaWAN.DevEui
     deviceName = getResponse.Name
     //get the tags for the device
    const command = new ListTagsForResourceCommand({ ResourceArn: deviceArn});
    const tagResponse = await wirelessClient.send(command);
    console.log(tagResponse);
    
    if(tagResponse.Tags !== undefined){
      for(var i = 0; i < tagResponse.Tags.length; i++){
        if(tagResponse.Tags[i].Key === "Vendor"){
          vendor = tagResponse.Tags[i].Value 
        }
        if(tagResponse.Tags[i].Key === "Model"){
          model = tagResponse.Tags[i].Value 
        }
      }
    }
  }
  else{
    deviceArn = "arn:aws:iot:" + process.env.AWS_REGION + ":" + process.env.ACCOUNT_ID + ":thing/" + event.thingName;
    deviceName = event.thingName;
    devEui = event.thingName;
    model = "generic"
    vendor = "generic"
  }
  
  
  
  var databaseName =  process.env.TIMESTREAM_DATABASE_NAME
  var tableName = (process.env.TIMESTREAM_TABLE_NAME.split("|"))[1]
  
  var queryResponse = {}
  const queryCommand = new QueryCommand({QueryString : "select * from " + databaseName + "." + tableName + " where DevEui='" + devEui + "' and measure_value::varchar = 'CREATED'"});
  
  try{
    queryResponse = await dbReadClient.send(queryCommand);
  }catch(e){
    
  }
  console.log(queryResponse)
  
  var timestamp = Date.now().toString() // Unix time in milliseconds get jsonBody.e_timestamp
  
  var existingRecords = []
  if(queryResponse.Rows !== undefined){
    //load timestamp
    
    if(queryResponse.Rows.length > 0){
      
      for (var j = 0; j < queryResponse.Rows.length; j++){
        
        existingRecords[j] = {}
        for(var i = 0; i < queryResponse.Rows[j].Data.length; i++){
        
          existingRecords[j][queryResponse.ColumnInfo[i].Name] = queryResponse.Rows[j].Data[i].ScalarValue
         
        }
      }
    }
  }
  
  
  var records = []
  console.log(existingRecords)
   //if we are creating a new device with a deveui which is already in the database, delete all the existing ones to avoid duplicates
  if(existingRecords.length > 0){
    
    for(var i = 0; i < existingRecords.length; i++){
      
      timestamp = (new Date(existingRecords[i].time)).getTime().toString()
      const dimensionsForDelete = [
        {
          'Name': 'DevEui',
          'Value': existingRecords[i].DevEui
        },
        {
          'Name': 'Vendor',
          'Value': existingRecords[i].Vendor
        },
        {
          'Name': 'Model',
          'Value': existingRecords[i].Model
        },
        {
          'Name': 'Name',
          'Value': existingRecords[i].Name
        }
        
      ]
      records.push(
  
            {
                'Dimensions': dimensionsForDelete,
                'MeasureName': "status",
                'MeasureValue':  "DELETED",
                'MeasureValueType': "VARCHAR",
                'Time' : timestamp,
                'Version' : Date.now()
            } 
        )
    }
    
  }
  
//create a new sensor if the operation is CREATED  
 if(event.operation === "CREATED"){
    const dimensions = [
      {
        'Name': 'DevEui',
        'Value': devEui
      },
      {
        'Name': 'Vendor',
        'Value': vendor
      },
      {
        'Name': 'Model',
        'Value': model
      },
      {
        'Name': 'Name',
        'Value': deviceName
      }
      
    ]
  
    records.push(
  
            {
                'Dimensions': dimensions,
                'MeasureName': "status",
                'MeasureValue':  event.operation,
                'MeasureValueType': "VARCHAR",
                'Time': Date.now().toString(),
                'Version' : Date.now()
            } 
        )
 }


  const params = {
      DatabaseName: process.env.TIMESTREAM_DATABASE_NAME,
      TableName:  (process.env.TIMESTREAM_TABLE_NAME.split("|"))[1],
      Records: records
      
  }
  console.log(params);
  const writeCommand = new WriteRecordsCommand(params);
  var writeResponse = await dbWriteClient.send(writeCommand);
  console.log(writeResponse)
  
  
  var response = {
    statusCode: 200
  };
  return response;
};
