"""smokeping-easy backend — FastAPI application.

Route summary:
  Public:
    GET  /api/status                 liveness + auth/setup state (no secrets)
  Auth:
    POST /api/auth/login             password -> session cookie (rate limited)
    POST /api/auth/logout            destroy session
    GET  /api/auth/me                current session info
    POST /api/auth/password          change password (requires session)
  Targets (all require session):
    GET    /api/targets
    POST   /api/targets
    PUT    /api/targets/{id}
    DELETE /api/targets/{id}
    GET    /api/targets/{id}/latest
    GET    /api/targets/{id}/series
  Settings (require session):
    GET  /api/settings
    PUT  /api/settings/app

Every route except /api/auth/login and /api/status requires a valid session.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import ai_analyzer
import auth
import config_writer
import models_fetcher
import poller
import rrd_reader
import settings as settings_mod
import smokeping_ctrl
import telegram_bot
import validators
from log_middleware import AccessLogMiddleware
from models_fetcher import ProviderError

VERSION = "1.1.0"

# --- Logging ---------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("smokeping_easy.main")


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "-"


# --- App & middleware ------------------------------------------------------
limiter = Limiter(key_func=get_client_ip)
app = FastAPI(title="smokeping-easy", version=VERSION, docs_url=None, redoc_url=None)
app.state.limiter = limiter

# AccessLogMiddleware is the ONLY app middleware and is therefore the outermost
# one — it wraps and logs every request (with sensitive fields redacted).
app.add_middleware(AccessLogMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "rate_limited"})


@app.exception_handler(validators.ValidationError)
async def _validation_handler(request: Request, exc: validators.ValidationError):
    return JSONResponse(status_code=400, content={"error": exc.code, "detail": str(exc)})


@app.exception_handler(ProviderError)
async def _provider_handler(request: Request, exc: ProviderError):
    status = 429 if exc.code == "rate_limited" else 502
    return JSONResponse(status_code=status, content={"error": exc.code, "detail": exc.detail})


# --- Auth dependency -------------------------------------------------------


async def require_session(request: Request) -> auth.Session:
    token = request.cookies.get(auth.COOKIE_NAME)
    sess = auth.get_session(token)
    if sess is None:
        # 401 with a stable code so the frontend can redirect to login.
        raise _http(401, "unauthenticated")
    return sess


def _http(status: int, code: str, detail: str = "") -> "HTTPErr":
    return HTTPErr(status, code, detail)


class HTTPErr(Exception):
    def __init__(self, status: int, code: str, detail: str = ""):
        self.status = status
        self.code = code
        self.detail = detail


@app.exception_handler(HTTPErr)
async def _httperr_handler(request: Request, exc: HTTPErr):
    body = {"error": exc.code}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)


# --- Models ----------------------------------------------------------------


class LoginBody(BaseModel):
    password: str


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


class AppSettingsBody(BaseModel):
    language: str | None = None
    timezone: str | None = None


class TelegramSettingsBody(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None
    daily_report_enabled: bool | None = None
    daily_report_hour: int | None = None
    daily_report_minute: int | None = None


class AiSettingsBody(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    analysis_prompt: str | None = None


class AnalyzeBody(BaseModel):
    target_id: str
    range: str | None = "3h"
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


# --- Startup ---------------------------------------------------------------


@app.on_event("startup")
def _startup():
    settings_mod.load()  # ensure settings.json exists
    settings_mod.ensure_key()  # generate secret.key (chmod 600) on first boot
    auth.ensure_admin_seeded()
    # Groups are first-class; make sure a default exists and old targets are
    # backfilled with a group_id before we render.
    config_writer.ensure_default_group()
    config_writer.migrate_target_groups()
    # Keep the Smokeping Targets file in sync with our store on boot.
    try:
        config_writer.render_smokeping_targets()
    except Exception as exc:  # noqa: BLE001
        log.error("Could not render Targets on startup: %s", exc)
    poller.start()
    log.info("smokeping-easy backend %s started (log level %s)", VERSION, LOG_LEVEL)


@app.on_event("shutdown")
def _shutdown():
    poller.shutdown()


# --- Helpers ---------------------------------------------------------------


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        max_age=auth.SESSION_TTL_MINUTES * 60,
        httponly=True,
        samesite="strict",
        secure=auth.COOKIE_SECURE,
        path="/",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _apply_reload() -> dict:
    """Render the Targets file and reload Smokeping. Returns a status dict."""
    config_writer.render_smokeping_targets()
    ok, body = smokeping_ctrl.reload()
    return {"reloaded": ok, "reload_detail": body}


def _target_public(t: dict) -> dict:
    return t  # targets contain no secrets; return as-is


# --- Public ----------------------------------------------------------------


@app.get("/api/status")
def status(request: Request):
    # Sync route -> threadpool (the smokeping status probe may block briefly).
    token = request.cookies.get(auth.COOKIE_NAME)
    authed = auth.get_session(token) is not None
    app_cfg = settings_mod.load().get("app", {})
    resp = {
        "status": "ok",
        "version": VERSION,
        "authenticated": authed,
        "setup_required": not auth.password_is_configured(),
        "language": app_cfg.get("language", "es"),
        "timezone": app_cfg.get("timezone", "UTC"),
    }
    # Detailed system status is only exposed to authenticated sessions (and so
    # never probes Smokeping for anonymous/healthcheck traffic).
    if authed:
        sp = smokeping_ctrl.status()
        resp.update(
            smokeping_running=sp["running"],
            targets_count=len(config_writer.load_targets()),
            last_reload_at=smokeping_ctrl.get_last_reload(),
            smokeping_version=sp["version"],
        )
    return resp


# --- Auth ------------------------------------------------------------------


@app.post("/api/auth/login")
@limiter.limit("20/minute")
async def login(request: Request, response: Response):
    # Body is read manually (not via a Pydantic param) so the slowapi
    # @limiter.limit decorator does not interfere with body introspection.
    ip = get_client_ip(request)
    if auth.is_rate_limited(ip):
        retry = auth.retry_after_seconds(ip)
        return JSONResponse(
            status_code=429,
            content={"error": "too_many_attempts", "retry_after": retry},
            headers={"Retry-After": str(retry)},
        )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    password = (payload or {}).get("password", "")
    if not isinstance(password, str) or not auth.check_credentials(password):
        auth.record_failure(ip)
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})
    auth.clear_failures(ip)
    sess = auth.create_session(ip)
    _set_session_cookie(response, sess.token)
    return {"ok": True}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response, _s: auth.Session = Depends(require_session)):
    token = request.cookies.get(auth.COOKIE_NAME)
    auth.destroy_session(token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
async def me(sess: auth.Session = Depends(require_session)):
    return {"authenticated": True, "expires_at": int(sess.expires_at)}


@app.post("/api/auth/password")
async def change_password(
    body: PasswordBody, sess: auth.Session = Depends(require_session)
):
    if not auth.check_credentials(body.current_password):
        raise _http(400, "invalid_current_password")
    if len(body.new_password) < 8:
        raise _http(400, "password_too_short")
    auth.set_password(body.new_password)
    return {"ok": True}


# --- Targets ---------------------------------------------------------------


@app.get("/api/targets")
async def list_targets(_s: auth.Session = Depends(require_session)):
    return {"targets": config_writer.load_targets()}


# --- Monitor (NOC screen) --------------------------------------------------


class MonitorBody(BaseModel):
    order: list[str] | None = None
    hidden: list[str] | None = None
    group_order: list[str] | None = None


@app.get("/api/monitor")
def get_monitor(_s: auth.Session = Depends(require_session)):
    # Sync route -> threadpool (reads one RRD sample per target).
    targets = config_writer.load_targets()
    mon = settings_mod.load().get("monitor", {})
    tiles = []
    for t in targets:
        tiles.append({
            "id": t["id"],
            "label": t.get("label"),
            "host": t.get("host"),
            "group": t.get("group"),
            "latency_threshold_ms": t.get("latency_threshold_ms"),
            "loss_threshold_pct": t.get("loss_threshold_pct"),
            "latest": rrd_reader.get_latest(t),
        })
    return {
        "order": mon.get("order", []),
        "hidden": mon.get("hidden", []),
        "group_order": mon.get("group_order", []),
        "targets": tiles,
    }


@app.put("/api/settings/monitor")
async def update_monitor(body: MonitorBody, _s: auth.Session = Depends(require_session)):
    valid = {t["id"] for t in config_writer.load_targets()}
    updates: dict = {}
    if body.order is not None:
        # keep only known ids, de-duplicated, preserving order
        seen: set = set()
        updates["order"] = [i for i in body.order if i in valid and not (i in seen or seen.add(i))]
    if body.hidden is not None:
        updates["hidden"] = [i for i in set(body.hidden) if i in valid]
    if body.group_order is not None:
        seen2: set = set()
        updates["group_order"] = [
            g for g in body.group_order
            if isinstance(g, str) and g and not (g in seen2 or seen2.add(g))
        ][:200]
    if updates:
        settings_mod.update_section("monitor", updates)
    return settings_mod.load().get("monitor", {"order": [], "hidden": [], "group_order": []})


# --- Groups ----------------------------------------------------------------


class GroupBody(BaseModel):
    name: str


def _clean_group_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise _http(400, "group_name_required")
    if len(name) > validators.MAX_GROUP_LEN:
        raise _http(400, "group_too_long")
    return name


@app.get("/api/groups")
async def list_groups(_s: auth.Session = Depends(require_session)):
    groups = config_writer.load_groups()
    targets = config_writer.load_targets()
    counts: dict = {}
    for t in targets:
        counts[t.get("group_id")] = counts.get(t.get("group_id"), 0) + 1
    return {"groups": [{**g, "target_count": counts.get(g["id"], 0)} for g in groups]}


@app.post("/api/groups", status_code=201)
async def create_group(body: GroupBody, _s: auth.Session = Depends(require_session)):
    return {"group": config_writer.create_group(_clean_group_name(body.name))}


@app.put("/api/groups/{group_id}")
async def rename_group(group_id: str, body: GroupBody, _s: auth.Session = Depends(require_session)):
    group = config_writer.rename_group(group_id, _clean_group_name(body.name))
    if group is None:
        raise _http(404, "group_not_found")
    # Menu labels in Smokeping reflect the new name.
    _apply_reload()
    return {"group": group}


@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: str, _s: auth.Session = Depends(require_session)):
    code = config_writer.delete_group(group_id)
    if code == "ok":
        return {"ok": True}
    if code == "not_found":
        raise _http(404, "group_not_found")
    if code == "default":
        raise _http(409, "group_is_default")
    raise _http(409, "group_in_use")


def _resolve_group(payload: dict) -> dict:
    """Resolve the target's group from group_id (preferred) or a name."""
    gid = payload.get("group_id")
    if gid:
        g = config_writer.get_group(gid)
        if g:
            return g
    name = payload.get("group")
    if name:
        return config_writer.find_or_create_group_by_name(name)
    return config_writer.ensure_default_group()


