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

If `AISENSY_WEBHOOK_SECRET` is **non-empty**, requests must include a matching HMAC. If AiSensy does not support a shared secret, **delete** that variable (or leave it empty) so verification is skipped.

If webhooks still return **401**, inbound messages never reach the database (inbox stays empty; `last_inbound_at` never updates).

Campaign sends use `AISENSY_API_KEY` and the **worker queue**; they do not depend on webhooks for delivery.

### Campaign stuck on `sending` (no WhatsApp messages)

`Send now` only **enqueues** work on Redis (`enqueue_campaign_send`). The actual sends run inside an **RQ worker** (`run_campaign_send` → `send_campaign`). If you only deploy the FastAPI container and **no worker**, the campaign stays **`sending`** and nothing is delivered.

**Railway:** add a **second service** from the same backend image. The Dockerfile default runs **`start.sh`** (migrations + **Uvicorn**) — that is the **API**, not the worker. You must override **Deploy → Custom Start Command** for the worker service to:

`/app/scripts/start-worker.sh`

(or equivalently: `rq worker -u $REDIS_URL ${RQ_QUEUE_NAME:-whatsapp-agent}`)

If your logs show `launching uvicorn`, this service is still starting the API; fix the start command. See `backend/railway.worker.json`. Use the **same** `REDIS_URL` (and queue name) as the API, and copy the same env vars the jobs need. Disable HTTP health checks for the worker service if the image’s Dockerfile `HEALTHCHECK` curls `/healthz` (the worker does not run Uvicorn).

Locally you need two terminals: `uvicorn …` and `rq worker -u $REDIS_URL whatsapp-agent`.

### Inbox: `409` — outside 24h window

Free-form inbox replies require at least one **inbound** message stored in **this** app within the last `SERVICE_WINDOW_HOURS` (default 24). That timestamp comes from webhooks (or any path that creates inbound messages). Until inbound webhooks work, use **template campaigns** for first contact; use the inbox only after the user has replied.

### Dashboard looks empty vs AiSensy

This product **does not** sync AiSensy’s own UI into Postgres. You only see contacts/conversations/messages here when **(a)** AiSensy **POSTs webhooks** to your deployed `/api/v1/webhooks/aisensy/inbound` (and optionally `/status`), or **(b)** you create data via this API (campaigns, manual contact, etc.).

After logging in, open **Overview** on the dashboard: it calls `GET /api/v1/integrations/aisensy` and shows whether the API key is set, how many webhook events were stored, suggested webhook URLs for your current host, and short hints.

### Backend / LLM / Redis checks

- `GET /api/v1/integrations/system` (authenticated) — Postgres ping, Redis ping, RQ queue depth, `AI_PROVIDER` + whether the matching API key is set, optional KB embedding key, and counts of `ai_runs` (sent/failed) in the last 24h.
- Same URL with `?probe_llm=true` runs **one minimal LLM request** (may incur a small provider charge) to verify the key and model work; the Overview dashboard has a **Test LLM call** button that uses this.

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
