"""AI analysis: build a prompt from RRD data and call Claude/OpenAI.

Provides:
  * on-demand single-host analysis (analyze_target)
  * consolidated daily-report generation (generate_daily_report) — used by the
    Phase 6 scheduler.

A lightweight global rate limit protects against runaway cost.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque

import httpx

import rrd_reader
import settings as settings_mod
from models_fetcher import (ANTHROPIC_BASE, ANTHROPIC_VERSION, OPENAI_BASE,
                            ProviderError, extract_error_detail)

log = logging.getLogger("smokeping_easy.ai")

TIMEOUT = 60.0
MAX_TOKENS = 1200
AI_MAX_PER_MINUTE = int(os.environ.get("AI_MAX_PER_MINUTE", "10"))

LANG_NAMES = {"en": "English", "es": "Español", "pt": "Português"}

# --- Rate limit ------------------------------------------------------------
_lock = threading.Lock()
_calls: deque = deque()


def _check_rate_limit() -> None:
    now = time.time()
    with _lock:
        while _calls and _calls[0] < now - 60:
            _calls.popleft()
        if len(_calls) >= AI_MAX_PER_MINUTE:
            raise ProviderError("rate_limited")
        _calls.append(now)


# --- Data summarisation ----------------------------------------------------


def _summarise_series(series: dict) -> str:
    points = [p for p in series.get("points", []) if p.get("latency_ms") is not None]
    if not points:
        return "No latency samples in this period."
    lats = [p["latency_ms"] for p in points]
    losses = [p["loss_pct"] for p in series.get("points", []) if p.get("loss_pct") is not None]
    avg = sum(lats) / len(lats)
    lo, hi = min(lats), max(lats)
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    max_loss = max(losses) if losses else 0.0
    return (
        f"samples={len(points)}, "
        f"latency_ms avg={avg:.1f} min={lo:.1f} max={hi:.1f}, "
        f"loss_pct avg={avg_loss:.2f} max={max_loss:.2f}"
    )


def _lang_name() -> str:
    lang = settings_mod.load().get("app", {}).get("language", "es")
    return LANG_NAMES.get(lang, "Español")


# --- Prompts ---------------------------------------------------------------


def _render(template: str, **values) -> str:
    """Fill {placeholders} without str.format (so stray braces never crash)."""
    out = template
    for key, val in values.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def _prompt_ondemand(label: str, host: str, period: str, data_text: str) -> str:
    # Use the user's editable prompt if set, else the built-in default. This
    # lets the operator write the prompt in their own language.
    template = settings_mod.load().get("ai", {}).get("analysis_prompt") \
        or settings_mod.DEFAULT_ANALYSIS_PROMPT
    return _render(
        template, label=label, host=host, period=period,
        data=data_text, language=_lang_name(),
    )


def _prompt_daily(date_start: str, date_end: str, timezone: str, total: int, data_all: str) -> str:
    return (
        "Você é um especialista em redes gerando relatório diário de monitoramento.\n\n"
        f"Período: últimas 24h ({date_start} a {date_end})\n"
        f"Timezone: {timezone}\n"
        f"Total de hosts monitorados: {total}\n\n"
        "Dados consolidados:\n"
        f"{data_all}\n\n"
        "Gere um relatório executivo que:\n"
        "1. Destaque hosts com comportamento anômalo\n"
        "2. Identifique padrões correlacionados (problemas de upstream)\n"
        "3. Classifique o status geral: Estável / Atenção / Crítico\n"
        "4. Liste as 3 principais recomendações para o dia\n\n"
        f"Formato para Telegram (emojis, sem markdown complexo). Máximo 600 palavras. "
        f"Responda em {_lang_name()}."
    )


# --- Provider calls --------------------------------------------------------


def _call_claude(api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    url = f"{ANTHROPIC_BASE}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _post(url, headers, body)
    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text.strip() or "(empty response)"


def _call_openai(api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    url = f"{OPENAI_BASE}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    # Newer OpenAI models (o-series, gpt-4o, gpt-5, …) reject the legacy
    # `max_tokens` and require `max_completion_tokens`; the latter is accepted
    # by current chat models, so we use it universally.
    body = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _post(url, headers, body)
    choices = data.get("choices", [])
    if not choices:
        return "(empty response)"
    return (choices[0].get("message", {}).get("content", "") or "").strip() or "(empty response)"


def _post(url: str, headers: dict, body: dict) -> dict:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        log.warning("AI request network error: %s", type(exc).__name__)
        raise ProviderError("provider_unreachable") from exc
    if resp.status_code in (401, 403):
        raise ProviderError("invalid_api_key")
    if resp.status_code == 429:
        raise ProviderError("rate_limited")
    if resp.status_code >= 400:
        raise ProviderError("provider_error", extract_error_detail(resp))
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError("provider_error", "bad_json") from exc


def _dispatch(provider: str, api_key: str, model: str, prompt: str, max_tokens: int) -> str:
    if provider == "claude":
        return _call_claude(api_key, model, prompt, max_tokens)
    if provider == "openai":
        return _call_openai(api_key, model, prompt, max_tokens)
    raise ProviderError("invalid_provider")


# --- Public API ------------------------------------------------------------


def analyze_target(target: dict, provider: str, api_key: str, model: str,
                   range_key: str = "3h") -> str:
    if not api_key or not model:
        raise ProviderError("ai_not_configured")
    _check_rate_limit()
    ranges = {"3h": "-3h", "30h": "-30h", "10d": "-10d", "360d": "-360d"}
    series = rrd_reader.get_series(target, start=ranges.get(range_key, "-3h"))
    data_text = _summarise_series(series)
    prompt = _prompt_ondemand(
        target.get("label") or target.get("host"), target.get("host"),
        range_key, data_text,
    )
    return _dispatch(provider, api_key, model, prompt, MAX_TOKENS)


def generate_daily_report(targets: list[dict], provider: str, api_key: str,
                          model: str, date_start: str, date_end: str,
                          timezone: str) -> str:
    if not api_key or not model:
        raise ProviderError("ai_not_configured")
    _check_rate_limit()
    lines = []
    for t in targets:
        series = rrd_reader.get_series(t, start="-24h")
        lines.append(f"- {t.get('label') or t.get('host')} ({t.get('host')}): {_summarise_series(series)}")
    data_all = "\n".join(lines) if lines else "No targets configured."
    prompt = _prompt_daily(date_start, date_end, timezone, len(targets), data_all)
    return _dispatch(provider, api_key, model, prompt, 1600)
