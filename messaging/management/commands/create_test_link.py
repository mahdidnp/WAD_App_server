# import secrets
# from datetime import timedelta

# import requests
# from django.conf import settings
# from django.contrib.auth.models import User
# from django.core.management.base import BaseCommand
# from django.utils import timezone

# from devices.models import Account, Device, PairingCode
# from messaging.models import TelegramLinkToken


# class Command(BaseCommand):
#     help = "Create test account + device + pairing code + Telegram link. Prints the clickable link."

#     def handle(self, *args, **opts):
#         # 1. Test user + account
#         user, _ = User.objects.get_or_create(username="testuser")
#         account, _ = Account.objects.get_or_create(user=user)

#         # 2. Test device + fresh pairing code
#         device, _ = Device.objects.get_or_create(device_id="TEST-1")
#         PairingCode.objects.filter(device=device).delete()
#         PairingCode.objects.create(
#             code="48291301",
#             device=device,
#             issued_at=timezone.now(),
#             expires_at=timezone.now() + timedelta(hours=24),
#         )

#         # 3. Telegram link token
#         token = secrets.token_urlsafe(16)
#         TelegramLinkToken.objects.create(
#             token=token,
#             account=account,
#             expires_at=timezone.now() + timedelta(minutes=30),
#         )

#         # 4. Resolve bot username
#         bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
#         if not bot_username:
#             r = requests.get(
#                 f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe",
#                 timeout=15,
#             ).json()
#             if r.get("ok"):
#                 bot_username = r["result"]["username"]
#             else:
#                 self.stderr.write("Could not resolve bot username. Set TELEGRAM_BOT_USERNAME in .env.")
#                 return

#         url = f"https://t.me/{bot_username}?start=link_{token}"
#         self.stdout.write("")
#         self.stdout.write(self.style.SUCCESS("Open this link in Telegram:"))
#         self.stdout.write(f"  {url}")
#         self.stdout.write("")
#         self.stdout.write(self.style.SUCCESS("Then send this code in the bot:"))
#         self.stdout.write("  48291301")
#         self.stdout.write("")



import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from devices.models import Account, PairingCode
from messaging.models import TelegramLinkToken


class Command(BaseCommand):
    help = "Create/find a client account and print a Telegram linking URL."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Client's username (will be created if missing)")
        parser.add_argument(
            "--ttl-minutes", type=int, default=60,
            help="Link validity in minutes (default 60)",
        )
        parser.add_argument(
            "--show-codes", action="store_true",
            help="Also list live pairing codes this client can use",
        )

    def handle(self, *args, **opts):
        username = opts["username"]
        ttl = opts["ttl_minutes"]

        # 1. User + Account
        user, created_user = User.objects.get_or_create(username=username)
        account, created_account = Account.objects.get_or_create(user=user)

        if created_user or created_account:
            self.stdout.write(self.style.WARNING(
                f"Created new {'user ' if created_user else ''}"
                f"{'account' if created_account else ''} for '{username}'"
            ))
        else:
            self.stdout.write(f"Using existing account for '{username}' "
                              f"(id={account.id})")

        # 2. One-time link token
        token = secrets.token_urlsafe(16)
        TelegramLinkToken.objects.create(
            token=token,
            account=account,
            expires_at=timezone.now() + timedelta(minutes=ttl),
        )

        # 3. Resolve bot username
        bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        if not bot_username:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe",
                    timeout=15,
                ).json()
            except requests.RequestException as e:
                raise CommandError(f"Could not reach Telegram: {e}")
            if not r.get("ok"):
                raise CommandError(
                    "Could not resolve bot username. "
                    "Set TELEGRAM_BOT_USERNAME in .env or check your token."
                )
            bot_username = r["result"]["username"]

        # 4. Print
        url = f"https://t.me/{bot_username}?start=link_{token}"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"  LINK FOR '{username}'"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"  {url}")
        self.stdout.write("")
        self.stdout.write(f"  Valid for {ttl} minutes. Single-use.")
        self.stdout.write(f"  After clicking, send the bot the device's 8-digit code.")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")

        # 5. Optionally, show live pairing codes for this client's devices
        if opts["show_codes"]:
            codes = (
                PairingCode.objects
                .filter(device__owner=account, used_at__isnull=True,
                        expires_at__gt=timezone.now())
                .select_related("device")
                .order_by("expires_at")
            )
            if not codes:
                self.stdout.write("No live pairing codes for this account yet.")
                self.stdout.write("(Device hasn't published a code, or none claimed.)")
            else:
                self.stdout.write("Live pairing codes for this account:")
                for pc in codes:
                    self.stdout.write(
                        f"  code={pc.code}  device={pc.device.device_id}  "
                        f"expires={pc.expires_at:%Y-%m-%d %H:%M} UTC"
                    )
            self.stdout.write("")