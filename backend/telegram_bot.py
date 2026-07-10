"""Telegram Bot API client.

Secrets (bot token, chat id) are read from encrypted settings and decrypted
only in memory here. Long messages are split to respect Telegram's 4096-char
limit. Nothing sensitive is logged (the log middleware also redacts, but we are
careful here too).
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

import settings as settings_mod

log = logging.getLogger("smokeping_easy.telegram")

API_BASE = "https://api.telegram.org"
MAX_LEN = 4096
TIMEOUT = 20.0


def get_config() -> tuple[Optional[str], Optional[str]]:
    """Return (bot_token, chat_id), decrypted. Either may be None."""
    data = settings_mod.load().get("telegram", {})
    return settings_mod.decrypt(data.get("bot_token")), settings_mod.decrypt(data.get("chat_id"))


def is_configured() -> bool:
    token, chat_id = get_config()
    return bool(token and chat_id)


def _split(text: str) -> list[str]:
    """Split text into <=MAX_LEN chunks, preferring newline boundaries."""
    if len(text) <= MAX_LEN:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        # A single very long line is hard-split.
        while len(line) > MAX_LEN:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:MAX_LEN])
            line = line[MAX_LEN:]
        if len(current) + len(line) + 1 > MAX_LEN:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def send_message(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """Send a message (splitting if needed). Returns (ok, detail)."""
    url = f"{API_BASE}/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            for chunk in _split(text):
                resp = client.post(url, json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                })
                if resp.status_code != 200:
                    detail = _describe(resp)
                    log.warning("Telegram sendMessage failed: HTTP %d", resp.status_code)
                    return False, detail
        return True, "sent"
    except httpx.HTTPError as exc:
        log.warning("Telegram request error: %s", type(exc).__name__)
        return False, "network_error"


def _describe(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return str(body.get("description", "error"))
    except ValueError:
        return f"http_{resp.status_code}"


def send(text: str) -> tuple[bool, str]:
    """Send using the stored, encrypted configuration."""
    token, chat_id = get_config()
    if not token or not chat_id:
        return False, "not_configured"
    return send_message(token, chat_id, text)


def send_test(message: str) -> tuple[bool, str]:
    return send(message)
