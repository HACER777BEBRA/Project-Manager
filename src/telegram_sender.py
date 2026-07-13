from __future__ import annotations

import time

import requests

from .config import TelegramConfig


class TelegramSender:
    def __init__(self, cfg: TelegramConfig):
        self.cfg = cfg
        self.base = f"https://api.telegram.org/bot{cfg.bot_token}"

    def send_message(self, text: str, disable_preview: bool = True) -> dict:
        # Telegram limit ~4096 chars; split if needed
        chunks = _split_message(text, limit=4000)
        last: dict = {}
        for chunk in chunks:
            last = self._post(
                "sendMessage",
                {
                    "chat_id": self.cfg.chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": disable_preview,
                },
            )
            if len(chunks) > 1:
                time.sleep(0.35)
        return last

    def _post(self, method: str, payload: dict) -> dict:
        response = requests.post(f"{self.base}/{method}", json=payload, timeout=60)
        data = response.json()
        if not response.ok or not data.get("ok"):
            description = data.get("description") or response.text
            raise RuntimeError(f"Telegram API error: {description}")
        return data


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.split("\n"):
        add = len(line) + (1 if current else 0)
        if size + add > limit and current:
            parts.append("\n".join(current))
            current = [line]
            size = len(line)
        else:
            current.append(line)
            size += add
    if current:
        parts.append("\n".join(current))
    return parts
