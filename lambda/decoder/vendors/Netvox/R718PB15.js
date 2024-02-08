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
    
    this.decode = function(bytes, port){

        if(port !== 6){
            return undefined;
        }
        var version = bytes[0];
        var deviceType = bytes[1];
        var reportType = bytes[2];
        if(deviceType !== 0x58){
            return undefined;
        }
        if(reportType == 0x0A){
            var battery = (bytes[3] / 10);
            var soil_vwc = ((bytes[4] << 8) + bytes[5]) * 0.01;
            var soil_temperature = ((bytes[6] << 8) + bytes[7]) * 0.01;
            var water_level = ((bytes[8] << 8) + bytes[9]);
            var soil_ec = bytes[10] * 0.1;
            return {
                battery: battery,
                soil_vwc : soil_vwc,
                soil_temperature: soil_temperature,
                water_level: water_level,
                soil_ec: soil_ec
            }
        }
        else if(reportType == 0x10){
            var battery = (bytes[3] / 10);
            var soil_vwc = ((bytes[4] << 8) + bytes[5]) * 0.01;
            var soil_temperature = ((bytes[6] << 8) + bytes[7]) * 0.01;
            var soil_ec = bytes[8] * 0.01;
            return {
                battery: battery,
                soil_vwc : soil_vwc,
                soil_temperature: soil_temperature,
                soil_ec: soil_ec
            }
        }
        else{
            return undefined;
        }
      
    }
}