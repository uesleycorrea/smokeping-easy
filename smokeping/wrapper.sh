#!/usr/bin/with-contenv bash
# shellcheck shell=bash
#
# s6-overlay v3 longrun service that runs the internal Smokeping reload API.
#
# It runs as root (not abc) because reloading is done by cleanly restarting the
# supervised smokeping service via `s6-svc`, which requires access to the s6
# supervise control fifo (root-owned). This is an acceptable, tightly-scoped
# exception: the reload API listens on an INTERNAL port only (RELOAD_PORT,
# default 9000), is never published to the host, is protected by RELOAD_TOKEN,
# and only ever validates the config and restarts one service.

exec python3 /usr/local/bin/reload_server.py
