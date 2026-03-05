#!/usr/bin/env bash
# merge-main-into-prod-live.sh
#
# Merges a source branch (default: main) into prod-live while preserving
# all paths listed with merge=ours in .gitattributes.
#
# Usage (from prod-live branch):
#   ./scripts/merge-main-into-prod-live.sh           # merges main
#   ./scripts/merge-main-into-prod-live.sh <branch>  # merges another branch
#
# After this script completes:
#   git push origin prod-live
#
# VM update (after push):
#   cd /opt/innova-cx && git pull && docker compose --profile dev up --build -d

set -euo pipefail

source_branch="${1:-main}"
commit_message="${2:-Merge ${source_branch} into prod-live (preserve prod-live paths)}"

# --- Precondition checks ---

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${current_branch}" != "prod-live" ]]; then
  echo "Error: run this script from the prod-live branch (current: ${current_branch})." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: working tree is not clean. Commit or stash changes before merging." >&2
  exit 1
fi

if ! git rev-parse --verify "${source_branch}" >/dev/null 2>&1; then
  echo "Error: source branch '${source_branch}' was not found locally." >&2
  echo "Tip: run 'git fetch origin ${source_branch}:${source_branch}' first." >&2
  exit 1
fi

if [[ ! -f ".gitattributes" ]]; then
  echo "Error: .gitattributes not found in repo root." >&2
  exit 1
fi

# Ensure the 'ours' merge driver is registered in this clone
git config merge.ours.driver true

# --- Record pre-merge state ---

pre_merge_commit="$(git rev-parse HEAD)"

# --- Perform merge (staged only, no commit yet) ---

echo "→ Merging ${source_branch} into prod-live..."
if ! git merge --no-commit --no-ff "${source_branch}"; then
  echo
  echo "Merge stopped due to conflicts. Resolve all conflicts, then run:" >&2
  echo "  git add <resolved-files> && git commit -m \"${commit_message}\"" >&2
  exit 1
fi

# --- Restore protected paths to their prod-live pre-merge state ---
#
# Each path in .gitattributes with merge=ours must be preserved exactly as
# it was in prod-live before the merge. There are two cases:
#
#   (a) Path EXISTED in prod-live pre-merge  → restore to that version
#   (b) Path was ABSENT in prod-live pre-merge (intentionally deleted)
#       → remove it from the merge result so it stays absent
#
# The naive `git checkout ${pre_merge_commit} -- <path>` only handles (a).
# For (b) it would fatal-error, aborting the whole script.

mapfile -t protected_paths < <(awk '!/^[[:space:]]*#/ && /merge=ours/ {print $1}' .gitattributes)

if (( ${#protected_paths[@]} > 0 )); then
  echo "→ Restoring protected paths to their pre-merge prod-live state..."
  for path in "${protected_paths[@]}"; do
    if git ls-tree -r --name-only "${pre_merge_commit}" -- "${path}" 2>/dev/null | grep -q .; then
      # Case (a): path existed in prod-live — restore to pre-merge version
      git checkout "${pre_merge_commit}" -- "${path}" 2>/dev/null || true
      echo "   restored: ${path}"
    else
      # Case (b): path was absent in prod-live — remove it from merge result
      git rm -rf --cached --ignore-unmatch "${path}" > /dev/null 2>&1 || true
      rm -rf "${path}" 2>/dev/null || true
      echo "   kept absent: ${path}"
    fi
  done
  git add -A
fi

# --- Commit ---

git commit -m "${commit_message}"
echo "✓ Merge complete."
echo ""
echo "Next steps:"
echo "  git push origin prod-live"
echo "  VM: cd /opt/innova-cx && git pull && docker compose --profile dev up --build -d"
