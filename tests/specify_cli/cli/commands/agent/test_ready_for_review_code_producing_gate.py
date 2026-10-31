"""The review-readiness implementation-commit prerequisite is capability-keyed (#6328).

The pre-flight ``_validate_ready_for_review`` used to enter its Check 2
worktree-state block — the one that includes "an implementation commit exists on
the lane" — only for ``mission_type == "software-dev"``. A custom code-producing
mission type therefore reached review-readiness with an empty lane (#6315's
deferred "site 3"). These tests drive the **real** pre-flight through its
pre-existing entry point and prove:

* a custom mission type declaring ``code_producing: true`` with no lane commit is
  refused, naming the missing implementation commits (FR-006 / SC-001);
* the same fixture with a commit on the lane passes (same-fixture positive
  control, so the refusal above is not vacuous);
* a non-code-producing type — built-in or custom — is unaffected (FR-007);
* the built-in families keep today's verdicts (C-002 / SC-003);
* ``--force`` short-circuits before the capability is consulted (C-003).

The mission type is resolved through the **real** layered charter chain (a
throwaway org pack on disk), never by stubbing the capability, so a green test
means the production path works.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _validate_ready_for_review,
)
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "gate-demo"
_WP = "WP01"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _SilentConsole:
    def print(self, *args: object, **kwargs: object) -> None:
        pass


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_repo(tmp_path: Path, mission_type: str) -> tuple[Path, str, str]:
    """A clean repo with a base commit and one implementation commit after it.

    Returns ``(repo, base_sha, head_sha)``. ``base_sha`` is the ref the lane
    diverges from (so a commit beyond it exists); ``head_sha`` is the tip (so a
    commit beyond it does not).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("BASE = 1\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": mission_type}), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Mission Specification\n\nReal content.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD")

    (repo / "src" / "implementation.py").write_text("IMPL = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "the implementation commit")
    head_sha = _git(repo, "rev-parse", "HEAD")
    return repo, base_sha, head_sha


def _workspace(repo: Path) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=_SLUG,
        wp_id=_WP,
        execution_mode="code_change",
        mode_source="test",
        resolution_kind="worktree",
        workspace_name="lane-a",
        worktree_path=repo,
        branch_name="main",
        lane_id="lane-a",
        lane_wp_ids=[_WP],
    )


def _run_preflight(
    repo: Path,
    mission_type: str,
    *,
    review_base_ref: str,
    force: bool = False,
) -> tuple[bool, list[str]]:
    """Drive the real ``_validate_ready_for_review`` with the minimal collaborators."""
    return _validate_ready_for_review(
        repo,
        _SLUG,
        _WP,
        force=force,
        target_lane="for_review",
        review_base_ref=review_base_ref,
        check_kitty_specs=False,
        get_main_repo_root=lambda _repo: repo,
        get_mission_type=lambda _feature_dir: mission_type,
        get_feature_target_branch=lambda _repo, _slug: "main",
        resolve_workspace_for_wp=lambda _root, _slug, _wp: _workspace(repo),
        review_currency_check_branch=lambda **_kwargs: "main",
        behind_commits_touch_only_planning_artifacts=lambda _wt, _branch, _slug: True,
        filter_runtime_state_paths=lambda entries: entries,
        list_wp_branch_specs_changes_for_guard=lambda *_args, **_kwargs: [],
        console=_SilentConsole(),
    )


# ---------------------------------------------------------------------------
# A custom code-producing type, resolved through a real layered org pack
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubPack:
    pack_roots: tuple[Path, ...]
    repo_root: Path


