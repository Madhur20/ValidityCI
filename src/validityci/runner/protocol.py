"""The boundary between audit orchestration and an execution backend."""

from typing import Protocol, runtime_checkable

from validityci.schemas import ExecutionRequest, ExecutionResult


@runtime_checkable
class Runner(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute one request and return its terminal result."""

