from xml.etree.ElementTree import VERSION
import requests
import paho.mqtt.client as mqtt
import os
import json
import logging
import time
import re

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
logging.basicConfig(level=LOGLEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main')

VERSION = "2.0.0"

OCTOPRINT_API_KEY = os.environ.get('OCTOPRINT_API_KEY')
OCTOPRINT_ADDRESS = os.environ.get('OCTOPRINT_ADDRESS')
OCTOPRINT_USE_SSL = os.environ.get('OCTOPRINT_USE_SSL')

MQTT_ADDRESS = os.environ.get('MQTT_ADDRESS')
MQTT_PORT = int(os.environ.get('MQTT_PORT'))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC')
MQTT_USERNAME = os.environ.get('MQTT_USERNAME')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD')

UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL'))

if OCTOPRINT_USE_SSL:
    OCTOPRINT_URL = 'https://' + OCTOPRINT_ADDRESS + '/plugin/filamentmanager/'
else:
    OCTOPRINT_URL = 'http://' + OCTOPRINT_ADDRESS + '/plugin/filamentmanager/'

def get_api_call(url):
    headers = {
        'Authorization': 'Bearer ' + OCTOPRINT_API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.RequestException as e:
        logger.error('Error getting API call: {}'.format(e))
        return None

    if response.status_code != 200:
        logger.error('Error getting API call: {}'.format(response.status_code))
        return None
    else:
        return response.json()

def change_spool_selection(id):
    headers = {
        'Authorization': 'Bearer ' + OCTOPRINT_API_KEY,
        'Content-Type': 'application/json'
    }

    data = {
        "selection": {
            "tool": "0",
            "spool": {
                "id": int(id)
            }
        }
    }

    try:
        response = requests.patch(OCTOPRINT_URL + 'selections/0', data=json.dumps(data), headers=headers)
    except requests.exceptions.RequestException as e:
        logger.error('Error getting API call: {}'.format(e))
        return None

    if response.status_code != 200:
        logger.error('Error sending API call: {}'.format(response.status_code))
        return None
    else:
        return response.json()

def send_to_mqtt(topic, payload):

    client.publish(topic, payload)

def on_connect(client, userdata, flags, rc):
    logger.info('Connected with result code {}'.format(rc))
    client.subscribe(MQTT_TOPIC + '/selected/set')

def on_message(client, userdata, msg):
    logger.debug(f'Message from MQTT {msg.payload.decode("utf-8")}')
    spool_id = re.search('\((.*)\)', msg.payload.decode('utf-8').split()[-1]).group(1)
    logger.info(f'Setting spool to ID {spool_id}')
    change_spool_selection(spool_id)

logger.info('Starting filament manager')
logger.info(f'Using Octoprint Address: {OCTOPRINT_URL}')
logger.info(f'Using Octoprint API key ending: {OCTOPRINT_API_KEY[-4:]}')
logger.info(f'Using MQTT Topic: {MQTT_TOPIC}')
logger.info(f'Using MQTT Address: {MQTT_ADDRESS}:{MQTT_PORT}')

client = mqtt.Client()
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_ADDRESS, MQTT_PORT, 60)
client.loop_start()

while True:
    logger.info('Getting filament spool data')
    current_spools = get_api_call(OCTOPRINT_URL + 'spools')['spools']
    current_selections_id = get_api_call(OCTOPRINT_URL + 'selections')['selections'][0]['spool']['id']
    spool_ids = sorted([f'{spool["profile"]["vendor"]} {spool["profile"]["material"]} {spool["name"]}  ({spool["id"]})' for spool in current_spools])
    client.publish(MQTT_TOPIC + '/selected/id', current_selections_id)

    selection_config = {
        "~": MQTT_TOPIC + '/',
        "name": "OctoPrint Filament Manager Selected Spool",
        "uniq_id": "octoprint_filament_manager_selected_spool",
        "stat_t": "~selected/id",
        "cmd_t": "~selected/set",
        "options": spool_ids,
        "device": {
            "ids": "octoprint_filament_manager_selected_spool",
            "name": "OctoPrint Filament Manager Selected Spool",
            "mf": "OctoPrint Filament Manager MQTT",
            "sw": VERSION,
        }
    }
    client.publish('homeassistant/select/octoprint_filament_manager_selected_spool/config', json.dumps(selection_config))

    for spool in current_spools:
        logger.info('Getting filament data for spool: ' + spool['name'])
        cost = spool['cost']
        material = spool['profile']['material']
        vendor = spool['profile']['vendor']
        id = spool['id']
        used = round(spool['used'], 2)
        weight = spool['weight']
        name = spool['name']
        remaining = weight - ((used * weight) / 100 )
        active = 'on' if id == current_selections_id else 'off'
        spool_name = f'{vendor.capitalize()}{material.replace("+", "Plus").capitalize()}{name.capitalize()}'.replace(" ", "_")
        topic_base = MQTT_TOPIC + '/' + spool_name

        client.publish(topic_base + '/used', used)
        client.publish(topic_base + '/weight', weight)
        client.publish(topic_base + '/cost', cost)
        client.publish(topic_base + '/id', id)
        client.publish(topic_base + '/remaining', remaining)
        client.publish(topic_base + '/active', active)

        used_config = {
            "~": MQTT_TOPIC + '/',
            "name": f"{vendor} {material} {name.title()} Used",
            "uniq_id": spool_name + '_USED',
            "stat_t": f"~{spool_name}/used",
            "unit_of_meas": "%",
            "icon": "mdi:printer-3d-nozzle",
            "device": {
                "ids": spool_name,
                "name": vendor + ' ' + material + ' ' + name.title(),
                "mf": vendor,
                "model": material,
                "sw": VERSION,
            }
        }
        client.publish('homeassistant/sensor/' + spool_name + '_USED/config', json.dumps(used_config))

        weight_config = {
            "~": MQTT_TOPIC + '/',
            "name": f"{vendor} {material} {name.title()} Weight",
            "uniq_id": spool_name + '_WEIGHT',
            "stat_t": f"~{spool_name}/weight",
            "unit_of_meas": "g",
            "icon": "mdi:weight-gram",
            "device": {
                "ids": spool_name,
                "name": vendor + ' ' + material + ' ' + name.title(),
                "mf": vendor,
                "model": material,
                "sw": VERSION,
            }
        }
        client.publish('homeassistant/sensor/' + spool_name + '_WEIGHT/config', json.dumps(weight_config))
        id_config = {
            "~": MQTT_TOPIC + '/',
            "name": f"{vendor} {material} {name.title()} Spool ID",
            "uniq_id": spool_name + '_ID',
            "stat_t": f"~{spool_name}/id",
            "icon": "mdi:card-account-details",
            "device": {
                "ids": spool_name,
                "name": vendor + ' ' + material + ' ' + name.title(),
                "mf": vendor,
                "model": material,
                "sw": VERSION,
            }
        }
        client.publish('homeassistant/sensor/' + spool_name + '_ID/config', json.dumps(id_config))

        active_config = {
            "~": MQTT_TOPIC + '/',
            "name": f"{vendor} {material} {name.title()} Active",
            "uniq_id": spool_name + '_ACTIVE',
            "stat_t": f"~{spool_name}/active",
            "pl_on": "on",
            "pl_off": "off",
            "device": {
                "ids": spool_name,
                "name": vendor + ' ' + material + ' ' + name.title(),
                "mf": vendor,
                "model": material,
                "sw": VERSION,
            }
        }
        client.publish('homeassistant/binary_sensor/' + spool_name + '_ACTIVE/config', json.dumps(active_config))

        remaining_config = {
            "~": MQTT_TOPIC + '/',
            "name": f"{vendor} {material} {name.title()} Remaining",
            "uniq_id": spool_name + '_REMAINING',
            "stat_t": f"~{spool_name}/remaining",
            "unit_of_meas": "g",
            "icon": "mdi:timer-sand",
            "device": {
                "ids": spool_name,
                "name": vendor + ' ' + material + ' ' + name.title(),
                "mf": vendor,
                "model": material,
                "sw": VERSION,
            }
        }
        client.publish('homeassistant/sensor/' + spool_name + '_REMAINING/config', json.dumps(remaining_config))
    logger.info(f'Sleeping for {UPDATE_INTERVAL}')
    time.sleep(UPDATE_INTERVAL)
