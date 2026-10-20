#!/usr/bin/env bash
# backend/dist/data → web-draft/data, frontend/public/data
# contracts/mock    → web-draft/mock, frontend/public/mock
# contracts/golden_scores.json → web-draft/tests/golden_scores.json
# 실행(저장소 루트에서): bash scripts/sync_bundle.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/backend/dist/data"
MOCK="$ROOT/contracts/mock"

copy_dir() {  # src dst
  rm -rf "$2"
  mkdir -p "$2"
  cp -r "$1/." "$2/"
  echo "  $1 → $2 ($(find "$2" -name '*.json' | wc -l | tr -d ' ') files)"
}

echo "[sync_bundle]"
if [ -f "$DIST/meta.json" ]; then
  copy_dir "$DIST" "$ROOT/web-draft/data"
  [ -d "$ROOT/frontend" ] && copy_dir "$DIST" "$ROOT/frontend/public/data"
else
  echo "  backend/dist/data 없음 — 실데이터 번들은 건너뜀 (python pipeline/export_bundle.py 먼저)"
fi
copy_dir "$MOCK" "$ROOT/web-draft/mock"
[ -d "$ROOT/frontend" ] && copy_dir "$MOCK" "$ROOT/frontend/public/mock"
cp "$ROOT/contracts/golden_scores.json" "$ROOT/web-draft/tests/golden_scores.json"
echo "  contracts/golden_scores.json → web-draft/tests/golden_scores.json"
