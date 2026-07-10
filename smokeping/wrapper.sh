#!/usr/bin/with-contenv bash
# shellcheck shell=bash
#
# s6-overlay v3 longrun service that runs the internal Smokeping reload API.
#
# It runs as root (not abc) because reloading is done by cleanly restarting the
# supervised smokeping service via `s6-svc`, which requires access to the s6
# supervise control fifo (root-owned). This is an acceptable, tightly-scoped
# exception: the reload API listens on an INTERNAL port only (RELOAD_PORT,
# default 9731), is never published to the host, is protected by RELOAD_TOKEN,
# and only ever validates the config and restarts one service.

# --- Apache CGI handler --------------------------------------------------
# Make the Smokeping web CGI run under mod_cgi (cgi-script: a fresh process per
# request) instead of mod_fcgid, whose persistent worker CACHES the parsed
# config in memory and hides newly-added targets from the native web UI until
# it is recycled. The effective handler lives in site-confs/smokeping.conf
# (inside the <Directory> block, which overrides any global handler in
# httpd.conf). This runs at every start and is idempotent, so it also fixes
# pre-existing config volumes.
SP_SITE_CONF=/config/site-confs/smokeping.conf
if [ -f "$SP_SITE_CONF" ] && grep -q 'fcgid-script' "$SP_SITE_CONF"; then
    sed -i 's/AddHandler fcgid-script \.cgi/AddHandler cgi-script .cgi/' "$SP_SITE_CONF"
    # Apache may already have started with the old handler; restart it so the
    # change takes effect immediately.
    s6-svc -r /run/service/svc-apache 2>/dev/null || true
fi

exec python3 /usr/local/bin/reload_server.py
