import logging
import requests
from django.conf import settings

log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(Exception):
    def __init__(self, code: int, description: str, retry_after=None):
        super().__init__(f"[{code}] {description}")
        self.code = code
        self.retry_after = retry_after

    @property
    def blocked(self) -> bool:
        return self.code == 403

    @property
    def rate_limited(self) -> bool:
        return self.code == 429


def _call(method: str, payload: dict, timeout: int = 10) -> dict:
    url = _API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    r = requests.post(url, json=payload, timeout=timeout)
    data = r.json()
    if not data.get("ok"):
        raise TelegramError(
            code=data.get("error_code", r.status_code),
            description=data.get("description", ""),
            retry_after=data.get("parameters", {}).get("retry_after"),
        )
    return data


def send_message(chat_id: int, text: str, *, parse_mode=None, reply_markup=None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _call("sendMessage", payload)