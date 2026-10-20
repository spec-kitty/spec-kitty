"""Agent directories must stay excluded from language detection (#6444).

``charter.activation.language_authority.EXCLUDED_DIRS`` hand-copies the agent tool
directories, because ``charter`` cannot import ``specify_cli``. The canonical list is
``specify_cli.agent_utils.directories.AGENT_DIRS``; this guard fails when a new agent root
is added there without being excluded here, which would let its generated helper scripts
count as project sources. ``.github`` is the one deliberate exception: it also holds the
project's own workflows and issue templates, which are not tooling output.
"""

from __future__ import annotations

import pytest

from charter.activation.language_authority import EXCLUDED_DIRS
from specify_cli.agent_utils.directories import AGENT_DIRS

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_NOT_EXCLUDED = frozenset({".github"})


def test_every_agent_directory_root_is_excluded_from_language_detection() -> None:
    roots = {root for root, _subdir in AGENT_DIRS} - _NOT_EXCLUDED

    missing = sorted(roots - EXCLUDED_DIRS)

    assert not missing, f"agent directories missing from language_authority.EXCLUDED_DIRS: {missing}"
