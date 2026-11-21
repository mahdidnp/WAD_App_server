import json
import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from devices.models import Account, Device, PairingCode
from .models import TelegramLinkToken
from .providers import telegram as tg

log = logging.getLogger(__name__)

ADD_KEYBOARD = {"keyboard": [["➕ Link Device"]], "resize_keyboard": True}


def handle_update(update: dict):
    """Entry point. Called by runbot for every Telegram update."""
    msg = update.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    account = Account.objects.filter(telegram_chat_id=chat_id).first()

    # /start [payload]
    if text.startswith("/start"):
        payload = text[len("/start"):].strip()
        if payload.startswith("link_"):
            _link_token(chat_id, payload[5:])
        else:
            _start(chat_id, account)
        return

    # Everything below requires a linked account
    if not account:
        tg.send_message(chat_id, "Link your web account first (dashboard → Link Telegram).")
        return

    if text in ("/linkdevice", "/add", "➕ Link Device"):
        tg.send_message(chat_id, "Send the 8-digit code from your device's setup page.")
        return

    if len(text) == 8 and text.isdigit():
        _claim(account, chat_id, text)
        return

    tg.send_message(chat_id, "Send /linkdevice to link a device.", reply_markup=ADD_KEYBOARD)


def _start(chat_id, account):
    if account:
        tg.send_message(chat_id, "Welcome back. Tap Link Device.", reply_markup=ADD_KEYBOARD)
    else:
        tg.send_message(chat_id, "Welcome. Link your account from the dashboard first.")


def _link_token(chat_id, token):
    now = timezone.now()
    with transaction.atomic():
        try:
            link = TelegramLinkToken.objects.select_for_update().get(token=token)
        except TelegramLinkToken.DoesNotExist:
            tg.send_message(chat_id, "❌ Invalid link.")
            return
        if link.used_at or link.expires_at <= now:
            tg.send_message(chat_id, "❌ Link expired.")
            return
        conflict = Account.objects.filter(telegram_chat_id=chat_id).exclude(pk=link.account_id).first()
        if conflict:
            tg.send_message(chat_id, "⚠️ This Telegram is linked to another account.")
            return
        link.account.telegram_chat_id = chat_id
        link.account.telegram_linked_at = now
        link.account.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
        link.used_at = now
        link.save(update_fields=["used_at"])
    tg.send_message(chat_id, "✅ Telegram linked. Tap Link Device.", reply_markup=ADD_KEYBOARD)


def _claim(account, chat_id, code):
    # Rate limit: 5 attempts / 10 min / chat
    rk = f"rl:claim:{chat_id}"
    try:
        n = cache.incr(rk)
    except ValueError:
        cache.set(rk, 1, timeout=600)
        n = 1
    if n > 5:
        tg.send_message(chat_id, "Too many attempts. Try again in 10 minutes.")
        return

    now = timezone.now()
    try:
        with transaction.atomic():
            try:
                pc = PairingCode.objects.select_for_update().get(code=code)
            except PairingCode.DoesNotExist:
                raise ValueError("Invalid or expired code.")
            if pc.used_at or pc.expires_at <= now:
                raise ValueError("Invalid or expired code.")

            device = Device.objects.select_for_update().get(pk=pc.device_id)
            if device.owner_id is not None:
                raise ValueError("Device already claimed.")

            device.owner = account
            device.claimed_at = now
            device.pending_unclaim = False
            device.save(update_fields=["owner", "claimed_at", "pending_unclaim"])

            pc.used_at = now
            pc.used_by = account
            pc.save(update_fields=["used_at", "used_by"])
    except ValueError as e:
        tg.send_message(chat_id, f"❌ {e}")
        return
    except Exception:
        log.exception("claim_failed chat=%s code=%s", chat_id, code)
        tg.send_message(chat_id, "❌ Something went wrong.")
        return

    # MQTT notify (stubbed until mqtt_client exists — claim still succeeds)
    try:
        from mqtt_client.client import get_client
        client = get_client()
        if client:
            client.publish(f"pairing/{device.device_id}", b"", qos=1, retain=True)
            client.publish(
                f"devices/{device.device_id}/commands",
                json.dumps({"cmd": "paired"}).encode(), qos=1, retain=True,
            )
    except Exception:
        log.warning("mqtt notify skipped — claim still succeeded")

    tg.send_message(chat_id, f"✅ Device {device.device_id} linked.")