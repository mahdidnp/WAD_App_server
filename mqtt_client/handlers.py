import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from devices.models import Device, PairingCode
from messaging.providers import telegram as tg

log = logging.getLogger(__name__)


def _decode(payload: bytes) -> str:
    """Turn broker bytes into a stripped text string. Empty on decode failure."""
    try:
        return (payload or b"").decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def handle_pairing_message(device_id: str, payload: bytes):
    """Called for pairing/{device_id}/codes. Payload is the raw 8-digit code."""
    code = _decode(payload)
    if not (code.isdigit() and len(code) == 8):
        log.warning("invalid pairing code %r for device %s", code, device_id)
        return

    device, created = Device.objects.get_or_create(device_id=device_id)
    if created:
        log.info("new device registered: %s", device_id)

    now = timezone.now()

    with transaction.atomic():
        # Factory reset: device owned, no unclaim in flight → physical possession wins
        if device.owner_id is not None and not device.pending_unclaim:
            log.warning("factory reset detected for %s — clearing owner", device_id)
            device.owner = None
            device.claimed_at = None
            device.save(update_fields=["owner", "claimed_at"])

        # Replace-in-place: one row per device
        PairingCode.objects.filter(device=device).delete()
        PairingCode.objects.create(
            code=code,
            device=device,
            issued_at=now,
            expires_at=now + timedelta(hours=24),
        )

    print(f"✅ Stored pairing code {code} for device {device_id}")


def handle_telemetry_message(topic: str, payload: bytes):
    """Called for devices/{device_id}/data. Payload is the raw text to forward."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "devices" or parts[2] != "data":
        return
    device_id = parts[1]

    text = _decode(payload)
    if not text:
        log.warning("empty telemetry payload on %s", topic)
        return

    device = Device.objects.select_related("owner").filter(device_id=device_id).first()
    if not device:
        print(f"unknown device {device_id}")
        return

    account = device.owner
    if not account or not account.telegram_chat_id:
        print(f"no recipient for {device_id} (owner={account})")
        return

    message = f"📟 {device.device_id}\n{text}"

    try:
        tg.send_message(account.telegram_chat_id, message)
        print(f"notified chat={account.telegram_chat_id} for {device_id}: {text!r}")
    except tg.TelegramError as e:
        print(f"telegram send failed device={device_id} err={e}")