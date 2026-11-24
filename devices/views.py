import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from devices.models import Account, Device

from django.conf import settings
from django.contrib.auth import login
from devices.forms import SignupForm
from messaging.models import TelegramLinkToken      

LINK_COOLDOWN_SECONDS = 600

log = logging.getLogger(__name__)
def home(request):
    return render(request, "home.html")


def _human_duration(seconds: int) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    if m < 60:
        return f"{m}m"
    return f"{m // 60}h {m % 60}m"


def _link_context(account):
    """Compute the Telegram link state for the dashboard template."""
    link = TelegramLinkToken.objects.filter(account=account).first()
    now = timezone.now()

    if link is None:
        return {
            "link_state": "none",
            "link_url": None,
            "link_token": None,
            "link_expires_label": None,
            "link_cooldown_label": None,
            "can_regenerate": True,
        }

    expires_in = (link.expires_at - now).total_seconds()
    cooldown = max(0, LINK_COOLDOWN_SECONDS - (now - link.created_at).total_seconds())

    if link.used_at:
        state = "used"
    elif expires_in <= 0:
        state = "expired"
    else:
        state = "live"

    bot = getattr(settings, "TELEGRAM_BOT_USERNAME", "").lstrip("@")
    url = f"https://t.me/{bot}?start=link_{link.token}" if bot else None

    # Regenerate allowed when: no live link, or live link past cooldown
    can_regenerate = state != "live" or cooldown == 0

    return {
        "link_state": state,
        "link_url": url,
        "link_token": link.token,
        "link_expires_label": _human_duration(expires_in) if state == "live" else None,
        "link_cooldown_label": _human_duration(cooldown) if (state == "live" and cooldown > 0) else None,
        "can_regenerate": can_regenerate,
    }


@login_required
def dashboard(request):
    account, _ = Account.objects.get_or_create(user=request.user)
    devices = account.devices.all().order_by("-claimed_at")
    ctx = _link_context(account)
    return render(request, "dashboard.html", {
        "account": account,
        "devices": devices,
        "telegram_linked": account.telegram_chat_id is not None,
        **ctx,
    })

def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            Account.objects.create(user=user)
            login(request, user)
            messages.success(request, "Welcome! Your account is ready.")
            return redirect("home")
    else:
        form = SignupForm()

    return render(request, "signup.html", {"form": form})


@login_required
@require_POST
def unclaim_device(request, device_id):
    account, _ = Account.objects.get_or_create(user=request.user)
    device = get_object_or_404(Device, device_id=device_id, owner=account)

    if not device.claimed_at:
        messages.error(request, "Device has no claim timestamp — cannot remove.")
        return redirect("dashboard")

    if (timezone.now() - device.claimed_at) < timedelta(hours=24):
        messages.error(request, "Device cannot be removed within 24 hours of adding it.")
        return redirect("dashboard")

    device.owner = None
    device.claimed_at = None
    device.pending_unclaim = True
    device.unclaim_requested_at = timezone.now()
    device.save(update_fields=["owner", "claimed_at", "pending_unclaim", "unclaim_requested_at"])

    try:
        from mqtt_client.client import get_client
        client = get_client()
        if client:
            client.publish(
                f"devices/{device.device_id}/commands",
                json.dumps({"cmd": "unclaim"}).encode(),
                qos=1, retain=True,
            )
    except Exception:
        log.exception("failed to publish unclaim command for %s", device.device_id)

    messages.success(request, f"Device {device.device_id} removed. It will reset on next connection.")
    return redirect("dashboard")