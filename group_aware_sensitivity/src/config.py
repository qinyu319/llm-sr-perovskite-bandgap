from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else PROJECT_ROOT / "configs" / "group_aware_config.yaml"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_config_path"] = str(path)
    cfg["_project_root"] = str(PROJECT_ROOT)
    return cfg


def resolve_from_root(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def ensure_output_dirs() -> None:
    for rel in [
        "data",
        "outputs/group_labels",
        "outputs/splits/composition_family",
        "outputs/splits/halide_logo",
        "outputs/splits/a_site_logo",
        "outputs/per_split_results",
        "outputs/summary_tables",
        "outputs/figures",
    ]:
        (PROJECT_ROOT / rel).mkdir(parents=True, exist_ok=True)
