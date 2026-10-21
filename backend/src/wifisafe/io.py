"""경로 상수, 인코딩 자동 판별 CSV 읽기, JSON 쓰기, 스키마 검증.

[이 파일이 하는 일]
  여러 파일에서 공통으로 쓰는 '도구 상자'입니다.
  - 프로젝트 폴더 위치를 한곳에 정해 둔 상수 (CONFIG_DIR, DATA_DIR 등)
  - 한글 CSV 파일 읽기: 공공데이터 CSV는 UTF-8 또는 CP949(옛 한글 윈도우 방식)로 저장돼 있어 자동으로 판별한다
  - JSON·YAML 읽기/쓰기, 현재 시각·오늘 날짜
  - 스키마 검증: 만든 JSON 파일이 contracts/schemas/에 정한 모양을 지키는지 검사
    (스키마: "이 파일에는 이런 칸이 있고, 이 칸은 숫자여야 한다" 같은 규칙서)
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:   # API(Vercel)는 pandas 없이 이 모듈을 import한다 — pandas는 쓰는 함수 안에서 import
    import pandas as pd

# ── 폴더·파일 위치 ── (이 파일 위치에서 두 단계 위 = backend/ 폴더)
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent                       # 프로젝트 최상위 폴더
CONFIG_DIR = BACKEND_DIR / "config"                 # 사람이 정한 설정표
DATA_DIR = BACKEND_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "raw" / "snapshots"       # 날짜별 원본 데이터
MANIFEST_PATH = SNAPSHOT_DIR / "manifest.csv"       # 스냅샷 목록표
EXTERNAL_DIR = DATA_DIR / "external"                # 배경 통계 등 외부 자료
INTERIM_DIR = DATA_DIR / "interim"                  # 중간 결과(정제 후)
PROCESSED_DIR = DATA_DIR / "processed"              # 최종 결과(채점 후)
DIST_DATA_DIR = BACKEND_DIR / "dist" / "data"       # 화면용 번들을 내보내는 곳
CONTRACTS_DIR = REPO_DIR / "contracts"              # 백엔드·프론트엔드가 지킬 데이터 약속
SCHEMA_DIR = CONTRACTS_DIR / "schemas"
MOCK_DIR = CONTRACTS_DIR / "mock"
GOLDEN_PATH = CONTRACTS_DIR / "golden_scores.json"

# CSV를 읽을 때 차례로 시도해 볼 글자 인코딩 (utf-8-sig = 맨 앞에 BOM 표시가 붙은 UTF-8)
ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")


def load_env() -> None:
    """backend/.env 파일에 적힌 비밀값(DB 주소 등)을 환경변수로 불러온다. 도구가 설치돼 있지 않으면 건너뛴다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(BACKEND_DIR / ".env")


def app_mode() -> str:
    """APP_MODE 환경변수를 읽는다. dev(개발용, 기본값) 또는 final(발표용)만 허용."""
    mode = os.environ.get("APP_MODE", "dev").strip().lower()
    if mode not in ("dev", "final"):
        raise SystemExit(f"APP_MODE는 dev 또는 final 이어야 합니다: {mode!r}")
    return mode


def detect_encoding(path: Path) -> str:
    """파일을 각 인코딩으로 읽어 보고, 오류 없이 읽히는 첫 번째 인코딩을 돌려준다."""
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩 판별 실패({'/'.join(ENCODINGS)}): {path}")


def read_csv_any(path: Path) -> tuple[pd.DataFrame, str]:
    """인코딩을 자동 판별해 CSV를 읽는다. 모든 값을 글자로 읽고(숫자 변환 X), 칸 이름 앞뒤 공백을 지운다.

    돌려주는 값: (표, 판별된 인코딩)
    """
    import pandas as pd
    enc = detect_encoding(path)
    df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df, enc


