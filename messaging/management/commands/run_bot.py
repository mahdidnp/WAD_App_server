import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from messaging.bot import handle_update

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Long-poll Telegram and dispatch updates. Works on localhost and VPS identically."

    def handle(self, *args, **opts):
        token = settings.TELEGRAM_BOT_TOKEN
        base = f"https://api.telegram.org/bot{token}"

        # getUpdates and webhook are mutually exclusive — clear any old webhook
        r = requests.post(f"{base}/deleteWebhook", json={"drop_pending_updates": False}, timeout=10).json()
        if not r.get("ok"):
            self.stderr.write(f"deleteWebhook failed: {r}")
            return

        self.stdout.write(self.style.SUCCESS("Polling. Ctrl+C to stop."))

        offset = 0
        while True:
            try:
                r = requests.get(
                    f"{base}/getUpdates",
                    params={"offset": offset, "timeout": 25},
                    timeout=35,
                ).json()
            except requests.RequestException as e:
                log.warning("poll error: %s", e)
                time.sleep(3)
                continue

            if not r.get("ok"):
                self.stderr.write(f"getUpdates error: {r}")
                time.sleep(5)
                continue

            for u in r.get("result", []):
                offset = u["update_id"] + 1
                try:
                    handle_update(u)
                except Exception:
                    log.exception("handler error update_id=%s", u.get("update_id"))