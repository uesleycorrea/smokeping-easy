<h1 align="center">📡 smokeping-easy</h1>

<p align="center">
  <b>Smokeping + a modern, secure, trilingual web UI — up and running in 5 minutes with Docker Compose.</b><br>
  <i>Smokeping + una interfaz web moderna, segura y trilingüe — funcionando en 5 minutos con Docker Compose.</i><br>
  <i>Smokeping + uma interface web moderna, segura e trilíngue — no ar em 5 minutos com Docker Compose.</i>
</p>

<p align="center">
  🌐 English · Español · Português &nbsp;|&nbsp; 🔔 Telegram alerts &nbsp;|&nbsp; 🤖 AI analysis &nbsp;|&nbsp; 🔒 Secure by default &nbsp;|&nbsp; 🌍 IPv4 + IPv6
</p>

---

**What is this?** ISPs and network operators need to watch latency and packet
loss to many hosts. Smokeping is the classic tool for that, but configuring it
means editing text files. **smokeping-easy** wraps Smokeping in a clean web UI
where you add targets, set alert thresholds, get Telegram notifications, and ask
an AI to analyse problems — without ever touching a config file.

| | |
|---|---|
| **Latency & loss graphs** | Real RRD data, per target, in-app charts + native Smokeping graphs |
| **Telegram alerts** | Threshold breach + recovery messages, per-target cooldown (no spam) |
| **AI analysis** | On-demand host analysis and an optional daily report (Claude or OpenAI) |
| **Trilingual** | Full EN / ES / PT, switch language live |
| **Secure** | bcrypt login, encrypted secrets, rate limiting, non-root containers, CSP |
| **Dual-stack** | Works over IPv4 and IPv6 |

---

# 🇬🇧 English

## Requirements
- A Linux server with **Docker** and the **Docker Compose plugin** installed.
  (Install: <https://docs.docker.com/engine/install/> — the Compose plugin is
  included with modern Docker.)
- That's it. No Python, no Node, no build tools.

## Setup in 3 steps

```bash
# 1) Get the code
git clone https://github.com/YOUR-USER/smokeping-easy.git
cd smokeping-easy

# 2) Create your .env with strong random secrets
cp .env.example .env
# Generate secrets and put them in .env (edit the file, or run these):
sed -i "s|^RELOAD_TOKEN=.*|RELOAD_TOKEN=$(openssl rand -hex 32)|" .env
sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(openssl rand -hex 12)|" .env
# (Recommended) set your timezone, e.g. America/Mexico_City:
#   nano .env

# 3) Start everything
docker compose up -d
```

Now open **`http://YOUR-SERVER-IP:8080`** and log in with the `ADMIN_PASSWORD`
from your `.env`. Change it immediately under **Settings → Change password**.

> 💡 See your admin password: `grep ADMIN_PASSWORD .env`

## First things to do
1. **Add targets** (Targets tab): host or IP, a label, optional thresholds.
2. **Telegram alerts** (Alerts tab): paste your bot token and chat id, click
   *Send test message*. Set per-target latency/loss thresholds on each target.
3. **AI analysis** (AI Analysis tab): choose Claude or OpenAI, paste an API key,
   *Load models*, pick one, and analyse a host.

### How do I get a Telegram bot token & chat id?
1. In Telegram, talk to **@BotFather**, send `/newbot`, follow the prompts — it
   gives you a **bot token** like `123456:ABC-DEF...`.
2. Add your new bot to a group (or DM it), send it any message.
3. Get the **chat id**: open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and read
   `chat.id` (groups start with `-100...`).

## Enable HTTPS (optional but recommended)
Point a DNS record at your server, set `DOMAIN` and `ACME_EMAIL` in `.env`, then:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Traefik gets a free Let's Encrypt certificate and serves the app on **HTTPS**
(with automatic HTTP→HTTPS redirect). The session cookie becomes `Secure`.

## Everyday commands
```bash
docker compose ps                 # status
docker compose logs -f backend    # follow backend logs
docker compose down               # stop (keeps data volumes)
docker compose up -d --build      # apply updates
```

## Ports
| Port | Service | Exposed to host? |
|---|---|---|
| `8080` | Web UI (nginx) | ✅ yes (`HTTP_PORT`) |
| `8081` | Native Smokeping graphs | ✅ yes (`SMOKEPING_WEB_PORT`, optional) |
| `8000` | Backend API | ❌ internal only |
| `9000` | Smokeping reload API | ❌ internal only |

