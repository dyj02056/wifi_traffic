"""R1 판정 검증: 구로구 'wifi접속환경'과 우리 SSID 라벨(open/secure)의 일치율 (plan.md §8.3-5, 발표 검증 슬라이드).

[이 파일이 하는 일]
  우리가 SSID 이름으로 정한 '개방형/보안접속' 분류가 맞는지 확인하는 검증입니다.
  서울 구로구는 자체 와이파이 데이터에 접속 방식(정답)을 적어 두었으므로,
  ① 구로구 데이터의 각 지점과 가장 가까운 전국 데이터 지점을 찾아 짝짓고(반경 match_radius_m 안, 같은 SSID 우선)
  ② 우리 분류(pred)와 구로구 정답(truth)이 얼마나 일치하는지 계산합니다.
  혼동행렬(confusion)은 "정답이 open인데 우리가 secure로 본 경우가 몇 개" 같은 표입니다.

입력: data/external/guro_wifi.csv, config/guro_validation.yaml(컬럼명·값 매핑 — 실제 파일 보고 채움)
출력: data/interim/guro_validation.csv, guro_validation_summary.json

실행: python pipeline/validate_guro.py
"""
import _bootstrap  # noqa: F401
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from wifisafe.density import EARTH_RADIUS_M
from wifisafe.engine import load_tables
from wifisafe.io import CONFIG_DIR, EXTERNAL_DIR, INTERIM_DIR, PROCESSED_DIR, read_csv_any, read_yaml, write_csv, \
    write_json


def main():
    path = EXTERNAL_DIR / "guro_wifi.csv"
    if not path.exists():
        raise SystemExit(f"{path} 없음 → 서울 열린데이터광장/data.go.kr 15147901에서 받아 이 경로에 두세요")
    cfg = read_yaml(CONFIG_DIR / "guro_validation.yaml")
    g, enc = read_csv_any(path)
    cols = cfg.get("columns") or {}
    need = [k for k in ("access_env", "lat", "lng") if not cols.get(k)]
    if need or not cfg.get("access_env_map"):
        print(f"guro_wifi.csv 컬럼({enc}): {list(g.columns)}")
        for c in g.columns:
            vals = g[c].value_counts().head(8).index.tolist()
            print(f"  {c}: {vals}")
        raise SystemExit(f"config/guro_validation.yaml 미완성: columns {need} / access_env_map — 위 실제 컬럼·값으로 채우세요")
    for k, c in cols.items():
        if c and c not in g.columns:
            raise SystemExit(f"guro_validation.yaml columns.{k}='{c}'가 CSV에 없음. 실제: {list(g.columns)}")

    g = g.assign(_lat=pd.to_numeric(g[cols["lat"]], errors="coerce"), _lng=pd.to_numeric(g[cols["lng"]], errors="coerce"),
                 _truth=g[cols["access_env"]].str.strip().map(cfg["access_env_map"]))
    unmapped = sorted(set(g.loc[g["_truth"].isna(), cols["access_env"]]))
    g = g.dropna(subset=["_lat", "_lng", "_truth"])
    g = g[g["_truth"] != "ignore"]

    d1 = pd.read_parquet(PROCESSED_DIR / "wifi_clean.parquet")
    d1 = d1[(d1["sido"] == cfg["d1_sido"]) & (d1["sigungu"] == cfg["d1_sigungu"])].reset_index(drop=True)
    tables, status = load_tables()
    d1["pred"] = d1["ssid"].map(tables.ssid_labels).fillna("unlabeled")

    # 구로구 지점마다 가까운 전국 데이터 지점 5곳을 찾고, 반경 안 + SSID가 같은 것을 우선으로 짝짓는다
    tree = BallTree(np.radians(d1[["lat", "lng"]].to_numpy(float)), metric="haversine")
    dist, idx = tree.query(np.radians(g[["_lat", "_lng"]].to_numpy(float)), k=min(5, len(d1)))
    rows = []
    for (_, gr), ds, ix in zip(g.iterrows(), dist, idx):
        cand = [(d * EARTH_RADIUS_M, i) for d, i in zip(ds, ix) if d * EARTH_RADIUS_M <= cfg["match_radius_m"]]
        if cols.get("ssid"):
            same = [(d, i) for d, i in cand if d1.at[i, "ssid"] == str(gr[cols["ssid"]]).strip()]
            cand = same or cand
        if not cand:
            rows.append({"truth": gr["_truth"], "matched": False})
            continue
        d, i = cand[0]
        rows.append({"truth": gr["_truth"], "matched": True, "distance_m": round(d, 1), "d1_key": d1.at[i, "key"],
                     "d1_ssid": d1.at[i, "ssid"], "pred": d1.at[i, "pred"]})
    res = pd.DataFrame(rows)
    write_csv(INTERIM_DIR / "guro_validation.csv", res)
    # 일치율은 우리 분류가 open/secure로 정해진 지점만 대상으로 계산한다(unknown·미분류는 따로 셈)
    m = res[res["matched"]] if len(res) else res
    judged = m[m["pred"].isin(["open", "secure"])] if len(m) else m
    summary = {
        "guro_rows_used": int(len(g)), "matched": int(len(m)), "match_radius_m": cfg["match_radius_m"],
        "judged_open_or_secure": int(len(judged)),
        "agreement": round(float((judged["pred"] == judged["truth"]).mean()), 4) if len(judged) else None,
        "pred_unknown_or_unlabeled": int((~m["pred"].isin(["open", "secure"])).sum()) if len(m) else 0,
        "confusion": (pd.crosstab(judged["truth"], judged["pred"]).to_dict() if len(judged) else {}),
        "unmapped_access_env_values": unmapped, "r1_confirmed": status["r1_confirmed"],
        "config_status": cfg.get("status"),
    }
    write_json(INTERIM_DIR / "guro_validation_summary.json", summary)
    print(f"[validate_guro] 구로구 {summary['guro_rows_used']}행 중 매칭 {summary['matched']}행, "
          f"판정 가능 {summary['judged_open_or_secure']}행, 일치율 {summary['agreement']}")
    print(f"  혼동행렬(truth→pred): {summary['confusion']}")


if __name__ == "__main__":
    main()
