# Terra Rex Energy — WhatsApp AI Agent Platform

A lightweight, production-ready WhatsApp AI sales + support platform built as a
modular monolith. It uses **AiSensy** as the messaging BSP (no direct Meta Cloud
API), **FastAPI** for the backend, **Next.js** for the dashboard, **PostgreSQL**
(with `pgvector`) as the source of truth, and **Redis** for locks, cache, and
background jobs (via `rq`).

The platform supports:

- Inbound WhatsApp support with an AI that answers from a configurable
  knowledge base
- Campaign creation with CSV/Excel upload, column mapping, dedupe, scheduling,
  and per-recipient tracking — sent via AiSensy's campaign API
- Campaign reply attribution and continuation inside the inbox
- Instant human takeover from the dashboard (AI stops immediately and stays
  stopped until explicitly resumed)
- Service-window guard for 24h free-form messaging policy
- Agent profiles (tone, persona, escalation behavior, KB links)
- Lightweight RBAC with JWT auth

---

## Architecture overview

```
┌─────────────┐      ┌───────────────────┐      ┌──────────────┐
│ WhatsApp    │◀────▶│ AiSensy (BSP)     │◀────▶│ FastAPI API  │
│ end-users   │      │ campaign + inbox  │      │ (webhooks +  │
└─────────────┘      └───────────────────┘      │  dashboard)  │
                                                │              │
                                                │  ┌────────┐  │
                                                │  │ Redis  │  │
                                                │  │ locks, │  │
                                                │  │ queue  │  │
                                                │  └────────┘  │
                                                │              │
                                                │  ┌────────┐  │
                                                │  │Postgres│  │
                                                │  │+pgvect.│  │
                                                │  └────────┘  │
                                                └──────▲───────┘
                                                       │
                                              ┌────────┴────────┐
                                              │ RQ worker       │
                                              │ (AI replies,    │
                                              │  campaign send, │
                                              │  KB indexing)   │
                                              └─────────────────┘

                         ┌─────────────────────┐
                         │ Next.js dashboard   │
                         │ (inbox, campaigns,  │
                         │  KB, agents, auth)  │
                         └─────────────────────┘
```

Everything is a modular monolith. Provider-specific code lives only inside
`backend/app/integrations/aisensy/`. Business logic never calls AiSensy
directly — it calls the adapter.

---

## Repository layout

```
whatsapp-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/               # FastAPI routers
│   │   ├── core/                 # config, security, logging, redis
│   │   ├── db/                   # session, base
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── services/             # business logic
│   │   │   ├── conversation/     # state machine, inbox
│   │   │   ├── campaign/         # CSV parsing, send orchestration
│   │   │   ├── kb/               # chunking, retrieval
│   │   │   ├── ai/               # agent runner
│   │   │   └── messaging/        # service-window guard
│   │   ├── integrations/aisensy/ # adapter: client, webhook, normalizer
│   │   ├── workers/              # rq job definitions
│   │   ├── utils/                # csv, phone, retries, audit
│   │   └── main.py
│   ├── migrations/               # alembic
│   ├── scripts/seed.py           # Terra Rex seed data
│   ├── tests/                    # pytest
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/                     # Next.js 14 app router dashboard
├── infra/
│   ├── docker-compose.yml
│   └── postgres-init.sql
├── .env.example
└── README.md
```

---

## Quick start (local development)

```bash
# 1) copy env file and fill secrets
cp .env.example .env

# 2) bring up infra (postgres + redis)
docker compose -f infra/docker-compose.yml up -d

# 3) install backend deps + run migrations + seed
cd backend
pip install -e .
alembic upgrade head
python scripts/seed.py

# 4) run API and worker in two terminals
uvicorn app.main:app --reload --port 8000
rq worker -u $REDIS_URL whatsapp-agent

# 5) run frontend
cd ../frontend
npm install
npm run dev
# open http://localhost:3000
```

Default seeded admin:

```
email:    admin@terrarex.local
password: admin123
```

---

## Core flows

1. **Inbound support** — AiSensy webhook → `POST /api/v1/webhooks/aisensy/inbound`
   → raw payload persisted → normalizer converts to internal model →
   conversation upserted → worker job enqueued → AI runner checks state,
   retrieves KB, calls LLM, sends reply via `AiSensyClient.send_session_message`.
2. **Campaign send** — operator uploads CSV → mapping saved → recipients
   inserted → `send_now` enqueues a job → worker iterates recipients and calls
   `AiSensyClient.send_campaign` using the approved template.
3. **Campaign reply** — inbound webhook resolves the contact, looks up the most
   recent campaign recipient within a configurable attribution window, and
   links the new conversation/message to that campaign.
4. **Human takeover** — operator clicks "Take over" or sends a message.
   Conversation state becomes `HUMAN_ACTIVE`, an audit log is written, and any
   queued AI job checks the state before sending — it skips if takeover
   happened in the meantime.
