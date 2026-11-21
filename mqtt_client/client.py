import os
import paho.mqtt.client as mqtt

from mqtt_client.handlers import handle_mqtt_message

_client = None          # <-- ADD


def get_client():
    return _client      # <-- ADD


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker: {reason_code}")
    if reason_code == 0:
        client.subscribe("devices/+/data", qos=1)      # <-- CHANGED from "iot/test"
        print("Subscribed to topic: devices/+/data")


def on_message(client, userdata, msg):
    try:
        handle_mqtt_message(msg.topic, msg.payload)
    except Exception as error:
        print(f"Error processing MQTT message: {error}")


def start_mqtt_client():
    global _client                      # <-- ADD
    host = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="django_mqtt_listener",
    )
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    if username:
        client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to MQTT broker at {host}:{port}")
    client.connect(host, port, 60)

    _client = client                    # <-- ADD (so bot's _claim can publish)
    client.loop_forever()