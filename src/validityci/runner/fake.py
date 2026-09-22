"""Deterministic runner used by orchestration tests."""

from collections import deque
from collections.abc import Iterable

from validityci.schemas import ExecutionRequest, ExecutionResult


class FakeRunner:
    def __init__(self, results: Iterable[ExecutionResult]) -> None:
        self._results = deque(results)
        self._requests: list[ExecutionRequest] = []

    @property
    def requests(self) -> tuple[ExecutionRequest, ...]:
        return tuple(self._requests)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self._requests.append(request)
        if not self._results:
            raise RuntimeError("FakeRunner has no result configured for this request")
        result = self._results.popleft()
        if result.execution_id != request.execution_id:
            raise ValueError(
                "Configured result execution_id does not match the request: "
                f"{result.execution_id!r} != {request.execution_id!r}"
            )
        return result
