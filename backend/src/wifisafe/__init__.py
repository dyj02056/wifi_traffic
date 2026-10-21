"""wifisafe — 공공와이파이 위험요인 지표 채점 엔진.

※ 이 지도의 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.

[이 폴더(패키지)의 구성]
  파이썬에서 __init__.py가 있는 폴더는 '패키지'라고 부르며, 다른 코드에서 `from wifisafe import ...`로 불러 쓸 수 있습니다.
  - schema.py   : 공공데이터 원본 칸 이름 ↔ 코드 내부 이름 대응표, 지역 번호·지점 고유키 만들기
  - io.py       : 파일 읽기·쓰기 도우미 (CSV·JSON·YAML)
  - engine.py   : 원본 정제(clean) + 전체 채점(score) 흐름
  - rules.py    : 위험요인 R1~R8 판정 (R5는 density.py)
  - scoring.py  : 점수 공식(0~100점)과 등급
  - geo.py      : 이상한 좌표 찾기, 지도 화면 범위 계산
  - sensitivity.py : 민감도 분석(기준을 바꾸면 등급이 얼마나 바뀌나)
  - changes.py  : 날짜별 스냅샷 비교로 추가·삭제된 지점 찾기
  - explain.py, guardrails.py : 지점별 자동 설명 문장 만들기와 금지 표현 검사
  - safety_tips.py : 지점별 안전 수칙 문구
  - background.py, cases.py : 배경 통계·사례 카드 (점수에는 반영하지 않음)
  - bundle.py, assemble.py : 화면에 보낼 JSON 파일 묶음(번들) 만들기
  - db.py       : 번들을 데이터베이스에 저장하고 꺼내기
"""