def _run_custom_type_preflight(
    tmp_path: Path,
    *,
    declared: bool | None,
    commit_beyond_base: bool,
) -> tuple[bool, list[str]]:
    """Pre-flight for the custom org-layer type ``qa``."""
    from unittest.mock import patch

    from charter.offering.missions.mission_type_repository import resolve_layered_mission_types

    repo, base_sha, head_sha = _make_repo(tmp_path, "qa")
    org = tmp_path / "org"
    (org / "mission_types").mkdir(parents=True, exist_ok=True)
    extra = "" if declared is None else f"code_producing: {str(declared).lower()}\n"
    (org / "mission_types" / "qa.yaml").write_text(f"schema_version: 1\nid: qa\ndisplay_name: Qa\n{extra}", encoding="utf-8")
    (org / "missions" / "qa").mkdir(parents=True, exist_ok=True)
    steps = "".join(f"  - id: {step}\n    title: {step}\n" for step in ("specify", "implement", "review"))
    (org / "missions" / "qa" / "mission-runtime.yaml").write_text(f"mission:\n  key: qa\nsteps:\n{steps}", encoding="utf-8")
    ctx = _StubPack(pack_roots=(Path("/nonexistent-builtin-pack"), org), repo_root=repo)

    # Both fixtures hold a real implementation commit; only the ref the gate is
    # asked to diff against varies, which is exactly the gate's contract ("a
    # commit beyond *its* base"). ``commit_beyond_base=True`` points the base at
    # the commit BEFORE the implementation; ``False`` points it at the tip, so
    # no commit lies beyond it.
    review_base_ref = base_sha if commit_beyond_base else head_sha

    resolve_layered_mission_types.cache_clear()
    try:
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "charter.activation.mission_type_profiles.existing_mission_types",
                    return_value=["qa"],
                )
            )
            stack.enter_context(patch("charter.activation.pack_context.PackContext.from_config", return_value=ctx))
            return _run_preflight(repo, "qa", review_base_ref=review_base_ref)
    finally:
        resolve_layered_mission_types.cache_clear()


def test_custom_code_producing_type_without_lane_commit_is_refused(tmp_path: Path) -> None:
    """FR-006 / SC-001: the defect. Red before the capability-keyed guard."""
    passed, guidance = _run_custom_type_preflight(tmp_path, declared=True, commit_beyond_base=False)
    assert passed is False, "a code-producing custom type must not pass review-readiness with an empty lane"
    text = "\n".join(guidance)
    assert "No implementation commits on lane branch!" in text


def test_custom_code_producing_type_with_lane_commit_passes(tmp_path: Path) -> None:
    """Same-fixture positive control: the refusal above is not vacuous."""
    passed, guidance = _run_custom_type_preflight(tmp_path, declared=True, commit_beyond_base=True)
    assert passed is True, f"a code-producing custom type WITH a lane commit must pass, got {guidance}"


@pytest.mark.parametrize("declared", [False, None])
def test_custom_non_code_type_is_not_applied(tmp_path: Path, declared: bool | None) -> None:
    """FR-007: a custom type that declares false (or nothing) keeps bypassing."""
    passed, guidance = _run_custom_type_preflight(tmp_path, declared=declared, commit_beyond_base=False)
    assert passed is True, f"a non-code custom type must not be gated, got {guidance}"


# ---------------------------------------------------------------------------
# Built-in parity ratchet (SC-003 / C-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mission_type", "expect_blocked"),
    [
        ("software-dev", True),
        ("research", False),
        ("documentation", False),
        ("plan", False),
    ],
)
def test_builtin_verdicts_are_unchanged(tmp_path: Path, mission_type: str, expect_blocked: bool) -> None:
    """SC-003: the four built-ins keep exactly the verdicts they have on main."""
    repo, _base_sha, head_sha = _make_repo(tmp_path, mission_type)
    passed, guidance = _run_preflight(repo, mission_type, review_base_ref=head_sha)
    if expect_blocked:
        assert passed is False, "software-dev keeps the implementation-commit prerequisite"
        assert "No implementation commits on lane branch!" in "\n".join(guidance)
    else:
        assert passed is True, f"{mission_type} must keep bypassing the worktree prerequisite, got {guidance}"


def test_force_short_circuits_before_the_capability(tmp_path: Path) -> None:
    """C-003: ``--force`` returns success without consulting any check."""
    repo, _base_sha, head_sha = _make_repo(tmp_path, "qa")

    def _explode(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("force must not consult the capability")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("charter.activation.api.code_producing_for", _explode)
        passed, guidance = _run_preflight(repo, "qa", review_base_ref=head_sha, force=True)
    assert (passed, guidance) == (True, [])


# ---------------------------------------------------------------------------
# SC-002: the family-name literal is gone from the review-readiness path
# ---------------------------------------------------------------------------


def test_review_readiness_path_has_no_family_name_literal() -> None:
    """SC-002: a machine ratchet for "no ``software-dev`` comparison remains"."""
    import specify_cli.cli.commands.agent.tasks_parsing_validation as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "MISSION_TYPE_SOFTWARE_DEV" not in source, "the review-readiness path must ask the code_producing capability, not compare the family name"
    assert "code_producing_for" in source, "the capability must be reached through the activation api seam"
