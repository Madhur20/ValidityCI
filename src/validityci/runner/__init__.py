"""Execution backends for reproducible experiment runs."""

from validityci.runner.fake import FakeRunner
from validityci.runner.protocol import Runner

__all__ = ["FakeRunner", "Runner"]
