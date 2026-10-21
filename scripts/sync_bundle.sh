#!/usr/bin/env bash
# backend/dist/data → web-draft/data, frontend/public/data
# contracts/mock    → web-draft/mock, frontend/public/mock
# contracts/golden_scores.json → web-draft/tests/golden_scores.json
# 실행(저장소 루트에서): bash scripts/sync_bundle.sh
#
# [이 파일이 하는 일]
#   백엔드가 만든 화면용 데이터 묶음(번들)과 정답표(golden)를 두 화면 프로젝트(web-draft, frontend)에 복사한다.
#   그러면 API 서버 없이도 화면이 이 파일들로 동작한다(백업 데이터). 윈도우용은 sync_bundle.ps1.
#   복사할 폴더는 먼저 지우고 새로 복사하므로, 옛 지역 파일이 남지 않는다.
# set -euo pipefail: 명령 하나라도 실패하거나 없는 변수를 쓰면 바로 멈춘다(반쯤 복사된 상태를 막음)
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
