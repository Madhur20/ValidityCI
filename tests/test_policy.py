from __future__ import annotations

import unittest

from validityci.policy import (
    FINDING_POLICY_VERSION,
    finding_policies,
    resolve_finding_policy,
)
from validityci.schemas import Confidence, Severity


class FindingPolicyTests(unittest.TestCase):
    def test_supported_outcomes_have_expected_impact(self) -> None:
        expected = {
            ("metric_suitability.class_imbalance", "accuracy_on_imbalanced_target"): (
                Severity.WARNING,
                Confidence.HIGH,
            ),
            ("split.entity_overlap", "confirmed_overlap"): (
                Severity.BLOCKING,
                Confidence.HIGH,
            ),
            ("preprocessing.fit_scope", "confirmed_leakage"): (
                Severity.BLOCKING,
                Confidence.HIGH,
            ),
            ("preprocessing.fit_scope", "unverified_fit_scope"): (
                Severity.WARNING,
                Confidence.MEDIUM,
            ),
            ("reproducibility.repeated_execution", "diverged"): (
                Severity.WARNING,
                Confidence.HIGH,
            ),
        }

        for key, impact in expected.items():
            with self.subTest(key=key):
                policy = resolve_finding_policy(*key)
                self.assertEqual((policy.severity, policy.confidence), impact)
                self.assertEqual(policy.version, FINDING_POLICY_VERSION)
                self.assertTrue(policy.rationale)

    def test_policy_catalog_has_unique_stable_ids(self) -> None:
        policies = finding_policies()

        self.assertEqual(len(policies), 5)
        self.assertEqual(len({policy.policy_id for policy in policies}), len(policies))
        self.assertTrue(
            all(policy.policy_id.startswith("policy.") for policy in policies)
        )

    def test_unknown_outcome_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "No finding policy is registered"):
            resolve_finding_policy("split.entity_overlap", "guessed_overlap")


if __name__ == "__main__":
    unittest.main()
