"""Strict accept honours an explicit meta.json "no contracts" waiver (#5298).

``software-dev/mission.yaml`` declares ``paths.deliverables: contracts/``, so a
Mission with no ``contracts/`` is blocked by strict ``accept`` even when it
defines no interfaces (test remediation, refactors). The operator ruling keeps
that default and adds one explicit, auditable escape: ``meta.json`` carries
``"contracts": "none"`` and a non-empty ``contracts_rationale``.

These tests drive the real ``collect_feature_summary`` entry point on a genuine
software-dev-shaped repo (the ``test_accept_contracts_dedup.py`` fixture shape):

* well-formed waiver → no ``contracts`` path violation, rationale surfaced;
* no waiver → still blocked (paired control on the same fixture);
* malformed waiver → still blocked AND warned;
* the waiver never relaxes a build path convention (``tests/``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.acceptance import collect_feature_summary

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "nightly-drift-reds-01M43DRV"
_RATIONALE = "Test-drift remediation; this Mission defines no interfaces."


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


def _no_contracts_repo(
    tmp_path: Path,
    *,
    waiver: dict[str, object] | None,
    build_dirs: tuple[str, ...] = ("src", "tests", "docs"),
) -> Path:
    """A software-dev-shaped repo whose Mission has no ``contracts/``."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for build_dir in build_dirs:
        path = repo_root / build_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": "01M43DRVZZZZZZZZZZZZZZZZZZ",
        "mid8": "01M43DRV",
        "friendly_name": "Nightly drift reds",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-10-04T00:00:00Z",
        **(waiver or {}),
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "init")
    return repo_root


def _contracts_violations(path_violations: list[str]) -> list[str]:
    return [entry for entry in path_violations if "contracts" in entry]


def test_well_formed_waiver_clears_the_contracts_violation(tmp_path: Path) -> None:
    repo_root = _no_contracts_repo(tmp_path, waiver={"contracts": "none", "contracts_rationale": _RATIONALE})

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    assert summary.path_violations == []
    # Auditable: the waiver and its rationale are visible in the accept output.
    assert any(_RATIONALE in warning for warning in summary.warnings), summary.warnings
    # Coherent: a declared-absent artifact is not also nagged as "optional missing".
    assert "contracts" not in [entry.strip("/") for entry in summary.optional_missing]


def test_no_waiver_still_blocks_on_missing_contracts(tmp_path: Path) -> None:
    repo_root = _no_contracts_repo(tmp_path, waiver=None)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    assert _contracts_violations(summary.path_violations)
    assert summary.ok is False


@pytest.mark.parametrize(
    "waiver",
    [
        pytest.param({"contracts": "none"}, id="rationale-missing"),
        pytest.param({"contracts": "none", "contracts_rationale": ""}, id="rationale-blank"),
        pytest.param({"contracts": "skip", "contracts_rationale": _RATIONALE}, id="value-unknown"),
    ],
)
def test_malformed_waiver_still_blocks_and_warns(tmp_path: Path, waiver: dict[str, object]) -> None:
    repo_root = _no_contracts_repo(tmp_path, waiver=waiver)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    violations = _contracts_violations(summary.path_violations)
    assert violations
    assert summary.ok is False
    assert "meta.json" in "\n".join(violations), violations


def test_waiver_never_relaxes_a_build_path_convention(tmp_path: Path) -> None:
    repo_root = _no_contracts_repo(
        tmp_path,
        waiver={"contracts": "none", "contracts_rationale": _RATIONALE},
        build_dirs=("src", "docs"),
    )

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    rendered = "\n".join(summary.path_violations)
    assert "expects tests path" in rendered
    assert "expects deliverables path" not in rendered


def test_lenient_mode_with_a_waiver_has_no_missing_contracts_warning(tmp_path: Path) -> None:
    repo_root = _no_contracts_repo(tmp_path, waiver={"contracts": "none", "contracts_rationale": _RATIONALE})

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=False, mutate_matrix=False)

    assert summary.path_violations == []
    assert not any("expects deliverables path" in warning for warning in summary.warnings), summary.warnings


def test_a_contracts_path_that_is_not_a_mission_artifact_is_never_waived(tmp_path: Path) -> None:
    """The notice appears only where the validator can actually waive the path.

    A custom Mission that declares ``contracts/`` as a path convention but NOT
    as a mission artifact resolves it at the repository root like a build path;
    the waiver cannot apply there, so accept must neither skip it nor claim to.
    """
    from types import SimpleNamespace

    from specify_cli.acceptance.summary_core import evaluate_path_conventions

    repo_root = _no_contracts_repo(tmp_path, waiver={"contracts": "none", "contracts_rationale": _RATIONALE})
    feature_dir = repo_root / "kitty-specs" / _SLUG
    custom = SimpleNamespace(
        name="custom",
        domain="software-dev",
        config=SimpleNamespace(
            paths={"deliverables": "contracts/"},
            artifacts=SimpleNamespace(required=["spec.md"], optional=[]),
        ),
    )

    violations, warning, tokens = evaluate_path_conventions(custom, repo_root, feature_dir, feature_dir, strict_metadata=True)

    assert tokens == frozenset()
    assert "expects deliverables path" in "\n".join(violations)
    assert "waived" not in "\n".join(violations) + (warning or "")


def test_research_prefix_mode_reads_no_waiver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Research's ``path_prefix`` mode never resolves mission artifacts, so the
    waiver is not consulted there (the validator could not apply it)."""
    from types import SimpleNamespace

    from specify_cli.acceptance import summary_core

    repo_root = _no_contracts_repo(tmp_path, waiver={"contracts": "none", "contracts_rationale": _RATIONALE})
    feature_dir = repo_root / "kitty-specs" / _SLUG
    research = SimpleNamespace(
        name="research",
        domain="research",
        config=SimpleNamespace(
            paths={"deliverables": "contracts/"},
            artifacts=SimpleNamespace(required=["spec.md"], optional=["contracts/"]),
        ),
    )
    monkeypatch.setattr(summary_core, "_path_prefix_for_mission", lambda *_a: "research-out")

    assert summary_core._contracts_waiver_effect(research, feature_dir, feature_dir) == (frozenset(), None)
