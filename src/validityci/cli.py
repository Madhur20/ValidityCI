from __future__ import annotations

import argparse
from pathlib import Path
import sys

from validityci.audit import audit_experiment
from validityci.reporting import write_html, write_json


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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            report = audit_experiment(args.notebook, args.data, args.config)
            write_json(report, args.output)
            write_html(report, args.html)
            print(f"Audit status: {report.status}")
            print(f"Findings: {len(report.findings)}")
            print(f"JSON report: {args.output}")
            print(f"HTML report: {args.html}")
    except (OSError, ValueError) as error:
        print(f"ValidityCI error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

