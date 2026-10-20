import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "src", BACKEND / "pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
