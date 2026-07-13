"""Persistent application settings with at-rest encryption for secrets.

Secrets (Telegram bot token / chat id, AI API key) are encrypted with Fernet
and stored in ``settings.json`` prefixed with ``encrypted:``. The Fernet key
lives in ``secret.key`` (chmod 600), generated on first boot and never
committed.

The public ``get_public_settings()`` view NEVER returns decrypted secrets — it
only reports whether each secret is configured, so the frontend can render
"configured / not configured" without ever receiving the value.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("smokeping_easy.settings")

DATA_DIR = os.environ.get("APP_DATA_DIR", "/app/data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
KEY_PATH = os.path.join(DATA_DIR, "secret.key")

ENC_PREFIX = "encrypted:"

_lock = threading.RLock()
_fernet: Optional[Fernet] = None

DEFAULT_TIMEZONE = os.environ.get("TZ", "UTC")

# Default, editable on-demand analysis prompt. Placeholders {label} {host}
# {period} {data} {language} are substituted at analysis time. Users can edit
# it (in their own language) from Settings → AI.
DEFAULT_ANALYSIS_PROMPT = (
    "Você é um especialista em redes de telecomunicações analisando dados de monitoramento.\n\n"
    "Host monitorado: {label} ({host})\n"
    "Período: {period}\n"
    "Dados de latência e perda de pacotes:\n"
    "{data}\n\n"
    "Analise e:\n"
    "1. Identifique padrões ou anomalias\n"
    "2. Avalie a severidade: normal / atenção / crítico\n"
    "3. Sugira possíveis causas\n"
    "4. Recomende ações para um técnico de ISP\n\n"
    "Responda em {language}. Seja direto e técnico. Máximo 400 palavras."
)

DEFAULTS: dict[str, Any] = {
    "telegram": {
        "bot_token": None,
        "chat_id": None,
        "daily_report_enabled": False,
        "daily_report_hour": 7,
        "daily_report_minute": 0,
    },
    "ai": {
        "provider": "claude",
        "api_key": None,
        "model": None,
        "analysis_prompt": None,
    },
    "auth": {
        "password_hash": None,
    },
    "app": {
        "language": "es",
        "timezone": DEFAULT_TIMEZONE,
    },
    "monitor": {
        "order": [],    # ordered target ids shown on the NOC monitor
        "hidden": [],   # target ids excluded from the monitor
    },
}


# --- Encryption key --------------------------------------------------------


def _ensure_key() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    with _lock:
        if _fernet is not None:
            return _fernet
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as fh:
                key = fh.read().strip()
        else:
            key = Fernet.generate_key()
            # Write with restrictive permissions from the start.
            fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, key)
            finally:
                os.close(fd)
            log.info("Generated new encryption key at %s", KEY_PATH)
        try:
            os.chmod(KEY_PATH, 0o600)
        except OSError:
            pass
        _fernet = Fernet(key)
        return _fernet


def ensure_key() -> None:
    """Public: make sure secret.key exists (chmod 600) at boot time."""
    _ensure_key()


def encrypt(value: Optional[str]) -> Optional[str]:
    """Encrypt a secret. ``None``/empty passes through unchanged."""
    if value is None or value == "":
        return None
    token = _ensure_key().encrypt(value.encode("utf-8")).decode("ascii")
    return ENC_PREFIX + token


def decrypt(value: Optional[str]) -> Optional[str]:
    """Decrypt a stored secret. Returns None if empty/invalid."""
    if not value:
        return None
    if not value.startswith(ENC_PREFIX):
        # Legacy/plaintext — return as-is (should not happen in normal use).
        return value
    token = value[len(ENC_PREFIX):]
    try:
        return _ensure_key().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        log.warning("Failed to decrypt a stored secret (key mismatch?)")
        return None


def is_secret_set(value: Optional[str]) -> bool:
    return bool(value)


# --- Load / save -----------------------------------------------------------


def _merge_defaults(data: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULTS))  # deep copy
    for section, values in (data or {}).items():
        if section in merged and isinstance(values, dict):
            merged[section].update(values)
        else:
            merged[section] = values
    return merged


def load() -> dict:
    """Load settings, merged over defaults. Creates the file on first call."""
    with _lock:
        if not os.path.exists(SETTINGS_PATH):
            _write_raw(_merge_defaults({}))
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Could not read settings.json (%s); using defaults", exc)
            data = {}
        return _merge_defaults(data)


def _write_raw(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, SETTINGS_PATH)
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass


def save(data: dict) -> None:
    with _lock:
        _write_raw(data)


def update_section(section: str, values: dict) -> dict:
    """Merge ``values`` into a section and persist. Returns full settings."""
    with _lock:
        data = load()
        data.setdefault(section, {})
        data[section].update(values)
        save(data)
        return data


# --- Public (safe) view ----------------------------------------------------


def get_public_settings() -> dict:
    """Settings safe to send to the browser — NO decrypted secrets."""
    data = load()
    tg = data.get("telegram", {})
    ai = data.get("ai", {})
    app_ = data.get("app", {})
    return {
        "telegram": {
            "bot_token_set": is_secret_set(tg.get("bot_token")),
            "chat_id_set": is_secret_set(tg.get("chat_id")),
            "daily_report_enabled": bool(tg.get("daily_report_enabled")),
            "daily_report_hour": tg.get("daily_report_hour", 7),
            "daily_report_minute": tg.get("daily_report_minute", 0),
        },
        "ai": {
            "provider": ai.get("provider", "claude"),
            "api_key_set": is_secret_set(ai.get("api_key")),
            "model": ai.get("model"),
            "analysis_prompt": ai.get("analysis_prompt") or DEFAULT_ANALYSIS_PROMPT,
        },
        "app": {
            "language": app_.get("language", "es"),
            "timezone": app_.get("timezone", DEFAULT_TIMEZONE),
        },
        "monitor": data.get("monitor", {"order": [], "hidden": []}),
    }
