"""SC-001: a deactivation survives every promotion and a full upgrade (WP14, FR-001, FR-019).

A project made by a real ``spec-kitty init`` (fresh, so it lives on the
ledger) deactivates directive D while ``activated_directives`` is absent
("absent = all"). Then ``charter activate --preset default`` (no ``--force``),
the interview promotion (selecting D), a synthesis promotion, mission-type
seeding and a full ``spec-kitty upgrade`` run in turn. After each step D is
absent from ``charter context`` and from the effective set, and
``deactivated_directives`` still lists it. ``charter activate directive D``
serves D again.

The preset runs before the interview: the interview promotion seeds an absent
``activated_directives`` from the effective set (absent-key parity, #4400), so
after it the allow list is present (without D), and a non-forced preset that
would drop that list refuses (``PRESET_WOULD_OVERWRITE``) instead of running.
The allow list is therefore asserted absent up to the preset step.

``init``, ``charter``, ``context`` and ``upgrade`` run as real subprocesses; the
interview and synthesis promotions and the mission-type seeding are called in
process through the same writers those commands use.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_ledger import prepare_ledger_write
from charter.activation.charter_yaml_io import apply_yaml_write
from charter.activation.compiler import provision_mission_type_activations
from charter.activation.pack_context import PackContext
from charter.activation.synthesizer.reach_only import append_synthesized_activations
from charter.offering.artifact_kinds import ArtifactKind
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter.interview import _promote_interview_selections
from tests._support.activation_cli import REPO_ROOT, cli, git, init_git_repo, unwrapped

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_D = "024-locality-of-change"
_D_ID = "DIRECTIVE_024"
_OTHER = "010-specification-fidelity-requirement"
_SAFE = YAML(typ="safe")
_DEFAULT_TYPES = _SAFE.load((REPO_ROOT / "packs" / "built-in" / "presets" / "default.yaml").read_text(encoding="utf-8"))["mission_type_activations"]


def _ledger(repo: Path) -> dict[str, Any]:
    return dict(_SAFE.load(activation_ledger_path(repo).read_text(encoding="utf-8")) or {})


def _context_ids(repo: Path) -> set[str]:
    result = cli(repo, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded")
    assert result.returncode == 0, unwrapped(result)
    return {entry["id"] if isinstance(entry, dict) else str(entry) for entry in json.loads(result.stdout)["all_directives"]}


def _admitted(repo: Path) -> bool:
    return PackContext.from_config(repo).admits(ArtifactKind.DIRECTIVE, _D, available=frozenset({_D, _OTHER}))


def _assert_still_denied(repo: Path, step: str) -> None:
    assert _D_ID not in _context_ids(repo), f"after {step}: D is served by charter context"
    assert not _admitted(repo), f"after {step}: D is in the effective set"
    assert _D in _ledger(repo).get("deactivated_directives", []), f"after {step}: the deny entry is gone"


def _interview_promotion(repo: Path) -> None:
    selection = SimpleNamespace(selected_directives=[_D_ID], selected_tactics=[], selected_paradigms=[])
    _promote_interview_selections(repo, selection)


def _preset_default(repo: Path) -> None:
    result = cli(repo, "charter", "activate", "--preset", "default", "--no-compile")
    assert result.returncode == 0, unwrapped(result)


def _synthesis_promotion(repo: Path) -> None:
    append_synthesized_activations(repo, {"tactic": ["acceptance-test-first"]})


def _mission_type_seeding(repo: Path) -> None:
    apply_yaml_write(prepare_ledger_write(repo, {}, remove=["mission_type_activations"]))
    assert provision_mission_type_activations(repo) is True
    assert _ledger(repo)["mission_type_activations"] == _DEFAULT_TYPES  # the seeding really ran


def _full_upgrade(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "before upgrade")
    result = cli(repo, "upgrade", "--yes", "--no-worktrees")
    assert result.returncode == 0, unwrapped(result)


_STEPS: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("charter activate --preset default", _preset_default),
    ("the interview promotion", _interview_promotion),
    ("a synthesis promotion", _synthesis_promotion),
    ("mission-type seeding", _mission_type_seeding),
    ("a full spec-kitty upgrade", _full_upgrade),
)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    repo = init_git_repo(tmp_path / "project")
    result = cli(repo, "init", ".", "--ai", "claude")
    assert result.returncode == 0, unwrapped(result)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "spec-kitty init")
    return repo


def test_a_deactivation_with_no_allow_list_survives_every_promotion_and_upgrade(project: Path) -> None:
    assert activation_ledger_path(project).is_file(), "a fresh init lives on the ledger"
    assert "activated_directives" not in _ledger(project)
    assert _D_ID in _context_ids(project)  # positive control
    assert _admitted(project)

    deactivated = cli(project, "charter", "deactivate", "directive", _D, "--no-compile")
    assert deactivated.returncode == 0, unwrapped(deactivated)
    assert "activated_directives" not in _ledger(project)
    _assert_still_denied(project, "charter deactivate")

    for step, run in _STEPS:
        run(project)
        _assert_still_denied(project, step)
        if run is _preset_default:
            assert "activated_directives" not in _ledger(project), "the preset keeps the allow list absent"

    reactivated = cli(project, "charter", "activate", "directive", _D, "--no-compile")
    assert reactivated.returncode == 0, unwrapped(reactivated)
    assert _D_ID in _context_ids(project)
    assert _admitted(project)
    assert _D not in _ledger(project).get("deactivated_directives", [])