def read_config_csv(name: str) -> pd.DataFrame:
    """config/ 폴더의 CSV(사람이 정한 표)를 읽는다."""
    import pandas as pd
    return pd.read_csv(CONFIG_DIR / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def read_yaml(path: Path) -> dict:
    """YAML 파일을 읽는다(YAML: 사람이 읽고 쓰기 쉬운 설정 파일 형식). 빈 파일이면 빈 dict."""
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(path: Path, obj, compact: bool = False) -> None:
    """JSON 파일을 쓴다. 폴더가 없으면 만든다.

    compact=True면 공백 없이 한 줄로(용량 절약), 아니면 들여쓰기해서 사람이 읽기 쉽게.
    ensure_ascii=False: 한글을 \\uXXXX로 바꾸지 않고 그대로 저장.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path: Path):
    """JSON 파일을 읽는다."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: Path, df: pd.DataFrame) -> None:
    """표를 CSV로 저장한다. 엑셀에서 한글이 깨지지 않도록 utf-8-sig로 쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def now_iso() -> str:
    """현재 시각을 표준 형식 글자로. 예) "2026-10-21T14:03:00+09:00" (+09:00 = 한국 시간)"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today() -> str:
    """오늘 날짜. 예) "2026-10-21" """
    return datetime.now().strftime("%Y-%m-%d")


def contract_version() -> str:
    """contracts/VERSION 파일에 적힌 데이터 약속 버전 번호."""
    return (CONTRACTS_DIR / "VERSION").read_text(encoding="utf-8").strip()


# ── 스키마 검증 ──────────────────────────────────────────────
# 번들 파일 이름(또는 폴더 이름) → 검사에 쓸 스키마 이름
_SCHEMA_FOR = {
    "meta.json": "meta", "rules.json": "rules", "regions.json": "regions",
    "key_index.json": "key_index", "background.json": "background", "cases.json": "cases",
    "points": "points", "detail": "detail", "changes": "changes", "sensitivity": "sensitivity",
}
SCHEMA_NAMES = ("meta", "rules", "regions", "points", "detail", "key_index",
                "changes", "sensitivity", "background", "cases")


def _registry():
    """스키마끼리 서로 참조할 수 있도록(예: _common.schema.json) 모든 스키마를 한 목록에 등록한다."""
    from referencing import Registry, Resource
    resources = []
    for p in SCHEMA_DIR.glob("*.schema.json"):
        doc = read_json(p)
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


def validator_for(name: str):
    """이름에 해당하는 스키마 검사기를 만든다. 예) "points" → points.schema.json 검사기"""
    from jsonschema import Draft202012Validator
    schema = read_json(SCHEMA_DIR / f"{name}.schema.json")
    return Draft202012Validator(schema, registry=_registry())


def schema_name_for(rel_path: str) -> str | None:
    """번들 안의 파일 경로로 어떤 스키마를 써야 하는지 찾는다. 예) "points/41-goyang.json" → "points" """
    rel = rel_path.replace("\\", "/")
    if "/" in rel:
        return _SCHEMA_FOR.get(rel.split("/")[0])
    return _SCHEMA_FOR.get(rel)


def validate_bundle(bundle_dir: Path) -> list[str]:
    """번들 디렉터리의 모든 JSON을 스키마로 검증. 오류 메시지 목록을 돌려준다(비면 통과).

    꼭 있어야 하는 파일(meta·rules·regions·key_index·background·cases)이 빠져도 오류로 적는다.
    """
    errors: list[str] = []
    validators = {n: validator_for(n) for n in SCHEMA_NAMES}
    seen = set()
    for p in sorted(Path(bundle_dir).rglob("*.json")):
        rel = p.relative_to(bundle_dir).as_posix()
        name = schema_name_for(rel)
        if name is None:
            continue
        seen.add(name)
        for e in validators[name].iter_errors(read_json(p)):
            errors.append(f"{rel}: {'/'.join(map(str, e.absolute_path))}: {e.message}")
    for required in ("meta", "rules", "regions", "key_index", "background", "cases"):
        if required not in seen:
            errors.append(f"필수 파일 없음: {required}.json")
    return errors
