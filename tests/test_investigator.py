from __future__ import annotations

import json
from pathlib import Path
import unittest

from validityci.audit import audit_experiment
from validityci.investigator import (
    ReadOnlyInvestigatorContext,
    build_deterministic_investigator_summary,
    run_investigator,
)
from validityci.investigator_fake import FakeInvestigatorAdapter
from validityci.runner import FakeRunner
from validityci.schemas import (
    AuditReport,
    AuditStatus,
    ExecutionFailure,
    ExecutionResult,
    ExecutionStatus,
)


class InvestigatorContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]

    def test_read_only_context_returns_structured_copies(self) -> None:
        report = self._static_report()
        context = ReadOnlyInvestigatorContext(report)

        specification = context.get_experiment_specification()
        specification["primary_metric"] = "f1"

        self.assertEqual(report.config.primary_metric, "accuracy")
        self.assertEqual(
            context.get_evidence("evidence.class_distribution")["kind"],
            "dataset_profile",
        )
        self.assertIn("accuracy", context.get_notebook_cell(1)["source"])
        self.assertTrue(context.list_policy_requirements())
        with self.assertRaises(KeyError):
            context.get_evidence("evidence.missing")

    def test_deterministic_summary_cites_only_available_support(self) -> None:
        report = self._static_report()
        context = ReadOnlyInvestigatorContext(report)

        summary = build_deterministic_investigator_summary(report)

        self.assertEqual(summary.source, "deterministic_fallback")
        self.assertTrue(summary.verified_observations)
        known = set(context.supporting_record_ids())
        for observation in summary.verified_observations:
            self.assertTrue(set(observation.evidence_ids).issubset(known))
        self.assertIn("false positives", " ".join(summary.reviewer_questions))

    def test_failed_execution_stays_incomplete_and_becomes_unresolved(self) -> None:
        execution = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.CELL_FAILED,
            duration_ms=5,
            failure=ExecutionFailure(
                kind="notebook_cell_error",
                message="NameError: missing_model",
                cell_index=1,
            ),
        )
        report = self._executed_report(execution)

        summary = build_deterministic_investigator_summary(report)

        self.assertEqual(report.status, AuditStatus.INCOMPLETE)
        self.assertTrue(
            any("missing_model" in item.summary for item in summary.verified_observations)
        )
        self.assertTrue(summary.unresolved_assumptions)
        self.assertIn("Resolve incomplete", summary.recommended_next_action)

    def test_unsupported_metric_is_explicit_and_execution_qualified(self) -> None:
        fixture = (
            self.root
            / "benchmarks"
            / "investigator"
            / "fixtures"
            / "unsupported_primary_metric.json"
        )
        report = AuditReport.from_dict(json.loads(fixture.read_text(encoding="utf-8")))

        summary = build_deterministic_investigator_summary(report)

        self.assertEqual(
            summary.verified_observations[0].evidence_ids,
            ("execution.original/metric.1",),
        )
        self.assertIn("unsupported", summary.verified_observations[0].summary)
        self.assertTrue(summary.unresolved_assumptions)

    def test_deterministic_fallback_matches_permanent_report_snapshots(self) -> None:
        benchmark_root = self.root / "benchmarks" / "investigator"
        payload = json.loads(
            (benchmark_root / "fallback-snapshots.json").read_text(encoding="utf-8")
        )

        self.assertEqual(payload["schema_version"], "1.0.0")
        fixture_names = {
            path.name for path in (benchmark_root / "fixtures").glob("*.json")
        }
        self.assertEqual(set(payload["snapshots"]), fixture_names)
        for fixture_name, expected in payload["snapshots"].items():
            report = AuditReport.from_dict(
                json.loads(
                    (benchmark_root / "fixtures" / fixture_name).read_text(
                        encoding="utf-8"
                    )
                )
            )
            observed = build_deterministic_investigator_summary(report).to_dict()
            self.assertEqual(observed, expected, fixture_name)

    def test_rejected_adapter_returns_the_snapshotted_fallback(self) -> None:
        benchmark_root = self.root / "benchmarks" / "investigator"
        fixture_name = "clean_supported_holdout.json"
        report = AuditReport.from_dict(
            json.loads(
                (benchmark_root / "fixtures" / fixture_name).read_text(
                    encoding="utf-8"
                )
            )
        )
        snapshots = json.loads(
            (benchmark_root / "fallback-snapshots.json").read_text(encoding="utf-8")
        )["snapshots"]

        result = run_investigator(
            report,
            FakeInvestigatorAdapter(
                [self._adapter_output(evidence_ids=["evidence.hallucinated"])]
            ),
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.summary.to_dict(), snapshots[fixture_name])

    def test_valid_adapter_output_is_accepted(self) -> None:
        report = self._static_report()
        evidence_id = report.evidence[0].id
        adapter = FakeInvestigatorAdapter(
            [
                {
                    "experiment_claim": "Review the declared churn experiment.",
                    "verified_observations": [
                        {
                            "id": "observation.adapter.1",
                            "summary": "The dataset profile was recorded.",
                            "evidence_ids": [evidence_id],
                        }
                    ],
                    "unresolved_assumptions": ["Deployment prevalence is unknown."],
                    "reviewer_questions": ["What is the deployment prevalence?"],
                    "recommended_next_action": "Confirm the deployment population.",
                }
            ]
        )

        result = run_investigator(report, adapter)

        self.assertFalse(result.used_fallback)
        self.assertIsNone(result.rejection_reason)
        self.assertEqual(result.summary.source, "validated_adapter")
        self.assertEqual(len(adapter.contexts), 1)
        self.assertEqual(
            result.summary.verified_observations[0].evidence_ids, (evidence_id,)
        )

    def test_unknown_adapter_evidence_uses_deterministic_fallback(self) -> None:
        report = self._static_report()
        adapter = FakeInvestigatorAdapter(
            [self._adapter_output(evidence_ids=["evidence.hallucinated"])]
        )

        result = run_investigator(report, adapter)

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.summary.source, "deterministic_fallback")
        self.assertIn("unknown evidence", result.rejection_reason or "")

    def test_unknown_adapter_field_uses_deterministic_fallback(self) -> None:
        report = self._static_report()
        output = self._adapter_output(evidence_ids=[report.evidence[0].id])
        output["severity"] = "critical"

        result = run_investigator(report, FakeInvestigatorAdapter([output]))

        self.assertTrue(result.used_fallback)
        self.assertIn("Unknown investigator output fields", result.rejection_reason or "")

    def test_adapter_failure_uses_deterministic_fallback(self) -> None:
        report = self._static_report()

        result = run_investigator(
            report, FakeInvestigatorAdapter([RuntimeError("offline")])
        )

        self.assertTrue(result.used_fallback)
        self.assertIn("RuntimeError: offline", result.rejection_reason or "")

    @staticmethod
    def _adapter_output(*, evidence_ids: list[str]):
        return {
            "experiment_claim": "Review the declared experiment.",
            "verified_observations": [
                {
                    "id": "observation.adapter.1",
                    "summary": "An evidence-backed observation.",
                    "evidence_ids": evidence_ids,
                }
            ],
            "unresolved_assumptions": [],
            "reviewer_questions": [],
            "recommended_next_action": "Review the unresolved assumptions.",
        }

    def _static_report(self):
        return audit_experiment(
            self.root / "examples" / "imbalanced_churn.ipynb",
            self.root / "examples" / "customer_churn.csv",
            self.root / "examples" / "validityci.toml",
        )

    def _executed_report(self, result: ExecutionResult):
        return audit_experiment(
            self.root / "examples" / "imbalanced_churn.ipynb",
            self.root / "examples" / "customer_churn.csv",
            self.root / "examples" / "validityci.toml",
            runner=FakeRunner([result]),
        )


if __name__ == "__main__":
    unittest.main()
