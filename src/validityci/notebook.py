from __future__ import annotations

import json
from pathlib import Path

from validityci.schemas import NotebookCell, NotebookSummary


def inspect_notebook(path: str | Path) -> NotebookSummary:
    notebook_path = Path(path)
    with notebook_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    raw_cells = raw.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("Notebook does not contain a valid cells list")

    cells: list[NotebookCell] = []
    for index, raw_cell in enumerate(raw_cells):
        if not isinstance(raw_cell, dict):
            continue
        cell_type = str(raw_cell.get("cell_type", "unknown"))
        source_value = raw_cell.get("source", "")
        if isinstance(source_value, list):
            source = "".join(str(part) for part in source_value)
        else:
            source = str(source_value)
        cells.append(NotebookCell(index=index, cell_type=cell_type, source=source))

    return NotebookSummary(
        path=str(notebook_path),
        total_cells=len(cells),
        code_cells=sum(cell.cell_type == "code" for cell in cells),
        markdown_cells=sum(cell.cell_type == "markdown" for cell in cells),
        cells=tuple(cells),
    )


def cells_containing(summary: NotebookSummary, terms: tuple[str, ...]) -> tuple[int, ...]:
    lowered_terms = tuple(term.lower() for term in terms)
    return tuple(
        cell.index
        for cell in summary.cells
        if cell.cell_type == "code"
        and any(term in cell.source.lower() for term in lowered_terms)
    )
