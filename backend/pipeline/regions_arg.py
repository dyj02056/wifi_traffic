"""--sido/--sigungu/--region 인자 → region_id 목록 (pipeline 공용).

[이 파일이 하는 일]
  여러 pipeline 스크립트가 "어느 지역을 처리할지"를 같은 방식으로 받도록 돕는 공용 도구입니다.
  예) python pipeline/score.py --sido 서울특별시 --sigungu 구로구   또는   --region 11-guro
"""
import pandas as pd


def add_region_args(ap):
    """명령줄 인자 정의에 --region, --sido, --sigungu 세 가지를 추가한다."""
    ap.add_argument("--region", help="region_id (쉼표로 여러 개, 예: 11-guro)")
    ap.add_argument("--sido", help="시도명 (예: 서울특별시)")
    ap.add_argument("--sigungu", help="시군구명 (예: 구로구)")


def resolve_regions(df: pd.DataFrame, args, required: bool = False) -> list[str]:
    """입력한 인자를 실제 region_id 목록으로 바꾼다.

    - --region이 있으면 그대로 쓰되 데이터에 있는지 확인
    - 없으면 --sido/--sigungu 이름으로 찾는다. 시군구 이름이 여러 시도에 있으면(예: 중구) --sido를 요구한다
    - 아무것도 안 주면 빈 목록(= 전국). required=True면 오류
    """
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
