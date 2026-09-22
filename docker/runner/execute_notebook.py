"""Container entry point for executing one staged notebook."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError


SCHEMA_VERSION = "1.0.0"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--notebook", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell-timeout", required=True, type=int)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    return parser


def _failure(
    execution_id: str,
    status: str,
    duration_ms: int,
    kind: str,
    message: str,
    cell_index: int | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_id": execution_id,
        "status": status,
        "duration_ms": duration_ms,
        "output_fingerprint": None,
        "failure": {
            "kind": kind,
            "message": message,
            "cell_index": cell_index,
        },
    }


def _cell_error(notebook: Any) -> tuple[int | None, str]:
    for index, cell in enumerate(notebook.cells):
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                name = output.get("ename", "CellExecutionError")
                value = output.get("evalue", "Notebook cell failed")
                return index, f"{name}: {value}"
    return None, "Notebook cell failed"


def _fingerprint(notebook: Any) -> str:
    outputs = [
        {
            "cell_index": index,
            "outputs": cell.get("outputs", []),
        }
        for index, cell in enumerate(notebook.cells)
        if cell.get("cell_type") == "code"
    ]
    canonical = json.dumps(
        outputs,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def main() -> None:
    args = _parser().parse_args()
    started = time.monotonic()
    notebook = None
    try:
        notebook = nbformat.read(args.notebook, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=args.cell_timeout,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(args.notebook.parent)}},
        )
        client.execute()
        result = {
            "schema_version": SCHEMA_VERSION,
            "execution_id": args.execution_id,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - started) * 1000),
            "output_fingerprint": _fingerprint(notebook),
            "failure": None,
        }
    except CellExecutionError:
        cell_index, message = _cell_error(notebook)
        result = _failure(
            args.execution_id,
            "cell_failed",
            round((time.monotonic() - started) * 1000),
            "notebook_cell_error",
            message,
            cell_index,
        )
    except CellTimeoutError as error:
        result = _failure(
            args.execution_id,
            "timed_out",
            round((time.monotonic() - started) * 1000),
            "cell_timeout",
            str(error) or "Notebook cell exceeded its timeout",
        )
    except Exception as error:
        result = _failure(
            args.execution_id,
            "runner_error",
            round((time.monotonic() - started) * 1000),
            "notebook_execution_error",
            f"{type(error).__name__}: {error}",
        )

    serialized = json.dumps(result, sort_keys=True).encode("utf-8")
    if len(serialized) > args.max_output_bytes:
        result = _failure(
            args.execution_id,
            "runner_error",
            round((time.monotonic() - started) * 1000),
            "output_limit",
            "The execution result exceeded the configured output limit",
        )
        serialized = json.dumps(result, sort_keys=True).encode("utf-8")
    args.output.write_bytes(serialized)


if __name__ == "__main__":
    main()
