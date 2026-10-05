"""Tests for core/mission_creation.py — the programmatic mission-creation API."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from charter.activation.mission_type_profiles import ResolvedMissionType
from specify_cli.core.adapters import (
    register_pending_origin_consumer,
    reset_origin_consumer,
)
from specify_cli.core.mission_creation import (
    MissionCreationError,
    MissionCreationResult,
    create_mission_core,
)
from specify_cli.runtime.resolver import TemplateConfigurationError

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The default ``coord`` create runs on a REAL ``main`` checkout
# (``git init -b main``, independent of the machine's ``init.defaultBranch``).
# The coordination branch is minted for real, so the status log lives on the
# coordination surface (``created_files``), never in the PRIMARY ``feature_dir``.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cwd_outside_any_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree-context guard reads the real process cwd, and pytest may run
    from inside a lane worktree. Run each test from its ``tmp_path`` so the real
    guard sees a non-worktree directory (no patch)."""
    monkeypatch.chdir(tmp_path)


def _init_git_repo(repo: Path) -> None:
    """Initialise a minimal git repo on a real ``main`` with .kittify and kitty-specs."""
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    # WP04 fail-closed (C-A1): create_mission_core requires a non-empty
    # activated mission-type set, and mission types used in this file with
    # REAL (unmocked) resolve_mission_type_context resolution -- software-dev
    # (default) and documentation (test_documentation_mission_resolves_
    # authored_spec_template) -- must each be activated for their real
    # resolution to succeed.
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n  - documentation\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def _mission_summary(slug: str) -> dict[str, str]:
    """Return valid stakeholder-facing mission summary fields for test creates."""
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


def _configured_mission_context(
    template_set: dict[str, str] | None,
    *,
    mission_type: str = "software-dev",
) -> ResolvedMissionType:
    """Build an activated context while leaving filesystem resolution real."""
    return ResolvedMissionType(
        mission_type=mission_type,
        governance_text="",
        action_sequence=[],
        provenance="test",
        _template_set_thunk=lambda: template_set,
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_create_uses_configured_non_conventional_spec_override(tmp_path: Path) -> None:
    """Mission creation copies the configured filename, not a manufactured default."""
    _init_git_repo(tmp_path)
    mapped_name = "mission-blueprint.md"
    mapped_content = "# Project override selected through mission configuration\n"
    override = tmp_path / ".kittify" / "overrides" / "templates" / mapped_name
    override.parent.mkdir(parents=True)
    override.write_text(mapped_content, encoding="utf-8")

    with (
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=_configured_mission_context({"spec": mapped_name}),
        ),
    ):
        result = create_mission_core(tmp_path, "mapped-spec", **_mission_summary("mapped-spec"))

    spec_file = result.feature_dir / "spec.md"
    assert spec_file.read_text(encoding="utf-8") == mapped_content
    assert result.created_files.count(spec_file) == 1


def test_create_uses_configured_package_default_spec(tmp_path: Path) -> None:
    """The configured filename reaches the existing package-default tier."""
    _init_git_repo(tmp_path)
    mapped_name = "package-mission-blueprint.md"
    mapped_content = "# Package mission template\n"
    package_root = tmp_path / "package-missions"
    package_template = package_root / "software-dev" / "templates" / mapped_name
    package_template.parent.mkdir(parents=True)
    package_template.write_text(mapped_content, encoding="utf-8")

    with (
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=_configured_mission_context({"spec": mapped_name}),
        ),
        patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "empty-home",
        ),
        patch(
            "specify_cli.runtime.resolver.get_package_asset_root",
            return_value=package_root,
        ),
    ):
        result = create_mission_core(tmp_path, "package-spec", **_mission_summary("package-spec"))

    assert (result.feature_dir / "spec.md").read_text(encoding="utf-8") == mapped_content


@pytest.mark.parametrize(
    "template_set",
    [None, {"plan": "plan-template.md"}],
    ids=["null-template-set", "missing-spec-key"],
)
def test_create_fails_before_scaffolding_for_invalid_spec_mapping(
    tmp_path: Path,
    template_set: dict[str, str] | None,
) -> None:
    """Invalid activated configuration cannot leave a partially created mission."""
    _init_git_repo(tmp_path)

    with (
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=_configured_mission_context(
                template_set,
                mission_type="documentation",
            ),
        ),
        pytest.raises(TemplateConfigurationError) as exc_info,
    ):
        create_mission_core(
            tmp_path,
            "invalid-spec-config",
            mission="documentation",
            **_mission_summary("invalid-spec-config"),
        )

    assert exc_info.value.mission_type == "documentation"
    assert exc_info.value.artifact_kind == "spec"
    assert not any((tmp_path / "kitty-specs").iterdir())


