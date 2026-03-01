#!/usr/bin/env bash

set -euo pipefail

source_branch="${1:-main}"
commit_message="${2:-Merge ${source_branch} into prod-live (preserve prod-live paths)}"

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
  exit 1
fi

if [[ ! -f ".gitattributes" ]]; then
  echo "Error: .gitattributes not found in repo root." >&2
  exit 1
fi

pre_merge_commit="$(git rev-parse HEAD)"

echo "Merging ${source_branch} into prod-live (without auto-commit)..."
if ! git merge --no-commit --no-ff "${source_branch}"; then
  echo
  echo "Merge stopped due to conflicts. Resolve conflicts and commit manually." >&2
  exit 1
fi

mapfile -t protected_paths < <(awk '!/^[[:space:]]*#/ && /merge=ours/ {print $1}' .gitattributes)

if (( ${#protected_paths[@]} > 0 )); then
  echo "Restoring protected paths from pre-merge prod-live commit..."
  for path in "${protected_paths[@]}"; do
    git checkout "${pre_merge_commit}" -- "${path}"
  done
  git add -- "${protected_paths[@]}"
fi

git commit -m "${commit_message}"
echo "Merge complete."
