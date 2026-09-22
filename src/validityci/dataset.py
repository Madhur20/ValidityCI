from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path

from validityci.schemas import DatasetProfile


def profile_csv(path: str | Path, target_column: str) -> DatasetProfile:
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        if target_column not in columns:
            raise ValueError(
                f"Target column '{target_column}' was not found. Available columns: {', '.join(columns)}"
            )

        counts: Counter[str] = Counter()
        row_count = 0
        for row in reader:
            row_count += 1
            counts[str(row[target_column])] += 1

    if row_count == 0:
        raise ValueError("Dataset contains no data rows")
    if len(counts) != 2:
        raise ValueError(
            f"Iteration one supports binary classification; found {len(counts)} target classes"
        )

    minority_fraction = min(counts.values()) / row_count
    return DatasetProfile(
        path=str(dataset_path),
        row_count=row_count,
        columns=columns,
        target_column=target_column,
        class_counts=dict(sorted(counts.items())),
        minority_fraction=minority_fraction,
    )
