from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import PairingCode


class Command(BaseCommand):
    help = "Delete expired unused and stale used pairing codes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days", type=int, default=7,
            help="Keep rows for this many days past expiry/use (default 7).",
        )

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts["retention_days"])

        unused, _ = PairingCode.objects.filter(
            used_at__isnull=True,
            expires_at__lt=cutoff,
        ).delete()

        used, _ = PairingCode.objects.filter(
            used_at__isnull=False,
            used_at__lt=cutoff,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f"pruned unused={unused} used={used}")
        )