"""--sido/--sigungu/--region 인자 → region_id 목록 (pipeline 공용)."""
import pandas as pd


def add_region_args(ap):
    ap.add_argument("--region", help="region_id (쉼표로 여러 개, 예: 11-guro)")
    ap.add_argument("--sido", help="시도명 (예: 서울특별시)")
    ap.add_argument("--sigungu", help="시군구명 (예: 구로구)")


def resolve_regions(df: pd.DataFrame, args, required: bool = False) -> list[str]:
    if args.region:
        ids = [r.strip() for r in args.region.split(",") if r.strip()]
        unknown = sorted(set(ids) - set(df["region_id"]))
        if unknown:
            raise SystemExit(f"없는 region_id: {unknown}")
        return ids
    sub = df
    if args.sido:
        sub = sub[sub["sido"] == args.sido]
    if args.sigungu:
        sub = sub[sub["sigungu"] == args.sigungu]
    if not (args.sido or args.sigungu):
        if required:
            raise SystemExit("--region 또는 --sido/--sigungu를 지정하세요")
        return []
    ids = sorted(sub["region_id"].unique())
    if not ids:
        raise SystemExit(f"해당 지역 없음: sido={args.sido} sigungu={args.sigungu}")
    if args.sigungu and not args.sido and len(ids) > 1:
        names = sub.drop_duplicates("region_id")[["region_id", "sido"]].values.tolist()
        raise SystemExit(f"시군구명 '{args.sigungu}'가 여러 시도에 있습니다: {names} → --sido도 지정하세요")
    return ids
