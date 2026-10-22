"""Packaging assertion: keyring must not be declared as a project dependency."""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_packaging_windows_keyring.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_packaging_windows_keyring import (
    test_keyring_not_declared_in_project_dependencies as test_keyring_not_declared_in_project_dependencies,
)

pytestmark = [pytest.mark.integration]
