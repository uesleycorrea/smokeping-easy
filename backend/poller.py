"""Alerting scheduler.

Runs inside the backend process (APScheduler). Every 60 seconds it reads the
latest RRD sample for each target that has a threshold, and sends Telegram
alerts on breach / normalisation with a per-target cooldown so it never spams.

Alert state is persisted to ``alert_state.json`` so cooldown and
"already-alerting" status survive restarts.

The daily AI report job is added in Phase 6 (see :func:`_ensure_daily_job`).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import ai_analyzer
import config_writer
import rrd_reader
import settings as settings_mod
import telegram_bot

log = logging.getLogger("smokeping_easy.poller")

DATA_DIR = os.environ.get("APP_DATA_DIR", "/app/data")
STATE_PATH = os.path.join(DATA_DIR, "alert_state.json")
HISTORY_PATH = os.path.join(DATA_DIR, "job_history.json")
HISTORY_MAX = 50
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

_lock = threading.RLock()
_scheduler: Optional[BackgroundScheduler] = None

# --- Alert message templates (EN / ES / PT) --------------------------------
MESSAGES = {
    "en": {
        "latency_alert": "⚠️ [{label}] Latency: {value} ms (limit: {threshold} ms)",
        "latency_ok": "✅ [{label}] Latency back to normal: {value} ms",
        "loss_alert": "⚠️ [{label}] Packet loss: {value}% (limit: {threshold}%)",
        "loss_ok": "✅ [{label}] Packet loss back to normal: {value}%",
        "test": "✅ smokeping-easy: Telegram is configured correctly.",
    },
    "es": {
        "latency_alert": "⚠️ [{label}] Latencia: {value} ms (límite: {threshold} ms)",
        "latency_ok": "✅ [{label}] Latencia normalizada: {value} ms",
        "loss_alert": "⚠️ [{label}] Pérdida de paquetes: {value}% (límite: {threshold}%)",
        "loss_ok": "✅ [{label}] Pérdida normalizada: {value}%",
        "test": "✅ smokeping-easy: Telegram está configurado correctamente.",
    },
    "pt": {
        "latency_alert": "⚠️ [{label}] Latência: {value} ms (limite: {threshold} ms)",
        "latency_ok": "✅ [{label}] Latência normalizada: {value} ms",
        "loss_alert": "⚠️ [{label}] Perda de pacotes: {value}% (limite: {threshold}%)",
        "loss_ok": "✅ [{label}] Perda normalizada: {value}%",
        "test": "✅ smokeping-easy: o Telegram está configurado corretamente.",
    },
}


def _lang() -> str:
    lang = settings_mod.load().get("app", {}).get("language", "es")
    return lang if lang in MESSAGES else "es"


def msg(key: str, **params) -> str:
    return MESSAGES[_lang()][key].format(**params)


def _tz():
    name = settings_mod.load().get("app", {}).get("timezone", "UTC") or "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Unknown timezone %r, falling back to UTC", name)
        return ZoneInfo("UTC")


# --- Alert state persistence ----------------------------------------------


def _load_state() -> dict:
    with _lock:
        if not os.path.exists(STATE_PATH):
            return {}
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}


def _save_state(state: dict) -> None:
    with _lock:
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, STATE_PATH)


def _fmt(value: float) -> str:
    return f"{value:.1f}"


# --- Core poll -------------------------------------------------------------


def _eval_metric(state: dict, target: dict, metric: str, value: Optional[float],
                 threshold: Optional[float]) -> None:
    """Update state and fire alert/normalisation for one metric of one target.

    ``metric`` is 'latency' or 'loss'. Mutates ``state`` in place.
    """
    if threshold is None or value is None:
        return
    tid = target["id"]
    label = target.get("label") or target.get("host")
    cooldown = float(target.get("alert_cooldown_minutes", 30)) * 60.0
    now = time.time()

    tstate = state.setdefault(tid, {})
    mstate = tstate.setdefault(metric, {"active": False, "last_notified": 0, "since": 0, "value": None})

    breached = value > threshold

    if breached:
        due = (not mstate["active"]) or (now - mstate.get("last_notified", 0) >= cooldown)
        if due:
            key = f"{metric}_alert"
            ok, _ = telegram_bot.send(
                msg(key, label=label, value=_fmt(value), threshold=_fmt(threshold))
            )
            if not mstate["active"]:
                mstate["since"] = now
            mstate["active"] = True
            mstate["value"] = value
            if ok:
                mstate["last_notified"] = now
    else:
        if mstate["active"]:
            key = f"{metric}_ok"
            telegram_bot.send(msg(key, label=label, value=_fmt(value)))
            mstate["active"] = False
            mstate["value"] = value
            mstate["last_notified"] = 0
            mstate["since"] = 0


def poll_once() -> None:
    """One polling cycle over all targets with thresholds."""
    if not telegram_bot.is_configured():
        return  # nothing to notify to
    targets = config_writer.load_targets()
    state = _load_state()
    # Drop state for deleted targets.
    live_ids = {t["id"] for t in targets}
    for tid in list(state.keys()):
        if tid not in live_ids:
            state.pop(tid, None)

    for target in targets:
        lat_th = target.get("latency_threshold_ms")
        loss_th = target.get("loss_threshold_pct")
        if lat_th is None and loss_th is None:
            continue
        data = rrd_reader.get_latest(target)
        if not data:
            continue
        _eval_metric(state, target, "latency", data.get("avg_latency_ms"), lat_th)
        _eval_metric(state, target, "loss", data.get("loss_pct"), loss_th)

    _save_state(state)


def _poll_job():
    try:
        poll_once()
    except Exception as exc:  # noqa: BLE001 - never let the scheduler die
        log.exception("Poll cycle failed: %s", exc)


# --- Scheduler lifecycle ---------------------------------------------------


# --- Daily report job ------------------------------------------------------


def _record_history(entry: dict) -> None:
    with _lock:
        history = _load_history()
        entry["ts"] = datetime.now(_tz()).isoformat()
        history.insert(0, entry)
        history = history[:HISTORY_MAX]
        tmp = HISTORY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(history, fh, indent=2)
        os.replace(tmp, HISTORY_PATH)


def _load_history() -> list:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def run_daily_report() -> tuple[bool, str]:
    """Build the consolidated 24h AI report and send it over Telegram.

    Returns (ok, status). Records the outcome in job_history.json.
    """
    if not telegram_bot.is_configured():
        _record_history({"type": "daily_report", "status": "telegram_not_configured"})
        return False, "telegram_not_configured"

    ai = settings_mod.load().get("ai", {})
    provider = ai.get("provider", "claude")
    model = ai.get("model")
    key = settings_mod.decrypt(ai.get("api_key"))
    tzname = settings_mod.load().get("app", {}).get("timezone", "UTC")
    targets = config_writer.load_targets()

    now = datetime.now(_tz())
    start = now - timedelta(hours=24)
    fmt = "%Y-%m-%d %H:%M"

    try:
        text = ai_analyzer.generate_daily_report(
            targets, provider, key, model,
            start.strftime(fmt), now.strftime(fmt), tzname,
        )
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", type(exc).__name__)
        log.warning("Daily report generation failed: %s", code)
        _record_history({"type": "daily_report", "status": f"error:{code}"})
        return False, f"error:{code}"

    ok, detail = telegram_bot.send(text)
    status = "sent" if ok else f"telegram_failed:{detail}"
    _record_history({"type": "daily_report", "status": status, "chars": len(text)})
    return ok, status


def _daily_job():
    try:
        run_daily_report()
    except Exception as exc:  # noqa: BLE001 - never let the scheduler die
        log.exception("Daily report job crashed: %s", exc)


def _ensure_daily_job(scheduler: BackgroundScheduler) -> None:
    """Add/replace/remove the daily report cron job based on settings.

    The CronTrigger carries its own timezone, so this works on a running
    scheduler without touching the global scheduler timezone.
    """
    tg = settings_mod.load().get("telegram", {})
    enabled = bool(tg.get("daily_report_enabled")) and telegram_bot.is_configured()
    existing = scheduler.get_job("daily_report")
    if not enabled:
        if existing:
            scheduler.remove_job("daily_report")
        return
    hour = int(tg.get("daily_report_hour", 7))
    minute = int(tg.get("daily_report_minute", 0))
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=hour, minute=minute, timezone=_tz()),
        id="daily_report", replace_existing=True, max_instances=1, coalesce=True,
    )
    log.info("Daily report scheduled at %02d:%02d (%s)", hour, minute, _tz())


def trigger_daily_report_now() -> tuple[bool, str]:
    """Run the daily report immediately (manual trigger)."""
    return run_daily_report()


def get_history() -> list:
    return _load_history()


def start() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return
        scheduler = BackgroundScheduler(timezone=_tz())
        scheduler.add_job(
            _poll_job, "interval", seconds=POLL_INTERVAL,
            id="poller", replace_existing=True, max_instances=1, coalesce=True,
        )
        _ensure_daily_job(scheduler)
        scheduler.start()
        _scheduler = scheduler
        log.info("Alert poller started (every %ds, tz=%s)", POLL_INTERVAL, _tz())


def shutdown() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def reschedule() -> None:
    """Re-apply the daily-report schedule after settings change.

    We must NOT call ``scheduler.configure()`` on a running scheduler
    (APScheduler raises SchedulerAlreadyRunningError). The daily report job
    carries its own timezone in its CronTrigger, so re-adding it is enough.
    """
    with _lock:
        if _scheduler is None:
            return
        _ensure_daily_job(_scheduler)


def _job_info(job_id: str) -> dict:
    if _scheduler is None:
        return {"scheduled": False}
    job = _scheduler.get_job(job_id)
    if job is None:
        return {"scheduled": False}
    nxt = job.next_run_time
    return {"scheduled": True, "next_run": nxt.isoformat() if nxt else None}


def get_status() -> dict:
    """Status for the UI: telegram config, active alerts and job schedule."""
    state = _load_state()
    active = []
    for tid, metrics in state.items():
        for metric, ms in metrics.items():
            if ms.get("active"):
                active.append({"target_id": tid, "metric": metric, "value": ms.get("value")})
    history = _load_history()
    return {
        "telegram_configured": telegram_bot.is_configured(),
        "poller": _job_info("poller"),
        "daily_report": _job_info("daily_report"),
        "active_alerts": active,
        "last_report": history[0] if history else None,
    }