@app.post("/api/targets", status_code=201)
async def create_target(request: Request, _s: auth.Session = Depends(require_session)):
    payload = await request.json()
    fields = validators.validate_target(payload)
    group = _resolve_group(payload)
    fields["group_id"] = group["id"]
    fields["group"] = group["name"]
    now = _now_iso()
    target = {
        "id": validators.new_uuid(),
        **fields,
        "created_at": now,
        "updated_at": now,
    }
    targets = config_writer.load_targets()
    targets.append(target)
    config_writer.save_targets(targets)
    reload_status = _apply_reload()
    return {"target": target, **reload_status}


@app.put("/api/targets/{target_id}")
async def update_target(
    target_id: str, request: Request, _s: auth.Session = Depends(require_session)
):
    payload = await request.json()
    fields = validators.validate_target(payload, target_id=target_id)
    group = _resolve_group(payload)
    fields["group_id"] = group["id"]
    fields["group"] = group["name"]
    targets = config_writer.load_targets()
    found = None
    for t in targets:
        if t.get("id") == target_id:
            t.update(fields)
            t["updated_at"] = _now_iso()
            found = t
            break
    if found is None:
        raise _http(404, "target_not_found")
    config_writer.save_targets(targets)
    reload_status = _apply_reload()
    return {"target": found, **reload_status}


