# syntax=docker/dockerfile:1
#
# smokeping-easy — frontend (nginx, non-root).
#
# Based on the official *unprivileged* nginx image: it already runs as uid 101
# and listens on 8080, so no root is ever used at runtime.
FROM nginxinc/nginx-unprivileged:1.31-alpine

# Our server block (security headers, rate limits, /api + /smokeping proxy).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static assets (no build step — plain HTML + CDN Alpine.js/Chart.js).
COPY src/ /usr/share/nginx/html/
