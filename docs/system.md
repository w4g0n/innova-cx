# InnovaCX System Overview

This document is a presentation-ready overview of how the system works end-to-end, with extra focus on the AI pipeline.

## 1) System Purpose

InnovaCX handles customer **complaints** and **inquiries**.

Core objective:
- Capture ticket input from users.
- Enrich and prioritize tickets using AI.
- Route/store tickets so teams can act quickly.

## 2) High-Level Architecture

The platform has 3 layers:

1. Frontend Layer
- Built with **React + Vite**.
- Handles login, ticket form submission, role dashboards, and ticket views.
- Talks to backend APIs and (in pipeline mode) triggers orchestrator processing.

2. Backend Layer
- Built with **FastAPI**.
- Handles authentication, authorization, ticket CRUD, business endpoints, and dashboard data.
- Stores data in **PostgreSQL**.
- Receives final routed/prioritized ticket outputs from orchestrator.

3. AI Orchestration Layer
- Built as a separate **FastAPI orchestrator** using a **LangChain RunnableSequence** pipeline.
- Runs sequential AI/ML agents.
- Produces final model-informed outputs (sentiment, engineered features, priority, routing payload).

## 3) Runtime Profiles (Docker)

The system can run in these profiles:

- `frontend`
  - frontend + backend + postgres

- `pipeline`
  - frontend + backend + postgres + classifier + orchestrator
  - This is the main profile for demonstrating AI ticket flow.

- `dev`
  - everything in pipeline + chatbot + transcriber
  - Use when you want full local development services.

## 4) Frontend and Backend: What to Say in Meeting

### Frontend (what it does)
- Collects ticket details from users (text and optional audio flow).
- Supports role-based experiences (customer, employee, manager, operator).
- Sends ticket submissions to backend/orchestrator APIs.

### Backend (what it does)
- Owns user auth and token flow.
- Owns persistent ticket storage and status lifecycle.
- Exposes APIs consumed by frontend.
- Receives ticket decisions from orchestrator (priority, department, metadata).

### Database
- **PostgreSQL** stores users, tickets, assignments, statuses, and related operational records.

## 5) AI Pipeline (Main Talking Point)

The orchestrator processes submitted tickets as a pipeline of agents.

### Pipeline Goal
Convert raw submission data into a **decision-ready ticket**:
- classified
- sentiment-enriched
- feature-engineered
- prioritized
- routed

### Pipeline Steps

1. Input Intake
- Takes submitted text and optional audio context/features.
- If ticket type is already provided, classification can be skipped.

2. Classification Agent
- Uses classifier service (DistilRoBERTa-based complaint/inquiry classifier).
- Returns label + confidence.
- Uses safe fallback behavior when confidence is low.

3. Audio Analysis Agent (conditional)
- Runs only when audio context exists.
- Converts audio features into an audio sentiment signal.

4. Sentiment Analysis Agent (text)
- Runs local text sentiment inference (runtime model path configurable).
- If sentiment model artifact is missing, uses fallback predictor.
- Produces normalized text sentiment.

5. Sentiment Combiner Agent
- Combines text sentiment + audio sentiment into a single sentiment score/category.
- Provides a unified signal for downstream decisions.

6. Feature Engineering Agent
- Loads saved RF model artifacts from model state bundles.
- Predicts operational features:
  - business impact
  - safety concern
  - issue severity
  - issue urgency
  - recurrence (from upstream context/default)

7. Prioritization Agent (Fuzzy Logic)
- Uses fuzzy rule system + business modifiers.
- Inputs include sentiment, impact, severity, urgency, safety, recurrence, ticket type.
- Outputs final priority label/score.

8. Router/Storage Step
- Sends finalized complaint payload to backend ticket endpoint.
- Creates/stores ticket and returns ticket id.
- For inquiries, can route to chatbot flow.

## 6) AI Models and Decision Logic (Simple Breakdown)

When asked “what AI are you using?”, use this:

- **Classification model**: DistilRoBERTa-style complaint vs inquiry classifier.
- **Text sentiment model**: local sentiment inference runtime (transformer-based path; with fallback mode).
- **Audio sentiment**: audio-feature sentiment analyzer (energy/pitch/rate signals).
- **Feature engineering models**: saved **Random Forest** models for impact/safety/severity/urgency targets.
- **Prioritization**: **Fuzzy Logic engine** for explainable final priority decisions.

## 7) Why This Multi-Agent Design Works

Benefits to emphasize:
- Clear separation of concerns: each agent does one job well.
- Easier upgrades: replace one model without rewriting whole system.
- Better observability: step-by-step logs make debugging and demos easier.
- Explainability: fuzzy prioritization + explicit modifiers supports business justification.

## 8) End-to-End Flow (Presentation Script)

Use this script:

1. "User submits a ticket from the frontend."
2. "Backend/orchestrator trigger the AI pipeline."
3. "Pipeline classifies, scores sentiment, engineers operational features, and assigns priority."
4. "Final payload is routed/stored in backend with ticket id and priority."
5. "Operations teams use that output to respond faster and in the right order."

## 9) 30-Second Version

"InnovaCX is a layered system: React frontend, FastAPI backend with Postgres, and a LangChain-based orchestrator running multiple AI agents. The orchestrator takes ticket input, classifies complaint vs inquiry, computes text/audio sentiment, predicts operational features with Random Forest models, then applies fuzzy logic to assign explainable priority before routing the ticket. This makes the process modular, traceable, and easier to improve model-by-model."
