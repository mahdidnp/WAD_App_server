from celery import shared_task
from django.core.management import call_command


@shared_task
def prune_pairing_codes():
    call_command("prune_pairing_codes")