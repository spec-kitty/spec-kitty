"""Drift guard: the ``spec-commit`` example subject stays commitlint-tolerated.

``#3844`` (surfaced by the ``#3828`` landing commit-cleanliness squad,
scribe-sally lens): the specify mission-step prompt instructed agents to
commit ``spec.md`` with ``--message "Add spec for <slug>"`` -- no
``feature``/``mission`` word -- while its sibling lifecycle generators
(``mission_setup_plan`` / ``mission_finalize``) emit
``Add <artifact> for feature <slug>``. The root
``commitlint.config.cjs`` ``ignores`` regex #1 tolerates exactly the
``/^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) /`` shape, so
the sibling subjects pass but the bare ``Add spec for <slug>`` example
escaped the ignore and failed ``type-empty``/``subject-empty`` (advisory,
``continue-on-error``). Same generator/ignore drift class as ``#3678``
(record-analysis).

The fix aligns the example with its siblings using the canonically preferred
term (``mission``): ``--message "Add spec for mission <slug>"``.

This test extracts the example ``--message`` subject straight from the
source template (never a second, independently-typed literal) and asserts it
matches the commitlint ``ignores`` regex #1 -- the offline, unit-level proxy
for "commitlint tolerates this subject", per the ``#3678`` precedent in
``tests/specify_cli/cli/commands/agent/test_mission_record_analysis.py``
(the live ``npx @commitlint/cli`` run needs subprocess/network access, which
the ``unit``/``fast`` markers exclude).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Same repo-root resolution idiom as tests/charter_offering/missions/test_prompt_emptiness.py.
_REPO_ROOT = Path(__file__).parents[3]  # file → missions → doctrine → tests → root
_SPECIFY_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "specify" / "prompt.md"

# Unit-level proxy for commitlint.config.cjs `ignores` regex #1 — the
# tool-commit tolerance for mission lifecycle subjects. Kept in lockstep with
# the literal in commitlint.config.cjs; a deliberate change there is a
# deliberate change to what this guard accepts and should be reviewed as such.
_COMMITLINT_TOOL_COMMIT_IGNORE = re.compile(r"^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) ")

# The spec-commit instruction line inside the specify prompt. The example
# subject is the quoted --message value on this line.
_SPEC_COMMIT_MESSAGE_RE = re.compile(r'spec-kitty spec-commit .*--message "([^"]+)"')


def _example_spec_commit_subject() -> str:
    """Extract the example ``--message`` subject from the source template."""
    assert _SPECIFY_PROMPT.is_file(), f"software-dev/specify/prompt.md missing at: {_SPECIFY_PROMPT}"
    matches = _SPEC_COMMIT_MESSAGE_RE.findall(_SPECIFY_PROMPT.read_text(encoding="utf-8"))
    assert matches, (
        'no `spec-kitty spec-commit ... --message "..."` example found in '
        f"{_SPECIFY_PROMPT} -- the commit instruction was moved or reworded; "
        "update this guard to follow it"
    )
    return matches[0]


@pytest.mark.unit
@pytest.mark.fast
def test_spec_commit_example_subject_is_commitlint_tolerated() -> None:
    """The example subject must match the tool-commit ignore (not escape it)."""
    subject = _example_spec_commit_subject()
    assert _COMMITLINT_TOOL_COMMIT_IGNORE.search(subject), (
        f"the specify prompt's example spec-commit subject {subject!r} does not "
        "match commitlint.config.cjs ignores regex #1 "
        "(/^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) /) and "
        "would fail type-empty/subject-empty (#3844 generator/ignore drift "
        "class, cf. #3678)"
    )


@pytest.mark.unit
@pytest.mark.fast
def test_spec_commit_example_subject_uses_canonical_mission_term() -> None:
    """The example subject names the domain object: ``mission`` (#3844).

    The Terminology Canon prefers ``mission`` over the prohibited ``feature``
    for canonical operator-facing language; the commitlint ignore accepts
    both, so this pins the canonically preferred spelling without loosening
    the tolerance check above.
    """
    subject = _example_spec_commit_subject()
    assert " for mission " in subject, (
        f"example spec-commit subject {subject!r} should read 'Add spec for mission <slug>' (canonical term), not omit the domain-object word"
    )
