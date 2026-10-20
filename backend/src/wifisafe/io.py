"""경로 상수, 인코딩 자동 판별 CSV 읽기, JSON 쓰기, 스키마 검증."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = BACKEND_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "raw" / "snapshots"
MANIFEST_PATH = SNAPSHOT_DIR / "manifest.csv"
EXTERNAL_DIR = DATA_DIR / "external"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
DIST_DATA_DIR = BACKEND_DIR / "dist" / "data"
CONTRACTS_DIR = REPO_DIR / "contracts"
SCHEMA_DIR = CONTRACTS_DIR / "schemas"
MOCK_DIR = CONTRACTS_DIR / "mock"
GOLDEN_PATH = CONTRACTS_DIR / "golden_scores.json"

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(BACKEND_DIR / ".env")


def app_mode() -> str:
    mode = os.environ.get("APP_MODE", "dev").strip().lower()
    if mode not in ("dev", "final"):
        raise SystemExit(f"APP_MODE는 dev 또는 final 이어야 합니다: {mode!r}")
    return mode


def detect_encoding(path: Path) -> str:
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩 판별 실패({'/'.join(ENCODINGS)}): {path}")


def read_csv_any(path: Path) -> tuple[pd.DataFrame, str]:
    enc = detect_encoding(path)
    df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df, enc


def read_config_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(CONFIG_DIR / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def read_yaml(path: Path) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(path: Path, obj, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def contract_version() -> str:
    return (CONTRACTS_DIR / "VERSION").read_text(encoding="utf-8").strip()


# ── 스키마 검증 ──────────────────────────────────────────────
_SCHEMA_FOR = {
    "meta.json": "meta", "rules.json": "rules", "regions.json": "regions",
    "key_index.json": "key_index", "background.json": "background", "cases.json": "cases",
    "points": "points", "detail": "detail", "changes": "changes", "sensitivity": "sensitivity",
}
SCHEMA_NAMES = ("meta", "rules", "regions", "points", "detail", "key_index",
                "changes", "sensitivity", "background", "cases")


def _registry():
    from referencing import Registry, Resource
    resources = []
    for p in SCHEMA_DIR.glob("*.schema.json"):
        doc = read_json(p)
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


def validator_for(name: str):
    from jsonschema import Draft202012Validator
    schema = read_json(SCHEMA_DIR / f"{name}.schema.json")
    return Draft202012Validator(schema, registry=_registry())


def schema_name_for(rel_path: str) -> str | None:
    rel = rel_path.replace("\\", "/")
    if "/" in rel:
        return _SCHEMA_FOR.get(rel.split("/")[0])
    return _SCHEMA_FOR.get(rel)


def validate_bundle(bundle_dir: Path) -> list[str]:
    """번들 디렉터리의 모든 JSON을 스키마로 검증. 오류 메시지 목록을 돌려준다(비면 통과)."""
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