@app.delete("/api/targets/{target_id}")
async def delete_target(target_id: str, _s: auth.Session = Depends(require_session)):
    targets = config_writer.load_targets()
    new_targets = [t for t in targets if t.get("id") != target_id]
    if len(new_targets) == len(targets):
        raise _http(404, "target_not_found")
    config_writer.save_targets(new_targets)
    reload_status = _apply_reload()
    return {"ok": True, **reload_status}


@app.get("/api/targets/{target_id}/latest")
async def target_latest(target_id: str, _s: auth.Session = Depends(require_session)):
    target = config_writer.get_target(target_id)
    if target is None:
        raise _http(404, "target_not_found")
    return {"data": rrd_reader.get_latest(target)}


@app.get("/api/targets/{target_id}/series")
async def target_series(
    target_id: str, range: str = "3h", _s: auth.Session = Depends(require_session)
):
    target = config_writer.get_target(target_id)
    if target is None:
        raise _http(404, "target_not_found")
    allowed = {"3h": "-3h", "30h": "-30h", "10d": "-10d", "360d": "-360d"}
    start = allowed.get(range, "-3h")
    return {"target_id": target_id, "range": range, **rrd_reader.get_series(target, start=start)}


@app.get("/api/targets/{target_id}/mtr")
def target_mtr(target_id: str, cycles: int = 5, _s: auth.Session = Depends(require_session)):
    # Sync route -> runs in the threadpool (mtr blocks for several seconds).
    target = config_writer.get_target(target_id)
    if target is None:
        raise _http(404, "target_not_found")
    host = validators.validate_host(target["host"])  # re-validate before tracing
    cycles = max(1, min(10, cycles))
    ok, body = smokeping_ctrl.mtr(host, validators.is_ipv6(host), cycles)
    if not ok:
        raise _http(502, "mtr_failed", str(body.get("error") or body.get("detail") or ""))
    return body


