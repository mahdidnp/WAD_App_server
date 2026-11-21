import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Account(models.Model):
    """
    Application-level hub. One-to-one with Django's auth User.
    Telegram link is a nullable column here — there is NO separate
    TelegramAccount table (see spec §1).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account",
    )
    telegram_chat_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_linked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"

    def __str__(self):
        return f"Account<{self.user.username}>"

    @property
    def telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None


class Device(models.Model):
    """
    A physical ESP device. `owner` is nullable: NULL = unclaimed / claimable.
    `device_id` is the immutable factory serial from firmware NVS.
    """
    device_id = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devices",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)

    # --- unclaim handshake (spec §6.7) ---
    pending_unclaim = models.BooleanField(default=False)
    unclaim_requested_at = models.DateTimeField(null=True, blank=True)
    last_unclaim_nonce = models.UUIDField(null=True, blank=True)

    # --- telemetry / health ---
    fw_version = models.CharField(max_length=32, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices"
        indexes = [
            models.Index(fields=["owner"], name="dev_owner_idx"),
            models.Index(fields=["pending_unclaim"], name="dev_pending_idx"),
        ]

    def __str__(self):
        return self.device_id

    @property
    def is_claimed(self) -> bool:
        return self.owner_id is not None


class DeviceCredential(models.Model):
    """
    Per-device MQTT broker credentials. Never shared across devices.
    `password_hash` is an argon2/bcrypt hash — verify with Django's
    `check_password()` against a hasher-compatible object, or use
    `django.contrib.auth.hashers.check_password`.
    """
    device = models.OneToOneField(
        Device, on_delete=models.CASCADE, related_name="credential"
    )
    username = models.CharField(max_length=64, unique=True)  # "dev-{device_id}"
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "device_credentials"

    def __str__(self):
        return self.username


class PairingCode(models.Model):
    """
    One row per *code issuance* (history). `code` is the PK.

    Sticky rule: `used_at` is set once and NEVER cleared. The pairing
    handler's upsert must use `WHERE used_at IS NULL` so a stale device
    re-publishing an already-burned code cannot resurrect it.

    Retention policy (enforced by `prune_pairing_codes` command):
      - unused + expires_at < now - 7d  -> delete
      - used   + used_at    < now - 7d  -> delete
    """
    code = models.CharField(max_length=8, primary_key=True)
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="pairing_codes"
    )
    issued_at = models.DateTimeField()                 # server clock
    expires_at = models.DateTimeField()                # server clock, +24h
    used_at = models.DateTimeField(null=True, blank=True)  # STICKY
    used_by = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="used_pairing_codes",
    )

    class Meta:
        db_table = "pairing_codes"
        indexes = [
            # sweep query: expires_at < cutoff
            models.Index(fields=["expires_at"], name="pc_expires_idx"),
            # claim query only ever looks at live codes -> partial index
            models.Index(
                fields=["code"],
                name="pc_live_code_idx",
                condition=Q(used_at__isnull=True),
            ),
            # prune query: used_at < cutoff
            models.Index(fields=["used_at"], name="pc_used_idx"),
        ]

    def __str__(self):
        return self.code

    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()