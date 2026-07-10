"""Talk to the internal Smokeping reload API (reload_server.py).

The reload API lives inside the Smokeping container on an INTERNAL-only port
(``RELOAD_URL``, default http://smokeping:9000, never published to the host).
Requests carry the shared ``RELOAD_TOKEN``.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("smokeping_easy.ctrl")

RELOAD_URL = os.environ.get("RELOAD_URL", "http://smokeping:9000").rstrip("/")
RELOAD_TOKEN = os.environ.get("RELOAD_TOKEN", "")
TIMEOUT = float(os.environ.get("RELOAD_TIMEOUT", "30"))

_LAST_RELOAD_FILE = os.path.join(os.environ.get("APP_DATA_DIR", "/app/data"), "last_reload.json")
_STATUS_TTL = 15.0
_status_cache = {"at": 0.0, "data": {"running": False, "version": ""}}


def _headers() -> dict:
    return {"X-Reload-Token": RELOAD_TOKEN} if RELOAD_TOKEN else {}


def _post(path: str) -> tuple[bool, dict]:
    url = f"{RELOAD_URL}{path}"
    try:
        resp = httpx.post(url, headers=_headers(), timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        log.error("Reload API request failed (%s): %s", path, exc)
        return False, {"error": "unreachable", "detail": str(exc)}
    try:
        body = resp.json()
    except ValueError:
        body = {"detail": resp.text[:500]}
    ok = 200 <= resp.status_code < 300
    if not ok:
        log.warning("Reload API %s returned %d: %s", path, resp.status_code, body)
    return ok, body


def check() -> tuple[bool, dict]:
    """Validate the current Smokeping config syntax."""
    return _post("/check")


def _record_reload() -> None:
    try:
        with open(_LAST_RELOAD_FILE, "w", encoding="utf-8") as fh:
            json.dump({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, fh)
    except OSError:
        pass


def get_last_reload() -> str | None:
    """ISO timestamp of the last successful reload, or None."""
    try:
        with open(_LAST_RELOAD_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh).get("at")
    except (OSError, ValueError):
        return None


def status() -> dict:
    """Smokeping daemon status (running + version), cached for a few seconds."""
    now = time.time()
    if now - _status_cache["at"] < _STATUS_TTL:
        return _status_cache["data"]
    data = {"running": False, "version": ""}
    try:
        resp = httpx.get(f"{RELOAD_URL}/status", timeout=5)
        if resp.status_code == 200:
            body = resp.json()
            data = {"running": bool(body.get("running")), "version": body.get("version", "")}
    except (httpx.HTTPError, ValueError):
        pass
    _status_cache["at"] = now
    _status_cache["data"] = data
    return data


def reload() -> tuple[bool, dict]:
    """Validate and reload the Smokeping configuration."""
    ok, body = _post("/reload")
    if ok:
        _record_reload()
    return ok, body


def health() -> bool:
    try:
        resp = httpx.get(f"{RELOAD_URL}/health", timeout=5)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


MTR_TIMEOUT = float(os.environ.get("MTR_TIMEOUT", "45"))


def mtr(host: str, ipv6: bool = False, cycles: int = 5) -> tuple[bool, dict]:
    """Run an on-demand MTR from the smokeping container (server vantage)."""
    try:
        resp = httpx.post(
            f"{RELOAD_URL}/mtr",
            headers=_headers(),
            json={"host": host, "ipv6": ipv6, "cycles": cycles},
            timeout=MTR_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        log.error("MTR request failed: %s", exc)
        return False, {"error": "unreachable", "detail": str(exc)}
    try:
        body = resp.json()
    except ValueError:
        body = {"error": "bad_response"}
    return (200 <= resp.status_code < 300), body
