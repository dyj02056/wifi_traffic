# [이 테스트가 확인하는 것]
#   점수 계산 파일들이 배경 통계(background) 모듈을 불러오지 않는지 코드 자체를 읽어 확인한다.
#   범죄·침해 통계가 실수로라도 점수에 섞이지 않게 하는 '격리' 검사.
"""점수 모듈은 배경(범죄 통계) 모듈을 import하지 않는다 (plan.md §0-4)."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "wifisafe"
SCORING_MODULES = ("scoring.py", "rules.py", "density.py", "engine.py", "sensitivity.py")


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return names


def test_scoring_modules_do_not_import_background():
    for m in SCORING_MODULES:
        names = imported_names(SRC / m)
        assert not any("background" in n or "cases" in n for n in names), f"{m}: {names}"
