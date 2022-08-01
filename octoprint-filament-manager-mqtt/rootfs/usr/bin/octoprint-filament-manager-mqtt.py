from xml.etree.ElementTree import VERSION
import requests
import paho.mqtt.client as mqtt
import os
import json
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main')

VERSION = "1.0.6"

OCTOPRINT_API_KEY = os.environ.get('OCTOPRINT_API_KEY')
OCTOPRINT_ADDRESS = os.environ.get('OCTOPRINT_ADDRESS')
OCTOPRINT_USE_SSL = os.environ.get('OCTOPRINT_USE_SSL')

MQTT_ADDRESS = os.environ.get('MQTT_ADDRESS')
MQTT_PORT = int(os.environ.get('MQTT_PORT'))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC')
MQTT_USERNAME = os.environ.get('MQTT_USERNAME')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD')

UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL'))

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

def post_api_call(url, data):
    response = requests.post(url, data)
    return response.json()

def send_to_mqtt(topic, payload):
    logger.info('Sending to MQTT: {} {}'.format(topic, payload))
    client = mqtt.Client()

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.connect(MQTT_ADDRESS, MQTT_PORT, 60)
    client.publish(topic, payload)
    client.disconnect()

if OCTOPRINT_USE_SSL:
    url = 'https://' + OCTOPRINT_ADDRESS + '/plugin/filamentmanager/'
else:
    url = 'http://' + OCTOPRINT_ADDRESS + '/plugin/filamentmanager/'

logger.info('Starting filament manager')
logger.info(f'Using Octoprint Address: {url}')
logger.info(f'Using Octoprint API Key: {OCTOPRINT_API_KEY}')
logger.info(f'Using MQTT Address: {MQTT_ADDRESS}:{MQTT_PORT}')

while True:
    logger.info('Getting filament spool data')
    current_spools = get_api_call(url + 'spools')['spools']
    current_selections_id = get_api_call(url + 'selections')['selections'][0]['spool']['id']
    spool_ids = sorted([spool['id'] for spool in current_spools])
    send_to_mqtt(MQTT_TOPIC + '/selected/id', current_selections_id)


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
    send_to_mqtt('homeassistant/select/octoprint_filament_manager_selected_spool/config', json.dumps(selection_config))

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

        send_to_mqtt(topic_base + '/used', used)
        send_to_mqtt(topic_base + '/weight', weight)
        send_to_mqtt(topic_base + '/cost', cost)
        send_to_mqtt(topic_base + '/id', id)
        send_to_mqtt(topic_base + '/remaining', remaining)
        send_to_mqtt(topic_base + '/active', active)

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
        send_to_mqtt('homeassistant/sensor/' + spool_name + '_USED/config', json.dumps(used_config))

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
        send_to_mqtt('homeassistant/sensor/' + spool_name + '_WEIGHT/config', json.dumps(weight_config))
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
        send_to_mqtt('homeassistant/sensor/' + spool_name + '_ID/config', json.dumps(id_config))

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
        send_to_mqtt('homeassistant/binary_sensor/' + spool_name + '_ACTIVE/config', json.dumps(active_config))

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
        send_to_mqtt('homeassistant/sensor/' + spool_name + '_REMAINING/config', json.dumps(remaining_config))
    time.sleep(UPDATE_INTERVAL)
