"""Always-on gate: canonical command templates stay free of dev-time drift.

Source: ``tests/specify_cli/test_command_template_cleanliness.py`` (WP06 /
T026), which lives directly under ``tests/specify_cli`` — recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374,
decide-out-of-matrix-test-dirs ledger, lift-invariant disposition).

The source suite mixes two different topics: content CLEANLINESS (no
leftover dev-slug/absolute-path/deprecated-terminology artifacts — this
lift) and content GUIDANCE-PRESENCE (``--mission`` reminders, frontmatter
description, WP ownership fields — a broader, separate concern left
out-of-matrix). This lift narrows to the cleanliness invariant the ledger's
one-line summary names ("no drift/leftover placeholders").
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_root_command_template_cleanliness import test_no_dev_specific_mission_slugs as test_no_dev_specific_mission_slugs
from tests.architectural._lifted_root_command_template_cleanliness import test_no_absolute_user_paths as test_no_absolute_user_paths
from tests.architectural._lifted_root_command_template_cleanliness import test_no_planning_repository_terminology as test_no_planning_repository_terminology

pytestmark = [pytest.mark.architectural]
