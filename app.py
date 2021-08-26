import argparse
import ipaddress
import os
import time

import discoverhue
import pygame
from flask import Flask, request, make_response, jsonify
from flask_cors import CORS
from phue import Bridge
from nanoleafapi import Nanoleaf
from NanoLeafDiscovery import nano

from helpers import *

app = Flask(__name__)

pygame.init()
pygame.mixer.init()

dock = None
bridge = None


################################################################################
# Important Note: create a music folder in root, add mp3 files for music control


@app.route('/discover_bridge', methods=['GET'])
def discover():
    try:
        if request.method == 'GET':
            # Phillips Hue lights
            hue_found = discoverhue.find_bridges()
            for bridge in hue_found:
                print(' Phillips Bridge ID {br} at {ip}'.format(br=bridge, ip=hue_found[bridge]))

            # Nanoleaft lights
            nl_found = nano.discover(_id=True)
            for d in nl_found:
                print(' Nanoleaf Dock ID {dock} at {ip}'.format(dock=d['id'], ip=d['ip']))

            return make_response(jsonify({'phillips': hue_found, 'nanoleaf': nl_found}), 200)
    except Exception as e:
        print(e)


@app.route('/connect_lights', methods=['POST'])
def connect():
    try:
        # Validate if valid ip_address
        ipaddress.ip_address(request.json['dock_ip'])
        ipaddress.ip_address(request.json['bridge_ip'])
        if request.method == 'POST':
            # Create Bridge object. For the first time is required to push the Phillips Bridge's power button
            global bridge
            bridge = Bridge(request.json['bridge_ip'])

            # Create Dock object. For the first time is required to push the Nanoleaf Dock's power button
            global dock
            dock = Nanoleaf(request.json['dock_ip'])

            return make_response(jsonify({'message': 'dock_connected'}), 200)
    except ValueError:
        print(f"IP address not valid, please check them")
    except Exception as e:
        print(e)


@app.route('/control_lights', methods=['POST'])
def control():
    try:
        if request.method == 'POST':
            # For the first time is required to push the Bridge's button before execute the code delow
            bridge.connect()
            status = bridge.get_api()
            if any('error' in i for i in status):
                return make_response(jsonify(status), 500)

            lights = bridge.get_group('lab', 'lights')
            current_status = bridge.get_group('lab')['state']['any_on']

            # Light parameters command
            [r, g, b] = request.json['rgb'] \
                if ('rgb' in request.json and request.json['rgb'] is not None) \
                else [255, 255, 255]
            on = request.json['on'] if ('on' in request.json and request.json['on'] is not None) else None
            lights = request.json['lights'] \
                if ('lights' in request.json and request.json['lights'] is not None) \
                else lights
            light_ids = [int(light) for light in lights]  # get the light_id in int format

            command = rgbTohue(r, g, b)
            if on is not None and current_status != on:
                command['on'] = on

            # execute commands in lights
            bridge.set_light(light_ids, command)

            print("Phillips Hue state:")
            print(bridge.get_api())  # Get the status after change

            return make_response(jsonify({'message': 'command executed successfully'}), 200)
    except Exception as e:
        print(e)


@app.route('/control_nanoleaf', methods=['POST', 'PUT'])
def control_nano():
    try:
        if request.method == 'POST':
            [r, g, b] = request.json['rgb'] \
                if ('rgb' in request.json and request.json['rgb'] is not None) \
                else [255, 255, 255]
            on = request.json['on'] if ('on' in request.json and request.json['on'] is not None) else None

            # Validate if nanoleaf is on
            power = dock.get_power()
            if on or (power and on is None):
                dock.set_color((r, g, b))
            else:
                dock.power_off()

            print("Nanoleaf state:")
            print(f"on: {dock.get_power()}, "
                  f"hue: {dock.get_hue()}, "
                  f"bri: {dock.get_brightness()}, "
                  f"sat: {dock.get_saturation()}")  # Get the status after change

            return make_response(jsonify({'message': 'command executed successfully'}), 200)
    except Exception as e:
        print(e)


@app.route('/control_music/<action>', methods=['GET'])
def music(action):
    try:
        if request.method == 'GET':
            path = "./music/"
            track_list = os.listdir(path)
            pygame.mixer.music.set_volume(0) if action == "stop" else pygame.mixer.music.set_volume(1)
            for song in track_list:
                if song.endswith(".mp3"):
                    song_path = path + song
                    pygame.mixer.music.load(str(song_path))
                    print(action)
                    if action == "stop":
                        pygame.mixer.music.stop()
                        time.sleep(0.5)
                        pygame.mixer.music.unload()
                    elif action == "play":
                        pygame.mixer.music.play()
                        print("Playing... " + song)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.3)
            return make_response(jsonify({'message': 'command executed successfully'}), 200)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description="Phillips hue lights and music control")
    PARSER.add_argument('--debug', action='store_true',
                        help="Use flask debug/dev mode with file change reloading")
    ARGS = PARSER.parse_args()

    PORT = 5555

    # cross origen support
    CORS(app)

    if ARGS.debug:
        print("Running in debug mode")
        app.run(host='0.0.0.0', port=PORT, debug=True)
    else:
        app.run(host='0.0.0.0', port=PORT, debug=False)
