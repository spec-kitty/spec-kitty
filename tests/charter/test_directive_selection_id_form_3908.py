"""Regression guard for #3908: a stem-authored directive selection resolves.

``charter.yaml`` authors ``governance.charter.selected_directives`` as file
stems (``001-architectural-integrity-standard``) — the same activation
vocabulary ``test_config_stem_parity.py`` pins — while the built-in catalog
carries canonical config ids (``DIRECTIVE_001``). ``_resolve_directive_base``
compared the two spellings raw, so every stem-authored selection read as
unavailable and ``resolve_project_governance`` raised
``GovernanceResolutionError``.

The blast radius was quiet, which is what made it a P0: the compact context
path catches that error, degrades every kind to ``(none)``, and the command
still exits ``success: true``. A second ``spec-kitty charter context --action
specify`` (the steady-state/compact render) therefore reported no template set,
no paradigms and no directives on a repository whose charter selects 31 of
them, and runtime prompts carried the same empty governance.

These tests pin the two halves that matter: a stem-authored selection resolves,
and a genuinely absent one still fails loud rather than being normalized into
silence.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from charter.activation.compact import _resolve_governance_summary
from charter.activation.resolver import GovernanceResolutionError, resolve_project_governance
from charter.resolution import resolve_canonical_repo_root

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _project(tmp_path: Path, selected_directives: list[str]) -> Path:
    """A git-tracked project whose charter selects directives by the given ids.

    Charter resolution requires a git-tracked root (``resolve_canonical_repo_root``),
    so the fixture inits one rather than handing the loader a bare directory it
    would refuse.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    _write_charter(repo, selected_directives)
    return repo


def _write_charter(repo: Path, selected_directives: list[str]) -> None:
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(
        yaml.safe_dump(
            {
                "governance": {
                    "charter": {
                        "selected_paradigms": [],
                        "selected_directives": selected_directives,
                        "selected_tactics": [],
                        "selected_styleguides": [],
                        "selected_toolguides": [],
                        "selected_procedures": [],
                        "selected_agent_profiles": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_stem_authored_selection_resolves_to_its_canonical_directive(tmp_path: Path) -> None:
    repo = _project(tmp_path, ["001-architectural-integrity-standard", "034-test-first-development"])

    resolution = resolve_project_governance(repo)

    assert "DIRECTIVE_001" in resolution.directives
    assert "DIRECTIVE_034" in resolution.directives
    # One spelling on the wire: the stem must not survive alongside its
    # canonical id, or every consumer downstream sees the artifact twice.
    assert "001-architectural-integrity-standard" not in resolution.directives


def test_canonical_authored_selection_still_resolves(tmp_path: Path) -> None:
    """The other spelling keeps working — this fix widens, never swaps."""
    repo = _project(tmp_path, ["DIRECTIVE_001"])

    assert "DIRECTIVE_001" in resolve_project_governance(repo).directives


def test_a_genuinely_absent_directive_still_fails_loud(tmp_path: Path) -> None:
    """#3908 acceptance: missing artifacts stay explicit, never filtered away.

    The error also has to name the spelling the operator actually wrote, or the
    message sends them looking for a file name they never typed.
    """
    repo = _project(tmp_path, ["999-not-a-real-directive"])

    with pytest.raises(GovernanceResolutionError) as caught:
        resolve_project_governance(repo)

    assert "999-not-a-real-directive" in str(caught.value)


def test_this_repository_compact_context_keeps_its_activated_governance() -> None:
    """The reported reproduction, on the committed charter that exhibited it.

    ``_resolve_governance_summary`` is the compact render's governance leg — the
    exact call whose ``GovernanceResolutionError`` became
    ``Diagnostics: governance unresolved`` and an all-``(none)`` rail on the
    second ``charter context`` run. Asserting on content (a real template set
    and real directive ids), not on an exit code, per the issue's acceptance.
    """
    if resolve_canonical_repo_root(REPO_ROOT) != REPO_ROOT:
        pytest.skip("repository-level charter assertion must read the canonical checkout under test")

    template_set, paradigms, _tools, diagnostics, directives = _resolve_governance_summary(REPO_ROOT)

    assert not any("governance unresolved" in d for d in diagnostics), f"#3908: compact context lost this repository's activated governance: {diagnostics}"
    assert template_set != "(none)"
    assert paradigms != "(none)"
    assert any(d.startswith("DIRECTIVE_") for d in directives), "the compact rail must carry the charter's directive ids, not an empty set"
