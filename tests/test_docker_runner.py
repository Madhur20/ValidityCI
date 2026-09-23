from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from validityci.runner import DockerRunner, Runner
from validityci.schemas import (
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
    MetricSelector,
    ResourceLimits,
)


class DockerRunnerTests(unittest.TestCase):
    def test_success_uses_restricted_container_and_only_staged_inputs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            request = self._request(root)
            expected = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.SUCCEEDED,
                duration_ms=42,
                output_fingerprint="sha256:stable",
                metrics=(
                    MetricArtifact(
                        id="metric.1",
                        metric_name="accuracy",
                        status=MetricCaptureStatus.CAPTURED,
                        capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                        value=0.9,
                        cell_index=0,
                        sample_count=1,
                    ),
                ),
            )
            observed: dict[str, object] = {}

            def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                if command[1] == "rm":
                    return subprocess.CompletedProcess(command, 0, "", "")
                observed["command"] = command
                observed["kwargs"] = kwargs
                input_directory = self._mount_source(command, "/workspace/input")
                output_directory = self._mount_source(command, "/workspace/output")
                observed["input_names"] = sorted(path.name for path in input_directory.iterdir())
                (output_directory / "result.json").write_text(
                    json.dumps(expected.to_dict()), encoding="utf-8"
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            runner = DockerRunner()
            with patch("validityci.runner.docker.subprocess.run", side_effect=run):
                result = runner.execute(request)

        self.assertIsInstance(runner, Runner)
        self.assertEqual(result, expected)
        self.assertEqual(observed["input_names"], ["data.csv", "experiment.ipynb"])
        command = observed["command"]
        self.assertIsInstance(command, list)
        self.assertIn("none", self._option_values(command, "--network"))
        self.assertIn("--read-only", command)
        self.assertIn("ALL", self._option_values(command, "--cap-drop"))
        self.assertIn("no-new-privileges", self._option_values(command, "--security-opt"))
        self.assertIn("10001:10001", self._option_values(command, "--user"))
        self.assertIn("256m", self._option_values(command, "--memory"))
        self.assertIn("1", self._option_values(command, "--cpus"))
        self.assertIn("32", self._option_values(command, "--pids-limit"))
        self.assertIn("accuracy", self._option_values(command, "--metric-name"))
        self.assertIn("accuracy", self._option_values(command, "--metric-variable"))
        self.assertIn("entity_id", self._option_values(command, "--entity-column"))
        self.assertIn("1", self._option_values(command, "--positive-class"))
        self.assertNotIn("--privileged", command)
        self.assertEqual(observed["kwargs"]["timeout"], 2)  # type: ignore[index]

    def test_cell_failure_is_returned_without_becoming_container_error(self) -> None:
        with TemporaryDirectory() as directory:
            request = self._request(Path(directory))
            expected = ExecutionResult(
                execution_id=request.execution_id,
                status=ExecutionStatus.CELL_FAILED,
                duration_ms=12,
                failure=ExecutionFailure(
                    kind="notebook_cell_error",
                    message="NameError: missing_name is not defined",
                    cell_index=3,
                ),
            )

            def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[1] == "run":
                    output = self._mount_source(command, "/workspace/output")
                    (output / "result.json").write_text(
                        json.dumps(expected.to_dict()), encoding="utf-8"
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("validityci.runner.docker.subprocess.run", side_effect=run):
                result = DockerRunner().execute(request)

        self.assertEqual(result, expected)

    def test_host_timeout_forcibly_removes_container(self) -> None:
        with TemporaryDirectory() as directory:
            request = self._request(Path(directory))
            commands: list[list[str]] = []

            def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if command[1] == "run":
                    raise subprocess.TimeoutExpired(command, request.limits.timeout_seconds)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("validityci.runner.docker.subprocess.run", side_effect=run):
                result = DockerRunner().execute(request)

        self.assertEqual(result.status, ExecutionStatus.TIMED_OUT)
        self.assertEqual(result.failure.kind, "execution_timeout")  # type: ignore[union-attr]
        remove_commands = [command for command in commands if command[1:3] == ["rm", "--force"]]
        self.assertTrue(remove_commands)

    def test_network_request_is_rejected_before_docker_is_called(self) -> None:
        with TemporaryDirectory() as directory:
            request = self._request(Path(directory), network_enabled=True)
            with patch("validityci.runner.docker.subprocess.run") as run:
                result = DockerRunner().execute(request)

        self.assertEqual(result.status, ExecutionStatus.RUNNER_ERROR)
        self.assertEqual(result.failure.kind, "network_policy")  # type: ignore[union-attr]
        run.assert_not_called()

    def test_missing_docker_binary_becomes_structured_runner_error(self) -> None:
        with TemporaryDirectory() as directory:
            request = self._request(Path(directory))
            with patch(
                "validityci.runner.docker.subprocess.run",
                side_effect=FileNotFoundError("docker was not found"),
            ):
                result = DockerRunner().execute(request)

        self.assertEqual(result.status, ExecutionStatus.RUNNER_ERROR)
        self.assertEqual(result.failure.kind, "docker_unavailable")  # type: ignore[union-attr]

    @staticmethod
    def _request(root: Path, *, network_enabled: bool = False) -> ExecutionRequest:
        notebook = root / "experiment.ipynb"
        notebook.write_text('{"cells": []}', encoding="utf-8")
        data = root / "data.csv"
        data.write_text("feature,target\n1,0\n", encoding="utf-8")
        secret = root / "secret.txt"
        secret.write_text("must not be staged", encoding="utf-8")
        return ExecutionRequest(
            execution_id="execution.original",
            notebook_path=str(notebook),
            data_paths=(str(data),),
            working_directory=str(root),
            metric_selector=MetricSelector(
                metric_name="accuracy", variable_name="accuracy"
            ),
            entity_column="entity_id",
            positive_class="1",
            limits=ResourceLimits(
                timeout_seconds=2,
                memory_mb=256,
                cpu_count=1,
                process_limit=32,
                max_output_bytes=16_384,
            ),
            network_enabled=network_enabled,
        )

    @staticmethod
    def _mount_source(command: list[str], destination: str) -> Path:
        for index, item in enumerate(command):
            if item != "--mount":
                continue
            fields = dict(
                part.split("=", 1)
                for part in command[index + 1].split(",")
                if "=" in part
            )
            if fields.get("dst") == destination:
                return Path(fields["src"])
        raise AssertionError(f"No mount found for {destination}")

    @staticmethod
    def _option_values(command: list[str], option: str) -> list[str]:
        return [command[index + 1] for index, item in enumerate(command[:-1]) if item == option]


if __name__ == "__main__":
    unittest.main()
