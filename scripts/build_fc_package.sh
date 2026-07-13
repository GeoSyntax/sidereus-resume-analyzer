#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-dist/fc-backend}"
OUTPUT="$ROOT/$OUTPUT_DIR"
BACKEND="$ROOT/backend"

rm -rf "$OUTPUT"
mkdir -p "$OUTPUT"

cp -R "$BACKEND/app" "$OUTPUT/app"
cp "$BACKEND/bootstrap" "$OUTPUT/bootstrap"
cp "$BACKEND/requirements-prod.txt" "$OUTPUT/requirements-prod.txt"

python -m pip install -r "$BACKEND/requirements-prod.txt" -t "$OUTPUT" --upgrade
chmod +x "$OUTPUT/bootstrap"

echo "FC package prepared at $OUTPUT"

