#!/usr/bin/env python3
"""Internal Smokeping reload API.

Runs *inside* the Smokeping container and listens on an INTERNAL-only port
(default 9000, never mapped to the host). The backend calls it over the Docker
network to validate and reload the Smokeping configuration after the Targets
file changes.

Only the Python standard library is used so the Smokeping image only needs
`python3` installed (no pip).
"""
import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RELOAD_TOKEN = os.environ.get("RELOAD_TOKEN", "")
CONFIG_PATH = os.environ.get("SMOKEPING_CONFIG_FILE", "/etc/smokeping/config")
LISTEN_PORT = int(os.environ.get("RELOAD_PORT", "9000"))
SMOKEPING_BIN = os.environ.get("SMOKEPING_BIN", "/usr/sbin/smokeping")
SMOKEPING_SVC = os.environ.get("SMOKEPING_SVC", "/run/service/svc-smokeping")
MTR_BIN = os.environ.get("MTR_BIN", "/usr/sbin/mtr")

# Bound how many MTR runs can happen at once (each is a root subprocess).
_mtr_sem = threading.Semaphore(int(os.environ.get("MTR_MAX_CONCURRENT", "2")))
# Belt-and-suspenders host guard (subprocess uses an arg list + `--`, so shell
# injection is impossible; this only blocks obviously bogus values).
_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-\[\]]{1,253}$")


def run_smokeping(extra_args):
    """Run the smokeping binary with the configured config file."""
    return subprocess.run(
        [SMOKEPING_BIN, f"--config={CONFIG_PATH}", *extra_args],
        capture_output=True,
        text=True,
        timeout=60,
    )


_version_cache = None


def smokeping_version():
    """Return the Smokeping version as a readable dotted string (e.g. 2.9.0).

    ``smokeping --version`` prints a Perl-style version like ``2.009000``.
    """
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        out = subprocess.run([SMOKEPING_BIN, "--version"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        out = ""
    ver = out
    m = re.match(r"^(\d+)\.(\d+)$", out)
    if m:
        major, frac = m.group(1), m.group(2)
        while len(frac) % 3 != 0:
            frac += "0"
        parts = [str(int(frac[i:i + 3])) for i in range(0, len(frac), 3)]
        ver = major + "." + ".".join(parts)
    _version_cache = ver
    return ver


def smokeping_running():
    """True if the Smokeping master daemon process is alive."""
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as fh:
                cmd = fh.read()
        except OSError:
            continue
        if b"smokeping" in cmd and b"--nodaemon" in cmd:
            return True
    return False


def reload_master():
    """Reload the Smokeping configuration by restarting its s6 service.

    The LinuxServer image runs smokeping with ``--nodaemon`` under s6, and its
    SIGHUP handling is unreliable (it can exit rather than reload in place). The
    robust approach is to let the s6 supervisor cleanly restart the service:
    ``s6-svc -u`` guarantees the service is wanted-up (defeating any stale
    ``down`` state) and ``s6-svc -r`` restarts it so the new config is loaded.
    Requires root, which is why the reload API runs as root (internal-only,
    token-protected). Returns (ok, detail).
    """
    try:
        # Ensure the service is wanted-up, then restart it.
        up = subprocess.run(["s6-svc", "-u", SMOKEPING_SVC],
                            capture_output=True, text=True, timeout=15)
        res = subprocess.run(["s6-svc", "-r", SMOKEPING_SVC],
                             capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f"s6-svc error: {exc}"
    if res.returncode != 0:
        return False, (res.stderr or res.stdout or "s6-svc -r failed").strip()
    _ = up  # (up failures are non-fatal; the restart is what matters)
    return True, "smokeping service restarted"


def run_mtr(host, ipv6=False, cycles=5):
    """Run mtr --json against host and return (ok, payload).

    host is validated and passed after `--` so it can never be treated as an
    mtr option or shell command. cycles is clamped 1..10.
    """
    if not isinstance(host, str) or not _HOST_RE.match(host):
        return False, {"error": "invalid_host"}
    try:
        cycles = max(1, min(10, int(cycles)))
    except (TypeError, ValueError):
        cycles = 5

    cmd = [MTR_BIN, "--json", "-c", str(cycles)]
    if ipv6:
        cmd.append("-6")
    cmd += ["--", host]

    acquired = _mtr_sem.acquire(timeout=5)
    if not acquired:
        return False, {"error": "busy"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=cycles * 2 + 15)
    except subprocess.TimeoutExpired:
        return False, {"error": "timeout"}
    except FileNotFoundError:
        return False, {"error": "mtr_not_installed"}
    finally:
        _mtr_sem.release()

    if proc.returncode != 0:
        return False, {"error": "mtr_failed", "detail": (proc.stderr or "").strip()[:300]}
    try:
        report = json.loads(proc.stdout)["report"]
    except (ValueError, KeyError):
        return False, {"error": "bad_output"}

    hops = []
    for h in report.get("hubs", []):
        hops.append({
            "hop": h.get("count"),
            "host": h.get("host", "???"),
            "loss": h.get("Loss%"),
            "sent": h.get("Snt"),
            "last": h.get("Last"),
            "avg": h.get("Avg"),
            "best": h.get("Best"),
            "worst": h.get("Wrst"),
            "stdev": h.get("StDev"),
        })
    meta = report.get("mtr", {})
    return True, {"src": meta.get("src"), "dst": meta.get("dst"),
                  "cycles": cycles, "hops": hops}


class Handler(BaseHTTPRequestHandler):
    server_version = "smokeping-reload/1.0"

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        # Defense in depth: even though the port is internal-only, require a
        # shared token if one is configured.
        if not RELOAD_TOKEN:
            return True
        return self.headers.get("X-Reload-Token", "") == RELOAD_TOKEN

    def do_GET(self):
        path = self.path.rstrip("/")
        if path in ("/health", "/healthz"):
            return self._send(200, {"status": "ok"})
        if path == "/status":
            return self._send(200, {
                "running": smokeping_running(),
                "version": smokeping_version(),
            })
        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        path = self.path.rstrip("/") or "/"
        try:
            if path == "/mtr":
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    body = {}
                ok, payload = run_mtr(
                    body.get("host", ""),
                    bool(body.get("ipv6", False)),
                    body.get("cycles", 5),
                )
                return self._send(200 if ok else 400, payload)
            if path == "/check":
                chk = run_smokeping(["--check"])
                ok = chk.returncode == 0
                detail = (chk.stderr or chk.stdout or "").strip()
                return self._send(200 if ok else 422, {"valid": ok, "detail": detail})
            if path == "/reload":
                chk = run_smokeping(["--check"])
                if chk.returncode != 0:
                    detail = (chk.stderr or chk.stdout or "").strip()
                    return self._send(422, {"error": "invalid_config", "detail": detail})
                ok, detail = reload_master()
                if not ok:
                    return self._send(500, {"error": "reload_failed", "detail": detail})
                return self._send(200, {"status": "reloaded", "detail": detail})
        except subprocess.TimeoutExpired:
            return self._send(504, {"error": "timeout"})
        except Exception as exc:  # noqa: BLE001 - report any failure as 500
            return self._send(500, {"error": "internal", "detail": str(exc)})
        return self._send(404, {"error": "not_found"})

    def log_message(self, *args):  # silence default stderr access log
        return


def main():
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    print(f"[reload_server] listening on :{LISTEN_PORT} (config={CONFIG_PATH})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
