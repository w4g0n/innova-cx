# Prod-Live Branch Runbook

This document defines how `prod-live` is maintained for cloud production.

## Goal
`prod-live` is the deployment branch.
Some repository paths are intentionally kept different from `main` and must never be overwritten by merge updates.

## Protected Paths (Keep `prod-live` version)
These are enforced in `.gitattributes` with `merge=ours`:

- `README.md`
- `test.csv`
- `CLOUD_README.md`
- `deslop.pdf`
- `data/`
- `postman/`
- `docs/`
- `Prototype/`
- `database/documentation/`
- `ai-models/docs/`
- `ai-models/readme.md`
- `ai-models/README.md`
- `ai-models/legacy/`
- `frontend/readme.md`
- `frontend/README.md`
- `backend/readme.md`
- `backend/README.md`

## Required Git Config in Cloud/CI
`merge=ours` requires the merge driver to be configured in the merge environment.
Run this in the cloud runner/server before merge operations:

```bash
git config merge.ours.driver true
```

If this is missing, protected-path merge behavior is not guaranteed.

## Standard Merge Flow (`main` -> `prod-live`)
Always use the repo script so protected paths are restored to pre-merge `prod-live` state.

1. Checkout `prod-live`.
2. Ensure working tree is clean.
3. Run `./scripts/merge-main-into-prod-live.sh main`.
4. Run smoke tests / startup checks.
5. Push and deploy.

Example:

```bash
git checkout prod-live
git pull origin prod-live
./scripts/merge-main-into-prod-live.sh main
git push origin prod-live
```

## Branch Promotion Rules

Allowed branch flow:

- `feature/*` -> `dev`
- `dev` -> `main`
- `main` -> `prod-live`

Blocked flow:

- `prod-live` -> `main` or `dev`
- any non-`dev` branch -> `main`
- any non-`main` branch -> `prod-live`

CI enforces these rules on pull requests.

## One-Time Cleanup Policy
For paths that should not exist in `prod-live`, remove them once on `prod-live` and commit the deletion.
After that, protected path rules keep them from being reintroduced during merges.

## Model Files on `prod-live`
`prod-live` model artifacts should be stored in persistent Docker volumes, not committed to Git.
In this repo, `docker-compose.yml` already keeps model storage via named volumes:

- `hf_cache` mounted to `/app/hf_cache`
- `chatbot_models` mounted to `/app/models`

This keeps model files safe across `main` -> `prod-live` merges and container rebuilds.

If you still keep any model artifacts in protected Git paths (for example under `data/`), they should:

1. Stay on `prod-live` across merges from `main`.
2. Be used at runtime only if service config/env points to those exact model paths.

Always verify runtime env vars and model paths after deployment.

## Quick Verification Commands

```bash
# show protected-path rules
cat .gitattributes

# confirm working tree is clean
git status

# inspect files changed by latest merge/commit
git show --name-status --oneline -1
```
