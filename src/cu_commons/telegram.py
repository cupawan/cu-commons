"""Telegram Bot API client (send, edit, buttons, files, webhooks) and update parsing."""
import json
import os

import requests

from cu_commons.errors import ApiError
from cu_commons.http import request_json

API = "https://api.telegram.org"


class TelegramBot:
    def __init__(self, token: str, timeout: float = 30):
        if not token:
            raise ValueError("Telegram bot token is required")
        self.base = f"{API}/bot{token}"
        self.timeout = timeout

    @classmethod
    def from_env(cls, var: str = "TELEGRAM_BOT_TOKEN"):
        return cls(os.environ.get(var, ""))

    def call(self, method: str, **payload):
        body = request_json("POST", f"{self.base}/{method}", json={k: v for k, v in payload.items() if v is not None},
                            timeout=self.timeout)
        if not body or not body.get("ok"):
            raise ApiError(f"Telegram {method} failed: {body}")
        return body.get("result")

    # ---- messages
    def send_message(self, chat_id, text: str, reply_markup: dict | None = None, parse_mode: str | None = None,
                     disable_preview: bool = True):
        return self.call("sendMessage", chat_id=chat_id, text=text[:4096], reply_markup=reply_markup,
                         parse_mode=parse_mode, disable_web_page_preview=disable_preview)

    def edit_message(self, chat_id, message_id: int, text: str, reply_markup: dict | None = None):
        try:
            return self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text[:4096],
                             reply_markup=reply_markup, disable_web_page_preview=True)
        except ApiError as e:
            if "message is not modified" in str(e):
                return None
            raise

    def edit_buttons(self, chat_id, message_id: int, reply_markup: dict):
        return self.call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)

    def answer_callback(self, callback_id: str, text: str | None = None):
        return self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def send_document(self, chat_id, filename: str, content: bytes, caption: str | None = None,
                      mime_type: str = "application/octet-stream"):
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption[:1024]
        response = requests.post(f"{self.base}/sendDocument", data=data,
                                 files={"document": (filename, content, mime_type)}, timeout=self.timeout * 2)
        body = response.json() if response.content else {}
        if not body.get("ok"):
            raise ApiError(f"Telegram sendDocument failed: {body}", response.status_code)
        return body["result"]

    # ---- webhooks
    def set_webhook(self, url: str, secret_token: str | None = None, drop_pending: bool = False):
        return self.call("setWebhook", url=url, secret_token=secret_token, drop_pending_updates=drop_pending)

    def delete_webhook(self):
        return self.call("deleteWebhook")

    def webhook_info(self):
        return self.call("getWebhookInfo")

    # ---- keyboards
    @staticmethod
    def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
        """[[("label", "callback_data"), ...], ...] -> inline keyboard markup (callback_data <= 64 bytes)."""
        for row in rows:
            for _, data in row:
                if len(data.encode()) > 64:
                    raise ValueError(f"callback_data longer than 64 bytes: {data!r}")
        return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}

    @staticmethod
    def reply_keyboard(rows: list[list[str]], persistent: bool = True) -> dict:
        return {"keyboard": [[{"text": t} for t in row] for row in rows], "resize_keyboard": True,
                "is_persistent": persistent}


def parse_update(update: dict | str) -> dict:
    """Flatten a Telegram update into the fields bots usually need."""
    if isinstance(update, str):
        update = json.loads(update)
    callback = update.get("callback_query")
    if callback:
        message = callback.get("message") or {}
        return {"kind": "callback", "user_id": (callback.get("from") or {}).get("id"),
                "chat_id": (message.get("chat") or {}).get("id"), "message_id": message.get("message_id"),
                "callback_id": callback.get("id"), "data": callback.get("data") or "", "text": None}
    message = update.get("message") or update.get("edited_message") or {}
    kind = "document" if message.get("document") else "text" if "text" in message else "other"
    return {"kind": kind, "user_id": (message.get("from") or {}).get("id"),
            "chat_id": (message.get("chat") or {}).get("id"), "message_id": message.get("message_id"),
            "text": message.get("text"), "document": message.get("document"), "callback_id": None, "data": None}
