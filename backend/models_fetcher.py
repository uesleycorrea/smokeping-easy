"""Fetch the list of available models from the real provider API.

No model list is hardcoded — we query the provider so the UI always reflects
what the given API key can actually use.

  claude  -> GET https://api.anthropic.com/v1/models   (x-api-key)
  openai  -> GET https://api.openai.com/v1/models       (Authorization: Bearer)
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger("smokeping_easy.models")

ANTHROPIC_BASE = "https://api.anthropic.com"
OPENAI_BASE = "https://api.openai.com"
ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT = 20.0


class ProviderError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


def extract_error_detail(resp) -> str:
    """Pull the human-readable error message out of a provider response.

    Both OpenAI and Anthropic return ``{"error": {"message": "...", ...}}``.
    Falls back to the raw body / status so nothing is silently swallowed.
    """
    try:
        data = resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        return text[:300] if text else f"http_{resp.status_code}"
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return err.get("message") or err.get("type") or f"http_{resp.status_code}"
    if isinstance(err, str):
        return err
    return f"http_{resp.status_code}"


def fetch_models(provider: str, api_key: str) -> list[dict]:
    if not api_key:
        raise ProviderError("ai_not_configured")
    if provider == "claude":
        return _fetch_claude(api_key)
    if provider == "openai":
        return _fetch_openai(api_key)
    raise ProviderError("invalid_provider")


def _fetch_claude(api_key: str) -> list[dict]:
    url = f"{ANTHROPIC_BASE}/v1/models?limit=100"
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    data = _get(url, headers)
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if "claude" not in mid.lower():
            continue
        out.append({
            "id": mid,
            "name": m.get("display_name") or mid,
            "description": m.get("type", ""),
        })
    return out


# gpt-* models that are NOT chat/completions compatible (would error if picked).
_OPENAI_EXCLUDE = (
    "instruct", "realtime", "audio", "transcribe", "tts", "image",
    "search", "moderation", "embedding",
)


def _fetch_openai(api_key: str) -> list[dict]:
    url = f"{OPENAI_BASE}/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _get(url, headers)
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if not mid.startswith("gpt-"):
            continue
        if any(bad in mid for bad in _OPENAI_EXCLUDE):
            continue
        out.append({"id": mid, "name": mid})
    # Newest-looking first for convenience.
    out.sort(key=lambda x: x["id"], reverse=True)
    return out


def _get(url: str, headers: dict) -> dict:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("Models request network error: %s", type(exc).__name__)
        raise ProviderError("provider_unreachable") from exc
    if resp.status_code in (401, 403):
        raise ProviderError("invalid_api_key")
    if resp.status_code >= 400:
        raise ProviderError("provider_error", extract_error_detail(resp))
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError("provider_error", "bad_json") from exc
