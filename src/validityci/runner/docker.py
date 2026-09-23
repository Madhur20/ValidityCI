"""Restricted Docker implementation of the runner protocol."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

from validityci.schemas import (
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)


DEFAULT_RUNNER_IMAGE = "validityci-runner:0.6.0"
_CONTAINER_INPUT = "/workspace/input"
_CONTAINER_OUTPUT = "/workspace/output"


class DockerRunner:
    """Execute a notebook with a deliberately narrow Docker sandbox."""

    def __init__(self, image: str = DEFAULT_RUNNER_IMAGE, docker_binary: str = "docker") -> None:
        if not image.strip():
            raise ValueError("Docker image cannot be empty")
        if not docker_binary.strip():
            raise ValueError("Docker binary cannot be empty")
        self._image = image
        self._docker_binary = docker_binary

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started = time.monotonic()
        if request.network_enabled:
            return self._runner_error(
                request,
                started,
                "network_policy",
                "The restricted Docker runner does not permit network access",
            )

        try:
            notebook, data_paths = self._validate_inputs(request)
        except (OSError, ValueError) as error:
            return self._runner_error(request, started, "invalid_input", str(error))

        container_name = self._container_name(request.execution_id)
        try:
            with tempfile.TemporaryDirectory(prefix="validityci-run-") as directory:
                run_root = Path(directory)
                input_directory = run_root / "input"
                output_directory = run_root / "output"
                input_directory.mkdir(mode=0o700)
                output_directory.mkdir(mode=0o700)
                output_directory.chmod(0o777)

                staged_notebook = self._stage_file(notebook, input_directory)
                for data_path in data_paths:
                    self._stage_file(data_path, input_directory)
                input_directory.chmod(0o755)

                command = self._docker_command(
                    request=request,
                    container_name=container_name,
                    input_directory=input_directory,
                    output_directory=output_directory,
                    notebook_name=staged_notebook.name,
                )
                try:
                    completed = subprocess.run(
                        command,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=request.limits.timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    self._remove_container(container_name)
                    return ExecutionResult(
                        execution_id=request.execution_id,
                        status=ExecutionStatus.TIMED_OUT,
                        duration_ms=self._duration_ms(started),
                        failure=ExecutionFailure(
                            kind="execution_timeout",
                            message=(
                                "Notebook execution exceeded "
                                f"{request.limits.timeout_seconds} seconds"
                            ),
                        ),
                        execution_variant=request.execution_variant,
                    )
                except OSError as error:
                    return self._runner_error(
                        request, started, "docker_unavailable", str(error)
                    )

                result_path = output_directory / "result.json"
                if completed.returncode != 0:
                    message = self._bounded_message(
                        completed.stderr,
                        request.limits.max_output_bytes,
                        fallback="Docker exited without an error message",
                    )
                    return self._runner_error(
                        request, started, "container_error", message
                    )
                if not result_path.is_file():
                    return self._runner_error(
                        request,
                        started,
                        "missing_result",
                        "The runner container did not produce result.json",
                    )
                if result_path.stat().st_size > request.limits.max_output_bytes:
                    return self._runner_error(
                        request,
                        started,
                        "output_limit",
                        "The runner result exceeded the configured output limit",
                    )
                try:
                    raw = json.loads(result_path.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict):
                        raise TypeError("result.json must contain an object")
                    result = ExecutionResult.from_dict(raw)
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                    return self._runner_error(
                        request, started, "invalid_result", str(error)
                    )
                if result.execution_id != request.execution_id:
                    return self._runner_error(
                        request,
                        started,
                        "execution_id_mismatch",
                        "The container returned a result for another execution",
                    )
                if result.execution_variant is not request.execution_variant:
                    return self._runner_error(
                        request,
                        started,
                        "execution_variant_mismatch",
                        "The container returned a different execution variant",
                    )
                return result
        finally:
            self._remove_container(container_name)

    @staticmethod
    def _validate_inputs(
        request: ExecutionRequest,
    ) -> tuple[Path, tuple[Path, ...]]:
        notebook = Path(request.notebook_path).resolve(strict=True)
        if not notebook.is_file() or notebook.suffix.lower() != ".ipynb":
            raise ValueError("notebook_path must reference an existing .ipynb file")
        data_paths = tuple(Path(path).resolve(strict=True) for path in request.data_paths)
        if any(not path.is_file() for path in data_paths):
            raise ValueError("Every data path must reference a regular file")
        names = [notebook.name, *(path.name for path in data_paths)]
        if len(names) != len(set(names)):
            raise ValueError("Notebook and data files must have unique base names")
        return notebook, data_paths

    @staticmethod
    def _stage_file(source: Path, destination: Path) -> Path:
        target = destination / source.name
        shutil.copyfile(source, target)
        target.chmod(0o444)
        return target

    def _docker_command(
        self,
        *,
        request: ExecutionRequest,
        container_name: str,
        input_directory: Path,
        output_directory: Path,
        notebook_name: str,
    ) -> list[str]:
        limits = request.limits
        command = [
            self._docker_binary,
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--hostname",
            "validityci",
            "--read-only",
            "--init",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(limits.process_limit),
            "--memory",
            f"{limits.memory_mb}m",
            "--memory-swap",
            f"{limits.memory_mb}m",
            "--cpus",
            str(limits.cpu_count),
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--shm-size",
            "64m",
            "--ulimit",
            "nofile=1024:1024",
            "--user",
            "10001:10001",
            "--env",
            "HOME=/tmp",
            "--env",
            "MPLCONFIGDIR=/tmp/matplotlib",
            "--env",
            "PYTHONHASHSEED=0",
            "--mount",
            f"type=bind,src={input_directory},dst={_CONTAINER_INPUT},readonly",
            "--mount",
            f"type=bind,src={output_directory},dst={_CONTAINER_OUTPUT}",
            self._image,
            "--execution-id",
            request.execution_id,
            "--notebook",
            f"{_CONTAINER_INPUT}/{notebook_name}",
            "--output",
            f"{_CONTAINER_OUTPUT}/result.json",
            "--cell-timeout",
            str(limits.timeout_seconds),
            "--max-output-bytes",
            str(limits.max_output_bytes),
            "--execution-variant",
            request.execution_variant.value,
            "--random-seed",
            str(request.random_seed),
        ]
        if request.metric_selector is not None:
            command.extend(
                ["--metric-name", request.metric_selector.metric_name]
            )
            if request.metric_selector.variable_name is not None:
                command.extend(
                    ["--metric-variable", request.metric_selector.variable_name]
                )
        if request.entity_column is not None:
            command.extend(["--entity-column", request.entity_column])
        if request.positive_class is not None:
            command.extend(["--positive-class", request.positive_class])
        return command

    def _remove_container(self, container_name: str) -> None:
        try:
            subprocess.run(
                [self._docker_binary, "rm", "--force", container_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    @staticmethod
    def _container_name(execution_id: str) -> str:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "-", execution_id)[:40]
        return f"validityci-{safe_id}-{uuid4().hex[:10]}"

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, round((time.monotonic() - started) * 1000))

    @classmethod
    def _runner_error(
        cls,
        request: ExecutionRequest,
        started: float,
        kind: str,
        message: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            execution_id=request.execution_id,
            status=ExecutionStatus.RUNNER_ERROR,
            duration_ms=cls._duration_ms(started),
            failure=ExecutionFailure(kind=kind, message=message),
            execution_variant=request.execution_variant,
        )

    @staticmethod
    def _bounded_message(message: str, limit: int, *, fallback: str) -> str:
        normalized = message.strip() or fallback
        encoded = normalized.encode("utf-8")
        if len(encoded) <= limit:
            return normalized
        return encoded[:limit].decode("utf-8", errors="ignore") + "…"
