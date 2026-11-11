"""Report failures and notices to a Telegram chat."""
import json
import logging
import os
import traceback

from cu_commons.telegram import TelegramBot

logger = logging.getLogger(__name__)


class TelegramAlerter:
    def __init__(self, bot: TelegramBot, chat_id):
        self.bot, self.chat_id = bot, chat_id

    @classmethod
    def from_env(cls, token_var: str = "AlertsBotToken", chat_var: str = "SelfTgChatId"):
        """None when either variable is unset, so alerting stays optional."""
        token, chat_id = os.environ.get(token_var), os.environ.get(chat_var)
        return cls(TelegramBot(token), chat_id) if token and chat_id else None

    def notify(self, text: str) -> None:
        try:
            self.bot.send_message(self.chat_id, text[:4000])
        except Exception as e:  # alerting must never hide the original problem
            logger.error("alert delivery failed: %s", e)

    def error(self, service: str, exc: BaseException, extra: dict | None = None) -> dict:
        payload = {"service": service, "env": os.environ.get("APP_ENV", "unknown"), "error": str(exc),
                   "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__)[-5:], **(extra or {})}
        self.notify("⚠️ " + json.dumps(payload, ensure_ascii=False, indent=1, default=str))
        return payload
