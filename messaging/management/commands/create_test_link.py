import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import Account, Device, PairingCode
from messaging.models import TelegramLinkToken


class Command(BaseCommand):
    help = "Create test account + device + pairing code + Telegram link. Prints the clickable link."

    def handle(self, *args, **opts):
        # 1. Test user + account
        user, _ = User.objects.get_or_create(username="testuser")
        account, _ = Account.objects.get_or_create(user=user)

        # 2. Test device + fresh pairing code
        device, _ = Device.objects.get_or_create(device_id="TEST-1")
        PairingCode.objects.filter(device=device).delete()
        PairingCode.objects.create(
            code="48291301",
            device=device,
            issued_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # 3. Telegram link token
        token = secrets.token_urlsafe(16)
        TelegramLinkToken.objects.create(
            token=token,
            account=account,
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        # 4. Resolve bot username
        bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        if not bot_username:
            r = requests.get(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe",
                timeout=15,
            ).json()
            if r.get("ok"):
                bot_username = r["result"]["username"]
            else:
                self.stderr.write("Could not resolve bot username. Set TELEGRAM_BOT_USERNAME in .env.")
                return

        url = f"https://t.me/{bot_username}?start=link_{token}"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Open this link in Telegram:"))
        self.stdout.write(f"  {url}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Then send this code in the bot:"))
        self.stdout.write("  48291301")
        self.stdout.write("")