5. **Resume AI** — operator calls `POST /api/v1/inbox/{id}/resume-ai`, state
   returns to `AI_ACTIVE`, future inbound messages are AI-handled again.

---

## Required environment variables

See `.env.example` for the full list with placeholders. Summary:

### App auth / database / redis / infra

| Variable | Required | What it is |
|---|---|---|
| `APP_ENV` | yes | `local`, `staging`, `production` |
| `APP_SECRET_KEY` | yes | Random 64-byte hex, used for JWT signing and cookies |
| `APP_PORT` | no | default `8000` |
| `DATABASE_URL` | yes | Postgres DSN, e.g. `postgresql+psycopg://user:pass@localhost:5432/terrarex` |
| `REDIS_URL` | yes | Redis DSN, e.g. `redis://localhost:6379/0` |
| `CORS_ORIGINS` | yes | Comma-separated list (e.g. `http://localhost:3000`) |
| `JWT_ACCESS_TTL_MIN` | no | default `120` |

### AiSensy (BSP — get these from AiSensy dashboard)

| Variable | Required | What it is |
|---|---|---|
| `AISENSY_API_KEY` | yes | AiSensy API key used for all outbound calls |
| `AISENSY_BASE_URL` | yes | Defaults to `https://backend.aisensy.com` — override if AiSensy gives a custom URL |
| `AISENSY_CAMPAIGN_ENDPOINT` | yes | Path for campaign sends, default `/campaign/t1/api/v2` |
| `AISENSY_SESSION_ENDPOINT` | yes | Path for session (free-form) sends, default `/direct-apis/t1/messages` |
| `AISENSY_WEBHOOK_SECRET` | no | If set, inbound webhooks must send a matching HMAC (see troubleshooting). Empty = skip verification. |
| `AISENSY_SOURCE` | no | Tag string sent with campaign (e.g. `terrarex-dashboard`) |

### AI provider

| Variable | Required | What it is |
|---|---|---|
| `AI_PROVIDER` | yes | `anthropic` (default) or `openai` |
| `ANTHROPIC_API_KEY` | conditional | Required when `AI_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | conditional | Required when `AI_PROVIDER=openai` or when using OpenAI embeddings |
| `AI_MODEL` | no | Model ID, default `claude-sonnet-4-6` |
| `AI_EMBEDDING_PROVIDER` | yes | `openai` (default) — used for KB embeddings |
| `AI_EMBEDDING_MODEL` | no | default `text-embedding-3-small` |

### Business policy

| Variable | Required | What it is |
|---|---|---|
| `SERVICE_WINDOW_HOURS` | no | WhatsApp 24h free-form reply window, default `24` |
| `CAMPAIGN_ATTRIBUTION_HOURS` | no | Window in which a reply is attributed to the last campaign, default `72` |
| `BUSINESS_NAME` | no | default `Terra Rex Energy` |
| `BUSINESS_TIMEZONE` | no | default `Asia/Kolkata` |

### Frontend

| Variable | Required | What it is |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | yes | e.g. `http://localhost:8000/api/v1` |

Mandatory keys for a working local dev run:
`APP_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`,
`AISENSY_API_KEY`, `ANTHROPIC_API_KEY` (or
`OPENAI_API_KEY`), `NEXT_PUBLIC_API_BASE_URL`.

### Webhook returns 401 (`missing signature` / `bad signature`)

Production uses `AISENSY_WEBHOOK_SECRET` to verify `POST /api/v1/webhooks/aisensy/*`.
If AiSensy’s request is rejected with **401**, inbound messages never reach the database (inbox stays empty; `last_inbound_at` never updates).

1. In **Railway**, set `AISENSY_WEBHOOK_SECRET` to the **exact same** secret you configured in the **AiSensy webhook URL** settings (often a string you define in both places).
2. Redeploy or restart so the env is loaded.
3. If AiSensy does not send a signature header at all, either enable signing in AiSensy or temporarily set `AISENSY_WEBHOOK_SECRET` to **empty** to disable verification (less secure; debugging only).

Campaign sends use `AISENSY_API_KEY` and the worker queue; they do **not** depend on webhooks. If campaigns fail too, check worker logs, Redis, and template name in AiSensy.

---

## Notes on AiSensy assumptions

AiSensy's exact webhook payload shape is not publicly stable, so the
integration layer at `backend/app/integrations/aisensy/normalizer.py`
documents each assumed field and provides a single place to adjust. Internal
models never depend on the raw payload directly.

Outbound campaign payload fields supported:

```json
{
  "apiKey": "...",
  "campaignName": "...",
  "destination": "+91...",
  "userName": "...",
  "source": "...",
  "media": {"url": "...", "filename": "..."},
  "templateParams": ["..."],
  "tags": ["..."],
  "attributes": {"city": "Mumbai"}
}
```