def test_create_fails_before_scaffolding_for_unresolved_mapped_spec(tmp_path: Path) -> None:
    """An unresolved configured filename is actionable and produces no mission state."""
    _init_git_repo(tmp_path)
    mapped_name = "missing-mission-blueprint.md"

    with (
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=_configured_mission_context({"spec": mapped_name}),
        ),
        patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "empty-home",
        ),
        patch(
            "specify_cli.runtime.resolver.get_package_asset_root",
            side_effect=FileNotFoundError("no package templates"),
        ),
        pytest.raises(TemplateConfigurationError) as exc_info,
    ):
        create_mission_core(tmp_path, "missing-spec", **_mission_summary("missing-spec"))

    assert exc_info.value.mission_type == "software-dev"
    assert exc_info.value.artifact_kind == "spec"
    assert exc_info.value.mapped_filename == mapped_name
    assert mapped_name in str(exc_info.value)
    assert not any((tmp_path / "kitty-specs").iterdir())


def _refuse_commits_on(repo: Path, branch: str, message: str) -> None:
    """Real fault: a ``pre-commit`` hook that refuses every commit on ``branch``."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(
        f'#!/bin/sh\nif [ "$(git rev-parse --abbrev-ref HEAD)" = "{branch}" ]; then echo "{message}" >&2; exit 1; fi\nexit 0\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)
    # Pinned repo-locally so a global ``core.hooksPath`` cannot bypass the hook.
    subprocess.run(["git", "config", "core.hooksPath", str(hooks)], cwd=repo, check=True)


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def test_happy_path_creates_directory_and_returns_result(tmp_path: Path) -> None:
    """create_mission_core creates the mission dir, meta.json, spec.md and returns MissionCreationResult."""
    _init_git_repo(tmp_path)

    result = create_mission_core(tmp_path, "test-feature", **_mission_summary("test-feature"))

    assert isinstance(result, MissionCreationResult)
    # Post-083: mission_slug is "<human-slug>-<mid8>" where mid8 is the first
    # 8 chars of the ULID mission_id. No NNN- prefix is assigned pre-merge.
    assert result.mission_slug.startswith("test-feature-")
    assert len(result.mission_slug) == len("test-feature-") + 8
    # mission_number is None pre-merge (FR-044); a dense display number is
    # assigned only at merge time. Canonical identity is mission_id (ULID).
    assert result.mission_number is None
    assert result.target_branch == "main"
    assert result.current_branch == "main"
    assert result.feature_dir == tmp_path / "kitty-specs" / result.mission_slug
    assert result.feature_dir.is_dir()

    # meta.json exists and has correct content
    meta_file = result.feature_dir / "meta.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["mission_slug"] == result.mission_slug
    assert meta["target_branch"] == "main"
    assert meta["mission_type"] == "software-dev"
    # Canonical mission identity fields (083+)
    assert "mission_id" in meta
    assert isinstance(meta["mission_id"], str)
    assert len(meta["mission_id"]) == 26  # ULID is 26 chars
    assert meta["mission_number"] is None  # pre-merge: JSON null

    # spec.md exists
    assert (result.feature_dir / "spec.md").exists()

    # Subdirectories exist
    assert (result.feature_dir / "tasks").is_dir()
    assert (result.feature_dir / "checklists").is_dir()
    assert (result.feature_dir / "research").is_dir()

    # status.events.jsonl: on a real ``main`` the default coord create mints the
    # coordination branch, and the log lives on the coordination surface (re-pinned
    # on a real ``main``, equal or stronger, verified on the unchanged base f0f3daa55).
    assert result.coordination_branch == meta["coordination_branch"]
    assert result.coordination_branch_created is True
    assert not (result.feature_dir / "status.events.jsonl").exists()
    [log] = [p for p in result.created_files if p.name == "status.events.jsonl"]
    assert log.exists()
    committed = _git_out(tmp_path, "ls-tree", "-r", "--name-only", meta["coordination_branch"]).split()
    assert committed == [f"kitty-specs/{result.mission_slug}/status.events.jsonl"]


def test_result_created_files_populated(tmp_path: Path) -> None:
    """MissionCreationResult.created_files lists the key files."""
    _init_git_repo(tmp_path)

    result = create_mission_core(tmp_path, "my-feature", **_mission_summary("my-feature"))

    # Re-pinned on a real ``main`` (equal or stronger, verified on f0f3daa55): the scaffold
    # commit onto protected ``main`` is a bootstrap skip, so the create reports
    # every file it wrote, the coordination status log included.
    names = sorted(f.name for f in result.created_files)
    assert names == [".gitkeep", "README.md", "meta.json", "spec.md", "status.events.jsonl"]
    assert sorted(f.name for f in result.uncommitted_files) == [".gitkeep", "README.md", "meta.json", "spec.md"]


def _tracker_origin_consumer(
    repo_root: Path,
    feature_dir: Path,
    meta: dict[str, Any],
) -> tuple[bool, bool, str | None, dict[str, Any]]:
    """Test-only PendingOriginConsumer that routes through the tracker's binding logic.

    This consumer mirrors what ``tracker/origin_consumer.py`` (WP03) will implement.
    It is used in tests that verify the pending-origin registry dispatch chain,
    replacing the old approach of patching ``mission_creation.py`` internals directly.

    Imports are lazy so that the test's ``patch("specify_cli.tracker.origin.bind_mission_origin")``
    mock is active when the consumer runs.
    """
    from specify_cli.tracker.origin import OriginBindingError, bind_mission_origin
    from specify_cli.tracker.origin_models import OriginCandidate
    from specify_cli.tracker.ticket_context import clear_pending_origin, read_pending_origin

    pending = read_pending_origin(repo_root)
    if not pending:
        return False, False, None, meta

    provider = str(pending.get("provider") or "").strip().lower()
    issue_id = str(pending.get("issue_id") or "").strip()
    issue_key = str(pending.get("issue_key") or "").strip()

    if not provider or not issue_id or not issue_key:
        return True, False, "Pending origin is missing required provider/issue identifiers.", meta

    candidate = OriginCandidate(
        external_issue_id=issue_id,
        external_issue_key=issue_key,
        title=str(pending.get("title") or "").strip(),
        status=str(pending.get("status") or "").strip(),
        url=str(pending.get("url") or "").strip(),
        match_type="pending_origin",
        body=str(pending.get("body") or "").strip() or None,
    )

    try:
        updated_meta, _ = bind_mission_origin(
            feature_dir=feature_dir,
            candidate=candidate,
            provider=provider,
            resource_type=None,
            resource_id=None,
        )
    except OriginBindingError as exc:
        return True, False, str(exc), meta
    except Exception as exc:  # noqa: BLE001
        return True, False, str(exc), meta

    clear_pending_origin(repo_root)
    return True, True, None, updated_meta


def test_consumes_pending_origin_after_creation(tmp_path: Path) -> None:
    """A staged pending origin is bound and cleared during mission creation."""
    _init_git_repo(tmp_path)
    pending_origin = tmp_path / ".kittify" / "pending-origin.yaml"
    pending_origin.write_text(
        "\n".join(
            [
                "provider: linear",
                "issue_key: ENG-42",
                "issue_id: issue-123",
                "title: Implement dark mode",
                "url: https://linear.app/acme/ENG-42",
                "status: In Progress",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Register the test consumer that exercises the tracker binding path via
    # the core/adapters.py registry (WP02 boundary fix). WP03 will register the
    # real tracker consumer at startup; here we use the identical logic as a
    # test-only consumer so the binding assertions remain meaningful.
    register_pending_origin_consumer(_tracker_origin_consumer)
    try:
        with patch("specify_cli.tracker.origin.bind_mission_origin") as mock_bind_origin:
            mock_bind_origin.return_value = (
                {
                    "mission_id": "01KTESTMISSIONID00000000003",
                    "mission_number": None,
                    "slug": "ticket-feature-01KTESTM",
                    "mission_slug": "ticket-feature-01KTESTM",
                    "friendly_name": "ticket feature",
                    "mission_type": "software-dev",
                    "target_branch": "main",
                    "created_at": "2026-04-01T00:00:00+00:00",
                    "origin_ticket": {"provider": "linear"},
                },
                True,
            )
            result = create_mission_core(tmp_path, "ticket-feature", **_mission_summary("ticket-feature"))
    finally:
        reset_origin_consumer()

    assert result.origin_binding_attempted is True
    assert result.origin_binding_succeeded is True
    assert result.origin_binding_error is None
    assert pending_origin.exists() is False
    mock_bind_origin.assert_called_once()


def test_pending_origin_failure_is_reported_and_retained(tmp_path: Path) -> None:
    """Bind failures should not clear the staged pending origin."""
    _init_git_repo(tmp_path)
    pending_origin = tmp_path / ".kittify" / "pending-origin.yaml"
    pending_origin.write_text(
        "\n".join(
            [
                "provider: linear",
                "issue_key: ENG-42",
                "issue_id: issue-123",
                "title: Implement dark mode",
                "url: https://linear.app/acme/ENG-42",
                "status: In Progress",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    register_pending_origin_consumer(_tracker_origin_consumer)
    try:
        with patch("specify_cli.tracker.origin.bind_mission_origin", side_effect=RuntimeError("bind failed")):
            result = create_mission_core(tmp_path, "ticket-feature", **_mission_summary("ticket-feature"))
    finally:
        reset_origin_consumer()

    assert result.origin_binding_attempted is True
    assert result.origin_binding_succeeded is False
    assert result.origin_binding_error == "bind failed"
    assert pending_origin.exists() is True


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


def test_invalid_slug_raises(tmp_path: Path) -> None:
    """Non-kebab-case slug raises MissionCreationError."""
    _init_git_repo(tmp_path)

    with pytest.raises(MissionCreationError, match="Invalid feature slug"):
        create_mission_core(tmp_path, "Invalid_Slug", **_mission_summary("Invalid_Slug"))


def test_slug_starting_with_number_accepted(tmp_path: Path) -> None:
    """Slug starting with a digit is now valid per FR-017 (e.g. '068-feature-name' convention)."""
    _init_git_repo(tmp_path)

    # Slug validation must pass; creation may succeed or fail for non-slug reasons,
    # but must NOT raise MissionCreationError with "Invalid feature slug".
    try:
        create_mission_core(tmp_path, "123-fix", **_mission_summary("123-fix"))
    except MissionCreationError as exc:
        assert "Invalid feature slug" not in str(exc), (
            "Digit-prefixed slug '123-fix' must no longer be rejected for slug format. "
            f"Got: {exc}"
        )


def test_uppercase_slug_raises(tmp_path: Path) -> None:
    """Uppercase slug raises MissionCreationError."""
    _init_git_repo(tmp_path)

    with pytest.raises(MissionCreationError, match="Invalid feature slug"):
        create_mission_core(tmp_path, "User-Auth", **_mission_summary("User-Auth"))


# ---------------------------------------------------------------------------
# Context guard tests
# ---------------------------------------------------------------------------


def test_worktree_context_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running from inside a real linked worktree raises MissionCreationError."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "--detach", str(linked)], cwd=repo, capture_output=True, check=True)
    monkeypatch.chdir(linked)

    with pytest.raises(MissionCreationError, match="worktree"):
        create_mission_core(repo, "test-feature", **_mission_summary("test-feature"))
    assert not list((repo / "kitty-specs").iterdir())


def test_not_git_repo_raises(tmp_path: Path) -> None:
    """A real project directory that is not a git repository raises MissionCreationError."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (tmp_path / "kitty-specs").mkdir()

    with pytest.raises(MissionCreationError, match="git repository"):
        create_mission_core(tmp_path, "test-feature", **_mission_summary("test-feature"))
    assert not list((tmp_path / "kitty-specs").iterdir())


