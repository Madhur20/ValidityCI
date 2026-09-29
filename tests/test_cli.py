from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validityci.cli import main


class InvestigatorBenchmarkCliTests(unittest.TestCase):
    def test_baseline_command_writes_aggregate_report(self) -> None:
        root = Path(__file__).parents[1]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "benchmark.json"

            main(
                [
                    "benchmark-investigator",
                    "--benchmark",
                    str(root / "benchmarks" / "investigator" / "cases.json"),
                    "--output",
                    str(output),
                ]
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["benchmark_schema_version"], "1.0.0")
        self.assertEqual(result["case_count"], 13)
        self.assertTrue(result["aggregate"]["passes_release_gate"])

    def test_adversarial_corpus_exits_unsuccessfully_and_writes_results(self) -> None:
        root = Path(__file__).parents[1]
        benchmark_root = root / "benchmarks" / "investigator"
        with TemporaryDirectory() as directory:
            output = Path(directory) / "adversarial.json"

            with self.assertRaisesRegex(SystemExit, "1"):
                main(
                    [
                        "benchmark-investigator",
                        "--benchmark",
                        str(benchmark_root / "cases.json"),
                        "--responses",
                        str(benchmark_root / "adversarial-responses.json"),
                        "--output",
                        str(output),
                    ]
                )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["aggregate"]["factual_support_pass_rate"], 0.0)
        self.assertFalse(result["aggregate"]["passes_release_gate"])


if __name__ == "__main__":
    unittest.main()
