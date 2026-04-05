#!/bin/sh
set -eu

LOCK_HASH="$(sha256sum package-lock.json | awk '{print $1}')"
HASH_FILE="node_modules/.package-lock.hash"
CURRENT_HASH=""

if [ -f "$HASH_FILE" ]; then
  CURRENT_HASH="$(cat "$HASH_FILE" || true)"
fi

if [ ! -d node_modules ] || [ "$LOCK_HASH" != "$CURRENT_HASH" ]; then
  echo "Installing frontend dependencies with npm ci..."
  npm ci
  mkdir -p node_modules
  echo "$LOCK_HASH" > "$HASH_FILE"
else
  echo "Frontend dependencies are up to date."
fi

echo "Building for production..."
npm run build

echo "Starting preview server..."
exec npm run preview -- --host --port 5173