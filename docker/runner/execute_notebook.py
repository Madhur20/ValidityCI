"""Container entry point for executing and instrumenting one notebook."""

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


SCHEMA_VERSION = "1.1.0"
_METRIC_MARKER = "__VALIDITYCI_METRICS_V1__"
_SUPPORTED_METRIC_FUNCTIONS = {
    "accuracy": "accuracy_score",
    "balanced_accuracy": "balanced_accuracy_score",
    "f1": "f1_score",
    "precision": "precision_score",
    "recall": "recall_score",
    "roc_auc": "roc_auc_score",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--notebook", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell-timeout", required=True, type=int)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    parser.add_argument("--metric-name", choices=sorted(_SUPPORTED_METRIC_FUNCTIONS))
    parser.add_argument("--metric-variable")
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
        "failure": {"kind": kind, "message": message, "cell_index": cell_index},
        "metrics": [],
    }


def _instrumentation_source() -> str:
    metric_functions = repr(_SUPPORTED_METRIC_FUNCTIONS)
    return f"""
import functools as __validityci_functools
import numbers as __validityci_numbers
import sklearn.metrics as __validityci_sklearn_metrics

__validityci_metric_events__ = []
__validityci_metric_functions__ = {metric_functions}
__validityci_safe_parameters__ = {{
    "average", "pos_label", "zero_division", "multi_class", "max_fpr"
}}

def __validityci_wrap_metric(__validityci_metric_name, __validityci_original):
    @__validityci_functools.wraps(__validityci_original)
    def __validityci_wrapped(*args, **kwargs):
        result = __validityci_original(*args, **kwargs)
        if isinstance(result, __validityci_numbers.Real) and not isinstance(result, bool):
            try:
                sample_count = len(args[0]) if args else None
            except TypeError:
                sample_count = None
            parameters = {{
                key: value
                for key, value in kwargs.items()
                if key in __validityci_safe_parameters__
                and (value is None or isinstance(value, (str, bool, int, float)))
            }}
            __validityci_metric_events__.append({{
                "metric_name": __validityci_metric_name,
                "value": float(result),
                "cell_index": globals().get("__validityci_current_cell__"),
                "sample_count": sample_count,
                "parameters": parameters,
                "capture_method": "runtime_wrapper",
            }})
        return result
    return __validityci_wrapped

for __validityci_name, __validityci_function_name in __validityci_metric_functions__.items():
    __validityci_original = getattr(__validityci_sklearn_metrics, __validityci_function_name)
    setattr(
        __validityci_sklearn_metrics,
        __validityci_function_name,
        __validityci_wrap_metric(__validityci_name, __validityci_original),
    )
""".lstrip()


def _collector_source(metric_name: str | None, variable_name: str | None) -> str:
    return f"""
import json as __validityci_json
import math as __validityci_math
import numbers as __validityci_numbers

__validityci_expected_metric__ = {metric_name!r}
__validityci_metric_variable__ = {variable_name!r}
__validityci_events_to_return__ = list(globals().get("__validityci_metric_events__", []))
__validityci_expected_seen__ = any(
    event.get("metric_name") == __validityci_expected_metric__
    for event in __validityci_events_to_return__
)
if __validityci_expected_metric__ and not __validityci_expected_seen__:
    __validityci_fallback__ = globals().get(__validityci_metric_variable__) if __validityci_metric_variable__ else None
    if (
        isinstance(__validityci_fallback__, __validityci_numbers.Real)
        and not isinstance(__validityci_fallback__, bool)
        and __validityci_math.isfinite(float(__validityci_fallback__))
    ):
        __validityci_events_to_return__.append({{
            "metric_name": __validityci_expected_metric__,
            "value": float(__validityci_fallback__),
            "cell_index": None,
            "sample_count": None,
            "parameters": {{}},
            "capture_method": "manifest_variable",
        }})
    else:
        __validityci_reason__ = (
            f"No supported runtime call was observed and manifest variable "
            f"{{__validityci_metric_variable__!r}} was not a finite number"
            if __validityci_metric_variable__
            else "No supported runtime call was observed and no manifest variable was configured"
        )
        __validityci_events_to_return__.append({{
            "metric_name": __validityci_expected_metric__,
            "status": "unsupported",
            "capture_method": "not_observed",
            "reason": __validityci_reason__,
        }})
print({_METRIC_MARKER!r} + __validityci_json.dumps(__validityci_events_to_return__, sort_keys=True))
""".lstrip()


