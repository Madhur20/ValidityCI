"""Versioned data contracts used by ValidityCI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeAlias, cast
import tomllib


REPORT_SCHEMA_VERSION = "1.4.0"
EXECUTION_SCHEMA_VERSION = "1.3.0"
INSTRUMENTATION_SCHEMA_VERSION = "1.0.0"
SUPPORTED_TASKS = frozenset({"binary_classification"})
SUPPORTED_METRICS = frozenset(
    {"accuracy", "balanced_accuracy", "f1", "precision", "recall", "roc_auc"}
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, Any]


class AuditStatus(StrEnum):
    ATTENTION_REQUIRED = "attention_required"
    INCOMPLETE = "incomplete"
    PASSED_SUPPORTED_CHECKS = "passed_supported_checks"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    CELL_FAILED = "cell_failed"
    TIMED_OUT = "timed_out"
    RUNNER_ERROR = "runner_error"


class MetricCaptureStatus(StrEnum):
    CAPTURED = "captured"
    UNSUPPORTED = "unsupported"


class MetricCaptureMethod(StrEnum):
    RUNTIME_WRAPPER = "runtime_wrapper"
    MANIFEST_VARIABLE = "manifest_variable"
    NOT_OBSERVED = "not_observed"


class ReproducibilityStatus(StrEnum):
    REPRODUCED = "reproduced"
    DIVERGED = "diverged"
    INCOMPLETE = "incomplete"


class RuntimeEventType(StrEnum):
    SPLIT = "split"
    FIT = "fit"
    TRANSFORM = "transform"
    PREDICT = "predict"
    METRIC = "metric"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    task_type: str
    target_column: str
    primary_metric: str
    primary_metric_variable: str | None = None
    entity_column: str | None = None
    timestamp_column: str | None = None
    positive_class: str = "1"
    random_seed: int = 42

    def __post_init__(self) -> None:
        _require_non_empty("task_type", self.task_type)
        _require_non_empty("target_column", self.target_column)
        _require_non_empty("primary_metric", self.primary_metric)
        if self.task_type not in SUPPORTED_TASKS:
            raise ValueError(f"Unsupported task_type: {self.task_type}")
        if self.primary_metric not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported primary_metric: {self.primary_metric}")
        if self.primary_metric_variable is not None:
            _require_python_identifier(
                "primary_metric_variable", self.primary_metric_variable
            )
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be an integer")

    @classmethod
    def from_toml(cls, path: str | Path) -> "ExperimentConfig":
        with Path(path).open("rb") as handle:
            raw = tomllib.load(handle)
        experiment = raw.get("experiment")
        if not isinstance(experiment, dict):
            raise ValueError("Configuration must contain an [experiment] table")
        return cls.from_dict(experiment)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExperimentConfig":
        _reject_unknown(
            raw,
            {
                "task_type",
                "target_column",
                "primary_metric",
                "primary_metric_variable",
                "entity_column",
                "timestamp_column",
                "positive_class",
                "random_seed",
            },
            "experiment configuration",
        )
        return cls(
            task_type=_string(raw, "task_type"),
            target_column=_string(raw, "target_column"),
            primary_metric=_string(raw, "primary_metric"),
            primary_metric_variable=_optional_string(
                raw.get("primary_metric_variable")
            ),
            entity_column=_optional_string(raw.get("entity_column")),
            timestamp_column=_optional_string(raw.get("timestamp_column")),
            positive_class=_string(raw, "positive_class", default="1"),
            random_seed=_integer(raw, "random_seed", default=42),
        )

    def to_dict(self) -> JsonObject:
        return {
            "task_type": self.task_type,
            "target_column": self.target_column,
            "primary_metric": self.primary_metric,
            "primary_metric_variable": self.primary_metric_variable,
            "entity_column": self.entity_column,
            "timestamp_column": self.timestamp_column,
            "positive_class": self.positive_class,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True, slots=True)
class NotebookCell:
    index: int
    cell_type: str
    source: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("Notebook cell index cannot be negative")
        _require_non_empty("cell_type", self.cell_type)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NotebookCell":
        _reject_unknown(raw, {"index", "cell_type", "source"}, "notebook cell")
        return cls(
            index=_integer(raw, "index"),
            cell_type=_string(raw, "cell_type"),
            source=_string(raw, "source", allow_empty=True),
        )

    def to_dict(self) -> JsonObject:
        return {"index": self.index, "cell_type": self.cell_type, "source": self.source}


@dataclass(frozen=True, slots=True)
class NotebookSummary:
    path: str
    total_cells: int
    code_cells: int
    markdown_cells: int
    cells: tuple[NotebookCell, ...]

    def __post_init__(self) -> None:
        _require_non_empty("notebook path", self.path)
        if min(self.total_cells, self.code_cells, self.markdown_cells) < 0:
            raise ValueError("Notebook cell counts cannot be negative")
        if self.total_cells != len(self.cells):
            raise ValueError("total_cells does not match serialized cells")
        indexes = [cell.index for cell in self.cells]
        _require_unique([str(index) for index in indexes], "notebook cell indexes")
        if self.code_cells != sum(cell.cell_type == "code" for cell in self.cells):
            raise ValueError("code_cells does not match serialized cells")
        if self.markdown_cells != sum(cell.cell_type == "markdown" for cell in self.cells):
            raise ValueError("markdown_cells does not match serialized cells")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NotebookSummary":
        _reject_unknown(
            raw,
            {"path", "total_cells", "code_cells", "markdown_cells", "cells"},
            "notebook summary",
        )
        return cls(
            path=_string(raw, "path"),
            total_cells=_integer(raw, "total_cells"),
            code_cells=_integer(raw, "code_cells"),
            markdown_cells=_integer(raw, "markdown_cells"),
            cells=tuple(
                NotebookCell.from_dict(_mapping(item, "notebook cell"))
                for item in _sequence(raw, "cells")
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "path": self.path,
            "total_cells": self.total_cells,
            "code_cells": self.code_cells,
            "markdown_cells": self.markdown_cells,
            "cells": [cell.to_dict() for cell in self.cells],
        }


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    path: str
    row_count: int
    columns: tuple[str, ...]
    target_column: str
    class_counts: Mapping[str, int]
    minority_fraction: float

    def __post_init__(self) -> None:
        _require_non_empty("dataset path", self.path)
        _require_non_empty("target_column", self.target_column)
        if self.row_count <= 0:
            raise ValueError("row_count must be positive")
        _require_unique(list(self.columns), "dataset columns")
        if self.target_column not in self.columns:
            raise ValueError("target_column is not present in dataset columns")
        normalized = {str(label): _strict_int(count, "class count") for label, count in self.class_counts.items()}
        if len(normalized) != 2:
            raise ValueError("Binary classification profiles must contain exactly two classes")
        if any(count <= 0 for count in normalized.values()):
            raise ValueError("Class counts must be positive")
        if sum(normalized.values()) != self.row_count:
            raise ValueError("Class counts must sum to row_count")
        expected = min(normalized.values()) / self.row_count
        if not math.isclose(self.minority_fraction, expected, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("minority_fraction does not match class_counts")
        object.__setattr__(self, "class_counts", MappingProxyType(normalized))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DatasetProfile":
        _reject_unknown(
            raw,
            {"path", "row_count", "columns", "target_column", "class_counts", "minority_fraction"},
            "dataset profile",
        )
        counts = _mapping(_required(raw, "class_counts"), "class_counts")
        return cls(
            path=_string(raw, "path"),
            row_count=_integer(raw, "row_count"),
            columns=tuple(_string_value(item, "dataset column") for item in _sequence(raw, "columns")),
            target_column=_string(raw, "target_column"),
            class_counts={str(label): _strict_int(count, f"class_counts[{label!r}]") for label, count in counts.items()},
            minority_fraction=_number(raw, "minority_fraction"),
        )

    def to_dict(self) -> JsonObject:
        return {
            "path": self.path,
            "row_count": self.row_count,
            "columns": list(self.columns),
            "target_column": self.target_column,
            "class_counts": dict(self.class_counts),
            "minority_fraction": self.minority_fraction,
        }


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    kind: str
    summary: str
    details: Mapping[str, JsonValue] = field(default_factory=dict)
    notebook_cells: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier("evidence id", self.id)
        _require_non_empty("evidence kind", self.kind)
        _require_non_empty("evidence summary", self.summary)
        if any(index < 0 for index in self.notebook_cells):
            raise ValueError("Evidence notebook cell indexes cannot be negative")
        _require_unique([str(index) for index in self.notebook_cells], "evidence notebook cell indexes")
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Evidence":
        _reject_unknown(raw, {"id", "kind", "summary", "details", "notebook_cells"}, "evidence")
        return cls(
            id=_string(raw, "id"),
            kind=_string(raw, "kind"),
            summary=_string(raw, "summary"),
            details=cast(Mapping[str, JsonValue], _mapping(raw.get("details", {}), "evidence details")),
            notebook_cells=tuple(
                _strict_int(item, "notebook cell index")
                for item in _sequence(raw, "notebook_cells", default=())
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "kind": self.kind,
            "summary": self.summary,
            "details": _thaw_mapping(self.details),
            "notebook_cells": list(self.notebook_cells),
        }


@dataclass(frozen=True, slots=True)
class Finding:
    id: str
    check_id: str
    title: str
    severity: Severity
    confidence: Confidence
    summary: str
    evidence_ids: tuple[str, ...]
    recommendation: str

    def __post_init__(self) -> None:
        _require_identifier("finding id", self.id)
        _require_identifier("check_id", self.check_id)
        _require_non_empty("finding title", self.title)
        _require_non_empty("finding summary", self.summary)
        _require_non_empty("recommendation", self.recommendation)
        object.__setattr__(self, "severity", _enum_value(Severity, self.severity, "severity"))
        object.__setattr__(self, "confidence", _enum_value(Confidence, self.confidence, "confidence"))
        if not self.evidence_ids:
            raise ValueError("A finding must reference at least one evidence item")
        _require_unique(list(self.evidence_ids), "finding evidence references")
        for evidence_id in self.evidence_ids:
            _require_identifier("evidence reference", evidence_id)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Finding":
        _reject_unknown(
            raw,
            {"id", "check_id", "title", "severity", "confidence", "summary", "evidence_ids", "recommendation"},
            "finding",
        )
        return cls(
            id=_string(raw, "id"),
            check_id=_string(raw, "check_id"),
            title=_string(raw, "title"),
            severity=_enum_value(Severity, _string(raw, "severity"), "severity"),
            confidence=_enum_value(Confidence, _string(raw, "confidence"), "confidence"),
            summary=_string(raw, "summary"),
            evidence_ids=tuple(_string_value(item, "evidence reference") for item in _sequence(raw, "evidence_ids")),
            recommendation=_string(raw, "recommendation"),
        )

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "check_id": self.check_id,
            "title": self.title,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "summary": self.summary,
            "evidence_ids": list(self.evidence_ids),
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True, slots=True)
class MetricSelector:
    metric_name: str
    variable_name: str | None = None

    def __post_init__(self) -> None:
        if self.metric_name not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported metric selector: {self.metric_name}")
        if self.variable_name is not None:
            _require_python_identifier("metric variable", self.variable_name)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MetricSelector":
        _reject_unknown(raw, {"metric_name", "variable_name"}, "metric selector")
        return cls(
            metric_name=_string(raw, "metric_name"),
            variable_name=_optional_string(raw.get("variable_name")),
        )

    def to_dict(self) -> JsonObject:
        return {
            "metric_name": self.metric_name,
            "variable_name": self.variable_name,
        }


@dataclass(frozen=True, slots=True)
class RuntimeDataFingerprint:
    """Privacy-minimized identity for data observed by one runtime operation."""

    role: str
    fingerprint: str
    data_type: str
    row_count: int
    column_count: int | None = None

    def __post_init__(self) -> None:
        _require_identifier("runtime data role", self.role)
        _require_identifier("runtime data fingerprint", self.fingerprint)
        _require_non_empty("runtime data type", self.data_type)
        _strict_int(self.row_count, "runtime data row_count")
        if self.row_count < 0:
            raise ValueError("runtime data row_count cannot be negative")
        if self.column_count is not None:
            _strict_int(self.column_count, "runtime data column_count")
            if self.column_count < 0:
                raise ValueError("runtime data column_count cannot be negative")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RuntimeDataFingerprint":
        _reject_unknown(
            raw,
            {"role", "fingerprint", "data_type", "row_count", "column_count"},
            "runtime data fingerprint",
        )
        column_count = raw.get("column_count")
        if column_count is not None:
            column_count = _strict_int(column_count, "runtime data column_count")
        return cls(
            role=_string(raw, "role"),
            fingerprint=_string(raw, "fingerprint"),
            data_type=_string(raw, "data_type"),
            row_count=_integer(raw, "row_count"),
            column_count=column_count,
        )

    def to_dict(self) -> JsonObject:
        return {
            "role": self.role,
            "fingerprint": self.fingerprint,
            "data_type": self.data_type,
            "row_count": self.row_count,
            "column_count": self.column_count,
        }


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    id: str
    sequence: int
    event_type: RuntimeEventType
    operation: str
    cell_index: int
    inputs: tuple[RuntimeDataFingerprint, ...] = ()
    outputs: tuple[RuntimeDataFingerprint, ...] = ()
    parameters: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier("runtime event id", self.id)
        _strict_int(self.sequence, "runtime event sequence")
        if self.sequence < 1:
            raise ValueError("runtime event sequence must be positive")
        object.__setattr__(
            self,
            "event_type",
            _enum_value(RuntimeEventType, self.event_type, "runtime event type"),
        )
        _require_non_empty("runtime operation", self.operation)
        _strict_int(self.cell_index, "runtime event cell_index")
        if self.cell_index < 0:
            raise ValueError("runtime event cell_index cannot be negative")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        fingerprints = (*self.inputs, *self.outputs)
        if not fingerprints:
            raise ValueError("Runtime events require at least one data fingerprint")
        if any(not isinstance(item, RuntimeDataFingerprint) for item in fingerprints):
            raise TypeError("Runtime event data must contain RuntimeDataFingerprint values")
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RuntimeEvent":
        _reject_unknown(
            raw,
            {
                "id",
                "sequence",
                "event_type",
                "operation",
                "cell_index",
                "inputs",
                "outputs",
                "parameters",
            },
            "runtime event",
        )
        return cls(
            id=_string(raw, "id"),
            sequence=_integer(raw, "sequence"),
            event_type=_enum_value(
                RuntimeEventType, _string(raw, "event_type"), "runtime event type"
            ),
            operation=_string(raw, "operation"),
            cell_index=_integer(raw, "cell_index"),
            inputs=tuple(
                RuntimeDataFingerprint.from_dict(
                    _mapping(item, "runtime input fingerprint")
                )
                for item in _sequence(raw, "inputs")
            ),
            outputs=tuple(
                RuntimeDataFingerprint.from_dict(
                    _mapping(item, "runtime output fingerprint")
                )
                for item in _sequence(raw, "outputs")
            ),
            parameters=cast(
                Mapping[str, JsonValue],
                _mapping(raw.get("parameters", {}), "runtime event parameters"),
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "operation": self.operation,
            "cell_index": self.cell_index,
            "inputs": [item.to_dict() for item in self.inputs],
            "outputs": [item.to_dict() for item in self.outputs],
            "parameters": _thaw_mapping(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class RuntimeTrace:
    fingerprint_scope_id: str
    events: tuple[RuntimeEvent, ...]
    fingerprint_algorithm: str = "hmac-sha256"
    schema_version: str = INSTRUMENTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != INSTRUMENTATION_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported instrumentation schema version {self.schema_version!r}; "
                f"expected {INSTRUMENTATION_SCHEMA_VERSION!r}"
            )
        _require_identifier("fingerprint scope id", self.fingerprint_scope_id)
        if self.fingerprint_algorithm != "hmac-sha256":
            raise ValueError("Unsupported runtime fingerprint algorithm")
        object.__setattr__(self, "events", tuple(self.events))
        if any(not isinstance(event, RuntimeEvent) for event in self.events):
            raise TypeError("events must contain RuntimeEvent values")
        _require_unique([event.id for event in self.events], "runtime event IDs")
        expected_sequences = list(range(1, len(self.events) + 1))
        if [event.sequence for event in self.events] != expected_sequences:
            raise ValueError("Runtime event sequences must be contiguous and ordered")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RuntimeTrace":
        _reject_unknown(
            raw,
            {
                "schema_version",
                "fingerprint_scope_id",
                "fingerprint_algorithm",
                "events",
            },
            "runtime trace",
        )
        return cls(
            schema_version=_string(raw, "schema_version"),
            fingerprint_scope_id=_string(raw, "fingerprint_scope_id"),
            fingerprint_algorithm=_string(raw, "fingerprint_algorithm"),
            events=tuple(
                RuntimeEvent.from_dict(_mapping(item, "runtime event"))
                for item in _sequence(raw, "events")
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "fingerprint_scope_id": self.fingerprint_scope_id,
            "fingerprint_algorithm": self.fingerprint_algorithm,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class MetricArtifact:
    id: str
    metric_name: str
    status: MetricCaptureStatus
    capture_method: MetricCaptureMethod
    value: float | None = None
    cell_index: int | None = None
    sample_count: int | None = None
    parameters: Mapping[str, JsonValue] = field(default_factory=dict)
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("metric artifact id", self.id)
        if self.metric_name not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported metric artifact: {self.metric_name}")
        object.__setattr__(
            self,
            "status",
            _enum_value(MetricCaptureStatus, self.status, "metric capture status"),
        )
        object.__setattr__(
            self,
            "capture_method",
            _enum_value(MetricCaptureMethod, self.capture_method, "metric capture method"),
        )
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))
        if self.status is MetricCaptureStatus.CAPTURED:
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise TypeError("Captured metrics require a numeric value")
            value = float(self.value)
            if not math.isfinite(value):
                raise ValueError("Metric value must be finite")
            object.__setattr__(self, "value", value)
            if self.capture_method is MetricCaptureMethod.NOT_OBSERVED:
                raise ValueError("Captured metrics require an observation method")
            if self.reason is not None:
                raise ValueError("Captured metrics cannot contain an unsupported reason")
        else:
            if self.capture_method is not MetricCaptureMethod.NOT_OBSERVED:
                raise ValueError("Unsupported metrics must use method 'not_observed'")
            if self.value is not None or self.cell_index is not None or self.sample_count is not None:
                raise ValueError("Unsupported metrics cannot contain observed values")
            if self.parameters:
                raise ValueError("Unsupported metrics cannot contain parameters")
            if self.reason is None:
                raise ValueError("Unsupported metrics require a reason")
            _require_non_empty("unsupported metric reason", self.reason)
        if self.cell_index is not None:
            _strict_int(self.cell_index, "metric cell_index")
            if self.cell_index < 0:
                raise ValueError("metric cell_index cannot be negative")
        if self.sample_count is not None:
            _strict_int(self.sample_count, "metric sample_count")
            if self.sample_count < 0:
                raise ValueError("metric sample_count cannot be negative")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MetricArtifact":
        _reject_unknown(
            raw,
            {
                "id",
                "metric_name",
                "status",
                "capture_method",
                "value",
                "cell_index",
                "sample_count",
                "parameters",
                "reason",
            },
            "metric artifact",
        )
        value = raw.get("value")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise TypeError("metric value must be numeric")
        cell_index = raw.get("cell_index")
        if cell_index is not None:
            cell_index = _strict_int(cell_index, "metric cell_index")
        sample_count = raw.get("sample_count")
        if sample_count is not None:
            sample_count = _strict_int(sample_count, "metric sample_count")
        return cls(
            id=_string(raw, "id"),
            metric_name=_string(raw, "metric_name"),
            status=_enum_value(
                MetricCaptureStatus, _string(raw, "status"), "metric capture status"
            ),
            capture_method=_enum_value(
                MetricCaptureMethod,
                _string(raw, "capture_method"),
                "metric capture method",
            ),
            value=None if value is None else float(value),
            cell_index=cell_index,
            sample_count=sample_count,
            parameters=cast(
                Mapping[str, JsonValue],
                _mapping(raw.get("parameters", {}), "metric parameters"),
            ),
            reason=_optional_string(raw.get("reason")),
        )

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "status": self.status.value,
            "capture_method": self.capture_method.value,
            "value": self.value,
            "cell_index": self.cell_index,
            "sample_count": self.sample_count,
            "parameters": _thaw_mapping(self.parameters),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    timeout_seconds: int = 300
    memory_mb: int = 2048
    cpu_count: int = 2
    process_limit: int = 128
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        for name in (
            "timeout_seconds",
            "memory_mb",
            "cpu_count",
            "process_limit",
            "max_output_bytes",
        ):
            value = getattr(self, name)
            _strict_int(value, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ResourceLimits":
        fields = {
            "timeout_seconds",
            "memory_mb",
            "cpu_count",
            "process_limit",
            "max_output_bytes",
        }
        _reject_unknown(raw, fields, "resource limits")
        missing = sorted(fields - set(raw))
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return cls(**{name: _integer(raw, name) for name in fields})

    def to_dict(self) -> JsonObject:
        return {
            "timeout_seconds": self.timeout_seconds,
            "memory_mb": self.memory_mb,
            "cpu_count": self.cpu_count,
            "process_limit": self.process_limit,
            "max_output_bytes": self.max_output_bytes,
        }


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: str
    notebook_path: str
    data_paths: tuple[str, ...]
    working_directory: str
    metric_selector: MetricSelector | None = None
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    network_enabled: bool = False
    schema_version: str = EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTION_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported execution schema version {self.schema_version!r}; "
                f"expected {EXECUTION_SCHEMA_VERSION!r}"
            )
        _require_identifier("execution id", self.execution_id)
        _require_non_empty("notebook path", self.notebook_path)
        _require_non_empty("working directory", self.working_directory)
        object.__setattr__(self, "data_paths", tuple(self.data_paths))
        if not self.data_paths:
            raise ValueError("data_paths must contain at least one path")
        for path in self.data_paths:
            _require_non_empty("data path", path)
        _require_unique(list(self.data_paths), "data paths")
        if not isinstance(self.limits, ResourceLimits):
            raise TypeError("limits must be ResourceLimits")
        if self.metric_selector is not None and not isinstance(
            self.metric_selector, MetricSelector
        ):
            raise TypeError("metric_selector must be MetricSelector")
        if not isinstance(self.network_enabled, bool):
            raise TypeError("network_enabled must be a boolean")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExecutionRequest":
        _reject_unknown(
            raw,
            {
                "schema_version",
                "execution_id",
                "notebook_path",
                "data_paths",
                "working_directory",
                "metric_selector",
                "limits",
                "network_enabled",
            },
            "execution request",
        )
        network_enabled = _required(raw, "network_enabled")
        if not isinstance(network_enabled, bool):
            raise TypeError("network_enabled must be a boolean")
        metric_selector = raw.get("metric_selector")
        return cls(
            schema_version=_string(raw, "schema_version"),
            execution_id=_string(raw, "execution_id"),
            notebook_path=_string(raw, "notebook_path"),
            data_paths=tuple(
                _string_value(item, "data path")
                for item in _sequence(raw, "data_paths")
            ),
            working_directory=_string(raw, "working_directory"),
            metric_selector=(
                None
                if metric_selector is None
                else MetricSelector.from_dict(
                    _mapping(metric_selector, "metric selector")
                )
            ),
            limits=ResourceLimits.from_dict(
                _mapping(_required(raw, "limits"), "resource limits")
            ),
            network_enabled=network_enabled,
        )

    def to_dict(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "notebook_path": self.notebook_path,
            "data_paths": list(self.data_paths),
            "working_directory": self.working_directory,
            "metric_selector": (
                None if self.metric_selector is None else self.metric_selector.to_dict()
            ),
            "limits": self.limits.to_dict(),
            "network_enabled": self.network_enabled,
        }


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    kind: str
    message: str
    cell_index: int | None = None

    def __post_init__(self) -> None:
        _require_identifier("failure kind", self.kind)
        _require_non_empty("failure message", self.message)
        if self.cell_index is not None:
            _strict_int(self.cell_index, "cell_index")
            if self.cell_index < 0:
                raise ValueError("cell_index cannot be negative")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExecutionFailure":
        _reject_unknown(raw, {"kind", "message", "cell_index"}, "execution failure")
        cell_index = raw.get("cell_index")
        if cell_index is not None:
            cell_index = _strict_int(cell_index, "cell_index")
        return cls(
            kind=_string(raw, "kind"),
            message=_string(raw, "message"),
            cell_index=cell_index,
        )

    def to_dict(self) -> JsonObject:
        return {
            "kind": self.kind,
            "message": self.message,
            "cell_index": self.cell_index,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    fingerprint: str
    python_version: str
    python_implementation: str
    operating_system: str
    machine: str
    packages_fingerprint: str
    runner_fingerprint: str

    def __post_init__(self) -> None:
        _require_identifier("environment fingerprint", self.fingerprint)
        _require_non_empty("Python version", self.python_version)
        _require_non_empty("Python implementation", self.python_implementation)
        _require_non_empty("operating system", self.operating_system)
        _require_non_empty("machine", self.machine)
        _require_identifier("packages fingerprint", self.packages_fingerprint)
        _require_identifier("runner fingerprint", self.runner_fingerprint)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EnvironmentFingerprint":
        _reject_unknown(
            raw,
            {
                "fingerprint",
                "python_version",
                "python_implementation",
                "operating_system",
                "machine",
                "packages_fingerprint",
                "runner_fingerprint",
            },
            "environment fingerprint",
        )
        return cls(
            fingerprint=_string(raw, "fingerprint"),
            python_version=_string(raw, "python_version"),
            python_implementation=_string(raw, "python_implementation"),
            operating_system=_string(raw, "operating_system"),
            machine=_string(raw, "machine"),
            packages_fingerprint=_string(raw, "packages_fingerprint"),
            runner_fingerprint=_string(raw, "runner_fingerprint"),
        )

    def to_dict(self) -> JsonObject:
        return {
            "fingerprint": self.fingerprint,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "operating_system": self.operating_system,
            "machine": self.machine,
            "packages_fingerprint": self.packages_fingerprint,
            "runner_fingerprint": self.runner_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    execution_id: str
    status: ExecutionStatus
    duration_ms: int
    output_fingerprint: str | None = None
    failure: ExecutionFailure | None = None
    metrics: tuple[MetricArtifact, ...] = ()
    environment: EnvironmentFingerprint | None = None
    runtime_trace: RuntimeTrace | None = None
    schema_version: str = EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTION_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported execution schema version {self.schema_version!r}; "
                f"expected {EXECUTION_SCHEMA_VERSION!r}"
            )
        _require_identifier("execution id", self.execution_id)
        object.__setattr__(
            self, "status", _enum_value(ExecutionStatus, self.status, "execution status")
        )
        _strict_int(self.duration_ms, "duration_ms")
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        object.__setattr__(self, "metrics", tuple(self.metrics))
        if any(not isinstance(metric, MetricArtifact) for metric in self.metrics):
            raise TypeError("metrics must contain MetricArtifact values")
        _require_unique([metric.id for metric in self.metrics], "metric artifact IDs")
        if self.environment is not None and not isinstance(
            self.environment, EnvironmentFingerprint
        ):
            raise TypeError("environment must be EnvironmentFingerprint")
        if self.runtime_trace is not None and not isinstance(
            self.runtime_trace, RuntimeTrace
        ):
            raise TypeError("runtime_trace must be RuntimeTrace")
        if self.status is ExecutionStatus.SUCCEEDED:
            if self.output_fingerprint is None:
                raise ValueError("Successful executions require an output_fingerprint")
            _require_identifier("output fingerprint", self.output_fingerprint)
            if self.failure is not None:
                raise ValueError("Successful executions cannot contain failure details")
        else:
            if self.failure is None:
                raise ValueError("Unsuccessful executions require failure details")
            if not isinstance(self.failure, ExecutionFailure):
                raise TypeError("failure must be ExecutionFailure")
            if self.output_fingerprint is not None:
                raise ValueError("Unsuccessful executions cannot contain an output_fingerprint")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExecutionResult":
        _reject_unknown(
            raw,
            {
                "schema_version",
                "execution_id",
                "status",
                "duration_ms",
                "output_fingerprint",
                "failure",
                "metrics",
                "environment",
                "runtime_trace",
            },
            "execution result",
        )
        failure = raw.get("failure")
        environment = raw.get("environment")
        runtime_trace = raw.get("runtime_trace")
        return cls(
            schema_version=_string(raw, "schema_version"),
            execution_id=_string(raw, "execution_id"),
            status=_enum_value(
                ExecutionStatus, _string(raw, "status"), "execution status"
            ),
            duration_ms=_integer(raw, "duration_ms"),
            output_fingerprint=_optional_string(raw.get("output_fingerprint")),
            failure=(
                None
                if failure is None
                else ExecutionFailure.from_dict(_mapping(failure, "execution failure"))
            ),
            metrics=tuple(
                MetricArtifact.from_dict(_mapping(item, "metric artifact"))
                for item in _sequence(raw, "metrics")
            ),
            environment=(
                None
                if environment is None
                else EnvironmentFingerprint.from_dict(
                    _mapping(environment, "environment fingerprint")
                )
            ),
            runtime_trace=(
                None
                if runtime_trace is None
                else RuntimeTrace.from_dict(_mapping(runtime_trace, "runtime trace"))
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "output_fingerprint": self.output_fingerprint,
            "failure": None if self.failure is None else self.failure.to_dict(),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "environment": (
                None if self.environment is None else self.environment.to_dict()
            ),
            "runtime_trace": (
                None if self.runtime_trace is None else self.runtime_trace.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class ReproducibilityComparison:
    status: ReproducibilityStatus
    baseline_execution_id: str
    repeated_execution_id: str
    primary_metric: str
    baseline_metric_values: tuple[float, ...]
    repeated_metric_values: tuple[float, ...]
    metric_match: bool | None
    output_match: bool | None
    environment_match: bool | None
    max_absolute_delta: float | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status",
            _enum_value(
                ReproducibilityStatus, self.status, "reproducibility status"
            ),
        )
        _require_identifier("baseline execution id", self.baseline_execution_id)
        _require_identifier("repeated execution id", self.repeated_execution_id)
        if self.baseline_execution_id == self.repeated_execution_id:
            raise ValueError("Reproducibility comparison requires distinct executions")
        if self.primary_metric not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported comparison metric: {self.primary_metric}")
        object.__setattr__(
            self,
            "baseline_metric_values",
            _finite_float_tuple(self.baseline_metric_values, "baseline metric values"),
        )
        object.__setattr__(
            self,
            "repeated_metric_values",
            _finite_float_tuple(self.repeated_metric_values, "repeated metric values"),
        )
        for label, value in (
            ("metric_match", self.metric_match),
            ("output_match", self.output_match),
            ("environment_match", self.environment_match),
        ):
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{label} must be a boolean or null")
        if self.max_absolute_delta is not None:
            if isinstance(self.max_absolute_delta, bool) or not isinstance(
                self.max_absolute_delta, (int, float)
            ):
                raise TypeError("max_absolute_delta must be numeric")
            delta = float(self.max_absolute_delta)
            if not math.isfinite(delta) or delta < 0:
                raise ValueError("max_absolute_delta must be finite and non-negative")
            object.__setattr__(self, "max_absolute_delta", delta)
        object.__setattr__(self, "reasons", tuple(self.reasons))
        for reason in self.reasons:
            _require_non_empty("reproducibility reason", reason)
        signals = (self.metric_match, self.output_match, self.environment_match)
        if self.status is ReproducibilityStatus.REPRODUCED:
            if signals != (True, True, True) or self.reasons:
                raise ValueError("Reproduced comparisons require three matching signals")
        elif self.status is ReproducibilityStatus.DIVERGED:
            if False not in signals or not self.reasons:
                raise ValueError("Diverged comparisons require a mismatch and reason")
        elif None not in signals or not self.reasons:
            raise ValueError("Incomplete comparisons require a missing signal and reason")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReproducibilityComparison":
        _reject_unknown(
            raw,
            {
                "status",
                "baseline_execution_id",
                "repeated_execution_id",
                "primary_metric",
                "baseline_metric_values",
                "repeated_metric_values",
                "metric_match",
                "output_match",
                "environment_match",
                "max_absolute_delta",
                "reasons",
            },
            "reproducibility comparison",
        )
        max_delta = _required(raw, "max_absolute_delta")
        if max_delta is not None and (
            isinstance(max_delta, bool) or not isinstance(max_delta, (int, float))
        ):
            raise TypeError("max_absolute_delta must be numeric")
        return cls(
            status=_enum_value(
                ReproducibilityStatus,
                _string(raw, "status"),
                "reproducibility status",
            ),
            baseline_execution_id=_string(raw, "baseline_execution_id"),
            repeated_execution_id=_string(raw, "repeated_execution_id"),
            primary_metric=_string(raw, "primary_metric"),
            baseline_metric_values=tuple(
                _strict_number(item, "baseline metric value")
                for item in _sequence(raw, "baseline_metric_values")
            ),
            repeated_metric_values=tuple(
                _strict_number(item, "repeated metric value")
                for item in _sequence(raw, "repeated_metric_values")
            ),
            metric_match=_optional_boolean(raw, "metric_match"),
            output_match=_optional_boolean(raw, "output_match"),
            environment_match=_optional_boolean(raw, "environment_match"),
            max_absolute_delta=None if max_delta is None else float(max_delta),
            reasons=tuple(
                _string_value(item, "reproducibility reason")
                for item in _sequence(raw, "reasons")
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "status": self.status.value,
            "baseline_execution_id": self.baseline_execution_id,
            "repeated_execution_id": self.repeated_execution_id,
            "primary_metric": self.primary_metric,
            "baseline_metric_values": list(self.baseline_metric_values),
            "repeated_metric_values": list(self.repeated_metric_values),
            "metric_match": self.metric_match,
            "output_match": self.output_match,
            "environment_match": self.environment_match,
            "max_absolute_delta": self.max_absolute_delta,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class AuditReport:
    status: AuditStatus
    config: ExperimentConfig
    notebook: NotebookSummary
    dataset: DatasetProfile
    evidence: tuple[Evidence, ...]
    findings: tuple[Finding, ...]
    executions: tuple[ExecutionResult, ...] = ()
    reproducibility: ReproducibilityComparison | None = None
    schema_version: str = REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported report schema version {self.schema_version!r}; expected {REPORT_SCHEMA_VERSION!r}"
            )
        object.__setattr__(self, "status", _enum_value(AuditStatus, self.status, "audit status"))
        self.validate()

    def validate(self) -> None:
        evidence_ids = [item.id for item in self.evidence]
        finding_ids = [item.id for item in self.findings]
        execution_ids = [item.execution_id for item in self.executions]
        _require_unique(evidence_ids, "evidence IDs")
        _require_unique(finding_ids, "finding IDs")
        _require_unique(execution_ids, "execution IDs")
        if self.reproducibility is not None:
            if not isinstance(self.reproducibility, ReproducibilityComparison):
                raise TypeError("reproducibility must be ReproducibilityComparison")
            compared_ids = {
                self.reproducibility.baseline_execution_id,
                self.reproducibility.repeated_execution_id,
            }
            if not compared_ids.issubset(set(execution_ids)):
                raise ValueError(
                    "Reproducibility comparison references missing executions"
                )
        known = set(evidence_ids)
        missing = sorted(
            {reference for finding in self.findings for reference in finding.evidence_ids if reference not in known}
        )
        if missing:
            raise ValueError(f"Findings reference missing evidence: {', '.join(missing)}")
        if self.dataset.target_column != self.config.target_column:
            raise ValueError("Dataset target_column does not match experiment configuration")
        execution_failed = any(
            execution.status is not ExecutionStatus.SUCCEEDED
            for execution in self.executions
        )
        primary_metric_captured = any(
            metric.metric_name == self.config.primary_metric
            and metric.status is MetricCaptureStatus.CAPTURED
            for execution in self.executions
            for metric in execution.metrics
        )
        metric_capture_incomplete = bool(self.executions) and not primary_metric_captured
        comparison_incomplete = (
            self.reproducibility is not None
            and self.reproducibility.status is ReproducibilityStatus.INCOMPLETE
        )
        comparison_diverged = (
            self.reproducibility is not None
            and self.reproducibility.status is ReproducibilityStatus.DIVERGED
        )
        audit_incomplete = (
            execution_failed or metric_capture_incomplete or comparison_incomplete
        )
        if audit_incomplete and self.status is not AuditStatus.INCOMPLETE:
            raise ValueError(
                "Reports with unsuccessful execution or unsupported primary metric "
                "must use status 'incomplete'"
            )
        attention_required = bool(self.findings) or comparison_diverged
        if not audit_incomplete and attention_required and self.status is not AuditStatus.ATTENTION_REQUIRED:
            raise ValueError("Reports with findings must use status 'attention_required'")
        if (
            not audit_incomplete
            and not attention_required
            and self.status is not AuditStatus.PASSED_SUPPORTED_CHECKS
        ):
            raise ValueError("Reports without findings must use status 'passed_supported_checks'")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AuditReport":
        _reject_unknown(
            raw,
            {
                "schema_version",
                "status",
                "config",
                "notebook",
                "dataset",
                "evidence",
                "findings",
                "executions",
                "reproducibility",
            },
            "audit report",
        )
        reproducibility = raw.get("reproducibility")
        return cls(
            schema_version=_string(raw, "schema_version"),
            status=_enum_value(AuditStatus, _string(raw, "status"), "audit status"),
            config=ExperimentConfig.from_dict(_mapping(_required(raw, "config"), "config")),
            notebook=NotebookSummary.from_dict(_mapping(_required(raw, "notebook"), "notebook")),
            dataset=DatasetProfile.from_dict(_mapping(_required(raw, "dataset"), "dataset")),
            evidence=tuple(Evidence.from_dict(_mapping(item, "evidence")) for item in _sequence(raw, "evidence")),
            findings=tuple(Finding.from_dict(_mapping(item, "finding")) for item in _sequence(raw, "findings")),
            executions=tuple(
                ExecutionResult.from_dict(_mapping(item, "execution result"))
                for item in _sequence(raw, "executions")
            ),
            reproducibility=(
                None
                if reproducibility is None
                else ReproducibilityComparison.from_dict(
                    _mapping(reproducibility, "reproducibility comparison")
                )
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "config": self.config.to_dict(),
            "notebook": self.notebook.to_dict(),
            "dataset": self.dataset.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "findings": [item.to_dict() for item in self.findings],
            "executions": [item.to_dict() for item in self.executions],
            "reproducibility": (
                None
                if self.reproducibility is None
                else self.reproducibility.to_dict()
            ),
        }


def _required(raw: Mapping[str, Any], key: str) -> Any:
    if key not in raw:
        raise ValueError(f"Missing required field: {key}")
    return raw[key]


def _string(
    raw: Mapping[str, Any], key: str, *, default: str | None = None, allow_empty: bool = False
) -> str:
    if key not in raw:
        if default is None:
            raise ValueError(f"Missing required field: {key}")
        return default
    return _string_value(raw[key], key, allow_empty=allow_empty)


def _string_value(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not allow_empty:
        _require_non_empty(label, value)
    return value


def _optional_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TypeError("Optional configuration values must be strings")
    return value


def _integer(raw: Mapping[str, Any], key: str, *, default: int | None = None) -> int:
    if key not in raw:
        if default is None:
            raise ValueError(f"Missing required field: {key}")
        return default
    return _strict_int(raw[key], key)


def _strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _number(raw: Mapping[str, Any], key: str) -> float:
    value = _required(raw, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{key} must be finite")
    return number


def _strict_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _finite_float_tuple(values: tuple[float, ...], label: str) -> tuple[float, ...]:
    return tuple(_strict_number(value, label) for value in values)


def _optional_boolean(raw: Mapping[str, Any], key: str) -> bool | None:
    value = _required(raw, key)
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean or null")
    return value


def _sequence(
    raw: Mapping[str, Any], key: str, *, default: tuple[Any, ...] | None = None
) -> list[Any] | tuple[Any, ...]:
    if key not in raw:
        if default is None:
            raise ValueError(f"Missing required field: {key}")
        return default
    value = raw[key]
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} keys must be strings")
    return cast(Mapping[str, Any], value)


def _reject_unknown(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"Unknown fields in {label}: {', '.join(unknown)}")


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} cannot be empty")


def _require_identifier(label: str, value: str) -> None:
    _require_non_empty(label, value)
    if any(character.isspace() for character in value):
        raise ValueError(f"{label} cannot contain whitespace")


def _require_python_identifier(label: str, value: str) -> None:
    _require_non_empty(label, value)
    if not value.isidentifier():
        raise ValueError(f"{label} must be a Python identifier")


def _require_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"Duplicate {label}: {', '.join(sorted(duplicates))}")


def _enum_value(enum_type: type[StrEnum], value: Any, label: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        options = ", ".join(member.value for member in enum_type)
        raise ValueError(f"Invalid {label} {value!r}; expected one of: {options}") from error


def _freeze_json(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Evidence details cannot contain non-finite numbers")
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(cast(Mapping[str, Any], value))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError(f"Evidence details contain a non-JSON value: {type(value).__name__}")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, JsonValue]:
    if not all(isinstance(key, str) for key in value):
        raise TypeError("Evidence detail keys must be strings")
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _thaw_json(value: JsonValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _thaw_mapping(value: Mapping[str, JsonValue]) -> JsonObject:
    return {key: _thaw_json(item) for key, item in value.items()}


__all__ = [
    "EXECUTION_SCHEMA_VERSION",
    "INSTRUMENTATION_SCHEMA_VERSION",
    "REPORT_SCHEMA_VERSION",
    "AuditReport",
    "AuditStatus",
    "Confidence",
    "DatasetProfile",
    "Evidence",
    "EnvironmentFingerprint",
    "ExperimentConfig",
    "ExecutionFailure",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "Finding",
    "MetricArtifact",
    "MetricCaptureMethod",
    "MetricCaptureStatus",
    "MetricSelector",
    "NotebookCell",
    "NotebookSummary",
    "ResourceLimits",
    "ReproducibilityComparison",
    "ReproducibilityStatus",
    "RuntimeDataFingerprint",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeTrace",
    "Severity",
]
