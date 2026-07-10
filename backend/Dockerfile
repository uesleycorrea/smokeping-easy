# syntax=docker/dockerfile:1
#
# smokeping-easy — backend (FastAPI + uvicorn)
#
# Runs as a NON-root user whose UID/GID match PUID/PGID so the backend can write
# the shared Targets file on the smokeping-config volume. Reads RRD data through
# the `rrdtool` CLI (installed here; the /data volume is mounted read-only).
FROM python:3.14-slim

# Build-time UID/GID so the container user matches the shared-volume owner.
ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_DATA_DIR=/app/data

# rrdtool CLI (read RRD files) + ca-certificates (outbound HTTPS to Telegram/AI).
RUN apt-get update \
    && apt-get install -y --no-install-recommends rrdtool ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root application user.
RUN groupadd -g "${APP_GID}" app \
    && useradd -u "${APP_UID}" -g "${APP_GID}" -M -s /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data dir for settings.json / secret.key / state files. Owned by the app user.
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

# tini as PID 1 for correct signal handling / zombie reaping.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
