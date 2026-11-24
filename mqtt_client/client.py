import os
import paho.mqtt.client as mqtt

from mqtt_client.handlers import handle_pairing_message, handle_telemetry_message

_client = None


def get_client():
    return _client


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker: {reason_code}")
    if reason_code == 0:
        client.subscribe([
            ("pairing/+/codes", 1),
            ("devices/+/data", 1),
        ])
        print("Subscribed to: pairing/+/codes, devices/+/data")


def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        if topic.startswith("pairing/") and topic.endswith("/codes"):
            device_id = topic.split("/")[1]
            handle_pairing_message(device_id, msg.payload)
        elif topic.startswith("devices/") and topic.endswith("/data"):
            handle_telemetry_message(topic, msg.payload)
    except Exception as error:
        print(f"Error processing {topic}: {error}")


def start_mqtt_client():
    global _client
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

    _client = client
    client.loop_forever()