## Troubleshooting
- **Port already in use** → change `HTTP_PORT` in `.env` and `docker compose up -d`.
- **"No data yet" on a target** → Smokeping needs ~1–2 minutes to gather the
  first samples after you add a target.
- **Not in a git repo?** No problem — download the ZIP from GitHub instead of
  `git clone`.
- **Reset everything (deletes data):** `docker compose down -v`.

---

# 🇪🇸 Español

## Requisitos
- Un servidor Linux con **Docker** y el **plugin de Docker Compose** instalados
  (<https://docs.docker.com/engine/install/>). Nada más: sin Python, sin Node.

## Instalación en 3 pasos

```bash
# 1) Obtener el código
git clone https://github.com/TU-USUARIO/smokeping-easy.git
cd smokeping-easy

# 2) Crear tu .env con secretos aleatorios fuertes
cp .env.example .env
sed -i "s|^RELOAD_TOKEN=.*|RELOAD_TOKEN=$(openssl rand -hex 32)|" .env
sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(openssl rand -hex 12)|" .env
# (Recomendado) define tu zona horaria, p. ej. America/Mexico_City:  nano .env

# 3) Iniciar todo
docker compose up -d
```

Abre **`http://IP-DE-TU-SERVIDOR:8080`** e inicia sesión con el `ADMIN_PASSWORD`
de tu `.env`. Cámbialo enseguida en **Ajustes → Cambiar contraseña**.

> 💡 Ver tu contraseña: `grep ADMIN_PASSWORD .env`

## Primeros pasos
1. **Agrega objetivos** (pestaña Objetivos): host o IP, etiqueta, umbrales
   opcionales de latencia y pérdida.
2. **Alertas de Telegram** (pestaña Alertas): pega el token del bot y el chat id,
   pulsa *Enviar mensaje de prueba*.
3. **Análisis con IA** (pestaña Análisis IA): elige Claude u OpenAI, pega tu
   clave API, *Cargar modelos*, elige uno y analiza un host.

### ¿Cómo obtener el token del bot y el chat id de Telegram?
1. En Telegram, habla con **@BotFather**, envía `/newbot` y sigue los pasos:
   te dará un **token** como `123456:ABC-DEF...`.
2. Agrega el bot a un grupo (o escríbele) y envíale un mensaje.
3. Obtén el **chat id** abriendo
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y leyendo `chat.id`
   (los grupos empiezan con `-100...`).

## Activar HTTPS (opcional, recomendado)
Apunta un registro DNS a tu servidor, define `DOMAIN` y `ACME_EMAIL` en `.env`:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Traefik obtiene un certificado gratuito de Let's Encrypt y sirve la app por
**HTTPS** con redirección automática.

## Comandos útiles
```bash
docker compose ps                 # estado
docker compose logs -f backend    # ver logs del backend
docker compose down               # detener (conserva los datos)
docker compose up -d --build      # aplicar actualizaciones
```

## Solución de problemas
- **Puerto en uso** → cambia `HTTP_PORT` en `.env` y `docker compose up -d`.
- **"Sin datos aún"** → Smokeping tarda ~1–2 minutos en recolectar las primeras
  muestras tras agregar un objetivo.
- **Reiniciar todo (borra datos):** `docker compose down -v`.

---

# 🇧🇷 Português

## Requisitos
- Um servidor Linux com **Docker** e o **plugin do Docker Compose** instalados
  (<https://docs.docker.com/engine/install/>). Só isso: sem Python, sem Node.

## Instalação em 3 passos

```bash
# 1) Baixar o código
git clone https://github.com/SEU-USUARIO/smokeping-easy.git
cd smokeping-easy

# 2) Criar seu .env com segredos aleatórios fortes
cp .env.example .env
sed -i "s|^RELOAD_TOKEN=.*|RELOAD_TOKEN=$(openssl rand -hex 32)|" .env
sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(openssl rand -hex 12)|" .env
# (Recomendado) defina seu fuso horário, ex.: America/Sao_Paulo:  nano .env

# 3) Subir tudo
docker compose up -d
```

Abra **`http://IP-DO-SEU-SERVIDOR:8080`** e entre com o `ADMIN_PASSWORD` do seu
`.env`. Troque-o imediatamente em **Configurações → Alterar senha**.

> 💡 Ver sua senha: `grep ADMIN_PASSWORD .env`

## Primeiros passos
1. **Adicione alvos** (aba Alvos): host ou IP, um rótulo, limites opcionais de
   latência e perda.
2. **Alertas do Telegram** (aba Alertas): cole o token do bot e o chat id,
   clique em *Enviar mensagem de teste*.
3. **Análise com IA** (aba Análise IA): escolha Claude ou OpenAI, cole uma chave
   de API, *Carregar modelos*, selecione um e analise um host.

### Como obter o token do bot e o chat id do Telegram?
1. No Telegram, fale com o **@BotFather**, envie `/newbot` e siga os passos —
   ele fornece um **token** como `123456:ABC-DEF...`.
2. Adicione o bot a um grupo (ou mande DM) e envie qualquer mensagem.
3. Obtenha o **chat id** abrindo
   `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` e lendo `chat.id`
   (grupos começam com `-100...`).

## Ativar HTTPS (opcional, recomendado)
Aponte um registro DNS para o servidor, defina `DOMAIN` e `ACME_EMAIL` no `.env`:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

O Traefik obtém um certificado gratuito do Let's Encrypt e serve o app via
**HTTPS**, com redirecionamento automático.

## Comandos do dia a dia
```bash
docker compose ps                 # status
docker compose logs -f backend    # acompanhar logs do backend
docker compose down               # parar (mantém os dados)
docker compose up -d --build      # aplicar atualizações
```

## Solução de problemas
- **Porta em uso** → altere `HTTP_PORT` no `.env` e `docker compose up -d`.
- **"Sem dados ainda"** → o Smokeping leva ~1–2 minutos para coletar as
  primeiras amostras após você adicionar um alvo.
- **Resetar tudo (apaga os dados):** `docker compose down -v`.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
   Browser  ─────►  │  nginx (frontend)  :8080                     │
   (IPv4/IPv6)      │   • static SPA (Alpine.js + Chart.js, CDN)   │
                    │   • /api      → backend                      │
                    │   • /smokeping → smokeping (native graphs)   │
                    └───────┬──────────────────────┬──────────────┘
                            │ /api                  │ /smokeping
                    ┌───────▼─────────┐     ┌───────▼──────────────┐
                    │ backend (FastAPI)│     │ smokeping (LSIO)     │
                    │  • auth, targets │     │  • fping IPv4/IPv6   │
                    │  • poller (alerts)│◄───┤  • RRD data (/data)  │
                    │  • AI analysis   │     │  • reload API :9000  │
                    │  • writes Targets├────►│    (internal only)   │
                    └──────────────────┘     └──────────────────────┘
   Only nginx (and optionally the native Smokeping graphs) is published to the host.
```

- **Smokeping**: `lscr.io/linuxserver/smokeping` (pinned) + a tiny internal
  reload API. Probes hosts, writes RRD data.
- **Backend**: FastAPI + APScheduler. Validates input, writes the Smokeping
  `Targets` file, reads RRD, runs the alert poller and AI features.
- **Frontend**: static HTML + Alpine.js + Chart.js (no build step), served by
  nginx which also proxies the API.

See [SECURITY.md](SECURITY.md) for the full security model.

## License

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

smokeping-easy is free software licensed under the **GNU General Public License
v3.0**. You may use, study, modify and redistribute it; derivative versions must
stay open source under the same license. See the [LICENSE](LICENSE) file for the
full text, or the [friendly summary](https://www.gnu.org/licenses/gpl-3.0.html).

## Author

Created by **Uesley Correa** — [Telecom ISP Solutions](https://telecomisp.solutions)
· *Consulting and training for ISPs across Latin America.*

## Credits

Built on top of excellent open-source projects:

- [Smokeping](https://oss.oetiker.ch/smokeping/) — latency measurement & RRD graphing
- [FastAPI](https://fastapi.tiangolo.com/) — the Python backend framework
- [Alpine.js](https://alpinejs.dev/) — lightweight frontend reactivity
- [Chart.js](https://www.chartjs.org/) — in-app latency & loss charts
- [Docker](https://www.docker.com/) — packaging & orchestration
- [nginx](https://nginx.org/) — static serving & reverse proxy
- [LinuxServer.io](https://www.linuxserver.io/) — the base Smokeping image

Thanks to the ISP and network-operator community — contributions welcome!
