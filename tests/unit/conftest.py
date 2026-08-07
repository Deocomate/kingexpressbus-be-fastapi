"""Override session DB fixture — these unit tests need no MySQL."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    yield
