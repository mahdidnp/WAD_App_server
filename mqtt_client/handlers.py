import json
import logging

from devices.models import Device
from messaging.providers import telegram as tg

log = logging.getLogger(__name__)


def handle_mqtt_message(topic: str, payload: bytes):
    # Expect: devices/{device_id}/data
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "devices" or parts[2] != "data":
        return

    device_id = parts[1]
    try:
        data = json.loads(payload or b"{}")
    except json.JSONDecodeError:
        log.warning("bad JSON on %s", topic)
        return

    device = Device.objects.select_related("owner").filter(device_id=device_id).first()
    if not device:
        print(f"unknown device {device_id}")
        return

    account = device.owner
    if not account or not account.telegram_chat_id:
        print(f"no recipient for {device_id}")
        return

    text = f"📟 {device.device_id}\n" + "\n".join(
        f"{k}: {v}" for k, v in data.items() if k != "ts"
    )
    try:
        tg.send_message(account.telegram_chat_id, text)
        print(f"notified chat={account.telegram_chat_id} for {device_id}")
    except tg.TelegramError as e:
        print(f"telegram send failed: {e}")