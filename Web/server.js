'use strict';

var express = require('express');
var bodyParser = require('body-parser');

var ServiceClient = require('azure-iothub').Client;
var Message = require('azure-iot-common').Message;
var DeviceConnectionString = require('azure-iot-device').ConnectionString;
var nconf = require('nconf');

nconf.argv().env().file('./config.json');
var deviceConnString = nconf.get('deviceConnString');
var iotHubConnString = nconf.get('iotHubConnString');

var deviceId = DeviceConnectionString.parse(deviceConnString).DeviceId;
var iotHubClient = ServiceClient.fromConnectionString(iotHubConnString);

var app = express();
var port = process.env.PORT || 1337;
app.use(express.static('public'));
app.use(express.static('bower_components'));
app.use(bodyParser.json());

var completedCallback = function(err, res) {
    if (err) { console.log(err); }
    else { console.log(res); }
};

app.post('/api/command', function(req, res) {
    console.log('command received: ' + req.body.command);
	
    iotHubClient.open(function(err) {
        if (err) {
            console.error('Could not connect: ' + err.message);
        } else {
            var data = req.body.command;
            var message = new Message (data);
            console.log('Sending message: ' + data);
            iotHubClient.send(deviceId, message, printResultFor('send'));
        }
    });

    // Helper function to print results in the console
    function printResultFor(op) {
        return function printResult(err, res) {
            if (err) {
                console.log(op + ' error: ' + err.toString());
            } else {
                console.log(op + ' status: ' + res.constructor.name);
            }
        };
    }

    res.end();
});

app.listen(port, function() {
    console.log('app running on http://localhost:' + port);
});
