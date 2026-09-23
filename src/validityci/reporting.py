from __future__ import annotations

from html import escape
import json
from pathlib import Path

from validityci.schemas import AuditReport


def write_json(report: AuditReport, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_html(report: AuditReport, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    finding_sections = []
    evidence_by_id = {item.id: item for item in report.evidence}
    for finding in report.findings:
        evidence_items = []
        for evidence_id in finding.evidence_ids:
            evidence = evidence_by_id[evidence_id]
            cells = ", ".join(str(cell) for cell in evidence.notebook_cells) or "none identified"
            serialized_details = evidence.to_dict()["details"]
            evidence_items.append(
                f"<li><strong>{escape(evidence.summary)}</strong> "
                f"Notebook cells: {escape(cells)}<pre>{escape(json.dumps(serialized_details, indent=2))}</pre></li>"
            )
        finding_sections.append(
            "<section class='finding'>"
            f"<p class='severity'>{escape(finding.severity.upper())} · {escape(finding.confidence)} confidence</p>"
            f"<h2>{escape(finding.title)}</h2>"
            f"<p>{escape(finding.summary)}</p>"
            f"<ul>{''.join(evidence_items)}</ul>"
            f"<p><strong>Recommendation:</strong> {escape(finding.recommendation)}</p>"
            "</section>"
        )

    if not finding_sections:
        finding_sections.append("<section><h2>No findings from the supported checks</h2></section>")

    execution_items = []
    for execution in report.executions:
        detail = (
            f"Output fingerprint: <code>{escape(execution.output_fingerprint)}</code>"
            if execution.output_fingerprint is not None
            else escape(execution.failure.message if execution.failure else "No details available")
        )
        cell = (
            ""
            if execution.failure is None or execution.failure.cell_index is None
            else f" · cell {execution.failure.cell_index}"
        )
        metric_items = []
        for metric in execution.metrics:
            if metric.value is None:
                metric_detail = escape(metric.reason or "Metric was not observed")
            else:
                location = (
                    ""
                    if metric.cell_index is None
                    else f" · cell {metric.cell_index}"
                )
                sample_count = (
                    ""
                    if metric.sample_count is None
                    else f" · {metric.sample_count} samples"
                )
                metric_detail = (
                    f"<code>{metric.value:.12g}</code>{location}{sample_count} "
                    f"· {escape(metric.capture_method.replace('_', ' '))}"
                )
                if metric.confusion_matrix is not None:
                    confusion = metric.confusion_matrix
                    if confusion.status == "captured":
                        metric_detail += (
                            "<br>Binary confusion matrix "
                            f"(positive class <code>{escape(confusion.positive_class)}</code>): "
                            f"TN {confusion.true_negative} · FP {confusion.false_positive} · "
                            f"FN {confusion.false_negative} · TP {confusion.true_positive}"
                        )
                    else:
                        metric_detail += (
                            "<br>Confusion matrix unavailable: "
                            f"{escape(confusion.reason or 'unsupported')}"
                        )
            metric_items.append(
                f"<li><strong>{escape(metric.metric_name)}</strong>: "
                f"{metric_detail}</li>"
            )
        metrics = (
            f"<ul>{''.join(metric_items)}</ul>" if metric_items else ""
        )
        environment = (
            ""
            if execution.environment is None
            else (
                "<br>Environment: "
                f"<code>{escape(execution.environment.fingerprint)}</code> "
                f"· Python {escape(execution.environment.python_version)} "
                f"· {escape(execution.environment.operating_system)} "
                f"{escape(execution.environment.machine)}"
            )
        )
        runtime = ""
        if execution.runtime_trace is not None:
            runtime_items = []
            for event in execution.runtime_trace.events:
                data_items = (*event.inputs, *event.outputs)
                shapes = ", ".join(
                    (
                        f"{item.role}: {item.row_count}×{item.column_count}"
                        if item.column_count is not None
                        else f"{item.role}: {item.row_count} rows"
                    )
                    for item in data_items
                )
                runtime_items.append(
                    f"<li><code>{escape(event.event_type.value)}</code> · "
                    f"cell {event.cell_index} · {escape(event.operation)}"
                    f"<br>{escape(shapes)}</li>"
                )
            runtime = (
                "<details><summary>Runtime trace "
                f"v{escape(execution.runtime_trace.schema_version)} · "
                f"{len(execution.runtime_trace.events)} events</summary>"
                f"<ul>{''.join(runtime_items)}</ul></details>"
            )
        execution_items.append(
            "<li>"
            f"<strong>{escape(execution.status.replace('_', ' '))}</strong>{cell} "
            f"· {execution.duration_ms} ms<br>{detail}"
            f"{environment}"
            f"{metrics}"
            f"{runtime}"
            "</li>"
        )
    execution_section = (
        "<section><h2>Execution</h2><ul>"
        f"{''.join(execution_items)}"
        "</ul></section>"
        if execution_items
        else ""
    )

    reproducibility_section = ""
    if report.reproducibility is not None:
        comparison = report.reproducibility
        reasons = "".join(
            f"<li>{escape(reason)}</li>" for reason in comparison.reasons
        )
        reason_list = f"<ul>{reasons}</ul>" if reasons else ""
        baseline_values = ", ".join(
            f"{value:.12g}" for value in comparison.baseline_metric_values
        ) or "unavailable"
        repeated_values = ", ".join(
            f"{value:.12g}" for value in comparison.repeated_metric_values
        ) or "unavailable"
        reproducibility_section = (
            "<section><h2>Reproducibility</h2>"
            f"<p><strong>{escape(comparison.status.upper())}</strong></p>"
            f"<p>Metric match: {escape(str(comparison.metric_match))} · "
            f"Output match: {escape(str(comparison.output_match))} · "
            f"Environment match: {escape(str(comparison.environment_match))}</p>"
            f"<p><code>{escape(comparison.primary_metric)}</code>: "
            f"[{escape(baseline_values)}] → [{escape(repeated_values)}]</p>"
            f"{reason_list}</section>"
        )

    checks_section = ""
    if report.checks:
        check_items = "".join(
            "<li>"
            f"<strong>{escape(check.status.value.upper())}</strong> · "
            f"<code>{escape(check.check_id)}</code><br>"
            f"{escape(check.summary)}"
            "</li>"
            for check in report.checks
        )
        checks_section = (
            f"<section><h2>Deterministic checks</h2><ul>{check_items}</ul></section>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ValidityCI audit</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; max-width: 900px; margin: 48px auto; padding: 0 24px; color: #18212f; background: #f7f8fb; }}
    header, section {{ background: white; border: 1px solid #dde2ea; border-radius: 12px; padding: 24px; margin-bottom: 18px; }}
    h1, h2 {{ margin-top: 0; }}
    .status {{ font-weight: 700; color: #8a4b08; }}
    .severity {{ color: #a23b12; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.04em; }}
    pre {{ overflow-x: auto; background: #f1f4f8; padding: 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <header>
    <p class="status">{escape(report.status.replace('_', ' ').upper())}</p>
    <h1>ValidityCI experiment audit</h1>
    <p>{escape(report.notebook.path)}</p>
    <p>{report.dataset.row_count} rows · target <code>{escape(report.dataset.target_column)}</code> · primary metric <code>{escape(report.config.primary_metric)}</code></p>
  </header>
  {execution_section}
  {reproducibility_section}
  {checks_section}
  {''.join(finding_sections)}
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
