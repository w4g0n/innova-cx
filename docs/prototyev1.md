# Changes Since Last Commit

Generated: 2026-02-23 01:51:50 +04

## Quick Summary

- Total pending file changes: **129**
- Modified tracked files: **10**
- Deleted tracked files: **111**
- New untracked files (inside new folders): **112**
- New untracked paths (as shown by `git status`): **8**

## Human-Readable Highlights

- Multi-agent pipeline was restructured: active runtime orchestrator moved under `ai-models/MultiAgentPipeline/Orchestrator`.
- Legacy model/training code was moved out of active pipeline paths into `ai-models/legacy/...`.
- Backend services were reorganized (chatbot/transcriber moved under `backend/services/...`; old paths removed).
- Docker/profile setup and compose wiring were updated (frontend/pipeline/dev model).
- Frontend auth flow gained a skip-view selector path for quick role testing.
- Orchestrator agent import/logging fixes were applied for runtime stability and cleaner logs.