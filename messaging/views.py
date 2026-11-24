import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from devices.models import Account
from .models import TelegramLinkToken

LINK_COOLDOWN_SECONDS = 600      # 10 min between generations
LINK_TTL_SECONDS = 600          # 10 min validity



@login_required
@require_POST
def create_telegram_link(request):
    account, _ = Account.objects.get_or_create(user=request.user)
    now = timezone.now()

    if account.telegram_chat_id:
        messages.error(request, "Telegram is already linked. Unlink it first.")
        return redirect("dashboard")

    existing = TelegramLinkToken.objects.filter(account=account).first()
    if existing:
        age = (now - existing.created_at).total_seconds()
        if age < LINK_COOLDOWN_SECONDS and existing.used_at is None:
            wait = int(LINK_COOLDOWN_SECONDS - age)
            messages.warning(request, f"Please wait {wait}s before generating another link.")
            return redirect("dashboard")
        # Replace-in-place: delete-then-create so created_at resets (auto_now_add)
        existing.delete()

    try:
        TelegramLinkToken.objects.create(
            account=account,
            token=secrets.token_urlsafe(24),
            expires_at=now + timedelta(seconds=LINK_TTL_SECONDS),
        )
    except IntegrityError:
        messages.warning(request, "A link was just created. Refresh the page.")
        return redirect("dashboard")

    messages.success(
        request,
        f"Link generated. Open it in Telegram within {LINK_TTL_SECONDS // 60} minutes.",
    )
    return redirect("dashboard")


@login_required
@require_POST
def unlink_telegram(request):
    account, _ = Account.objects.get_or_create(user=request.user)
    if not account.telegram_chat_id:
        messages.info(request, "Telegram isn't linked.")
        return redirect("dashboard")

    account.telegram_chat_id = None
    account.telegram_linked_at = None
    account.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
    # Clear the used token so a fresh one can be generated
    TelegramLinkToken.objects.filter(account=account).delete()
    messages.success(request, "Telegram unlinked. You can link a new account now.")
    return redirect("dashboard")