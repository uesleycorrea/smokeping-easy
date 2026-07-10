<div align="center">

# 📡 smokeping-easy

**English** · [Español](README.es.md) · [Português](README.pt.md)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://github.com/uesleycorrea/smokeping-easy/releases)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/)

*Smokeping with a modern web UI, Telegram alerts and AI analysis — up in minutes with Docker Compose.*

</div>

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📡 smokeping-easy   Targets  AI Analysis  Settings  Graphs  About  🟢 │
├──────────────────────────────────────────────────────────────────────┤
│  Monitored targets                                    [ + Add target ]│
│                                                                        │
│  LABEL           HOST                LATENCY      LOSS      ACTIONS     │
│  ── Public DNS ─────────────────────────────────────────────────────  │
│  Google DNS      8.8.8.8             ▏20.4 ms▕    ▏0 %▕    Graph Edit ✕ │
│  Cloudflare v6   2606:4700:4700::11  ▏21.9 ms▕    ▏0 %▕    Graph Edit ✕ │
│  ── Routers ────────────────────────────────────────────────────────  │
│  Core Router     10.0.0.1            ▏ 1.2 ms▕    ▏0 %▕    Graph Edit ✕ │
│                                                                        │
│  Click a host → live MTR route.   Click Graph → latency & loss chart.  │
└──────────────────────────────────────────────────────────────────────┘
```

## 🌐 What is this?

ISPs and network operators need to watch **latency and packet loss** to many
hosts, and — when something breaks — understand **why**. Smokeping is the classic
tool for the measurements, but configuring it means editing text files by hand.

**smokeping-easy** wraps Smokeping in a clean, trilingual web UI where you add
targets, set alert thresholds, get Telegram notifications, trace routes with MTR
and ask an AI to analyse problems — **without ever touching a config file**.

Built for ISPs and network operators across Latin America (and everywhere else).

## ✨ Features

- 🌍 **Trilingual web UI** — English, Spanish and Portuguese, switchable live.
- 🎯 **Add targets from the UI** — no config files, ever. Organize them in groups.
- 🔔 **Telegram alerts** — per-target latency & loss thresholds, sent on breach.
- 🧊 **Configurable alert interval (cooldown)** per target — no spam when a
  problem persists.
- ✅ **Recovery alerts** — a message when a value returns to normal.
- 📅 **Automated daily report** via Telegram, written by AI.
- 🤖 **On-demand AI analysis** of a host, with a dynamic model selector
  (Claude / OpenAI).
- 🧠 **Model dropdown loaded from the real provider API** — nothing hardcoded.
- ✍️ **Editable AI prompt** — write it in your own language.
- 📈 **In-app latency & loss charts** (Chart.js) with selectable periods.
- 🛰️ **On-demand MTR** — click a host to trace the live route from the server.
- 🔐 **Password auth with brute-force protection** (bcrypt + server-side sessions).
- 🚦 **Rate limiting** on login and the AI APIs.
- 🌐 **Native dual-stack IPv4 / IPv6.**
- 🔧 **Configurable port** via `.env`.
- 🔒 **Secrets encrypted at rest** (Fernet / AES).
- 🛡️ **Optional TLS profile** with Traefik + Let's Encrypt.
- ℹ️ **About tab** with license and credits.

## 📋 Prerequisites

- **Docker Engine 24+**
- **Docker Compose v2+** (the `docker compose` plugin)
- A **free port** on the host (default: `3000`)
- *(For alerts)* a **Telegram bot** created via [@BotFather](https://t.me/BotFather)
- *(For AI analysis)* an **Anthropic or OpenAI API key**

That's it — no Python, Node or build tools required.

## 🚀 Install in 3 steps

**1. Clone**

```bash
git clone https://github.com/uesleycorrea/smokeping-easy
cd smokeping-easy
```

**2. Configure**

```bash
cp .env.example .env
# In most cases you only need to set HTTP_PORT (default 3000).
```

**3. Start**

```bash
docker compose up -d --build
```

Open **http://localhost:3000** and log in.

**Initial password** — if you left `ADMIN_PASSWORD` empty, one is generated on
first boot and printed to the logs:

```bash
docker compose logs backend | grep -i password
```

## 👣 First use (step by step)

1. Open the UI and **log in** with the initial password.
2. Go to **Settings → Change password** and set your own.
3. Go to **Targets** and add your first hosts.
4. *(Optional)* In **Settings → Telegram alerts**, configure the bot and set
   thresholds on your targets.
5. *(Optional)* In **Settings → AI provider**, paste an API key and load models.

## 💬 How to get your Telegram Chat ID

1. Talk to [@BotFather](https://t.me/BotFather), send `/newbot`, follow the
   prompts — you get a **bot token** like `123456:ABC-DEF…`.
2. Send any message to your new bot (or add it to a group and post a message).
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   read `chat.id` (group IDs start with `-100…`).

## ⚙️ `.env` configuration

| Variable | Default | Description |
|---|---|---|
| `HTTP_PORT` | `3000` | Web UI port on the host. Usually the only value to change. |
| `SMOKEPING_WEB_PORT` | `8081` | Port for the read-only native Smokeping graphs. |
| `PUID` / `PGID` | `1000` | User/group that owns the shared volumes. |
| `TZ` | `UTC` | Timezone (e.g. `America/Mexico_City`). |
| `ADMIN_PASSWORD` | *(empty)* | Initial admin password. Empty → auto-generated & logged. |
| `RELOAD_TOKEN` | *(empty)* | Token for the internal reload API (port 9000, never exposed). Optional. |
| `SESSION_TTL_MINUTES` | `120` | Session lifetime. |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed logins per IP before lockout. |
| `LOGIN_WINDOW_MINUTES` | `10` | Lockout window. |
| `LOG_LEVEL` | `INFO` | Log verbosity. Avoid `DEBUG` in production. |
| `DOMAIN` | — | *(TLS only)* your domain, e.g. `monitor.example.com`. |
| `ACME_EMAIL` | — | *(TLS only)* email for Let's Encrypt. |

## 🔒 TLS profile (production HTTPS)

Point a DNS record at your server, set `DOMAIN` and `ACME_EMAIL` in `.env`, then:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Traefik obtains and renews a free Let's Encrypt certificate, serves the app over
**HTTPS** (auto-redirect from HTTP) and marks the session cookie `Secure`.

## 🔄 Updating

```bash
git pull
docker compose up -d --build
```

Your data (targets, groups, settings, latency history) lives in Docker volumes
and is preserved across updates.

## 🗺️ Roadmap

**v1.0.0 — shipped**

- [x] Trilingual web UI (EN / ES / PT)
- [x] Target CRUD from the UI, organized in groups
- [x] Group management (create / rename keeps history / delete)
- [x] Telegram threshold alerts with per-target cooldown & recovery
- [x] Automated daily AI report
- [x] On-demand AI analysis with dynamic model selection (Claude / OpenAI)
- [x] Editable AI prompt
- [x] In-app latency & loss charts
- [x] On-demand MTR (server → target route)
- [x] bcrypt auth, brute-force protection, rate limiting
- [x] Dual-stack IPv4 / IPv6
- [x] Encrypted secrets at rest
- [x] Optional TLS profile (Traefik + Let's Encrypt)

## 🛡️ Security

Highlights: bcrypt password + server-side `HttpOnly`/`SameSite` sessions,
login brute-force protection, all input validated server-side, secrets
Fernet-encrypted at rest, the backend and reload API never exposed to the host,
non-root containers, and a strict Content-Security-Policy. See
[SECURITY.md](SECURITY.md) for the full model and how to report a vulnerability.

## 🤝 Contributing

Contributions are welcome — especially from the Latin American ISP community!
Open an [issue](https://github.com/uesleycorrea/smokeping-easy/issues) to report
a bug or suggest a feature, or send a
[pull request](https://github.com/uesleycorrea/smokeping-easy/pulls). Ideas from
network operators make this better for everyone.

## 👤 Author

**Uesley Correa**
[Telecom ISP Solutions](https://telecomisp.solutions) — *Soluciones para ISPs en
América Latina.*

## 📄 License

Licensed under the **GNU General Public License v3.0**. You may use, study,
modify and redistribute it; derivative versions must stay open source under the
same license. See [LICENSE](LICENSE) or
[gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html).

Built on [Smokeping](https://oss.oetiker.ch/smokeping/),
[FastAPI](https://fastapi.tiangolo.com/), [Alpine.js](https://alpinejs.dev/),
[Chart.js](https://www.chartjs.org/), [Docker](https://www.docker.com/),
[nginx](https://nginx.org/) and the
[LinuxServer.io](https://www.linuxserver.io/) Smokeping image.