def test_detached_head_raises(tmp_path: Path) -> None:
    """A real detached HEAD raises MissionCreationError."""
    _init_git_repo(tmp_path)
    subprocess.run(["git", "checkout", "--detach"], cwd=tmp_path, capture_output=True, check=True)

    with pytest.raises(MissionCreationError, match="detached HEAD"):
        create_mission_core(tmp_path, "test-feature", **_mission_summary("test-feature"))


# ---------------------------------------------------------------------------
# Target branch tests
# ---------------------------------------------------------------------------


def test_explicit_target_branch(tmp_path: Path) -> None:
    """Explicit target_branch overrides the current branch."""
    _init_git_repo(tmp_path)

    result = create_mission_core(
        tmp_path,
        "test-feature",
        target_branch="2.x",
        **_mission_summary("test-feature"),
    )

    assert result.target_branch == "2.x"
    assert result.current_branch == "main"
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["target_branch"] == "2.x"

    tasks_readme = (result.feature_dir / "tasks" / "README.md").read_text(
        encoding="utf-8"
    )
    assert 'planning_base_branch: "2.x"' in tasks_readme
    assert 'merge_target_branch: "2.x"' in tasks_readme


def test_target_branch_defaults_to_current(tmp_path: Path) -> None:
    """When no target_branch provided, uses the current branch."""
    _init_git_repo(tmp_path)
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True, check=True)

    result = create_mission_core(tmp_path, "my-feature", **_mission_summary("my-feature"))

    assert result.target_branch == "develop"
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["target_branch"] == "develop"

    tasks_readme = (result.feature_dir / "tasks" / "README.md").read_text(
        encoding="utf-8"
    )
    assert 'planning_base_branch: "develop"' in tasks_readme
    assert 'merge_target_branch: "develop"' in tasks_readme


