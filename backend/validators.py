"""Centralised input validation.

SECURITY: this module is the single source of truth for validating anything
that comes from the API. In particular:

  * ``validate_host()`` MUST be called on every ``host`` value before it is
    written to the Smokeping config or used to build an RRD path.
  * ``safe_rrd_path()`` MUST be used to build every RRD file path — never
    concatenate user input into a filesystem path directly.

Error messages carry a stable ``code`` so the frontend can translate them via
i18n (the message text here is a safe English fallback, never raw user input).
"""
from __future__ import annotations

import ipaddress
import os
import re
import uuid
from typing import Any, Optional

# --- Errors ----------------------------------------------------------------


class ValidationError(ValueError):
    """User input failed validation. ``code`` is a stable i18n key."""

    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


# --- Constants -------------------------------------------------------------

MAX_HOST_LEN = 253
MAX_LABEL_LEN = 100
MAX_GROUP_LEN = 60

MIN_PROBE_INTERVAL = 10
MAX_PROBE_INTERVAL = 3600
DEFAULT_PROBE_INTERVAL = 60

MIN_COOLDOWN = 1
MAX_COOLDOWN = 1440
DEFAULT_COOLDOWN = 30

# Strict RFC-1123-ish hostname: labels of alnum/hyphen, no leading/trailing
# hyphen, total <= 253. This is intentionally strict: anything not matching
# (and not a valid IP literal) is rejected, which by construction excludes all
# shell metacharacters, whitespace and path separators.
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)

_SLUG_STRIP_RE = re.compile(r"[^A-Za-z0-9]+")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


# --- Host validation -------------------------------------------------------


def is_ipv6(host: str) -> bool:
    """True if ``host`` is a (already validated) IPv6 literal."""
    try:
        return isinstance(ipaddress.ip_address(host), ipaddress.IPv6Address)
    except ValueError:
        return False


def validate_host(host: Any) -> str:
    """Validate and normalise a monitored host (IPv4, IPv6 or hostname).

    Returns the normalised host string. Raises :class:`ValidationError`.
    """
    if not isinstance(host, str):
        raise ValidationError("Host must be text", "host_type")
    host = host.strip()
    if not host:
        raise ValidationError("Host is required", "host_required")
    if len(host) > MAX_HOST_LEN:
        raise ValidationError("Host is too long", "host_too_long")

    # Bracketed IPv6, e.g. [2001:db8::1]
    if host.startswith("[") and host.endswith("]"):
        inner = host[1:-1]
        try:
            return str(ipaddress.IPv6Address(inner))
        except ValueError as exc:
            raise ValidationError("Invalid IPv6 address", "host_invalid") from exc

    # Bare IP literal (v4 or v6)
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass

    # Hostname
    if _HOSTNAME_RE.match(host):
        return host.lower()

    raise ValidationError("Invalid host or IP address", "host_invalid")


def probe_for_host(host: str) -> str:
    """Return the Smokeping probe name appropriate for ``host``."""
    return "FPing6" if is_ipv6(host) else "FPing"


# --- Slugs & paths ---------------------------------------------------------


def slugify(text: Optional[str], fallback: str = "item") -> str:
    """Return a Smokeping/filesystem-safe id: ``[A-Za-z0-9_]`` only."""
    slug = _SLUG_STRIP_RE.sub("_", (text or "").strip()).strip("_")
    slug = slug[:40]
    return slug or fallback


def group_slug(group: Optional[str]) -> str:
    """Deterministic Smokeping section id for a target group."""
    return slugify(group, "default")


def target_section_id(target_id: str) -> str:
    """Deterministic, filesystem-safe Smokeping section id for a target.

    Derived from the target UUID so it is stable across edits and never
    collides. The ``t`` prefix guarantees it starts with a letter.
    """
    hexid = re.sub(r"[^0-9a-fA-F]", "", str(target_id))[:12] or "0"
    return f"t{hexid}"


def safe_rrd_path(data_dir: str, *segments: str) -> str:
    """Build an RRD path under ``data_dir``, refusing any path traversal.

    Every segment must be a plain name (no separators, no ``..``). The final
    resolved path must stay inside ``data_dir``.
    """
    base = os.path.realpath(data_dir)
    for seg in segments:
        if not isinstance(seg, str) or not seg:
            raise ValidationError("Invalid path segment", "path_segment")
        if seg in (".", "..") or "/" in seg or "\\" in seg or "\x00" in seg:
            raise ValidationError("Invalid path segment", "path_segment")
    candidate = os.path.realpath(os.path.join(base, *segments))
    if candidate != base and not candidate.startswith(base + os.sep):
        raise ValidationError("Path traversal detected", "path_traversal")
    return candidate


# --- Field validation ------------------------------------------------------


def _clean_text(value: Any, field: str, max_len: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text", f"{field}_type")
    value = _CONTROL_RE.sub("", value).strip()
    if required and not value:
        raise ValidationError(f"{field} is required", f"{field}_required")
    if len(value) > max_len:
        raise ValidationError(f"{field} is too long", f"{field}_too_long")
    return value


def _validate_int(value: Any, field: str, lo: int, hi: int, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number", f"{field}_type") from exc
    if ivalue < lo or ivalue > hi:
        raise ValidationError(f"{field} out of range", f"{field}_range")
    return ivalue


def _validate_optional_number(
    value: Any, field: str, lo: float, hi: float
) -> Optional[float]:
    """Optional threshold: ``None``/empty means 'no alert for this metric'."""
    if value is None or value == "":
        return None
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number", f"{field}_type") from exc
    if fvalue < lo or fvalue > hi:
        raise ValidationError(f"{field} out of range", f"{field}_range")
    return fvalue


def validate_target(data: Any, target_id: Optional[str] = None) -> dict:
    """Validate a target payload from the API.

    Returns a normalised dict of the *editable* fields (host, label, group,
    probe_interval, thresholds, cooldown). Id/timestamps are managed by the
    caller. Raises :class:`ValidationError`.
    """
    if not isinstance(data, dict):
        raise ValidationError("Invalid payload", "payload_type")

    host = validate_host(data.get("host"))
    label = _clean_text(data.get("label") or data.get("host"), "label", MAX_LABEL_LEN)
    group = _clean_text(data.get("group") or "Default", "group", MAX_GROUP_LEN)
    probe_interval = _validate_int(
        data.get("probe_interval"), "probe_interval",
        MIN_PROBE_INTERVAL, MAX_PROBE_INTERVAL, DEFAULT_PROBE_INTERVAL,
    )
    latency_threshold_ms = _validate_optional_number(
        data.get("latency_threshold_ms"), "latency_threshold_ms", 0, 600000
    )
    loss_threshold_pct = _validate_optional_number(
        data.get("loss_threshold_pct"), "loss_threshold_pct", 0, 100
    )
    cooldown = _validate_int(
        data.get("alert_cooldown_minutes"), "alert_cooldown_minutes",
        MIN_COOLDOWN, MAX_COOLDOWN, DEFAULT_COOLDOWN,
    )

    return {
        "host": host,
        "label": label,
        "group": group,
        "probe_interval": probe_interval,
        "latency_threshold_ms": latency_threshold_ms,
        "loss_threshold_pct": loss_threshold_pct,
        "alert_cooldown_minutes": cooldown,
    }


def new_uuid() -> str:
    return str(uuid.uuid4())
