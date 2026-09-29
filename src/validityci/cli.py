from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from validityci.audit import audit_experiment
from validityci.investigator_benchmark import (
    deterministic_baseline_run,
    load_investigator_benchmark,
    load_investigator_responses,
    score_investigator_benchmark,
)
from validityci.reporting import write_html, write_json
from validityci.runner import DEFAULT_RUNNER_IMAGE, DockerRunner
from validityci.schemas import ResourceLimits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validityci",
        description="Independently validate machine-learning experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="Audit a supported notebook and dataset")
    audit_parser.add_argument("notebook", type=Path)
    audit_parser.add_argument("--data", required=True, type=Path)
    audit_parser.add_argument("--config", required=True, type=Path)
    audit_parser.add_argument("--output", type=Path, default=Path("build/audit.json"))
    audit_parser.add_argument("--html", type=Path, default=Path("build/audit.html"))
    audit_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the notebook with the restricted Docker runner",
    )
    audit_parser.add_argument("--runner-image", default=DEFAULT_RUNNER_IMAGE)
    audit_parser.add_argument("--timeout", type=int, default=300, metavar="SECONDS")
    audit_parser.add_argument("--memory", type=int, default=2048, metavar="MB")
    audit_parser.add_argument("--cpus", type=int, default=2)
    audit_parser.add_argument("--process-limit", type=int, default=128)
    audit_parser.add_argument("--max-output-bytes", type=int, default=1_000_000)
    audit_parser.add_argument(
        "--runs",
        type=int,
        choices=(1, 2),
        default=2,
        help="Number of fresh executions when --execute is enabled (default: 2)",
    )
    audit_parser.add_argument(
        "--group-counterfactual",
        action="store_true",
        help=(
            "Run one additional execution with supported train/test splits "
            "replaced by a configured group-isolated split"
        ),
    )
    benchmark_parser = subparsers.add_parser(
        "benchmark-investigator",
        help="Score structured investigator responses against the benchmark",
    )
    benchmark_parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmarks/investigator/cases.json"),
    )
    benchmark_parser.add_argument(
        "--responses",
        type=Path,
        help="Candidate response JSON; omit to score the deterministic baseline",
    )
    benchmark_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/investigator-benchmark.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            if args.group_counterfactual and not args.execute:
                raise ValueError("--group-counterfactual requires --execute")
            limits = ResourceLimits(
                timeout_seconds=args.timeout,
                memory_mb=args.memory,
                cpu_count=args.cpus,
                process_limit=args.process_limit,
                max_output_bytes=args.max_output_bytes,
            )
            runner = DockerRunner(args.runner_image) if args.execute else None
            report = audit_experiment(
                args.notebook,
                args.data,
                args.config,
                runner=runner,
                limits=limits,
                execution_count=args.runs,
                group_counterfactual=args.group_counterfactual,
            )
            write_json(report, args.output)
            write_html(report, args.html)
            print(f"Audit status: {report.status}")
            print(f"Findings: {len(report.findings)}")
            if report.executions:
                for execution in report.executions:
                    print(f"Execution {execution.execution_id}: {execution.status}")
            if report.reproducibility is not None:
                print(f"Reproducibility: {report.reproducibility.status}")
            if report.counterfactual is not None:
                print(f"Counterfactual: {report.counterfactual.status}")
            print(f"JSON report: {args.output}")
            print(f"HTML report: {args.html}")
        elif args.command == "benchmark-investigator":
            benchmark = load_investigator_benchmark(args.benchmark)
            if args.responses is None:
                run = deterministic_baseline_run(benchmark)
                source = "deterministic baseline"
            else:
                responses = load_investigator_responses(args.responses)
                run = score_investigator_benchmark(benchmark, responses)
                source = str(args.responses)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(run.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print(f"Investigator benchmark: {source}")
            print(f"Cases: {len(run.case_scores)}")
            print(f"Factual support pass rate: {run.factual_support_pass_rate:.3f}")
            print(f"Mean usefulness: {run.mean_usefulness_score:.3f}")
            print(f"Release gate: {'passed' if run.passes_release_gate else 'failed'}")
            print(f"Benchmark report: {args.output}")
            if not run.passes_release_gate:
                raise SystemExit(1)
    except (OSError, ValueError) as error:
        print(f"ValidityCI error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
