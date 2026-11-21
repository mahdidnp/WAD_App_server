import logging

from celery import shared_task
from django.utils import timezone

from .models import NotificationLog
from .providers import telegram as tg

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_task(self, device_id: str, payload: dict):
    """
    Runs in a Celery worker. Never blocks the MQTT handler or web request.
    Handles 403 (blocked) and 429 (rate limit) per spec §6.6.
    """
    from devices.models import Device

    try:
        device = Device.objects.select_related("owner").get(device_id=device_id)
    except Device.DoesNotExist:
        log.warning("telegram_task_unknown_device device_id=%s", device_id)
        return

    account = device.owner
    if not account or not account.telegram_chat_id:
        NotificationLog.objects.create(
            account=account, device=device,
            status="dropped_no_chat", body=str(payload),
        )
        return

    text = _format_telemetry(device, payload)
    nlog = NotificationLog.objects.create(
        account=account, device=device,
        chat_id=account.telegram_chat_id, body=text, status="queued",
    )

    try:
        tg.send_message(account.telegram_chat_id, text, parse_mode="Markdown")
        nlog.status = "sent"
        nlog.sent_at = timezone.now()
        nlog.save(update_fields=["status", "sent_at"])

    except tg.TelegramError as e:
        if e.blocked:
            account.telegram_chat_id = None
            account.telegram_linked_at = None
            account.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
            nlog.status = "blocked"
            nlog.save(update_fields=["status"])
            return

        if e.rate_limited:
            nlog.status = "failed"
            nlog.error = f"429 retry_after={e.retry_after}"
            nlog.save(update_fields=["status", "error"])
            raise self.retry(countdown=e.retry_after or 60)

        nlog.status = "failed"
        nlog.error = str(e)
        nlog.save(update_fields=["status", "error"])


def _format_telemetry(device, payload: dict) -> str:
    parts = [f"📟 *{device.device_id}*"]
    for k, v in payload.items():
        if k == "ts":
            continue
        parts.append(f"{k}: `{v}`")
    return "\n".join(parts)