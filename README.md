# InnovaCX

AI-powered customer experience platform built for **Dubai CommerCity (DCC)**. InnovaCX uses sentiment analysis, audio intelligence, and machine learning to automatically triage, prioritise, and route customer complaints — so every customer feels heard and every team works smarter.

---

## What It Does

| Capability | Description |
|---|---|
| **Sentiment Analysis** | Detects emotional tone in complaints to flag urgency in real time |
| **Audio Intelligence** | Transcribes and analyses voice complaints for nuance text alone misses |
| **Smart Prioritisation** | Ranks tickets by urgency and customer value automatically |
| **Nova AI Chatbot** | Guides customers through complaint submission and status checks |
| **Multi-role Dashboards** | Dedicated views for Customers, Employees, Managers, and Operators |
| **Auto-generated Reports** | PDF reports for employee performance and complaint trends |

---

## Repository Structure

```
innova-cx/
├── frontend/          # React + Vite SPA (this is the UI)
├── backend/           # FastAPI backend (REST API + auth)
├── ai-models/         # ML models (sentiment, prioritisation, chatbot agent)
├── data/              # Synthetic data generators
├── database/          # DB schemas and migrations
├── infrastructure/    # Docker / cloud deployment config
├── monitoring/        # Logging and observability
├── postman/           # API collections for testing
├── scripts/           # Utility scripts
└── docs/              # Project documentation
```

---

## Tech Stack

### Frontend
- **React 19** + **Vite 7** — fast dev server and build
- **React Router v7** — client-side routing with lazy-loaded pages
- **Recharts** — dashboards and complaint trend charts
- **@react-pdf/renderer** — in-browser PDF report generation
- **Axios** — HTTP client for API calls
- Plain global **CSS** with design tokens (no CSS Modules or Tailwind)

### Backend
- **FastAPI** (Python)
- JWT authentication with role-based access control

### AI / ML
- Sentiment analysis service
- Rule-based and ML prioritisation
- Multi-agent pipeline (DSPy)
- Nova chatbot agent

> **Note:** Trained model files are not included in this repository. The `frontend` profile runs without them (chatbot uses mock mode). The `live` profile requires model files to be pre-downloaded on the host.

---

## User Roles & Routes

| Role | Entry Point | Key Pages |
|---|---|---|
| **Public** | `/` | Landing, About, Login, Forgot Password |
| **Customer** | `/customer` | Landing, My Tickets, Ticket Details, Fill Form, Settings |
| **Employee** | `/employee` | Dashboard, All Complaints, Ticket Details, Reports, Notifications |
| **Manager** | `/manager` | Dashboard, All Complaints, Ticket Details, Employees, Approvals, Trends |
| **Operator** | `/operator` | Dashboard, Model Analysis, Chatbot Analysis, User Management |

All authenticated routes are protected by `ProtectedRoute` — unauthenticated users are redirected to `/login`.

---

## Getting Started

### Run with Docker (Recommended)

**Step 1 — Clone the repository**
```bash
git clone https://github.com/w4g0n/innova-cx.git
cd innova-cx
```

**Step 2 — Configure environment variables**
```bash
cp .env.install .env
```

All values are pre-filled with safe development defaults — no editing required.

**Step 3 — Start the application**
```bash
docker compose --profile frontend up --build
```

Wait for `Application startup complete` before opening the browser.

**Step 4 — Open in your browser**

| URL | Service |
|---|---|
| http://localhost:5173 | Frontend |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | API Docs (Swagger) |

**Default login credentials**

| Role | Email | Password |
|---|---|---|
| Customer | customer1@innovacx.net | Innova@2025 |
| Employee | ahmed@innovacx.net | Innova@2025 |
| Manager | hamad@innovacx.net | Innova@2025 |
| Operator | operator@innovacx.net | Innova@2025 |

**OTP / MFA**

- **Customers** — check the Docker logs for the one-time code:
  ```bash
  docker compose logs backend
  # [DEV] Email OTP for customer1@innovacx.net: 123456
  ```
- **Staff** — scan the QR code shown after login with any authenticator app (Google Authenticator, Authy, etc.)

> For production deployment, use `.env.example` as your template — it documents all required variables with no defaults.

---

### Docker Compose Profiles

| Profile | Services Started | Use When |
|---|---|---|
| `frontend` | frontend, backend, postgres | UI and API development |
| `pipeline` | orchestrator, backend, postgres | ML pipeline testing |
| `live` | all services | Full integration or production |

```bash
docker compose --profile [profile-name] up --build
```

---

### Local Development (without Docker)

**Frontend**
```bash
cd frontend
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build
npm run preview   # preview production build
```

**Backend**
```bash
cd backend
pip install -r requirements.txt
# see backend/README.md for env vars and DB setup
```

**AI Models**
```bash
cd ai-models
pip install -r requirements.txt
# see ai-models/README.md for model setup
```

---

## Frontend Design System

The UI uses CSS custom properties defined in `frontend/src/index.css`:

| Token | Usage |
|---|---|
| `--gradient-brand` | Primary purple gradient (buttons, accents) |
| `--glass-bg` | Frosted glass backgrounds |
| `--radius-lg` / `--radius-pill` | Border radius scale |
| `--font-heading` | Display font for hero headings |
| `--ease-spring` / `--ease-out` | Animation easing |
| `--dur-slow` | Slow animation duration |

Pages use `animation: fadeUp 0.4s var(--ease-out) both` on root containers for consistent entrance transitions.

---

## Branch Convention

| Branch | Purpose |
|---|---|
| `main` | Stable releases |
| `v5_FrontendRedesign` | Current active frontend redesign (React + Vite) |
| `backend/*` | Backend feature branches |
| `ai/*` | AI/ML model branches |

---

## Team

CSIT321 Project — Year 3, Big Data and Artificial Intelligence
Dubai CommerCity · InnovaCX © 2026
