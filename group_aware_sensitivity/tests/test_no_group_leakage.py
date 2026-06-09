from __future__ import annotations

import pandas as pd

from src.config import PROJECT_ROOT


def test_saved_split_files_have_no_group_overlap() -> None:
    manifest = pd.read_csv(PROJECT_ROOT / "outputs" / "splits" / "split_manifest.csv")
    for row in manifest.itertuples(index=False):
        assert "\\" not in row.train_indices_file
        assert "\\" not in row.test_indices_file
        train = pd.read_csv(PROJECT_ROOT / row.train_indices_file)
        test = pd.read_csv(PROJECT_ROOT / row.test_indices_file)
        train_groups = set(train[row.group_column].astype(str))
        test_groups = set(test[row.group_column].astype(str))
        assert train_groups.isdisjoint(test_groups), row.split_id
