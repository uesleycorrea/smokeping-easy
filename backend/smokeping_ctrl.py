"""Talk to the internal Smokeping reload API (reload_server.py).

The reload API lives inside the Smokeping container on an INTERNAL-only port
(``RELOAD_URL``, default http://smokeping:9000, never published to the host).
Requests carry the shared ``RELOAD_TOKEN``.
"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("smokeping_easy.ctrl")

RELOAD_URL = os.environ.get("RELOAD_URL", "http://smokeping:9000").rstrip("/")
RELOAD_TOKEN = os.environ.get("RELOAD_TOKEN", "")
TIMEOUT = float(os.environ.get("RELOAD_TIMEOUT", "30"))


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


def reload() -> tuple[bool, dict]:
    """Validate and reload the Smokeping configuration."""
    return _post("/reload")


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
