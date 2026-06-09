from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT
from src.excel_report import build_excel_report


def main() -> None:
    decision_path = PROJECT_ROOT / "outputs" / "summary_tables" / "group_aware_decision.txt"
    decision = decision_path.read_text(encoding="utf-8").strip()
    out = build_excel_report(decision)
    print(out)


if __name__ == "__main__":
    main()
