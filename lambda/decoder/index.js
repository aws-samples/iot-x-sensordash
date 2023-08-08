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
const { IoTWirelessClient, ListTagsForResourceCommand  } = require("@aws-sdk/client-iot-wireless");

const dbClient = new TimestreamWriteClient({ region: process.env.AWS_REGION  })
const wirelessClient = new IoTWirelessClient({ region: process.env.AWS_REGION  });


exports.handler = async (event) => {
    
    //check the vendor, model and call the relevant decoder
    async function decoder(payload, event){
        
        var deviceArn = "arn:aws:iotwireless:" + process.env.AWS_REGION + ":" + process.env.ACCOUNT_ID + ":WirelessDevice/" + event.WirelessDeviceId;
        const command = new ListTagsForResourceCommand({ ResourceArn: deviceArn});
        const response = await wirelessClient.send(command);
        console.log(response);
        var vendor = "";
        var model = "";
        if(response.Tags !== undefined){
          for(var i = 0; i < response.Tags.length; i++){
            if(response.Tags[i].Key === "Vendor"){
              vendor = response.Tags[i].Value 
            }
            if(response.Tags[i].Key === "Model"){
              model = response.Tags[i].Value 
            }
          }
        }
        if(vendor !== "" && model !== ""){
            
            var decoder = require("./vendors/" + vendor + "/" + model + ".js")
            var decoderObj = new decoder()
            return decoderObj.decode(payload, event.WirelessMetadata.LoRaWAN.FPort)
          
        }
        return undefined;
    }
    
    //finally write the decoded payload to timestream
    async function writeToTimstream(decodedPayload){
        
      
        const currentTime = Date.now().toString() // Unix time in milliseconds get jsonBody.e_timestamp
        const dimensions = [{
            'Name': 'DevEui',
            'Value': event.WirelessMetadata.LoRaWAN.DevEui
        }]
        var records = []
        for(var measureName in decodedPayload){
            var measureValueType = "VARCHAR";
            switch(typeof(decodedPayload[measureName])){

                case "number":
                    measureValueType = "DOUBLE";
                    break;

                case "bigint":
                    measureValueType = "BIGINT";
                    break;

                case "boolean":
                    measureValueType = "BOOLEAN";
                    break;

                case "string":
                    measureValueType = "VARCHAR";
                    break;

                default:
            }
            records.push(

                {
                    'Dimensions': dimensions,
                    'MeasureName': measureName,
                    'MeasureValue':  decodedPayload[measureName].toString(),
                    'MeasureValueType': measureValueType,
                    'Time': currentTime
                } 
            )
        }
     
        const params = {
            DatabaseName: process.env.TIMESTREAM_DATABASE_NAME,
            TableName:  (process.env.TIMESTREAM_TABLE_NAME.split("|"))[1],
            Records: records
        }
        console.log(params);
        const command = new WriteRecordsCommand(params);
        var response = await dbClient.send(command);
        console.log(response)
    }
    
    
    //base 64 decode of lorawan payload
    var payload = Buffer.from(event.PayloadData, 'base64');
    //decode binary payload and convert to JSON
    var decodedPayload = await decoder(payload, event);
    //write to timestream
    if(decodedPayload !== undefined){
      await writeToTimstream(decodedPayload);
    }

};