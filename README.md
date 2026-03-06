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

### Frontend
```bash
cd frontend
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build
npm run preview   # preview production build
```

### Backend
```bash
cd backend
pip install -r requirements.txt
# see backend/README.md for env vars and DB setup
```

### AI Models
```bash
cd ai-models
pip install -r requirements.txt
# see ai-models/README.md for model setup
```

### Docker (all services)
```bash
docker-compose up
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