# ---------------------------------------------------------------------------
# Mission tests
# ---------------------------------------------------------------------------


def test_documentation_mission_resolves_authored_spec_template(tmp_path: Path) -> None:
    """documentation is creatable: its authored spec mapping resolves (#2689).

    Before the mission-step-creatability slice the shipped documentation type
    carried a null spec mapping and creation failed closed; it now resolves the
    per-type authored spec template. The fail-closed contract for a genuinely
    unmapped kind is covered by ``tests/runtime/test_resolver_unit.py``.
    """
    _init_git_repo(tmp_path)

    result = create_mission_core(
        tmp_path,
        "docs-feature",
        mission="documentation",
        **_mission_summary("docs-feature"),
    )

    assert result.meta["mission_type"] == "documentation"
    assert any((tmp_path / "kitty-specs").iterdir())


def test_default_mission_is_software_dev(tmp_path: Path) -> None:
    """When mission is None, defaults to 'software-dev'."""
    _init_git_repo(tmp_path)

    result = create_mission_core(tmp_path, "basic-feature", **_mission_summary("basic-feature"))

    assert result.meta["mission_type"] == "software-dev"


# ---------------------------------------------------------------------------
# FR-001: meta.json commit fails loudly (mission_creation.py:767, :792)
# ---------------------------------------------------------------------------


