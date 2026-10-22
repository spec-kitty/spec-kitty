"""Single home of the command-template cleanliness checks the always-on gate narrows to (#5015).

``tests/specify_cli/test_command_template_cleanliness.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_root_command_template_cleanliness.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

PROMPT_DRIVEN: list[str] = sorted(PROMPT_DRIVEN_COMMANDS)


_PROMPT_STEPS_DIR = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"


_FORBIDDEN_HOME_LITERAL = "/Users/" + "robe" + "rt/"


def _template_content(command: str) -> str:
    """Read and return the content of a command template file."""
    return (_PROMPT_STEPS_DIR / command / "prompt.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_no_dev_specific_mission_slugs(command: str) -> None:
    """Templates must not contain the 057- or 058- dev-time feature slugs.

    The 057- and 058- slugs are development artifacts that leaked from source
    templates during authoring. Generic example slugs like '014-checkout-flow'
    or '020-my-feature' are legitimate documentation placeholders and are allowed.
    """
    content = _template_content(command)
    # Check specifically for the dev-time feature slugs
    for bad_slug in ("057-", "058-"):
        assert bad_slug not in content, f"{command}.md contains dev-time feature slug '{bad_slug}' - strip before shipping to consumers"


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_no_absolute_user_paths(command: str) -> None:
    """Templates must not contain absolute paths tied to a specific machine."""
    content = _template_content(command)
    assert _FORBIDDEN_HOME_LITERAL not in content, f"{command}.md contains a forbidden user-specific home path literal"
    assert re.search(r"/Users/[^/]+/", content) is None, f"{command}.md contains macOS absolute user path '/Users/<user>/'"
    assert re.search(r"/home/[^/]+/", content) is None, f"{command}.md contains Linux absolute user path '/home/<user>/'"


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_no_planning_repository_terminology(command: str) -> None:
    """Templates must not use deprecated planning-location terminology.

    The correct phrase is 'repository root checkout'. Older variants caused
    agents to confuse planning location with branch choice.
    """
    content = _template_content(command)
    assert "planning repository" not in content.lower(), f"{command}.md uses deprecated 'planning repository' terminology - use 'repository root checkout' instead"
    assert "planning repo" not in content.lower(), f"{command}.md uses deprecated 'planning repo' terminology - use 'repository root checkout' instead"
    assert "project root checkout" not in content.lower(), (
        f"{command}.md uses deprecated 'project root checkout' terminology - use 'repository root checkout' instead"
    )
    assert "main repository root" not in content.lower(), f"{command}.md uses ambiguous 'main repository root' terminology - use 'repository root checkout' instead"