# --- Settings --------------------------------------------------------------


@app.get("/api/settings")
async def get_settings(_s: auth.Session = Depends(require_session)):
    return settings_mod.get_public_settings()


@app.put("/api/settings/app")
async def update_app_settings(
    body: AppSettingsBody, _s: auth.Session = Depends(require_session)
):
    updates = {}
    if body.language is not None:
        if body.language not in ("en", "es", "pt"):
            raise _http(400, "invalid_language")
        updates["language"] = body.language
    if body.timezone is not None:
        updates["timezone"] = body.timezone.strip()[:64]
    if updates:
        settings_mod.update_section("app", updates)
        poller.reschedule()
    return settings_mod.get_public_settings()["app"]


@app.put("/api/settings/telegram")
async def update_telegram_settings(
    body: TelegramSettingsBody, _s: auth.Session = Depends(require_session)
):
    updates: dict = {}
    # Secrets: a non-empty value replaces (encrypted); blank/None keeps current.
    if body.bot_token:
        updates["bot_token"] = settings_mod.encrypt(body.bot_token.strip())
    if body.chat_id:
        updates["chat_id"] = settings_mod.encrypt(body.chat_id.strip())
    if body.daily_report_enabled is not None:
        updates["daily_report_enabled"] = bool(body.daily_report_enabled)
    if body.daily_report_hour is not None:
        if not 0 <= body.daily_report_hour <= 23:
            raise _http(400, "invalid_hour")
        updates["daily_report_hour"] = body.daily_report_hour
    if body.daily_report_minute is not None:
        if not 0 <= body.daily_report_minute <= 59:
            raise _http(400, "invalid_minute")
        updates["daily_report_minute"] = body.daily_report_minute
    if updates:
        settings_mod.update_section("telegram", updates)
        poller.reschedule()
    return settings_mod.get_public_settings()["telegram"]


