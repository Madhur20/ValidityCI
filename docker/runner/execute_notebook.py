"""Container entry point for executing and instrumenting one notebook."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import time
from typing import Any

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError


SCHEMA_VERSION = "1.3.0"
INSTRUMENTATION_SCHEMA_VERSION = "1.0.0"
_COLLECTOR_MARKER = "__VALIDITYCI_RUNTIME_V1__"
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
        "environment": None,
        "runtime_trace": None,
    }


def _environment_fingerprint() -> dict[str, str]:
    packages = sorted(
        (
            distribution.metadata.get("Name", "").casefold(),
            distribution.version,
        )
        for distribution in metadata.distributions()
    )
    packages_payload = json.dumps(
        packages, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    packages_fingerprint = "sha256:" + hashlib.sha256(packages_payload).hexdigest()
    runner_fingerprint = "sha256:" + hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    environment = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "machine": platform.machine(),
        "packages_fingerprint": packages_fingerprint,
        "runner_fingerprint": runner_fingerprint,
    }
    payload = json.dumps(
        environment, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "fingerprint": "sha256:" + hashlib.sha256(payload).hexdigest(),
        **environment,
    }


def _instrumentation_source() -> str:
    metric_functions = repr(_SUPPORTED_METRIC_FUNCTIONS)
    return f"""
import functools as __validityci_functools
import hashlib as __validityci_hashlib
import hmac as __validityci_hmac
import json as __validityci_json
import numbers as __validityci_numbers
import secrets as __validityci_secrets
import numpy as __validityci_numpy
import pandas as __validityci_pandas
import scipy.sparse as __validityci_sparse
import sklearn.base as __validityci_sklearn_base
import sklearn.metrics as __validityci_sklearn_metrics
import sklearn.model_selection as __validityci_model_selection

__validityci_metric_events__ = []
__validityci_runtime_events__ = []
__validityci_fingerprint_key__ = __validityci_secrets.token_bytes(32)
__validityci_fingerprint_scope_id__ = "scope." + __validityci_secrets.token_hex(16)
__validityci_metric_functions__ = {metric_functions}
__validityci_safe_parameters__ = {{
    "average", "pos_label", "zero_division", "multi_class", "max_fpr"
}}

