-- Neon(Postgres + PostGIS) 스키마 (docs/requests.md #15). 여러 번 실행해도 안전하다(IF NOT EXISTS).
-- 적용: python pipeline/db_migrate.py   (DATABASE_URL 필요)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 수집한 원본 스냅샷 기록 (원본 파일 자체는 저장하지 않는다 — 무료 0.5GB 한도)
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_date date PRIMARY KEY,
    sha256        text NOT NULL,
    rows          integer NOT NULL,
    source_url    text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now()
);

-- 최신 스냅샷의 정제 결과만 보관. 다음 수집 때 이것과 비교해 추가·삭제를 찾는다.
CREATE TABLE IF NOT EXISTS wifi_current (
    key        text PRIMARY KEY,
    region_id  text NOT NULL,
    sido       text NOT NULL,
    sigungu    text NOT NULL,
    place_name text,
    ssid       text,
    lat        double precision NOT NULL,
    lng        double precision NOT NULL,
    geom       geography(Point, 4326) NOT NULL,
    record     jsonb NOT NULL          -- clean_frame() 한 행 전체
);
CREATE INDEX IF NOT EXISTS wifi_current_geom_idx ON wifi_current USING gist (geom);
CREATE INDEX IF NOT EXISTS wifi_current_region_idx ON wifi_current (region_id);

-- 스냅샷 사이 추가·삭제 이력 (wifisafe.changes.CHANGE_COLS)
CREATE TABLE IF NOT EXISTS wifi_changes (
    snapshot_from date NOT NULL,
    snapshot_to   date NOT NULL,
    key           text NOT NULL,
    change        text NOT NULL CHECK (change IN ('added', 'removed')),
    region_id     text NOT NULL,
    sido          text,
    sigungu       text,
    place_name    text,
    ssid          text,
    lat           double precision NOT NULL,
    lng           double precision NOT NULL,
    PRIMARY KEY (snapshot_to, key, change)
);
CREATE INDEX IF NOT EXISTS wifi_changes_region_idx ON wifi_changes (region_id);

-- 화면용 문서(contracts/ 스키마와 같은 JSON). path = 정적 번들 상대경로 (예: points/11-seocho.json)
CREATE TABLE IF NOT EXISTS bundle_docs (
    path       text PRIMARY KEY,
    doc        jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 회원 (구글·네이버 로그인, requests #19). 이메일 등 지역 외 개인정보는 저장하지 않는다.
CREATE TABLE IF NOT EXISTS users (
    id           bigserial PRIMARY KEY,
    provider     text NOT NULL CHECK (provider IN ('google', 'naver', 'dev')),
    provider_id  text NOT NULL,
    display_name text NOT NULL,
    sido         text,
    sigungu      text,
    region_id    text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_id)
);
