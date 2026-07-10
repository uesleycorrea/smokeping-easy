"""Read latency / packet-loss data from Smokeping RRD files.

Uses the ``rrdtool`` CLI (installed in the backend image) against the shared
``/data`` volume (mounted read-only). Every path is built with
``validators.safe_rrd_path`` — never by string concatenation — to prevent path
traversal from a crafted group/target.

Smokeping RRD data sources (confirmed against the running image):
    loss   : GAUGE, number of lost pings out of ``pings`` (default 20)
    median : GAUGE, median round-trip time in SECONDS
So: latency_ms = median * 1000 ; loss_pct = loss / pings * 100
"""
from __future__ import annotations

import logging
import math
import os
import subprocess
from typing import Optional

import config_writer
import validators

log = logging.getLogger("smokeping_easy.rrd")

DATA_DIR = os.environ.get("SMOKEPING_DATA_DIR", "/data")
PINGS = int(os.environ.get("SMOKEPING_PINGS", "20"))
RRDTOOL = os.environ.get("RRDTOOL_BIN", "rrdtool")


def rrd_path_for(target: dict) -> str:
    """Safe absolute RRD path for a target (raises on traversal)."""
    gslug, filename = config_writer.rrd_relative_segments(target)
    return validators.safe_rrd_path(DATA_DIR, gslug, filename)


def _run_fetch(path: str, start: str, end: str = "now", cf: str = "AVERAGE"):
    proc = subprocess.run(
        [RRDTOOL, "fetch", path, cf, "--start", start, "--end", end],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "rrdtool fetch failed")
    return proc.stdout


def _parse_fetch(output: str) -> tuple[list[str], list[tuple[int, list[float]]]]:
    """Return (ds_names, [(timestamp, [values...]), ...])."""
    lines = [ln for ln in output.splitlines() if ln.strip()]
    if not lines:
        return [], []
    ds_names = lines[0].split()
    rows: list[tuple[int, list[float]]] = []
    for line in lines[1:]:
        if ":" not in line:
            continue
        ts_str, _, rest = line.partition(":")
        try:
            ts = int(ts_str.strip())
        except ValueError:
            continue
        values = []
        for tok in rest.split():
            try:
                values.append(float(tok))
            except ValueError:
                values.append(math.nan)
        rows.append((ts, values))
    return ds_names, rows


def _extract(ds_names, values) -> dict:
    idx = {name: i for i, name in enumerate(ds_names)}
    median = values[idx["median"]] if "median" in idx and idx["median"] < len(values) else math.nan
    loss = values[idx["loss"]] if "loss" in idx and idx["loss"] < len(values) else math.nan
    latency_ms = None if math.isnan(median) else round(median * 1000.0, 3)
    loss_pct = None if math.isnan(loss) else round((loss / PINGS) * 100.0, 2)
    return {"avg_latency_ms": latency_ms, "loss_pct": loss_pct}


def get_latest(target: dict, lookback: str = "-15m") -> Optional[dict]:
    """Return the most recent non-empty sample, or None if no data yet.

    ``{"timestamp": int, "avg_latency_ms": float|None, "loss_pct": float|None}``
    """
    try:
        path = rrd_path_for(target)
    except validators.ValidationError:
        log.warning("Refusing unsafe RRD path for target %s", target.get("id"))
        return None
    if not os.path.exists(path):
        return None
    try:
        out = _run_fetch(path, start=lookback)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        log.warning("rrdtool fetch failed for %s: %s", path, exc)
        return None
    ds_names, rows = _parse_fetch(out)
    # Walk backwards to the last row that actually has a median value.
    for ts, values in reversed(rows):
        data = _extract(ds_names, values)
        if data["avg_latency_ms"] is not None or data["loss_pct"] is not None:
            data["timestamp"] = ts
            return data
    return None


def get_series(target: dict, start: str = "-3h", end: str = "now") -> dict:
    """Return a time series suitable for charting.

    ``{"points": [{"t": ts, "latency_ms": float|None, "loss_pct": float|None}]}``
    """
    result = {"points": []}
    try:
        path = rrd_path_for(target)
    except validators.ValidationError:
        log.warning("Refusing unsafe RRD path for target %s", target.get("id"))
        return result
    if not os.path.exists(path):
        return result
    try:
        out = _run_fetch(path, start=start, end=end)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        log.warning("rrdtool fetch failed for %s: %s", path, exc)
        return result
    ds_names, rows = _parse_fetch(out)
    for ts, values in rows:
        data = _extract(ds_names, values)
        result["points"].append(
            {"t": ts, "latency_ms": data["avg_latency_ms"], "loss_pct": data["loss_pct"]}
        )
    return result
