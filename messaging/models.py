from django.db import models


class TelegramLinkToken(models.Model):
    """
    One-time token for the `/start link_<token>` account-linking flow.
    TTL 10 minutes, single use. Cheap to prune the same way as PairingCode.
    """
    token = models.CharField(max_length=64, unique=True)
    account = models.ForeignKey(
        "devices.Account", on_delete=models.CASCADE, related_name="link_tokens"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "telegram_link_tokens"
        indexes = [
            models.Index(fields=["expires_at"], name="tlt_expires_idx"),
        ]

    def __str__(self):
        return self.token

class TelegramLinkToken(models.Model):
    token = models.CharField(max_length=64, unique=True)
    account = models.OneToOneField(          # ← was ForeignKey
        "devices.Account", on_delete=models.CASCADE, related_name="link_token"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "telegram_link_tokens"

    def __str__(self):
        return self.token

class NotificationLog(models.Model):
    """
    Outbound Telegram audit trail. Not required for correctness —
    safe to prune (e.g. keep 30 days) if volume becomes an issue.
    """
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("dropped_no_chat", "Dropped — no chat_id"),
        ("blocked", "Blocked by user"),
    ]

    account = models.ForeignKey(
        "devices.Account",
        null=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    device = models.ForeignKey(
        "devices.Device",
        null=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    chat_id = models.BigIntegerField(null=True, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_logs"
        indexes = [
            models.Index(fields=["account", "created_at"], name="nlog_acct_idx"),
            models.Index(fields=["status"], name="nlog_status_idx"),
        ]