# --- Alerts ----------------------------------------------------------------


@app.post("/api/alerts/test")
async def test_alert(_s: auth.Session = Depends(require_session)):
    if not telegram_bot.is_configured():
        raise _http(400, "telegram_not_configured")
    ok, detail = telegram_bot.send_test(poller.msg("test"))
    if not ok:
        raise _http(502, "provider_error", detail)
    return {"ok": True}


@app.get("/api/alerts/status")
async def alerts_status(_s: auth.Session = Depends(require_session)):
    return poller.get_status()


# --- Reports ---------------------------------------------------------------


@app.post("/api/reports/daily/run")
def run_daily_report(_s: auth.Session = Depends(require_session)):
    # Sync route -> runs in the threadpool (the AI + Telegram calls block).
    ok, status = poller.trigger_daily_report_now()
    if not ok:
        raise _http(502, "report_failed", status)
    return {"ok": True, "status": status}


@app.get("/api/reports/history")
async def reports_history(_s: auth.Session = Depends(require_session)):
    return {"history": poller.get_history()}


# --- System ----------------------------------------------------------------


@app.post("/api/smokeping/reload")
def smokeping_reload(_s: auth.Session = Depends(require_session)):
    # Sync route -> threadpool (the reload restarts the service, ~seconds).
    ok, body = smokeping_ctrl.reload()
    if not ok:
        raise _http(502, "reload_failed", str(body.get("detail") or body.get("error") or ""))
    return {"ok": True, "last_reload_at": smokeping_ctrl.get_last_reload()}


# --- AI analysis -----------------------------------------------------------


def _ai_creds(provider: str | None, api_key: str | None, model: str | None):
    """Resolve provider/api_key/model from the request, falling back to
    the stored (encrypted) AI settings."""
    ai_cfg = settings_mod.load().get("ai", {})
    provider = provider or ai_cfg.get("provider") or "claude"
    key = api_key or settings_mod.decrypt(ai_cfg.get("api_key"))
    model = model or ai_cfg.get("model")
    return provider, key, model


@app.get("/api/models")
async def list_models(
    provider: str = "claude", api_key: str = "", _s: auth.Session = Depends(require_session)
):
    prov, key, _model = _ai_creds(provider, api_key or None, None)
    if not key:
        raise _http(400, "ai_not_configured")
    models = models_fetcher.fetch_models(prov, key)
    return {"provider": prov, "models": models}


@app.put("/api/settings/ai")
async def update_ai_settings(
    body: AiSettingsBody, _s: auth.Session = Depends(require_session)
):
    updates: dict = {}
    if body.provider is not None:
        if body.provider not in ("claude", "openai"):
            raise _http(400, "invalid_provider")
        updates["provider"] = body.provider
    if body.model is not None:
        updates["model"] = body.model.strip()[:100] or None
    if body.api_key:
        updates["api_key"] = settings_mod.encrypt(body.api_key.strip())
    if body.analysis_prompt is not None:
        # Empty string resets to the built-in default.
        updates["analysis_prompt"] = body.analysis_prompt.strip()[:4000] or None
    if updates:
        settings_mod.update_section("ai", updates)
    return settings_mod.get_public_settings()["ai"]


@app.post("/api/analyze")
async def analyze(body: AnalyzeBody, _s: auth.Session = Depends(require_session)):
    target = config_writer.get_target(body.target_id)
    if target is None:
        raise _http(404, "target_not_found")
    prov, key, model = _ai_creds(body.provider, body.api_key, body.model)
    if not key or not model:
        raise _http(400, "ai_not_configured")
    text = ai_analyzer.analyze_target(target, prov, key, model, body.range or "3h")
    return {"analysis": text}
