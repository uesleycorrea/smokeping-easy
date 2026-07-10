# syntax=docker/dockerfile:1
#
# smokeping-easy — Smokeping image
#
# Built on top of the official LinuxServer.io Smokeping image. We add:
#   * python3 + a tiny internal "reload API" (reload_server.py) so the backend
#     can validate/reload the config over the Docker network without needing
#     the Docker socket.
#   * our own self-contained main config (/etc/smokeping/config) that inlines
#     every static section and @includes only /config/Targets (the dynamic file
#     managed by the backend).
#   * a seed Targets file so a fresh /config volume boots with a valid config.
#
# The base image tag is PINNED (never :latest) for reproducible builds.
FROM lscr.io/linuxserver/smokeping:2.9.0-r0-ls176

# python3 for the stdlib reload/MTR server; mtr for on-demand path tracing.
RUN apk add --no-cache python3 mtr

# Internal reload API + our config.
COPY reload_server.py /usr/local/bin/reload_server.py
COPY config/config    /etc/smokeping/config
COPY config/Targets   /defaults/smoke-conf/Targets

# Register the reload API as an s6-overlay v3 supervised long-running service.
RUN set -eux; \
    mkdir -p /etc/s6-overlay/s6-rc.d/svc-reload/dependencies.d; \
    echo longrun > /etc/s6-overlay/s6-rc.d/svc-reload/type; \
    touch /etc/s6-overlay/s6-rc.d/svc-reload/dependencies.d/init-services; \
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/svc-reload; \
    chmod +x /usr/local/bin/reload_server.py

COPY wrapper.sh /etc/s6-overlay/s6-rc.d/svc-reload/run
RUN chmod +x /etc/s6-overlay/s6-rc.d/svc-reload/run
