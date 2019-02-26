import re, sys
import subprocess
import PyCmdMessenger
import serial.tools.list_ports
from flask import Flask, request, abort, jsonify, g
from flask_cors import CORS
from jsonschema import validate, ValidationError
from serial import SerialException
from .exceptions import InvalidUsage
from .exceptions import ArduinoError


arduino = None
messenger = None

commands = [
                ["kAcknowledge", "s"],
                ["kError", ""],
                ["kArduinoReady", ""],
                ["kTestMode", ""],
                ["kUpdateScoreboard", "ssssss"],
                ["kScoreboardUpdated", "ssssssssssss"],
                ["kGetCurrentScore", ""],
                ["kReturnCurrentScore", "ssssss"]
            ]

schema = {
  'scores': { 
    "type" : "object",
    "properties" : {
      "scorestr1" : {"type" : "string"},
      "scorestr2" : {"type" : "string"},      
    },
  },
}

scores = {"scorestr1": "0,0,0",
          "scorestr2": "0,0,-",
          }

def get_success(**kwargs):
    return jsonify(success=True, **kwargs)

def get_arduino_serial_port():
    for comport in serial.tools.list_ports.comports():
        if comport.manufacturer == 'Arduino (www.arduino.cc)':
            return comport.device
  
    return None

def create_app():

    app = Flask(__name__)    
    CORS(app)

    @app.route("/ping")
    def ping():
        """
        Method to allow pinging as a test of the API
        """
        return get_success(response="PONG")

    @app.route("/init")
    def init():
        """
        Init method to begin comms with the arduino
        and set the scores to zeroes
        """
        global arduino
        global messenger
        #Try and discover which serial/usb port the arduino is attached to
        ard_device = get_arduino_serial_port()
        if ard_device is None:
            raise InvalidUsage( 
                      message="Arduino not found in serial devices")

        #Attempt connection to the arduino
        try:

            arduino = PyCmdMessenger.ArduinoBoard(ard_device, 
                                            baud_rate=115200,
                                            int_bytes=2,
                                            long_bytes=4,
                                            float_bytes=4,
                                            double_bytes=4)

        except (ValueError, SerialException) as err:
            raise InvalidUsage(
                      message=err,
                      status_code=400,
                      payload={
                            'settings': {
                                'address': ard_device,
                                'baud_rate': 115200,
                                'int_bytes': 2,
                                'long_bytes': 4,
                                'float_bytes': 4,
                                'double_bytes': 4
                              }
                          }
                      )
          
        messenger = PyCmdMessenger.CmdMessenger(arduino, commands,
                          field_separator=',', command_separator='#')
        #Attempt to read ready message from arduino
        #timeout if nothing returned
        ready = messenger.receive()
        print(ready)
        if ready[0] != 'kAcknowledge':
            raise ArduinoError(
                message="Error communicating with Arduino",
                status_code=400)

        return get_success(response=ready)

    @app.route("/update", methods=['POST'])
    def update_score():
        """
        Route to update scoreboard.
        Expects json object in the format
        { 'scores': {
                scorestr1: "....",
                scorestr2: "...."
            }
        }
        """
        global arduino
        global messenger
        input_json = request.json

        print(input_json, file=sys.stderr)

        if not input_json or not 'scores' in request.json:
            raise InvalidUsage( 
                      message="'scores' object was not present in request'",
                      status_code=400,
                      payload=input_json)

        if not 'scorestr1' in input_json['scores'] or not 'scorestr2' in input_json['scores']: 
            raise InvalidUsage( 
                      message="'scoresstr1' or 'scorestr2' were not present in request'",
                      status_code=400,
                      payload=input_json )
        else:
            try:
                validate(instance=input_json, schema=schema)
            except ValidationError as err:
                raise InvalidUsage(message = err.message, status_code=400, payload=input_json)

            scores['scorestr1'] = input_json['scores']['scorestr1']
            scores['scorestr2'] = input_json['scores']['scorestr2']

        #Check score str are digits or -'s
        #If not return 406 not acceptable
        if re.match("[^-\d,]", scores['scorestr1']) or re.match("[^-\d,]", scores['scorestr2']):
            raise InvalidUsage(
                message="'scorestr1' or 'scorestr2' do not contain appropriate data [-\d,]",
                status_code=406, 
                payload=input_json)

        #Try and update via the arduino and expect a good return value
        str1_arr = scores['scorestr1'].split(",")
        str2_arr = scores['scorestr2'].split(",")

        # Check lengths of scores, some need --- adding?
        batAScore = str1_arr[0]
        batBScore = str1_arr[2]
        totalScore = str1_arr[1]
        wickets = str2_arr[0]
        overs = str2_arr[1]
        target = str2_arr[2]

        messenger.send("kUpdateScoreboard",
                        batAScore, totalScore,
                        batBScore, wickets,
                        overs, target)

        newmsg = messenger.receive()
        if newmsg[0] != 'kScoreboardUpdated':
            raise ArduinoError(
                message="Error updating score with Arduino",
                status_code=400)

        #Return a 202 (Acccepted code if accepted)
        return get_success(response=newmsg)

    @app.route("/currentscore")
    def get_score():
        """
        Route to get current score from the scoreboard.
        Returns json object as response in the format
        { 'scores': {
                scorestr1: "....",
                scorestr2: "...."
            }
        }
        """
        global messenger
        messenger.send("kGetCurrentScore")
        gotscore = messenger.receive()

        if gotscore[0] != 'kReturnCurrentScore':
            raise ArduinoError(
                message="Error fetching score from Arduino",
                status_code=400)

        print(gotscore)
        scores['scorestr1'] = "{},{},{}".format(gotscore[1][0], 
                                        gotscore[1][1],
                                        gotscore[1][2])
        scores['scorestr2'] = "{},{},{}".format(gotscore[1][3], 
                                        gotscore[1][4],
                                        gotscore[1][5])
        resp = {'scores': scores}
        return get_success(response=resp)

    return app
