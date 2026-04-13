# InnovaCX — Claude Context

AI-powered customer complaint management platform for Dubai CommerCity. Multi-role (Customer / Employee / Manager / Operator). University project (CSIT321).

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19 + Vite 7, React Router v7, Recharts, Axios, plain CSS (custom properties) |
| Backend | FastAPI + Uvicorn, SQLAlchemy 2, psycopg2, Pydantic v2 |
| Database | PostgreSQL (3 roles: innovacx_admin, innovacx_app, readonly) |
| Auth | JWT + OAuth + MFA (PyOTP) |
| AI | DSPy multi-agent pipeline, sentiment analysis, Whisper transcription, edge-tts |
| Infra | Docker Compose (profiles: frontend, pipeline, live) |

## Directory Layout

```
innova-cx/
├── frontend/src/
│   ├── pages/          # Route pages — customer/, employee/, manager/, operator/, plus public pages
│   ├── components/     # Reusable UI — chatbot/, common/, dashboard/, forms/
│   ├── services/       # API client (api.js, userService.js)
│   ├── hooks/          # Custom React hooks
│   ├── utils/          # Helpers (auth.ts, hostUtils.js, etc.)
│   └── index.css       # Global design tokens (CSS custom properties)
├── backend/
│   ├── api/            # FastAPI route handlers — main.py is the primary entry (large: ~372KB)
│   │   ├── main.py                     # Primary router + most endpoints
│   │   ├── analytics_service.py        # Analytics calculations
│   │   ├── auto_assign_employee.py     # Auto-assignment logic
│   │   ├── department_routing_service.py
│   │   ├── pipeline_queue_api.py
│   │   ├── security_hardening.py
│   │   ├── ticket_creation_gate.py
│   │   └── ai_explainability.py
│   └── services/
│       ├── authentication/   # JWT, OAuth, MFA, RBAC
│       ├── chatbot/          # Nova AI chatbot (multi-agent, 23 subdirs)
│       └── transcriber/      # Audio transcription service
├── database/
│   ├── migrations/     # 23 numbered migration files
│   ├── init.sql        # Full schema init (~183KB)
│   └── seeds/          # Seed data scripts
├── ai-models/
│   └── MultiAgentPipeline/   # DSPy-based orchestration
├── data/               # Synthetic data generators (v1–v8, for ML training/testing)
├── services/           # Standalone microservice entrypoints (chatbot, transcriber)
├── tests/              # Test suite
├── scripts/            # Deployment + benchmarking utilities
├── docs/               # Project documentation
├── docker-compose.yml  # Primary compose file (3 profiles)
├── Makefile            # Build/run shortcuts
└── .env.example        # Environment variable template
```

## Key Architectural Notes

- **Backend API is monolithic in `main.py`** — most business logic lives there. Other `api/` files are focused modules.
- **Chatbot and Transcriber run as separate Docker containers** — they communicate with the main backend over the internal `innovacx-network`.
- **Database uses least-privilege roles** — `innovacx_app` is the runtime role, not admin.
- **Frontend uses no CSS framework** — all styling via CSS custom properties defined in `index.css`. Design tokens: `--gradient-brand`, `--glass-bg`, animation tokens.
- **React Router uses lazy loading** — routes are code-split per page directory.
- **AI pipeline is DSPy-based** — lives in `ai-models/MultiAgentPipeline/`, separate from the main backend service.

## Branch Convention

- `main` — stable/production
- `dev` — integration branch
- `backend/*`, `ai/*` — feature branches
- `v5_FrontendRedesign` — active frontend redesign work

## Environment

Copy `.env.example` → `.env`. Docker Compose handles service wiring. Use `make` commands for common tasks.
