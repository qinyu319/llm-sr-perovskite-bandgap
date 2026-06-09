from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.data_validation import load_and_validate


def main() -> None:
    cfg = load_config()
    result = load_and_validate(cfg)
    print(f"Training raw rows: {len(result.train_raw)}")
    print(f"Training valid rows: {len(result.curated)}")
    print(f"Training rows excluded by strict QC: {len(result.train_invalid)}")
    print(f"External test rows isolated from selection: {len(result.test_raw)}")


if __name__ == "__main__":
    main()