def __validityci_data_fingerprint(value, role):
    try:
        if isinstance(value, __validityci_pandas.DataFrame):
            hashed = __validityci_pandas.util.hash_pandas_object(
                value, index=True, categorize=True
            ).values.tobytes()
            data_type = "dataframe"
            rows, columns = value.shape
            descriptor = [str(dtype) for dtype in value.dtypes]
        elif isinstance(value, __validityci_pandas.Series):
            hashed = __validityci_pandas.util.hash_pandas_object(
                value, index=True, categorize=True
            ).values.tobytes()
            data_type = "series"
            rows, columns = len(value), None
            descriptor = str(value.dtype)
        elif __validityci_sparse.issparse(value):
            normalized = value.tocsr()
            hashed = b"".join((
                normalized.data.tobytes(),
                normalized.indices.tobytes(),
                normalized.indptr.tobytes(),
            ))
            data_type = "sparse_matrix"
            rows, columns = normalized.shape
            descriptor = str(normalized.dtype)
        elif isinstance(value, __validityci_numpy.ndarray):
            array = value
            if array.ndim == 0:
                return None
            if array.dtype.hasobject:
                hashed = __validityci_pandas.util.hash_array(
                    array.reshape(-1), categorize=True
                ).tobytes()
            else:
                hashed = __validityci_numpy.ascontiguousarray(array).tobytes()
            data_type = "ndarray"
            rows = len(array)
            columns = 1 if array.ndim == 1 else int(array.shape[1])
            descriptor = {{"dtype": str(array.dtype), "shape": list(array.shape)}}
        elif isinstance(value, (list, tuple)) and value:
            series = __validityci_pandas.Series(value)
            hashed = __validityci_pandas.util.hash_pandas_object(
                series, index=True, categorize=True
            ).values.tobytes()
            data_type = "sequence"
            rows, columns = len(value), None
            descriptor = str(series.dtype)
        else:
            return None
        metadata = __validityci_json.dumps(
            {{"type": data_type, "rows": rows, "columns": columns, "descriptor": descriptor}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = __validityci_hmac.new(
            __validityci_fingerprint_key__, metadata + b"\\0" + hashed,
            __validityci_hashlib.sha256,
        ).hexdigest()
        return {{
            "role": role,
            "fingerprint": "hmac-sha256:" + digest,
            "data_type": data_type,
            "row_count": int(rows),
            "column_count": None if columns is None else int(columns),
        }}
    except Exception:
        return None

def __validityci_fingerprint_many(values, prefix):
    fingerprints = []
    for index, value in enumerate(values):
        fingerprint = __validityci_data_fingerprint(value, f"{{prefix}}.{{index}}")
        if fingerprint is not None:
            fingerprints.append(fingerprint)
    return fingerprints

def __validityci_record_event(event_type, operation, inputs, outputs, parameters=None):
    cell_index = globals().get("__validityci_current_cell__")
    if not isinstance(cell_index, int):
        return
    input_fingerprints = __validityci_fingerprint_many(inputs, "input")
    output_fingerprints = __validityci_fingerprint_many(outputs, "output")
    if not input_fingerprints and not output_fingerprints:
        return
    sequence = len(__validityci_runtime_events__) + 1
    __validityci_runtime_events__.append({{
        "id": f"runtime.{{sequence}}",
        "sequence": sequence,
        "event_type": event_type,
        "operation": operation,
        "cell_index": cell_index,
        "inputs": input_fingerprints,
        "outputs": output_fingerprints,
        "parameters": parameters or {{}},
    }})

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
            __validityci_record_event(
                "metric",
                "sklearn.metrics." + __validityci_original.__name__,
                args[:2],
                (),
                parameters,
            )
        return result
    return __validityci_wrapped

for __validityci_name, __validityci_function_name in __validityci_metric_functions__.items():
    __validityci_original = getattr(__validityci_sklearn_metrics, __validityci_function_name)
    setattr(
        __validityci_sklearn_metrics,
        __validityci_function_name,
        __validityci_wrap_metric(__validityci_name, __validityci_original),
    )

__validityci_original_train_test_split__ = __validityci_model_selection.train_test_split
@__validityci_functools.wraps(__validityci_original_train_test_split__)
def __validityci_train_test_split(*args, **kwargs):
    result = __validityci_original_train_test_split__(*args, **kwargs)
    safe_parameters = {{
        key: value
        for key, value in kwargs.items()
        if key in {{"test_size", "train_size", "shuffle", "random_state"}}
        and (value is None or isinstance(value, (str, bool, int, float)))
    }}
    __validityci_record_event(
        "split", "sklearn.model_selection.train_test_split", args, result,
        safe_parameters,
    )
    return result
__validityci_model_selection.train_test_split = __validityci_train_test_split

__validityci_original_getattribute__ = __validityci_sklearn_base.BaseEstimator.__getattribute__
def __validityci_estimator_getattribute(self, name):
    attribute = __validityci_original_getattribute__(self, name)
    if name not in {{"fit", "fit_transform", "transform", "predict"}} or not callable(attribute):
        return attribute
    if getattr(attribute, "__validityci_wrapped__", False):
        return attribute
    @__validityci_functools.wraps(attribute)
    def __validityci_method(*args, **kwargs):
        result = attribute(*args, **kwargs)
        event_type = "transform" if name in {{"fit_transform", "transform"}} else name
        operation = type(self).__module__ + "." + type(self).__qualname__ + "." + name
        outputs = () if name == "fit" else (result,)
        __validityci_record_event(event_type, operation, args, outputs)
        return result
    __validityci_method.__validityci_wrapped__ = True
    return __validityci_method
__validityci_sklearn_base.BaseEstimator.__getattribute__ = __validityci_estimator_getattribute
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
__validityci_payload__ = {{
    "metrics": __validityci_events_to_return__,
    "runtime_trace": {{
        "schema_version": {INSTRUMENTATION_SCHEMA_VERSION!r},
        "fingerprint_scope_id": globals().get("__validityci_fingerprint_scope_id__"),
        "fingerprint_algorithm": "hmac-sha256",
        "events": list(globals().get("__validityci_runtime_events__", [])),
    }},
}}
print({_COLLECTOR_MARKER!r} + __validityci_json.dumps(__validityci_payload__, sort_keys=True))
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


def _extract_runtime(collector_cell: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for output in collector_cell.get("outputs", []):
        if output.get("output_type") != "stream":
            continue
        text = output.get("text", "")
        position = text.find(_COLLECTOR_MARKER)
        if position < 0:
            continue
        payload = json.loads(text[position + len(_COLLECTOR_MARKER):].strip())
        if not isinstance(payload, dict):
            raise TypeError("Runtime collector must return an object")
        events = payload.get("metrics")
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
        runtime_trace = payload.get("runtime_trace")
        if not isinstance(runtime_trace, dict):
            raise TypeError("Runtime collector must return a trace object")
        return artifacts, runtime_trace
    raise ValueError("Runtime collector output was not found")


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
        metrics, runtime_trace = _extract_runtime(notebook.cells[-1])
        _restore_notebook(notebook, original_cells)
        result = {
            "schema_version": SCHEMA_VERSION,
            "execution_id": args.execution_id,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - started) * 1000),
            "output_fingerprint": _fingerprint(notebook),
            "failure": None,
            "metrics": metrics,
            "environment": _environment_fingerprint(),
            "runtime_trace": runtime_trace,
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
