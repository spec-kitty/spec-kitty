"""Module-docstring ``docs/*.md`` pointers must resolve — the docs-lane guard that
closes the prose-only down-route hole (#4849, follow-up to #4842).

A docstring-only ``.py`` edit is classified *prose-only* and down-routed off the
module-test matrix + architectural battery (#4842). Some code-shard tests assert
that a module docstring's ``docs/...md`` "see also" pointers resolve (e.g.
``tests/cli/commands/test_upgrade_help_doc_refs.py``); those shards are skipped on
a prose-only PR, so a docstring edit that introduces a **dangling** doc pointer
would not be caught per-PR — only by the nightly full run.

This guard lives in ``tests/docs/`` — the lane the prose-only down-route forces ON
(``ci-router.yml`` ``tests-docs.if`` includes ``prose_only == 'true'``) and which
also runs whenever ``tests/docs/**`` changes — so a new dangling module-docstring
doc pointer reds *here* on a prose-only PR instead of slipping to nightly. It is a
**shrink-only ratchet**: the ``docs/*.md`` pointers that dangle today are
grandfathered (they are pre-existing debt in unrelated subsystems, out of scope to
chase from a CI-routing change — DIRECTIVE_024 locality); the guard fails only when
a **new** dangling pointer appears, or when the grandfathered set can be shrunk.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_DOC_REF = re.compile(r"docs/[A-Za-z0-9._/-]+\.md")

# Pre-existing dangling ``docs/*.md`` pointers in ``src/**`` docstrings/comments as
# of #4849. These are grandfathered so this NEW guard does not inherit unrelated
# cleanup: the guard's job is to stop a prose-only down-route from hiding a *new*
# dangling pointer, not to fix historical drift in other subsystems. Removing an
# entry here (by fixing the pointer at its source) is always allowed and the
# shrink-only assertion rewards it; ADDING an entry is not — fix the pointer instead.
_GRANDFATHERED_DANGLING: frozenset[str] = frozenset(
    {
        "docs/TRACKER_ARCH_ROLE.md",
        "docs/adr/3.x/2026-06-07-1-wp-lane-fsm-genesis-and-finalize-clobber.md",
        "docs/cli/custom-commands.md",
        "docs/development/read-side-seam-classification.md",
        "docs/development/ssh-deploy-keys.md",
        "docs/guides/use-retrospective-learning.md",
        "docs/trail-model.md",
    }
)


def _dangling_doc_refs() -> set[str]:
    """Every ``docs/*.md`` pointer in a ``src/**`` Python file that does not resolve."""
    dangling: set[str] = set()
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for ref in set(_DOC_REF.findall(text)):
            if not (_REPO_ROOT / ref).is_file():
                dangling.add(ref)
    return dangling


def test_no_new_dangling_module_doc_pointer() -> None:
    """No ``src/**`` docstring/comment may point at a ``docs/*.md`` that does not exist.

    Closes the #4842 prose-only down-route hole: a docstring-only edit that adds a
    dangling doc pointer reds here (docs lane, forced on for prose-only PRs) instead
    of only in nightly. Grandfathered pre-existing danglers are tolerated.
    """
    new_dangling = _dangling_doc_refs() - _GRANDFATHERED_DANGLING
    assert not new_dangling, (
        f"New dangling docs/*.md pointer(s) in src/** — fix the pointer (a prose-only PR would not have caught this per-PR): {sorted(new_dangling)}"
    )


def test_grandfathered_set_is_shrink_only() -> None:
    """The grandfathered dangling set must never contain entries that now resolve.

    Fixing a pointer (so it resolves) must be paired with removing it from
    ``_GRANDFATHERED_DANGLING`` — this keeps the ratchet honest and monotonically
    shrinking rather than silently masking a resolved entry forever.
    """
    stale = {ref for ref in _GRANDFATHERED_DANGLING if (_REPO_ROOT / ref).is_file()}
    assert not stale, f"Grandfathered pointer(s) now resolve; remove them from _GRANDFATHERED_DANGLING: {sorted(stale)}"
