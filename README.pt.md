<div align="center">

# 📡 smokeping-easy

[English](README.md) · [Español](README.es.md) · **Português**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Version](https://img.shields.io/badge/version-1.1.0-brightgreen.svg)](https://github.com/uesleycorrea/smokeping-easy/releases)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/)

*Smokeping com uma interface web moderna, alertas no Telegram e análise de IA — no ar em minutos com Docker Compose.*

</div>

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📡 smokeping-easy   Alvos  Análise IA  Configurações  Gráficos  Sobre 🟢│
├──────────────────────────────────────────────────────────────────────┤
│  Alvos monitorados                                  [ + Adicionar alvo]│
│                                                                        │
│  RÓTULO          HOST                LATÊNCIA     PERDA     AÇÕES       │
│  ── Public DNS ─────────────────────────────────────────────────────  │
│  Google DNS      8.8.8.8             ▏20.4 ms▕    ▏0 %▕    Gráf Edit ✕  │
│  Cloudflare v6   2606:4700:4700::11  ▏21.9 ms▕    ▏0 %▕    Gráf Edit ✕  │
│  ── Routers ────────────────────────────────────────────────────────  │
│  Router Core     10.0.0.1            ▏ 1.2 ms▕    ▏0 %▕    Gráf Edit ✕  │
│                                                                        │
│  Clique num host → rota MTR ao vivo.  Clique em Gráfico → latência/perda│
└──────────────────────────────────────────────────────────────────────┘
```

## 🌐 O que é isto?

ISPs e operadores de rede precisam acompanhar a **latência e a perda de pacotes**
até muitos hosts e, quando algo quebra, entender o **porquê**. O Smokeping é a
ferramenta clássica para as medições, mas configurá-lo significa editar arquivos
de texto na mão.

O **smokeping-easy** envolve o Smokeping numa interface web limpa e trilíngue onde
você cadastra alvos, define limites de alerta, recebe avisos no Telegram, traça
rotas com MTR e pede a uma IA para analisar problemas — **sem nunca tocar num
arquivo de configuração**.

Feito para ISPs e operadores de rede na América Latina (e no mundo todo).

## ✨ Funcionalidades

- 🌍 **Interface web trilíngue** — inglês, espanhol e português, ao vivo.
- 🎯 **Cadastro de alvos pela UI** — sem arquivos de configuração. Organize em grupos.
- 🔔 **Alertas no Telegram** — limites de latência e perda por alvo.
- 🧊 **Intervalo entre alertas configurável** por alvo — sem spam.
- ✅ **Alertas de normalização** — aviso quando o valor volta ao normal.
- 📅 **Relatório diário automatizado** via Telegram, escrito por IA.
- 🤖 **Análise com IA sob demanda**, com seletor dinâmico de modelo (Claude / OpenAI).
- 🧠 **Lista de modelos carregada da API real do provedor** — nada hardcoded.
- ✍️ **Prompt de IA editável** — escreva no seu próprio idioma.
- 📈 **Gráficos de latência e perda no app** (Chart.js) com períodos selecionáveis.
- 🛰️ **MTR sob demanda** — clique num host para traçar a rota ao vivo.
- 🔐 **Autenticação com proteção contra força bruta** (bcrypt + sessões no servidor).
- 🚦 **Rate limiting** no login e nas APIs de IA.
- 🌐 **Dual-stack IPv4 / IPv6 nativo.**
- 🔧 **Porta configurável** via `.env`.
- 🔒 **Segredos criptografados em repouso** (Fernet / AES).
- 🛡️ **Perfil TLS opcional** com Traefik + Let's Encrypt.
- ℹ️ **Aba Sobre** com licença e créditos.

## 📋 Pré-requisitos

- **Docker Engine 24+**
- **Docker Compose v2+** (o plugin `docker compose`)
- Uma **porta livre** no host (padrão: `3000`)
- *(Para alertas)* um **bot do Telegram** criado via [@BotFather](https://t.me/BotFather)
- *(Para análise IA)* uma **API key da Anthropic ou OpenAI**

Só isso — sem Python, Node ou ferramentas de build.

## 🐳 Instalar o Docker e o Docker Compose

Já tem instalado? Confira com:

```bash
docker --version && docker compose version
```

Se os dois mostrarem uma versão, pule para a próxima seção.

**Linux (Ubuntu, Debian, Fedora, etc.)** — o script oficial instala o Docker
Engine *e* o plugin do Compose:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Depois habilite o Docker no boot e (opcional) use sem `sudo`:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # saia e entre na sessão novamente para valer
```

**Windows / macOS** — instale o
[Docker Desktop](https://docs.docker.com/get-docker/) (o Compose já vem incluso).

Outras distribuições e métodos manuais:
<https://docs.docker.com/engine/install/>

## 🚀 Instalação em 3 passos

**1. Clonar**

```bash
git clone https://github.com/uesleycorrea/smokeping-easy
cd smokeping-easy
```

**2. Configurar**

```bash
cp .env.example .env
# Na maioria dos casos você só precisa ajustar HTTP_PORT (padrão 3000).
```

**3. Subir**

```bash
docker compose up -d --build
```

Abra **http://localhost:3000** e faça login.

**Senha inicial** — se você deixou `ADMIN_PASSWORD` vazio, uma senha é gerada no
primeiro boot e impressa nos logs:

```bash
docker compose logs backend | grep -i password
```

## 👣 Primeiro uso (passo a passo)

1. Abra a interface e **faça login** com a senha inicial.
2. Vá em **Configurações → Alterar senha** e defina a sua.
3. Vá em **Alvos** e cadastre seus primeiros hosts.
4. *(Opcional)* Em **Configurações → Alertas do Telegram**, configure o bot e
   defina limites nos seus alvos.
5. *(Opcional)* Em **Configurações → Provedor de IA**, cole uma API key e carregue
   os modelos.

## 💬 Como obter seu Chat ID do Telegram

1. Fale com o [@BotFather](https://t.me/BotFather), envie `/newbot` e siga os
   passos — você recebe um **token** como `123456:ABC-DEF…`.
2. Envie qualquer mensagem ao seu novo bot (ou adicione-o a um grupo e poste algo).
3. Abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no navegador e leia o
   `chat.id` (grupos começam com `-100…`).

## ⚙️ Configuração do `.env`

| Variável | Padrão | Descrição |
|---|---|---|
| `HTTP_PORT` | `3000` | Porta da web no host. Geralmente a única a mudar. |
| `SMOKEPING_WEB_PORT` | `8081` | Porta dos gráficos nativos do Smokeping (somente leitura). |
| `PUID` / `PGID` | `1000` | Usuário/grupo dono dos volumes compartilhados. |
| `TZ` | `UTC` | Fuso horário (ex.: `America/Sao_Paulo`). |
| `ADMIN_PASSWORD` | *(vazio)* | Senha inicial. Vazio → gerada automaticamente e registrada nos logs. |
| `RELOAD_TOKEN` | *(vazio)* | Token da API interna de reload (porta 9000, nunca exposta). Opcional. |
| `SESSION_TTL_MINUTES` | `120` | Duração da sessão. |
| `LOGIN_MAX_ATTEMPTS` | `5` | Tentativas falhas por IP antes do bloqueio. |
| `LOGIN_WINDOW_MINUTES` | `10` | Janela do bloqueio. |
| `LOG_LEVEL` | `INFO` | Nível de log. Evite `DEBUG` em produção. |
| `DOMAIN` | — | *(só TLS)* seu domínio, ex.: `monitor.example.com`. |
| `ACME_EMAIL` | — | *(só TLS)* email para o Let's Encrypt. |

## 🔒 Perfil TLS (HTTPS em produção)

Aponte um registro DNS para o servidor, defina `DOMAIN` e `ACME_EMAIL` no `.env`, e:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

O Traefik obtém e renova um certificado gratuito do Let's Encrypt, serve o app via
**HTTPS** (redirecionamento automático) e marca o cookie de sessão como `Secure`.

## 🔄 Atualização

```bash
git pull
docker compose up -d --build
```

Seus dados (alvos, grupos, configurações, histórico de latência) ficam em volumes
do Docker e são preservados entre atualizações.

## 🛠️ Solução de problemas

**Os alvos não aparecem no Smokeping após adicionar pela interface**
Geralmente é um conflito de nome com outro container chamado `smokeping` no mesmo
host. O smokeping-easy já usa um hostname interno explícito (`smokeping-easy-svc`)
para evitar isso — confira se está numa versão recente e reconstrua
(`docker compose up -d --build`).

**A interface não abre / "port is already in use"**
Outra aplicação está usando a mesma porta do host. Edite `HTTP_PORT` no `.env`
(padrão `3000`) para uma porta livre e rode `docker compose up -d`.

**Conflito com Portainer / GenieACS na porta interna 9000**
Nenhum esperado: a API interna de reload do Smokeping **nunca é publicada ao
host** (só existe na rede do Docker) e a porta padrão agora é `9731`. Apenas se
você rodar o stack com `network_mode: host` e a `9731` estiver ocupada, mude o
`RELOAD_PORT` no `.env`.

## 🗺️ Roadmap

**Incluído**

- [x] Interface web trilíngue (EN / ES / PT)
- [x] Cadastro/edição de alvos pela UI, organizados em grupos
- [x] Gestão de grupos (criar / renomear mantém o histórico / excluir)
- [x] Alertas do Telegram por limite com intervalo e normalização por alvo
- [x] Relatório diário automatizado com IA
- [x] Análise com IA sob demanda com seleção dinâmica de modelo (Claude / OpenAI)
- [x] Prompt de IA editável
- [x] Gráficos de latência e perda no app
- [x] MTR sob demanda (rota servidor → alvo)
- [x] Autenticação bcrypt, proteção contra força bruta, rate limiting
- [x] Dual-stack IPv4 / IPv6
- [x] Segredos criptografados em repouso
- [x] Perfil TLS opcional (Traefik + Let's Encrypt)
- [x] Card de status do sistema + reload manual do Smokeping nas Configurações

## 🛡️ Segurança

Destaques: senha bcrypt + sessões no servidor `HttpOnly`/`SameSite`, proteção
contra força bruta, toda entrada validada no backend, segredos criptografados com
Fernet em repouso, o backend e a API de reload nunca expostos ao host, containers
sem root e uma Content-Security-Policy estrita. Veja o
[SECURITY.md](SECURITY.md) para o modelo completo e como reportar uma
vulnerabilidade.

## 🤝 Contribuindo

Contribuições são bem-vindas — especialmente da comunidade ISP latino-americana!
Abra uma [issue](https://github.com/uesleycorrea/smokeping-easy/issues) para
reportar um bug ou sugerir uma funcionalidade, ou envie um
[pull request](https://github.com/uesleycorrea/smokeping-easy/pulls). Ideias de
operadores de rede tornam tudo melhor para todos.

## 👤 Autor

**Uesley Correa**
[Telecom ISP Solutions](https://telecomisp.solutions) — *Soluciones para ISPs en
América Latina.*

## 📄 Licença

Licenciado sob a **GNU General Public License v3.0**. Você pode usar, estudar,
modificar e redistribuir; versões derivadas devem permanecer de código aberto sob
a mesma licença. Veja [LICENSE](LICENSE) ou
[gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html).
