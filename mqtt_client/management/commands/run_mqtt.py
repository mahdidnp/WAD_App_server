from django.core.management.base import BaseCommand
from mqtt_client.client import start_mqtt_client


class Command(BaseCommand):

    help = "Start MQTT listener"

    def handle(self, *args, **options):

        self.stdout.write(
            self.style.SUCCESS("Starting MQTT listener...")
        )

        start_mqtt_client()