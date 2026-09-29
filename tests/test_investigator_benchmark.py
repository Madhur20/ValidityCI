from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validityci.investigator_benchmark import (
    BenchmarkCategory,
    InvestigatorResponse,
    deterministic_baseline_run,
    deterministic_baseline_response,
    load_investigator_benchmark,
    load_investigator_responses,
    score_investigator_benchmark,
    score_investigator_response,
)
from validityci.schemas import AuditReport


class InvestigatorBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]
        cls.path = cls.root / "benchmarks" / "investigator" / "cases.json"
        cls.adversarial_path = (
            cls.root
            / "benchmarks"
            / "investigator"
            / "adversarial-responses.json"
        )
        cls.benchmark = load_investigator_benchmark(cls.path)

    def test_catalog_has_required_size_categories_and_resolvable_fixtures(self) -> None:
        self.assertGreaterEqual(len(self.benchmark.cases), 10)
        self.assertEqual(
            {case.category for case in self.benchmark.cases},
            set(BenchmarkCategory),
        )
        for case in self.benchmark.cases:
            relative_path = case.fixture.split("#", 1)[0]
            self.assertTrue((self.root / relative_path).is_file(), case.id)

    def test_report_fixtures_match_expected_statuses_and_support_ids(self) -> None:
        for case in self.benchmark.cases:
            fixture = self.root / case.fixture.split("#", 1)[0]
            if fixture.suffix != ".json":
                continue
            report = AuditReport.from_dict(
                json.loads(fixture.read_text(encoding="utf-8"))
            )
            self.assertEqual(report.status, case.expected_audit_status, case.id)
            observed_checks = {
                check.check_id: check.status for check in report.checks
            }
            self.assertEqual(
                observed_checks,
                dict(case.expected_check_statuses),
                case.id,
            )
            support_ids = {
                *(evidence.id for evidence in report.evidence),
                *(check.check_id for check in report.checks),
                *(execution.execution_id for execution in report.executions),
                *(
                    f"{execution.execution_id}/{metric.id}"
                    for execution in report.executions
                    for metric in execution.metrics
                ),
            }
            self.assertTrue(
                set(case.allowed_evidence_ids).issubset(support_ids), case.id
            )

    def test_deterministic_baseline_is_factual_but_not_fully_useful(self) -> None:
        for case in self.benchmark.cases:
            response = deterministic_baseline_response(case)
            score = score_investigator_response(case, response)

            self.assertTrue(score.passes_factual_support_gate, case.id)
            self.assertEqual(score.evidence_link_accuracy, 1.0, case.id)
            self.assertEqual(score.unsupported_claim_rate, 0.0, case.id)
            self.assertLess(score.usefulness_score, 1.0, case.id)

    def test_complete_supported_response_receives_full_score(self) -> None:
        case = self.benchmark.case("group_isolated_counterfactual")
        response = InvestigatorResponse(
            case_id=case.id,
            observations={
                observation.id: observation.evidence_ids
                for observation in case.observations
            },
            reviewer_question_ids=tuple(
                question.id for question in case.reviewer_questions
            ),
            unresolved_assumption_ids=tuple(
                assumption.id for assumption in case.unresolved_assumptions
            ),
        )

        score = score_investigator_response(case, response)

        self.assertEqual(score.observation_recall, 1.0)
        self.assertEqual(score.reviewer_question_recall, 1.0)
        self.assertEqual(score.unresolved_assumption_recall, 1.0)
        self.assertEqual(score.usefulness_score, 1.0)
        self.assertTrue(score.passes_factual_support_gate)

    def test_aggregate_baseline_is_versioned_and_passes_release_gate(self) -> None:
        run = deterministic_baseline_run(self.benchmark)

        self.assertEqual(run.benchmark_schema_version, "1.0.0")
        self.assertEqual(run.response_schema_version, "1.0.0")
        self.assertEqual(run.factual_support_pass_rate, 1.0)
        self.assertEqual(run.mean_unsupported_claim_rate, 0.0)
        self.assertTrue(run.passes_release_gate)
        self.assertEqual(run.to_dict()["case_count"], len(self.benchmark.cases))

    def test_response_file_loads_and_requires_every_case(self) -> None:
        baseline = [
            deterministic_baseline_response(case) for case in self.benchmark.cases
        ]
        payload = {
            "schema_version": "1.0.0",
            "responses": [
                {
                    "case_id": response.case_id,
                    "observations": {
                        observation_id: list(evidence_ids)
                        for observation_id, evidence_ids in response.observations.items()
                    },
                    "reviewer_question_ids": [],
                    "unresolved_assumption_ids": [],
                    "asserted_forbidden_claim_ids": [],
                }
                for response in baseline
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "responses.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored = load_investigator_responses(path)

        run = score_investigator_benchmark(self.benchmark, restored)
        self.assertTrue(run.passes_release_gate)
        with self.assertRaisesRegex(ValueError, "Missing benchmark responses"):
            score_investigator_benchmark(self.benchmark, restored[:-1])

    def test_wrong_evidence_or_forbidden_claim_fails_factual_gate(self) -> None:
        case = self.benchmark.case("entity_overlap_holdout")
        response = InvestigatorResponse(
            case_id=case.id,
            observations={
                "confirmed_entity_overlap": ("evidence.class_distribution",)
            },
            asserted_forbidden_claim_ids=("claim_overlap_quantifies_bias",),
        )

        score = score_investigator_response(case, response)

        self.assertFalse(score.passes_factual_support_gate)
        self.assertGreater(score.unsupported_claim_rate, 0.0)
        self.assertEqual(score.evidence_link_accuracy, 0.0)

    def test_permanent_adversarial_corpus_fails_every_factual_gate(self) -> None:
        responses = load_investigator_responses(self.adversarial_path)

        run = score_investigator_benchmark(self.benchmark, responses)

        self.assertEqual(len(responses), len(self.benchmark.cases))
        self.assertEqual(run.factual_support_pass_rate, 0.0)
        self.assertFalse(run.passes_release_gate)
        self.assertTrue(
            all(
                not score.passes_factual_support_gate
                for score in run.case_scores.values()
            )
        )

    def test_case_mismatch_is_rejected(self) -> None:
        case = self.benchmark.case("clean_supported_holdout")
        with self.assertRaisesRegex(ValueError, "case ID"):
            score_investigator_response(
                case,
                InvestigatorResponse(case_id="another_case", observations={}),
            )

    def test_duplicate_case_ids_are_rejected(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["cases"][1]["id"] = raw["cases"][0]["id"]
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "cases.json"
            invalid.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "case IDs"):
                load_investigator_benchmark(invalid)

    def test_catalog_contains_no_seeded_entity_values_or_row_indices(self) -> None:
        serialized = "".join(
            path.read_text(encoding="utf-8")
            for path in sorted(self.path.parent.rglob("*.json"))
        )
        for forbidden in (
            "C001",
            "C002",
            "row_indices",
            "fingerprint_key",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
