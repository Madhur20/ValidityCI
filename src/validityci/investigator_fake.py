"""Deterministic investigator adapter for tests and offline evaluation."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any

from validityci.investigator import ReadOnlyInvestigatorContext


class FakeInvestigatorAdapter:
    """Return configured drafts or failures while recording read-only contexts."""

    def __init__(self, results: Iterable[Mapping[str, Any] | Exception]) -> None:
        self._results = deque(results)
        self.contexts: list[ReadOnlyInvestigatorContext] = []

    def generate(
        self, context: ReadOnlyInvestigatorContext
    ) -> Mapping[str, Any]:
        self.contexts.append(context)
        if not self._results:
            raise RuntimeError("Fake investigator adapter has no remaining result")
        result = self._results.popleft()
        if isinstance(result, Exception):
            raise result
        return result


__all__ = ["FakeInvestigatorAdapter"]
