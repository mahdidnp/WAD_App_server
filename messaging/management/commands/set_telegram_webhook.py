from django.core.management.base import BaseCommand
from messanging.providers import telegram as tg


class Command(BaseCommand):
    help = "Register the Telegram webhook with Telegram."

    def handle(self, *args, **opts):
        result = tg.set_webhook()
        self.stdout.write(self.style.SUCCESS(str(result)))


