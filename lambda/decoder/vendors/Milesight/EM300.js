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
module.exports = function(){
    
    //Payload format: [channel (1 byte), type (1 byte), value (n bytes),... <repeat>]
    var channelMap = {
        "1" : { 
                "75" : {name: "battery", valueType: "uint8"}
                } ,
        "3" : { 
                "67" : {name: "temperature", valueType: "int16"}
            },
        "4" : { 
                "68" : {name: "humidity", valueType: "uint8"}
            },
        "5" : { 
                "00" : {name: "water_leak", valueType: "uint8"}, 
                "c8" : { name: "counter" , valueType: "uint32"}
            },
        "6" : { 
                "00" : { name: "magnet_switch", valueType: "uint8"}
            }
    }
    this.decode = function(bytes, port){

        var response = {}
        for(var i = 0; i < bytes.length; i++){
            if(channelMap[bytes[i].toString(16)] !== undefined){
                if(channelMap[bytes[i].toString(16)][bytes[i + 1].toString(16)] !== undefined){
                    var name = channelMap[bytes[i].toString(16)][bytes[i + 1].toString(16)]["name"];
                    var valueType = channelMap[bytes[i].toString(16)][bytes[i + 1].toString(16)]["valueType"];
                    var value = 0;
                    switch(valueType){
                        case "uint8":
                            value = bytes[i + 2]
                            break;

                        case "int16":
                            value = bytes[i + 2] << 8 + bytes[i + 3]
                            break;
                        
                        case "uint32":
                            value = bytes[i + 2] << 24 + bytes[i + 3] << 16 + bytes[i + 4] << 8 + bytes[i + 5]
                            break;

                    }
                    response[name] = value
                }
            }
        }
        return response;
    }
}