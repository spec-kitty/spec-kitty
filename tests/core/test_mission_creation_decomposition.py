"""Characterisation tests for ``_create_mission_core_impl`` (FR-026 / T050).

Pins today's observable behaviour of mission creation, driven ONLY through the
pre-existing public entry point :func:`create_mission_core`, before the
decomposition (T051) that brings ``_create_mission_core_impl`` down to
complexity <=15. These tests must stay green, unmodified, through T051.

Every assertion is on a typed exception class, a structured result/meta field,
or a file/git fact -- never on log wording (charter ATDD / non-vacuity).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import (
    MissionAlreadyExistsError,
    MissionCreationError,
    create_mission_core,
)

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)


def _init_repo(repo: Path) -> None:
    """A provisioned Spec Kitty project with one commit on a non-protected branch.

    ``main``/``master`` are protected by default (``ProtectionPolicy``), which
    would make the create-time scaffold commit a disclosed bootstrap SKIP
    rather than a real commit; the tests below need the real commit, so the
    fixture uses a feature-shaped branch name instead.
    """
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    _git(repo, "init", "-b", "work")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _commit_spec(repo: Path, feature_dir: Path) -> None:
    """Commit ``spec.md`` so the mission reads as genuinely 'worked' (live).

    Mirrors ``tests/core/test_mission_create_idempotency_guard.py``: a
    genesis / no-progress prior (zero WP events AND spec.md never committed)
    is auto-allowed (FR-003), so a genuine live-duplicate test must commit
    spec.md first.
    """
    spec_path = feature_dir / "spec.md"
    spec_path.write_text("# Spec\n\nSubstantive spec content.\n", encoding="utf-8")
    rel = spec_path.relative_to(repo)
    _git(repo, "add", str(rel))
    _git(repo, "commit", "-m", f"Add spec for {feature_dir.name}")


def _summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


@pytest.fixture(autouse=True)
def _not_a_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test PROCESS may itself run from inside a lane worktree (this repo's
    own execution context, per CLAUDE.md), which would trip the worktree-context
    guard on every ``tmp_path``-based fixture repo. Pin the guard's input to the
    real ``tmp_path`` fixture repository instead of the process cwd.
    """
    monkeypatch.setattr(f"{_CORE_MODULE}.is_worktree_context", lambda cwd: False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _init_repo(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Pre-write validation errors (section 1 / 2 / 2.5 / 3)
# ---------------------------------------------------------------------------


def test_invalid_slug_raises_mission_creation_error(repo: Path) -> None:
    with pytest.raises(MissionCreationError, match="kebab-case"):
        create_mission_core(repo, "Invalid_Slug", **_summary("invalid"))


def test_explicitly_empty_friendly_name_raises(repo: Path) -> None:
    with pytest.raises(MissionCreationError, match="friendly_name"):
        create_mission_core(repo, "empty-friendly", friendly_name="   ")


def test_worktree_context_without_allow_flag_is_refused(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f"{_CORE_MODULE}.is_worktree_context", lambda cwd: True)
    with pytest.raises(MissionCreationError, match="worktree"):
        create_mission_core(repo, "worktree-guard", **_summary("worktree-guard"))


def test_worktree_context_bypassed_with_allow_flag(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f"{_CORE_MODULE}.is_worktree_context", lambda cwd: True)
    result = create_mission_core(
        repo,
        "worktree-allowed",
        allow_worktree_context=True,
        **_summary("worktree-allowed"),
    )
    assert result.feature_dir.exists()


def test_not_a_git_repo_raises(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    provision_test_charter(tmp_path)
    (tmp_path / "kitty-specs").mkdir()
    with pytest.raises(MissionCreationError, match="git"):
        create_mission_core(tmp_path, "no-git", **_summary("no-git"))


def test_unborn_head_raises_with_remedy(repo: Path) -> None:
    unborn = repo.parent / "unborn"
    unborn.mkdir()
    (unborn / ".kittify").mkdir()
    provision_test_charter(unborn)
    (unborn / "kitty-specs").mkdir()
    _git(unborn, "init", "-b", "main")
    _git(unborn, "config", "user.email", "test@test.com")
    _git(unborn, "config", "user.name", "Test")
    with pytest.raises(MissionCreationError, match="no commits yet"):
        create_mission_core(unborn, "unborn-guard", **_summary("unborn-guard"))


def test_detached_head_raises(repo: Path) -> None:
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    _git(repo, "checkout", "--detach", head_sha)
    with pytest.raises(MissionCreationError, match="detached HEAD"):
        create_mission_core(repo, "detached-guard", **_summary("detached-guard"))


def test_live_duplicate_raises_already_exists(repo: Path) -> None:
    first = create_mission_core(repo, "dup-mission", **_summary("dup-mission"))
    _commit_spec(repo, first.feature_dir)
    # See test_live_duplicate_allowed_with_flag: force a distinct mid8/dir so
    # this exercises the #4033 idempotency GUARD itself, not the unrelated
    # #3861 identical-scaffold commit fallback that a same-mid8 collision
    # would otherwise trip instead.
    time.sleep(1.1)
    with pytest.raises(MissionAlreadyExistsError):
        create_mission_core(repo, "dup-mission", **_summary("dup-mission"))
    assert len(list((repo / "kitty-specs").glob("dup-mission-*"))) == 1


def test_live_duplicate_allowed_with_flag(repo: Path) -> None:
    first = create_mission_core(repo, "dup-allowed", **_summary("dup-allowed"))
    _commit_spec(repo, first.feature_dir)
    # mid8 is the first 8 Crockford-base32 chars of the minted ULID, which
    # encode only the millisecond timestamp; two creates in rapid succession
    # can mint the SAME mid8 and collide on the second mission's dir name.
    # Mirrors tests/core/test_mission_create_idempotency_guard.py.
    time.sleep(1.1)
    second = create_mission_core(repo, "dup-allowed", allow_duplicate=True, **_summary("dup-allowed"))
    assert second.feature_dir.exists()
    assert second.feature_dir != first.feature_dir


def test_invalid_purpose_summary_raises(repo: Path) -> None:
    with pytest.raises(MissionCreationError):
        create_mission_core(repo, "bad-purpose", friendly_name="Bad Purpose", purpose_tldr="", purpose_context="")


def test_empty_activation_set_raises_and_leaves_no_scaffold(repo: Path) -> None:
    from charter.activation.pack_context import CharterPackConfigError

    config_path = repo / ".kittify" / "config.yaml"
    config_path.write_text("mission_type_activations: []\n")
    with pytest.raises(CharterPackConfigError):
        create_mission_core(repo, "no-activation", **_summary("no-activation"))
    assert not (repo / "kitty-specs" / "no-activation").exists()


# ---------------------------------------------------------------------------
# Successful create: result + meta shape
# ---------------------------------------------------------------------------


def test_successful_create_result_and_meta_shape(repo: Path) -> None:
    result = create_mission_core(repo, "happy-path", **_summary("happy-path"))

    assert result.mission_slug.startswith("happy-path-")
    assert result.mission_number is None
    assert result.target_branch == "work"
    assert result.current_branch == "work"
    assert result.uncommitted_files == [result.feature_dir / "spec.md"]

    meta = result.meta
    for key in (
        "mission_id",
        "mid8",
        "slug",
        "mission_slug",
        "friendly_name",
        "purpose_tldr",
        "purpose_context",
        "mission_type",
        "target_branch",
        "created_at",
        "topology",
        "flattened",
    ):
        assert key in meta, key

    # pr_bound / retain_branches / retain_worktrees absent by default (FR-010).
    assert "pr_bound" not in meta
    assert "retain_branches" not in meta
    assert "retain_worktrees" not in meta


def test_pr_bound_and_retention_present_only_when_true(repo: Path) -> None:
    result = create_mission_core(
        repo,
        "flagged-mission",
        pr_bound=True,
        retain_branches=True,
        retain_worktrees=True,
        **_summary("flagged-mission"),
    )
    assert result.meta["pr_bound"] is True
    assert result.meta["retain_branches"] is True
    assert result.meta["retain_worktrees"] is True


def test_coord_topology_writes_coordination_branch(repo: Path) -> None:
    result = create_mission_core(repo, "coord-mission", topology=MissionTopology.COORD, **_summary("coord-mission"))
    assert result.meta.get("coordination_branch")
    assert result.coordination_branch is not None


def test_single_branch_topology_never_writes_coordination_branch(repo: Path) -> None:
    result = create_mission_core(
        repo,
        "single-branch-mission",
        topology=MissionTopology.SINGLE_BRANCH,
        **_summary("single-branch-mission"),
    )
    assert "coordination_branch" not in result.meta
    assert result.coordination_branch is None


def test_documentation_mission_writes_documentation_state(repo: Path) -> None:
    result = create_mission_core(
        repo,
        "doc-mission",
        mission="documentation",
        topology=MissionTopology.SINGLE_BRANCH,
        **_summary("doc-mission"),
    )
    # `set_documentation_state` writes the on-disk meta.json but does not
    # update the already-built in-memory `meta` dict this function returns
    # (characterised as-is; not a behaviour this WP changes).
    on_disk_meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "documentation_state" in on_disk_meta


def test_status_log_holds_exactly_created_and_specify_started(repo: Path) -> None:
    result = create_mission_core(repo, "event-mission", **_summary("event-mission"))
    log_path = result.feature_dir / "status.events.jsonl"
    events = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    event_types = [event.get("event_type") for event in events]
    assert event_types.count("MissionCreated") == 1
    assert event_types.count("SpecifyStarted") == 1


def test_scaffold_commit_is_single_commit_excluding_spec_md(repo: Path) -> None:
    result = create_mission_core(repo, "scaffold-commit", **_summary("scaffold-commit"))
    head = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    parent_count = _git(repo, "rev-list", "--count", head).stdout.decode().strip()
    assert parent_count == "2"  # init + scaffold commit
    tree_files = _git(repo, "ls-tree", "-r", "--name-only", head).stdout.decode().splitlines()
    slug = result.mission_slug
    assert f"kitty-specs/{slug}/meta.json" in tree_files
    assert f"kitty-specs/{slug}/status.events.jsonl" in tree_files
    assert f"kitty-specs/{slug}/tasks/README.md" in tree_files
    assert f"kitty-specs/{slug}/tasks/.gitkeep" in tree_files
    assert f"kitty-specs/{slug}/spec.md" not in tree_files


# ---------------------------------------------------------------------------
# Ordering pin: the spec template is resolved before any mission state exists.
# ---------------------------------------------------------------------------


def test_template_resolution_precedes_any_mission_state(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _TemplateProbe(Exception):
        pass

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise _TemplateProbe

    monkeypatch.setattr("specify_cli.runtime.resolver.resolve_configured_template", _raise)
    with pytest.raises(_TemplateProbe):
        create_mission_core(repo, "template-order", **_summary("template-order"))
    assert not (repo / "kitty-specs" / "template-order").exists()
    assert not list((repo / "kitty-specs").glob("template-order-*"))


# ---------------------------------------------------------------------------
# Non-vacuity: a temporarily-disabled duplicate guard must fail this suite.
# Verified manually (not left as a runnable test): commenting out the
# `if not allow_duplicate:` guard body in `_create_mission_core_impl` turns
# `test_live_duplicate_raises_already_exists` red. See T050 Activity Log.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HIGH-2 fix-cycle-1 regression: the owned arm must take
# owned_create_root.repository_root as the SINGLE source of the repository
# root, never a caller-supplied bare `repo_root` left unresolved, and must
# fail closed rather than silently mixing roots that disagree.
# ---------------------------------------------------------------------------


def test_owned_create_canonicalizes_a_symlinked_repo_root(tmp_path: Path) -> None:
    """A symlinked ``repo_root`` must resolve to the same canonical root the
    owned fact carries -- ``canonical_repo_root`` in the result (and the
    ``--json`` payload it feeds) must be the REAL path, never the symlink."""
    from specify_cli.core.owned_mission import resolve_owned_create_root

    real_root = tmp_path / "real-repo"
    real_root.mkdir()
    _init_repo(real_root)
    owned = tmp_path / "owned"
    _git(real_root, "worktree", "add", "-b", "owned-work", str(owned))

    symlink_root = tmp_path / "symlink-repo"
    symlink_root.symlink_to(real_root, target_is_directory=True)

    owned_create_root = resolve_owned_create_root(symlink_root, owned)
    result = create_mission_core(
        symlink_root,
        "symlink-owned",
        owned_create_root=owned_create_root,
        topology=MissionTopology.SINGLE_BRANCH,
        **_summary("symlink-owned"),
    )
    assert result.canonical_repo_root == real_root.resolve()
    assert result.canonical_repo_root != symlink_root


def test_owned_create_refuses_a_mismatched_repo_root(tmp_path: Path) -> None:
    """A caller-supplied ``repo_root`` that disagrees with the validated fact's
    own ``repository_root`` must fail closed -- never silently prefer one."""
    from specify_cli.core.owned_mission import resolve_owned_create_root

    real_repo_root = tmp_path / "real-repo"
    real_repo_root.mkdir()
    _init_repo(real_repo_root)
    owned = tmp_path / "owned"
    _git(real_repo_root, "worktree", "add", "-b", "owned-work", str(owned))

    other_repo_root = tmp_path / "other-repo"
    other_repo_root.mkdir()
    _init_repo(other_repo_root)

    owned_create_root = resolve_owned_create_root(real_repo_root, owned)
    with pytest.raises(MissionCreationError, match="repository root mismatch"):
        create_mission_core(
            other_repo_root,
            "mismatched-owned",
            owned_create_root=owned_create_root,
            topology=MissionTopology.SINGLE_BRANCH,
            **_summary("mismatched-owned"),
        )


# ---------------------------------------------------------------------------
# MEDIUM-8 fix-cycle-1: focused unit tests for the T051-extracted pure
# helpers, driven directly (not only through the public
# create_mission_core() entry point).
# ---------------------------------------------------------------------------


def test_validate_create_inputs_rejects_invalid_slug() -> None:
    from specify_cli.core.mission_creation import _validate_create_inputs

    with pytest.raises(MissionCreationError, match="kebab-case"):
        _validate_create_inputs("Not_Kebab", None)


def test_validate_create_inputs_rejects_explicitly_empty_friendly_name() -> None:
    from specify_cli.core.mission_creation import _validate_create_inputs

    with pytest.raises(MissionCreationError, match="friendly_name"):
        _validate_create_inputs("valid-slug", "   ")


def test_validate_create_inputs_defaults_friendly_name_from_slug() -> None:
    from specify_cli.core.mission_creation import _validate_create_inputs

    assert _validate_create_inputs("user-auth", None) == "user auth"


def test_validate_create_inputs_normalizes_whitespace_in_friendly_name() -> None:
    from specify_cli.core.mission_creation import _validate_create_inputs

    assert _validate_create_inputs("user-auth", "  User   Auth  ") == "User Auth"


def _meta_build_kwargs(feature_dir: Path, **overrides: object) -> dict[str, object]:
    from specify_cli.core.mission_creation import _Purpose

    defaults: dict[str, object] = {
        "feature_dir": feature_dir,
        "mission_id": "01TESTMISSIONIDXXXXXXXXXX",
        "mid8": "01TESTMI",
        "mission_slug_formatted": "meta-build-test-01TESTMI",
        "normalized_friendly_name": "Meta Build Test",
        "purpose": _Purpose(tldr="Test meta build.", context="Exercise _build_create_meta directly."),
        "mission": None,
        "planning_branch": "work",
        "pr_bound": False,
        "retain_branches": False,
        "retain_worktrees": False,
        "commit_to_target": False,
        "resolved_root": feature_dir.parent,
        "write_root": feature_dir.parent,
        "topology": MissionTopology.SINGLE_BRANCH,
        "force_recreate_coordination_branch": False,
    }
    defaults.update(overrides)
    return defaults


def test_build_create_meta_pr_bound_absent_by_default(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import _build_create_meta

    feature_dir = tmp_path / "kitty-specs" / "meta-build-test-01TESTMI"
    feature_dir.mkdir(parents=True)
    result = _build_create_meta(**_meta_build_kwargs(feature_dir))
    assert "pr_bound" not in result.meta


def test_build_create_meta_pr_bound_true_when_requested(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import _build_create_meta

    feature_dir = tmp_path / "kitty-specs" / "meta-build-test-01TESTMI"
    feature_dir.mkdir(parents=True)
    result = _build_create_meta(**_meta_build_kwargs(feature_dir, pr_bound=True))
    assert result.meta["pr_bound"] is True


def test_build_create_meta_retention_fields_absent_by_default(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import _build_create_meta

    feature_dir = tmp_path / "kitty-specs" / "meta-build-test-01TESTMI"
    feature_dir.mkdir(parents=True)
    result = _build_create_meta(**_meta_build_kwargs(feature_dir))
    assert "retain_branches" not in result.meta
    assert "retain_worktrees" not in result.meta


def test_build_create_meta_retention_fields_true_when_requested(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import _build_create_meta

    feature_dir = tmp_path / "kitty-specs" / "meta-build-test-01TESTMI"
    feature_dir.mkdir(parents=True)
    result = _build_create_meta(**_meta_build_kwargs(feature_dir, retain_branches=True, retain_worktrees=True))
    assert result.meta["retain_branches"] is True
    assert result.meta["retain_worktrees"] is True


def test_build_create_meta_single_branch_never_mints_coordination_branch(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import _build_create_meta

    feature_dir = tmp_path / "kitty-specs" / "meta-build-test-01TESTMI"
    feature_dir.mkdir(parents=True)
    result = _build_create_meta(**_meta_build_kwargs(feature_dir))
    assert "coordination_branch" not in result.meta
    assert result.coordination_branch_created is False
    assert result.meta["topology"] == "single_branch"