def _prepare_notebook(
    notebook: Any, metric_name: str | None, variable_name: str | None
) -> list[Any]:
    original_cells = list(notebook.cells)
    execution_cells = [nbformat.v4.new_code_cell(_instrumentation_source())]
    for index, cell in enumerate(original_cells):
        if cell.get("cell_type") == "code":
            execution_cells.append(
                nbformat.v4.new_code_cell(
                    f"__validityci_current_cell__ = {index}\n"
                )
            )
        execution_cells.append(cell)
    execution_cells.append(
        nbformat.v4.new_code_cell(_collector_source(metric_name, variable_name))
    )
    notebook.cells = execution_cells
    return original_cells


def _restore_notebook(notebook: Any, original_cells: list[Any]) -> None:
    notebook.cells = original_cells


def _extract_metrics(collector_cell: Any) -> list[dict[str, Any]]:
    for output in collector_cell.get("outputs", []):
        if output.get("output_type") != "stream":
            continue
        text = output.get("text", "")
        position = text.find(_METRIC_MARKER)
        if position < 0:
            continue
        events = json.loads(text[position + len(_METRIC_MARKER):].strip())
        if not isinstance(events, list):
            raise TypeError("Metric collector must return an array")
        artifacts = []
        for index, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                raise TypeError("Metric collector entries must be objects")
            unsupported = event.get("status") == "unsupported"
            artifacts.append(
                {
                    "id": f"metric.{index}",
                    "metric_name": event["metric_name"],
                    "status": "unsupported" if unsupported else "captured",
                    "capture_method": event["capture_method"],
                    "value": None if unsupported else event["value"],
                    "cell_index": None if unsupported else event.get("cell_index"),
                    "sample_count": None if unsupported else event.get("sample_count"),
                    "parameters": {} if unsupported else event.get("parameters", {}),
                    "reason": event.get("reason") if unsupported else None,
                }
            )
        return artifacts
    raise ValueError("Metric collector output was not found")


def _cell_error(original_cells: list[Any]) -> tuple[int | None, str]:
    for index, cell in enumerate(original_cells):
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
            "outputs": [
                {
                    key: value
                    for key, value in output.items()
                    if key not in {"execution_count", "transient"}
                }
                for output in cell.get("outputs", [])
            ],
        }
        for index, cell in enumerate(notebook.cells)
        if cell.get("cell_type") == "code"
    ]
    canonical = json.dumps(
        outputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def main() -> None:
    args = _parser().parse_args()
    started = time.monotonic()
    notebook = None
    original_cells: list[Any] = []
    try:
        notebook = nbformat.read(args.notebook, as_version=4)
        original_cells = _prepare_notebook(
            notebook, args.metric_name, args.metric_variable
        )
        client = NotebookClient(
            notebook,
            timeout=args.cell_timeout,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(args.notebook.parent)}},
        )
        client.execute()
        metrics = _extract_metrics(notebook.cells[-1])
        _restore_notebook(notebook, original_cells)
        result = {
            "schema_version": SCHEMA_VERSION,
            "execution_id": args.execution_id,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - started) * 1000),
            "output_fingerprint": _fingerprint(notebook),
            "failure": None,
            "metrics": metrics,
        }
    except CellExecutionError:
        cell_index, message = _cell_error(original_cells)
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
