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
            metric_items.append(
                f"<li><strong>{escape(metric.metric_name)}</strong>: "
                f"{metric_detail}</li>"
            )
        metrics = (
            f"<ul>{''.join(metric_items)}</ul>" if metric_items else ""
        )
        execution_items.append(
            "<li>"
            f"<strong>{escape(execution.status.replace('_', ' '))}</strong>{cell} "
            f"· {execution.duration_ms} ms<br>{detail}"
            f"{metrics}"
            "</li>"
        )
    execution_section = (
        "<section><h2>Execution</h2><ul>"
        f"{''.join(execution_items)}"
        "</ul></section>"
        if execution_items
        else ""
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
  {''.join(finding_sections)}
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
