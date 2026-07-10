<div align="center">

# 📡 smokeping-easy

[English](README.md) · **Español** · [Português](README.pt.md)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Version](https://img.shields.io/badge/version-1.1.0-brightgreen.svg)](https://github.com/uesleycorrea/smokeping-easy/releases)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/)

*Smokeping con una interfaz web moderna, alertas de Telegram y análisis con IA — funcionando en minutos con Docker Compose.*

</div>

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📡 smokeping-easy   Destinos  Análisis IA  Ajustes  Gráficas  Acerca 🟢│
├──────────────────────────────────────────────────────────────────────┤
│  Destinos monitoreados                              [ + Agregar dest. ]│
│                                                                        │
│  ETIQUETA        HOST                LATENCIA     PÉRDIDA   ACCIONES    │
│  ── Public DNS ─────────────────────────────────────────────────────  │
│  Google DNS      8.8.8.8             ▏20.4 ms▕    ▏0 %▕    Graf Edit ✕  │
│  Cloudflare v6   2606:4700:4700::11  ▏21.9 ms▕    ▏0 %▕    Graf Edit ✕  │
│  ── Routers ────────────────────────────────────────────────────────  │
│  Router Core     10.0.0.1            ▏ 1.2 ms▕    ▏0 %▕    Graf Edit ✕  │
│                                                                        │
│  Clic en un host → ruta MTR en vivo.  Clic en Gráfica → latencia/pérd. │
└──────────────────────────────────────────────────────────────────────┘
```

## 🌐 ¿Qué es esto?

Los ISP y operadores de red necesitan vigilar la **latencia y la pérdida de
paquetes** hacia muchos hosts y, cuando algo falla, entender **por qué**.
Smokeping es la herramienta clásica para medir, pero configurarlo implica editar
archivos de texto a mano.

**smokeping-easy** envuelve Smokeping en una interfaz web limpia y trilingüe
donde agregas destinos, defines umbrales de alerta, recibes avisos por Telegram,
trazas rutas con MTR y le pides a una IA que analice los problemas — **sin tocar
jamás un archivo de configuración**.

Hecho para ISP y operadores de red en América Latina (y en todas partes).

## ✨ Funcionalidades

- 🌍 **Interfaz web trilingüe** — inglés, español y portugués, en vivo.
- 🎯 **Alta de destinos desde la UI** — sin archivos de configuración. Organízalos en grupos.
- 🔔 **Alertas de Telegram** — umbrales de latencia y pérdida por destino.
- 🧊 **Intervalo entre alertas configurable** por destino — sin spam.
- ✅ **Alertas de normalización** — un aviso cuando el valor vuelve a la normalidad.
- 📅 **Reporte diario automatizado** por Telegram, escrito por IA.
- 🤖 **Análisis con IA a demanda**, con selector dinámico de modelo (Claude / OpenAI).
- 🧠 **Lista de modelos cargada desde la API real del proveedor** — nada hardcodeado.
- ✍️ **Prompt de IA editable** — escríbelo en tu propio idioma.
- 📈 **Gráficas de latencia y pérdida en la app** (Chart.js) con períodos seleccionables.
- 🛰️ **MTR a demanda** — haz clic en un host para trazar la ruta en vivo.
- 🔐 **Autenticación con protección contra fuerza bruta** (bcrypt + sesiones del lado servidor).
- 🚦 **Rate limiting** en el login y en las APIs de IA.
- 🌐 **Doble pila IPv4 / IPv6 nativa.**
- 🔧 **Puerto configurable** vía `.env`.
- 🔒 **Secretos cifrados en reposo** (Fernet / AES).
- 🛡️ **Perfil TLS opcional** con Traefik + Let's Encrypt.
- ℹ️ **Pestaña Acerca de** con licencia y créditos.

## 📋 Requisitos

- **Docker Engine 24+**
- **Docker Compose v2+** (el plugin `docker compose`)
- Un **puerto libre** en el host (por defecto: `3000`)
- *(Para alertas)* un **bot de Telegram** creado con [@BotFather](https://t.me/BotFather)
- *(Para análisis IA)* una **API key de Anthropic u OpenAI**

Nada más: sin Python, Node ni herramientas de compilación.

## 🐳 Instalar Docker y Docker Compose

¿Ya los tienes? Verifica con:

```bash
docker --version && docker compose version
```

Si ambos muestran una versión, salta a la siguiente sección.

**Linux (Ubuntu, Debian, Fedora, etc.)** — el script oficial instala Docker
Engine *y* el plugin de Compose:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Luego inicia Docker al arrancar y (opcional) úsalo sin `sudo`:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # cierra sesión y vuelve a entrar para que aplique
```

**Windows / macOS** — instala
[Docker Desktop](https://docs.docker.com/get-docker/) (Compose ya viene incluido).

Otras distribuciones y métodos manuales:
<https://docs.docker.com/engine/install/>

## 🚀 Instalación en 3 pasos

**1. Clonar**

```bash
git clone https://github.com/uesleycorrea/smokeping-easy
cd smokeping-easy
```

**2. Configurar**

```bash
cp .env.example .env
# En la mayoría de los casos solo necesitas ajustar HTTP_PORT (por defecto 3000).
```

**3. Iniciar**

```bash
docker compose up -d --build
```

Abre **http://localhost:3000** e inicia sesión.

**Contraseña inicial** — si dejaste `ADMIN_PASSWORD` vacío, se genera una en el
primer arranque y se imprime en los logs:

```bash
docker compose logs backend | grep -i password
```

## 👣 Primer uso (paso a paso)

1. Abre la interfaz e **inicia sesión** con la contraseña inicial.
2. Ve a **Ajustes → Cambiar contraseña** y define la tuya.
3. Ve a **Destinos** y agrega tus primeros hosts.
4. *(Opcional)* En **Ajustes → Alertas de Telegram**, configura el bot y define
   umbrales en tus destinos.
5. *(Opcional)* En **Ajustes → Proveedor de IA**, pega una API key y carga modelos.

## 💬 Cómo obtener tu Chat ID de Telegram

1. Habla con [@BotFather](https://t.me/BotFather), envía `/newbot` y sigue los
   pasos — obtendrás un **token** como `123456:ABC-DEF…`.
2. Envía cualquier mensaje a tu nuevo bot (o agrégalo a un grupo y publica algo).
3. Abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` en el navegador y lee
   `chat.id` (los grupos empiezan con `-100…`).

## ⚙️ Configuración de `.env`

| Variable | Por defecto | Descripción |
|---|---|---|
| `HTTP_PORT` | `3000` | Puerto de la web en el host. Suele ser el único a cambiar. |
| `SMOKEPING_WEB_PORT` | `8081` | Puerto de las gráficas nativas de Smokeping (solo lectura). |
| `PUID` / `PGID` | `1000` | Usuario/grupo dueño de los volúmenes compartidos. |
| `TZ` | `UTC` | Zona horaria (ej. `America/Mexico_City`). |
| `ADMIN_PASSWORD` | *(vacío)* | Contraseña inicial. Vacío → autogenerada y registrada en logs. |
| `RELOAD_TOKEN` | *(vacío)* | Token de la API interna de recarga (puerto 9000, nunca expuesto). Opcional. |
| `SESSION_TTL_MINUTES` | `120` | Duración de la sesión. |
| `LOGIN_MAX_ATTEMPTS` | `5` | Intentos fallidos por IP antes del bloqueo. |
| `LOGIN_WINDOW_MINUTES` | `10` | Ventana del bloqueo. |
| `LOG_LEVEL` | `INFO` | Nivel de logs. Evita `DEBUG` en producción. |
| `DOMAIN` | — | *(solo TLS)* tu dominio, ej. `monitor.example.com`. |
| `ACME_EMAIL` | — | *(solo TLS)* email para Let's Encrypt. |

## 🔒 Perfil TLS (HTTPS en producción)

Apunta un registro DNS a tu servidor, define `DOMAIN` y `ACME_EMAIL` en `.env`, y:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Traefik obtiene y renueva un certificado gratuito de Let's Encrypt, sirve la app
por **HTTPS** (redirección automática) y marca la cookie de sesión como `Secure`.

## 🔄 Actualización

```bash
git pull
docker compose up -d --build
```

Tus datos (destinos, grupos, ajustes, historial de latencia) viven en volúmenes
de Docker y se conservan entre actualizaciones.

## 🛠️ Solución de problemas

**Los destinos no aparecen en Smokeping tras agregarlos en la UI**
Suele ser un choque de nombre con otro contenedor llamado `smokeping` en el
mismo host. smokeping-easy ya usa un hostname interno explícito
(`smokeping-easy-svc`) para evitarlo — asegúrate de estar en una versión reciente
y reconstruye (`docker compose up -d --build`).

**La interfaz no abre / "port is already in use"**
Otra aplicación está usando el mismo puerto del host. Edita `HTTP_PORT` en
`.env` (por defecto `3000`) a un puerto libre y luego `docker compose up -d`.

**Conflicto con Portainer / GenieACS en el puerto interno 9000**
No se espera ninguno: la API interna de recarga de Smokeping **nunca se publica
al host** (solo existe en la red de Docker) y su puerto por defecto ahora es
`9731`. Solo si ejecutas el stack con `network_mode: host` y `9731` está ocupado,
cambia `RELOAD_PORT` en `.env`.

## 🗺️ Hoja de ruta

**Incluido**

- [x] Interfaz web trilingüe (EN / ES / PT)
- [x] Alta/edición de destinos desde la UI, organizados en grupos
- [x] Gestión de grupos (crear / renombrar conserva el historial / eliminar)
- [x] Alertas de Telegram por umbral con intervalo y normalización por destino
- [x] Reporte diario automatizado con IA
- [x] Análisis con IA a demanda con selección dinámica de modelo (Claude / OpenAI)
- [x] Prompt de IA editable
- [x] Gráficas de latencia y pérdida en la app
- [x] MTR a demanda (ruta servidor → destino)
- [x] Autenticación bcrypt, protección contra fuerza bruta, rate limiting
- [x] Doble pila IPv4 / IPv6
- [x] Secretos cifrados en reposo
- [x] Perfil TLS opcional (Traefik + Let's Encrypt)
- [x] Panel de estado del sistema + recarga manual de Smokeping en Ajustes

## 🛡️ Seguridad

Puntos clave: contraseña bcrypt + sesiones del lado servidor `HttpOnly`/`SameSite`,
protección contra fuerza bruta, toda la entrada validada en el backend, secretos
cifrados con Fernet en reposo, el backend y la API de recarga nunca expuestos al
host, contenedores sin root y una Content-Security-Policy estricta. Consulta
[SECURITY.md](SECURITY.md) para el modelo completo y cómo reportar una
vulnerabilidad.

## 🤝 Contribuir

¡Las contribuciones son bienvenidas, especialmente de la comunidad ISP
latinoamericana! Abre un
[issue](https://github.com/uesleycorrea/smokeping-easy/issues) para reportar un
error o sugerir una función, o envía un
[pull request](https://github.com/uesleycorrea/smokeping-easy/pulls). Las ideas
de los operadores de red lo mejoran para todos.

## 👤 Autor

**Uesley Correa**
[Telecom ISP Solutions](https://telecomisp.solutions) — *Soluciones para ISPs en
América Latina.*

## 📄 Licencia

Bajo la **Licencia Pública General de GNU v3.0**. Puedes usarlo, estudiarlo,
modificarlo y redistribuirlo; las versiones derivadas deben permanecer de código
abierto bajo la misma licencia. Consulta [LICENSE](LICENSE) o
[gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html).
