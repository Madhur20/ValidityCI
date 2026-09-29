"""Run one notebook with and without instrumentation in the restricted image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validityci.differential import compare_instrumented_and_reference
from validityci.runner import DEFAULT_RUNNER_IMAGE, DockerRunner
from validityci.schemas import ExecutionRequest, MetricSelector, ResourceLimits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--metric-name", required=True)
    parser.add_argument("--metric-variable")
    parser.add_argument("--entity-column")
    parser.add_argument("--positive-class")
    parser.add_argument("--runner-image", default=DEFAULT_RUNNER_IMAGE)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    request_values = {
        "notebook_path": str(args.notebook),
        "data_paths": (str(args.data),),
        "working_directory": str(args.notebook.parent),
        "metric_selector": MetricSelector(
            metric_name=args.metric_name,
            variable_name=args.metric_variable,
        ),
        "entity_column": args.entity_column,
        "positive_class": args.positive_class,
        "limits": ResourceLimits(timeout_seconds=args.timeout),
    }
    instrumented = DockerRunner(args.runner_image).execute(
        ExecutionRequest(
            execution_id="execution.differential.instrumented",
            **request_values,
        )
    )
    reference = DockerRunner(
        args.runner_image, instrumentation_enabled=False
    ).execute(
        ExecutionRequest(
            execution_id="execution.differential.reference",
            **request_values,
        )
    )
    comparison = compare_instrumented_and_reference(instrumented, reference)
    print(
        json.dumps(
            {
                "comparison": comparison.to_dict(),
                "instrumented": instrumented.to_dict(),
                "reference": reference.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not comparison.equivalent:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
