"""pipeline/ 스크립트가 config·wifisafe를 import할 수 있게 경로를 잡는다."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from wifisafe.io import load_env  # noqa: E402

load_env()
