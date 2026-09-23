"""Non-vacuity gate: ``_gate_coverage._composite_action_path`` rejects
path-traversal (spec-kitty#4408).

``_composite_action_path`` resolves a step's ``uses: ./.github/actions/<name>``
ref to the local composite-action definition file it names, by joining
``actions_dir / name / file_name`` and checking ``.is_file()``. Unlike its
sibling :func:`tests.architectural._gate_coverage._resolve_script_path` (which
resolves the candidate and checks ``is_relative_to(repo_root)``), it never
normalized or contained the result: a ``uses:`` ref carrying ``..`` segments
(``./.github/actions/../../secrets``) resolves — via ordinary filesystem
``..`` traversal at ``.is_file()`` time — to a file *outside* ``actions_dir``,
which :func:`tests.architectural._gate_coverage._splice_step_level_actions`
would then read and attribute to the wrong action, exactly the mis-attribution
#4408 flags.

This is the guard's own permanent non-vacuity test (T004): it stays RED
against the pre-fix ``_composite_action_path`` and pins that the fix mirrors
``_resolve_script_path``'s containment guard without changing the function's
signature (private, self-referenced only; ~18 importers of the module as a
whole).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural import _gate_coverage as gc

pytestmark = pytest.mark.architectural


def _make_actions_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal ``.github/actions/<name>/action.yml`` tree plus an escape
    target *outside* the actions directory a traversal ref could reach.
    """
    actions_dir = tmp_path / ".github" / "actions"
    warmup = actions_dir / "warmup"
    warmup.mkdir(parents=True)
    (warmup / "action.yml").write_text("runs:\n  steps: []\n", encoding="utf-8")

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "action.yml").write_text("runs:\n  steps: [{run: 'cat /etc/passwd'}]\n", encoding="utf-8")

    return actions_dir, secrets_dir


def test_traversal_uses_ref_is_rejected_4408(tmp_path: Path) -> None:
    """A ``uses:`` ref whose name climbs out of ``actions_dir`` via ``..``
    must resolve to ``None``, never to a file outside ``actions_dir`` -- the
    #4408 non-vacuity demo. RED on the pre-fix implementation (it returns the
    escaped path); GREEN after the containment guard is added.
    """
    actions_dir, secrets_dir = _make_actions_tree(tmp_path)
    escaping_uses = "./.github/actions/../../secrets"

    result = gc._composite_action_path(escaping_uses, actions_dir)

    assert result is None, f"traversal ref resolved to {result!r} outside actions_dir {actions_dir}"
    assert not (result is not None and secrets_dir in result.parents)


def test_ordinary_local_action_still_resolves(tmp_path: Path) -> None:
    """The containment guard must not break the normal, non-traversal case."""
    actions_dir, _ = _make_actions_tree(tmp_path)

    result = gc._composite_action_path("./.github/actions/warmup", actions_dir)

    assert result == (actions_dir / "warmup" / "action.yml").resolve()


def test_nested_local_action_still_resolves(tmp_path: Path) -> None:
    """A legitimately nested action name (``a/b``) still resolves inside
    ``actions_dir``; only an actual escape is rejected.
    """
    actions_dir = tmp_path / ".github" / "actions"
    nested = actions_dir / "group" / "child"
    nested.mkdir(parents=True)
    (nested / "action.yml").write_text("runs:\n  steps: []\n", encoding="utf-8")

    result = gc._composite_action_path("./.github/actions/group/child", actions_dir)

    assert result == (nested / "action.yml").resolve()


def test_missing_local_action_still_returns_none(tmp_path: Path) -> None:
    actions_dir = (tmp_path / ".github" / "actions").resolve()
    actions_dir.mkdir(parents=True)

    result = gc._composite_action_path("./.github/actions/does-not-exist", actions_dir)

    assert result is None