def test_meta_json_commit_hard_failure_raises_for_documentation_mission(
    tmp_path: Path,
) -> None:
    """FR-001 Acceptance Scenario 4: the hard-failure guard is not partial to
    the primary mission-type branch -- a ``documentation`` mission-type creation
    must raise identically on a hard git failure at the scaffold commit.

    #2693 collapsed the create commit legs into ONE transactional scaffold
    commit (``meta.json`` + ``status.events.jsonl`` + ``tasks/README.md`` +
    ``tasks/.gitkeep``) that runs after the ``documentation``-only
    ``set_documentation_state`` write, so ``meta.json`` carries the doc state.
    There is now a single ``_commit_feature_file`` call site; a real
    ``pre-commit`` hook refusing the planning-branch commit exercises it.

    Revert sensitivity: re-wrapping the scaffold ``_commit_feature_file`` call in
    ``contextlib.suppress(Exception)`` swallows the ``RuntimeError`` silently,
    ``create_mission_core`` returns normally, and ``pytest.raises`` below fails
    with "DID NOT RAISE".
    """
    _init_git_repo(tmp_path)
    subprocess.run(["git", "checkout", "-q", "-b", "develop"], cwd=tmp_path, check=True)
    # A real hard git failure (a ``pre-commit`` hook refusing the scaffold
    # commit on the planning branch) instead of a stubbed ``_commit_feature_file``.
    _refuse_commits_on(tmp_path, "develop", "documentation state commit rejected")

    with pytest.raises(RuntimeError, match="documentation state commit rejected"):
        create_mission_core(
            tmp_path,
            "docs-meta-commit-hard-failure",
            mission="documentation",
            **_mission_summary("docs-meta-commit-hard-failure"),
        )


# ---------------------------------------------------------------------------
# Mission identity / slug formatting tests (post-083: ULID + mid8)
# ---------------------------------------------------------------------------


def test_slug_uses_mid8_suffix_not_numeric_prefix(tmp_path: Path) -> None:
    """Post-083: mission_slug is '<human-slug>-<mid8>', not '<NNN>-<slug>'.

    The canonical machine identity is mission_id (ULID); mission_number is
    None until merge time. The 8-char mid8 suffix disambiguates missions
    that share a human slug (FR-032, FR-044).
    """
    _init_git_repo(tmp_path)

    result = create_mission_core(tmp_path, "padded-test", **_mission_summary("padded-test"))

    # No NNN- prefix — slug is "<human-slug>-<mid8>".
    assert result.mission_slug.startswith("padded-test-")
    assert len(result.mission_slug) == len("padded-test-") + 8
    # mission_number is None pre-merge (no dense number assigned).
    assert result.mission_number is None
    # Canonical identity lives in meta.mission_id (ULID, 26 chars).
    assert isinstance(result.meta["mission_id"], str)
    assert len(result.meta["mission_id"]) == 26
    # The mid8 suffix on the slug matches the first 8 chars of mission_id.
    assert result.mission_slug.endswith(result.meta["mission_id"][:8])
