#!/usr/bin/env python

import time
import sys
import grovepi
import iothub_client
from iothub_client import *
from iothub_client_args import *
from datetime import datetime
import math
import json

DEVICE_ID = 'raspberry-1'

THRESHOLD_MIN = 10
THRESHOLD_MAX = 40

LIGHT_MIN = 0
LIGHT_MAX = 100

slide = 0  # pin 1 (yellow wire)
sensor = 4
light_sensor = 1
led = 3
relay = 7

grovepi.pinMode(relay, "OUTPUT")
grovepi.pinMode(led, "OUTPUT")
grovepi.pinMode(slide, "INPUT")
grovepi.pinMode(light_sensor, "INPUT")

# HTTP options
# Because it can poll "after 9 seconds" polls will happen effectively
# at ~10 seconds.
# Note that for scalabilty, the default value of minimumPollingTime
# is 25 minutes. For more information, see:
# https://azure.microsoft.com/documentation/articles/iot-hub-devguide/#messaging
timeout = 241000
minimum_polling_time = 9

# messageTimeout - the maximum time in milliseconds until a message times out.
# The timeout period starts at IoTHubClient.send_event_async.
# By default, messages do not expire.
message_timeout = 10000

receive_context = 0
received_count = 0

# global counters
receive_callbacks = 0
send_callbacks = 0
blob_callbacks = 0
override = 0

# chose HTTP, AMQP or MQTT as transport protocol
protocol = IoTHubTransportProvider.AMQP

# String containing Hostname, Device Id & Device Key in the format:
# "HostName=<host_name>;DeviceId=<device_id>;SharedAccessKey=<device_key>"
connection_string = "xxx"

msg = {}
msg["deviceId"] = DEVICE_ID


# some embedded platforms need certificate information


def set_certificates(iotHubClient):
    from iothub_client_cert import certificates
    try:
        iotHubClient.set_option("TrustedCerts", certificates)
        print("set_option TrustedCerts successful")
    except IoTHubClientError as e:
        print("set_option TrustedCerts failed (%s)" % e)


def receive_message_callback(message, counter):
    try:
        global receive_callbacks
        global override
        buffer = message.get_bytearray()
        size = len(buffer)
        print("Received Message [%d]:" % counter)
        print("    Data: <<<%s>>> & Size=%d" % (buffer[:size].decode('utf-8'), size))
        command = buffer[:size].decode('utf-8')
        if command == "ledon":
            override = 1
            grovepi.digitalWrite(led, 1)
        elif command == "ledoff":
            override = 1
            grovepi.digitalWrite(led, 0)
        elif command == "fanon":
            override = 1
            grovepi.digitalWrite(relay, 1)
        elif command == "fanoff":
            override = 1
            grovepi.digitalWrite(relay, 0)
        elif command == "reset":
            override = 0
        counter += 1
        receive_callbacks += 1
        return IoTHubMessageDispositionResult.ACCEPTED
    except:
        return IoTHubMessageDispositionResult.ACCEPTED


def send_confirmation_callback(message, result, user_context):
    return
    global send_callbacks
    try:
        print(
            "Confirmation[%d] received for message with result = %s" %
            (user_context, result))
        map_properties = message.properties()
        print("    message_id: %s" % message.message_id)
        print("    correlation_id: %s" % message.correlation_id)
        send_callbacks += 1
        print("    Total calls confirmed: %d" % send_callbacks)
    except:
        pass


def iothub_client_init():
    # prepare iothub client
    iotHubClient = IoTHubClient(connection_string, protocol)
    if iotHubClient.protocol == IoTHubTransportProvider.HTTP:
        iotHubClient.set_option("timeout", timeout)
        iotHubClient.set_option("MinimumPollingTime", minimum_polling_time)
    # set the time until a message times out
    iotHubClient.set_option("messageTimeout", message_timeout)
    # some embedded platforms need certificate information
    # set_certificates(iotHubClient)
    # to enable MQTT logging set to 1
    if iotHubClient.protocol == IoTHubTransportProvider.MQTT:
        iotHubClient.set_option("logtrace", 0)

    iotHubClient.set_message_callback(receive_message_callback, receive_context)
    return iotHubClient


def normalise(val, min, max, rangemin, rangemax):
    norm = float(val - min) / float(max - min)
    return math.ceil(norm * float(rangemax - rangemin) + rangemin)



def iothub_client_sample_run():
    global override
    i = 0
    while True:
        try:
            iotHubClient = iothub_client_init()
            while True:
                # time.sleep(0.2)
                # Read sensor value from potentiometer
                threshold = grovepi.analogRead(slide)
                # threshold = THRESHOLD_MIN + int(THRESHOLD_MAX * (1024 - threshold) / 1024)
                threshold = normalise(threshold, 0, 1024, THRESHOLD_MIN, THRESHOLD_MAX)

                [temp, humidity] = grovepi.dht(sensor, 0)
                light = grovepi.analogRead(light_sensor)
                light = normalise(light, 0, 800, LIGHT_MIN, LIGHT_MAX)
                # light = (1 + float(light - 800) / 800) * 100

                print "temp =", temp, " humidity =", humidity, " threshold =", threshold, "light =", light

                if math.isnan(temp) or math.isnan(humidity) or math.isnan(
                        light) or threshold > THRESHOLD_MAX or threshold < THRESHOLD_MIN or light > LIGHT_MAX or light < LIGHT_MIN:
                    print "skipping this round, error readings"
                    continue


                if override == 0:
                    if light < 30:
                        grovepi.digitalWrite(led, 1)  # Send HIGH to switch on LED
                    else:
                        grovepi.digitalWrite(led, 0)  # Send LOW to switch off LED

                    if threshold < temp:
                        grovepi.digitalWrite(relay, 1)
                    else:
                        grovepi.digitalWrite(relay, 0)

                msg["temperature_threshold"] = threshold
                msg["temperature"] = temp
                msg["humidity"] = humidity
                msg["utctimestamp"] = datetime.today().isoformat()
                msg["light"] = light
                msg["fan_state"] = grovepi.digitalRead(relay)

                message = IoTHubMessage(json.dumps(msg))
                message.message_id = "message_%s_%d" % (DEVICE_ID, i)
                message.correlation_id = "correlation_%s_%d" % (DEVICE_ID, i)
                iotHubClient.send_event_async(message, send_confirmation_callback, i)
                i += 1

        except IoTHubError as e:
            print("Unexpected error %s from IoTHub" % e)
        except KeyboardInterrupt:
            print("IoTHubClient sample stopped")
            grovepi.digitalWrite(led, 0)
            grovepi.digitalWrite(relay, 0)
            sys.exit(0)
        except IOError:
            print "Error"
        except Exception:
            print Exception


            # print_last_message_time(iotHubClient)


def usage():
    print("Usage: iothub_client_sample.py -p <protocol> -c <connectionstring>")
    print("    protocol        : <amqp, http, mqtt>")
    print("    connectionstring: <HostName=<host_name>;DeviceId=<device_id>;SharedAccessKey=<device_key>>")


if __name__ == '__main__':
    print("\nPython %s" % sys.version)
    print("IoT Hub for Python SDK Version: %s" % iothub_client.__version__)

    try:
        (connection_string, protocol) = get_iothub_opt(sys.argv[1:], connection_string, protocol)
    except OptionError as o:
        print(o)
        usage()
        sys.exit(1)

    print("Starting the IoT Hub Python sample...")
    print("    Protocol %s" % protocol)
    print("    Connection string=%s" % connection_string)

    iothub_client_sample_run()
