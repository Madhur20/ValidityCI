from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from validityci.audit import audit_experiment
from validityci.reporting import write_html
from validityci.schemas import (
    REPORT_SCHEMA_VERSION,
    AuditReport,
    Evidence,
    ExperimentConfig,
    Finding,
)


class ConfigTests(unittest.TestCase):
    def test_loads_supported_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validityci.toml"
            path.write_text(
                "[experiment]\n"
                'task_type = "binary_classification"\n'
                'target_column = "outcome"\n'
                'primary_metric = "f1"\n'
                'primary_metric_variable = "validation_f1"\n'
                'entity_column = "customer_id"\n',
                encoding="utf-8",
            )
            config = ExperimentConfig.from_toml(path)

        self.assertEqual(config.target_column, "outcome")
        self.assertEqual(config.entity_column, "customer_id")
        self.assertEqual(config.primary_metric_variable, "validation_f1")
        self.assertEqual(config.random_seed, 42)


class AuditTests(unittest.TestCase):
    def test_flags_accuracy_for_imbalanced_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "validityci.toml"
            config_path.write_text(
                "[experiment]\n"
                'task_type = "binary_classification"\n'
                'target_column = "outcome"\n'
                'primary_metric = "accuracy"\n',
                encoding="utf-8",
            )
            data_path = root / "data.csv"
            data_path.write_text(
                "feature,outcome\n1,0\n2,0\n3,0\n4,0\n5,0\n6,0\n7,0\n8,0\n9,0\n10,1\n",
                encoding="utf-8",
            )
            notebook_path = root / "experiment.ipynb"
            notebook_path.write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "source": ["from sklearn.metrics import accuracy_score\n"],
                                "metadata": {},
                                "outputs": [],
                                "execution_count": None,
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )

            report = audit_experiment(notebook_path, data_path, config_path)

        self.assertEqual(report.status, "attention_required")
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].check_id, "metric_suitability.class_imbalance")
        self.assertEqual(
            report.findings[0].policy_id, "policy.metric_accuracy_imbalance"
        )
        self.assertEqual(report.findings[0].policy_version, "1.0.0")
        self.assertEqual(report.evidence[0].notebook_cells, (0,))

    def test_accepts_f1_for_imbalanced_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "validityci.toml").write_text(
                "[experiment]\n"
                'task_type = "binary_classification"\n'
                'target_column = "outcome"\n'
                'primary_metric = "f1"\n',
                encoding="utf-8",
            )
            (root / "data.csv").write_text(
                "feature,outcome\n1,0\n2,0\n3,0\n4,0\n5,0\n6,0\n7,0\n8,0\n9,0\n10,1\n",
                encoding="utf-8",
            )
            (root / "experiment.ipynb").write_text(
                json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
                encoding="utf-8",
            )

            report = audit_experiment(
                root / "experiment.ipynb",
                root / "data.csv",
                root / "validityci.toml",
            )

        self.assertEqual(report.status, "passed_supported_checks")
        self.assertEqual(report.findings, ())

    def test_report_round_trips_through_json(self) -> None:
        report = self._build_report()

        encoded = json.dumps(report.to_dict())
        restored = AuditReport.from_dict(json.loads(encoded))

        self.assertEqual(restored, report)
        self.assertEqual(restored.schema_version, REPORT_SCHEMA_VERSION)

    def test_html_report_renders_immutable_evidence(self) -> None:
        report = self._build_report()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.html"

            write_html(report, output)

            rendered = output.read_text(encoding="utf-8")
        self.assertIn("Accuracy may hide minority-class failures", rendered)
        self.assertIn("minority_fraction", rendered)
        self.assertIn("policy.metric_accuracy_imbalance", rendered)

    def test_rejects_dangling_evidence_reference(self) -> None:
        raw = self._build_report().to_dict()
        raw["findings"][0]["evidence_ids"] = ["evidence.missing"]

        with self.assertRaisesRegex(ValueError, "missing evidence"):
            AuditReport.from_dict(raw)

    def test_rejects_duplicate_evidence_ids(self) -> None:
        report = self._build_report()
        duplicate = Evidence.from_dict(report.evidence[0].to_dict())

        with self.assertRaisesRegex(ValueError, "Duplicate evidence IDs"):
            AuditReport(
                status=report.status,
                config=report.config,
                notebook=report.notebook,
                dataset=report.dataset,
                evidence=(report.evidence[0], duplicate),
                findings=report.findings,
            )

    def test_rejects_duplicate_finding_ids(self) -> None:
        report = self._build_report()
        duplicate = Finding.from_dict(report.findings[0].to_dict())

        with self.assertRaisesRegex(ValueError, "Duplicate finding IDs"):
            AuditReport(
                status=report.status,
                config=report.config,
                notebook=report.notebook,
                dataset=report.dataset,
                evidence=report.evidence,
                findings=(report.findings[0], duplicate),
            )

    def test_evidence_details_are_immutable(self) -> None:
        evidence = self._build_report().evidence[0]

        with self.assertRaises(TypeError):
            evidence.details["minority_fraction"] = 0.5  # type: ignore[index]

    def test_rejects_unknown_schema_version(self) -> None:
        raw = self._build_report().to_dict()
        raw["schema_version"] = "99.0.0"

        with self.assertRaisesRegex(ValueError, "Unsupported report schema version"):
            AuditReport.from_dict(raw)

    def _build_report(self) -> AuditReport:
        root = Path(__file__).parents[1]
        return audit_experiment(
            root / "examples" / "imbalanced_churn.ipynb",
            root / "examples" / "customer_churn.csv",
            root / "examples" / "validityci.toml",
        )


if __name__ == "__main__":
    unittest.main()
