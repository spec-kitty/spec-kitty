"""Integration tests for the specify/plan auto-commit boundary (issue #846).

Locks in the contract from
``kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/specify-plan-commit-boundary.md``:

(a) ``mission create`` does NOT commit ``spec.md`` (``meta.json`` is still written).
(b) Uncommitted populated ``spec.md`` -> setup-plan blocks ("committed AND substantive").
(c) Committed but scaffold-only ``spec.md`` -> setup-plan blocks (substantive-spec).
(d) Committed substantive spec + populated plan -> plan commits, phase_complete=True.
(e) Same as (d) but plan left as template -> setup-plan returns phase_complete=False.

Plus a focused unit-style assertion for the section-presence-only gate:
scaffold + 300 bytes of arbitrary prose stays NON-substantive.
"""

from __future__ import annotations

import json
from contextlib import chdir
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.mission_creation import create_mission_core
from specify_cli.missions._substantive import is_committed, is_substantive
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Repo / mission fixtures
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_git_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "-m", "init", "--allow-empty")
    # WP04 fail-closed follow-up: create_mission_core() hard-requires an
    # activated mission type; a bare git-init fixture never ran
    # `spec-kitty init`, so provision the same default charter surface here.
    provision_test_charter(repo)


def _summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ")
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so stakeholders can track outcomes without parsing the spec text directly."),
    }


def _create_mission(repo: Path, slug: str) -> Path:
    """Run create_mission_core against ``repo`` and return the feature_dir."""
    with chdir(repo):
        result = create_mission_core(repo, slug, **_summary(slug))
    feature_dir: Path = result.feature_dir
    return feature_dir


def _file_in_head(repo: Path, rel_path: str) -> bool:
    """Return True iff ``rel_path`` is tracked AND present at HEAD."""
    ls = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", rel_path],
        capture_output=True,
    )
    if ls.returncode != 0:
        return False
    head = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{rel_path}"],
        capture_output=True,
    )
    return head.returncode == 0


# ---------------------------------------------------------------------------
# spec / plan content helpers
# ---------------------------------------------------------------------------


_SUBSTANTIVE_SPEC = """\
# Spec — Test Mission

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Auth flow | Users sign in via SSO with email and one-time code. | High | Open |
"""

_SCAFFOLD_SPEC = """\
# Spec — Test Mission

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | [Short title] | As a [role], I want [goal] so that [benefit]. | High | Open |
"""


_SUBSTANTIVE_PLAN = """\
# Plan — Test Mission

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer, rich, pytest
**Storage**: filesystem only
**Testing**: pytest with integration coverage
"""

_SCAFFOLD_PLAN = """\
# Plan — Test Mission

## Technical Context

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]
"""

_PLAN_WITH_ONLY_LANGUAGE = """\
# Plan — Test Mission

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]
"""


def _commit_file(repo: Path, rel_path: str, message: str) -> None:
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


# ---------------------------------------------------------------------------
# Unit assertion — section-presence only (no byte-length OR fallback)
# ---------------------------------------------------------------------------


def test_is_substantive_rejects_scaffold_plus_arbitrary_prose(tmp_path: Path) -> None:
    """Scaffold + 300 bytes of prose without an FR row stays NON-substantive."""
    spec = tmp_path / "spec.md"
    body = _SCAFFOLD_SPEC + "\n\n" + ("Lorem ipsum prose paragraph. " * 20)
    assert len(body) > 600  # well over any imagined byte threshold
    spec.write_text(body, encoding="utf-8")
    assert is_substantive(spec, "spec") is False


def test_is_substantive_accepts_populated_fr_row(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    assert is_substantive(spec, "spec") is True


def test_is_substantive_accepts_bold_bullet_fr_row(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("- **FR-001**: Deliver the real workflow, not template filler.\n", encoding="utf-8")
    assert is_substantive(spec, "spec") is True


def test_is_substantive_rejects_empty_user_story_scaffold_with_spacing(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("| FR-001 | As a [role], I want [goal], so that [benefit]. | | High | Open |\n", encoding="utf-8")
    assert is_substantive(spec, "spec") is False


def test_is_substantive_rejects_placeholder_technical_context(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(_SCAFFOLD_PLAN, encoding="utf-8")
    assert is_substantive(plan, "plan") is False


def test_is_substantive_rejects_language_without_peer_context(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(_PLAN_WITH_ONLY_LANGUAGE, encoding="utf-8")
    assert is_substantive(plan, "plan") is False


def test_is_substantive_accepts_populated_technical_context(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(_SUBSTANTIVE_PLAN, encoding="utf-8")
    assert is_substantive(plan, "plan") is True


def test_is_committed_returns_false_for_untracked(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    f = tmp_path / "untracked.md"
    f.write_text("hello", encoding="utf-8")
    assert is_committed(f, tmp_path) is False


def test_is_committed_returns_true_for_committed(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    f = tmp_path / "tracked.md"
    f.write_text("hello", encoding="utf-8")
    _commit_file(tmp_path, "tracked.md", "add tracked")
    assert is_committed(f, tmp_path) is True


def test_is_committed_returns_false_for_staged_only(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    f = tmp_path / "staged.md"
    f.write_text("hello", encoding="utf-8")
    _git(tmp_path, "add", "staged.md")
    assert is_committed(f, tmp_path) is False


# ---------------------------------------------------------------------------
# Scenario (a) — mission create does NOT commit spec.md
# ---------------------------------------------------------------------------


def test_mission_create_does_not_commit_spec_md(tmp_path: Path) -> None:
    """meta.json is written; spec.md is left untracked on disk."""
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-a")

    rel_root = feature_dir.relative_to(tmp_path)
    spec_rel = str(rel_root / "spec.md")

    assert (feature_dir / "spec.md").exists(), "spec.md scaffold must remain on disk"
    assert (feature_dir / "meta.json").exists(), "meta.json must still be written"
    assert _file_in_head(tmp_path, spec_rel) is False, "spec.md must NOT be committed at create"


# ---------------------------------------------------------------------------
# setup-plan invocation helpers
# ---------------------------------------------------------------------------


def _run_setup_plan(repo: Path, mission_handle: str) -> dict[str, object]:
    """Invoke ``mission setup-plan --json --mission <handle>`` against ``repo``.

    Returns the parsed JSON payload from the command. Patches the path
    detection helpers so the command treats ``repo`` as the project root and
    finds the feature directly under ``kitty-specs/``.
    """
    from specify_cli.cli.commands.agent import mission as mission_module
    from typer.testing import CliRunner

    runner = CliRunner()
    feature_dir = repo / "kitty-specs" / mission_handle

    def _fake_show_branch_context(_repo_root: Path, _slug: str, _json: bool) -> tuple[str, str]:
        return ("main", "main")

    # These fixtures intentionally exercise setup-plan commits on synthetic
    # main branches; opt in through the explicit protected-branch test override.
    with (
        patch.dict(os.environ, {"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"}),
        patch.object(mission_module, "locate_project_root", return_value=repo),
        patch.object(mission_module, "_enforce_git_preflight"),
        patch.object(
            mission_module,
            "_find_feature_directory",
            return_value=feature_dir,
        ),
        patch.object(
            mission_module,
            "_show_branch_context",
            side_effect=_fake_show_branch_context,
        ),
        patch.object(mission_module, "get_current_branch", return_value="main"),
        patch.object(mission_module, "_resolve_feature_target_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_module.app,
            ["setup-plan", "--json", "--mission", mission_handle],
            catch_exceptions=False,
        )
    assert result.exit_code in (0, 1), f"unexpected exit {result.exit_code}: {result.output}"
    # Locate the JSON envelope in the output (commands print plain JSON).
    output = result.output.strip()
    # Find the last '{' ... '}' block.
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {output!r}"
    payload: dict[str, object] = json.loads(output[start : end + 1])
    return payload


# ---------------------------------------------------------------------------
# Scenario (b) — uncommitted populated spec blocks setup-plan
# ---------------------------------------------------------------------------


def test_setup_plan_blocks_when_spec_uncommitted(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-b")
    handle = feature_dir.name
    # Populate spec but do NOT commit it.
    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")

    payload = _run_setup_plan(tmp_path, handle)

    assert payload.get("phase_complete") is False
    assert payload.get("result") == "blocked"
    reason = str(payload.get("blocked_reason", ""))
    assert "committed AND substantive" in reason
    # plan.md must not have been written / committed
    plan_path = feature_dir / "plan.md"
    plan_rel = str(plan_path.relative_to(tmp_path))
    assert _file_in_head(tmp_path, plan_rel) is False


# ---------------------------------------------------------------------------
# Scenario (c) — committed but scaffold-only spec blocks setup-plan
# ---------------------------------------------------------------------------


def test_setup_plan_blocks_when_spec_committed_but_scaffold(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-c")
    handle = feature_dir.name
    # Commit a scaffold-only spec.md.
    (feature_dir / "spec.md").write_text(_SCAFFOLD_SPEC, encoding="utf-8")
    spec_rel = str((feature_dir / "spec.md").relative_to(tmp_path))
    _commit_file(tmp_path, spec_rel, "add scaffold spec")

    payload = _run_setup_plan(tmp_path, handle)

    assert payload.get("phase_complete") is False
    assert payload.get("result") == "blocked"
    assert payload.get("spec_committed") is True
    assert payload.get("spec_substantive") is False
    plan_rel = str((feature_dir / "plan.md").relative_to(tmp_path))
    assert _file_in_head(tmp_path, plan_rel) is False


# ---------------------------------------------------------------------------
# Scenario (d) — committed substantive spec + populated plan -> commit + phase_complete=True
# ---------------------------------------------------------------------------


def test_setup_plan_commits_substantive_plan(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-d")
    handle = feature_dir.name

    # Populate + commit substantive spec.
    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    spec_rel = str((feature_dir / "spec.md").relative_to(tmp_path))
    _commit_file(tmp_path, spec_rel, "add substantive spec")

    # Pre-write the plan so setup-plan does NOT overwrite it (C-007).
    (feature_dir / "plan.md").write_text(_SUBSTANTIVE_PLAN, encoding="utf-8")

    payload = _run_setup_plan(tmp_path, handle)

    assert payload.get("phase_complete") is True
    assert payload.get("result") == "success"
    plan_rel = str((feature_dir / "plan.md").relative_to(tmp_path))
    # Placement is artifact-class-determined (write-surface coherence,
    # planning-on-primary contract): ``plan.md`` is a FINALIZED_EXECUTION_PLAN
    # planning artifact, so its auto-commit ALWAYS lands on the primary
    # ``target_branch`` (HEAD here is ``main``) for every mission shape — even
    # when ``mission create`` declares a coordination_branch in meta.json. Only
    # status/bookkeeping artifacts (status.events.jsonl, issue-matrix, etc.)
    # land on the coordination ref. Assert the planning artifact on primary.
    assert _file_in_head(tmp_path, plan_rel) is True
    # Bifurcation proof: when a coordination_branch is declared, the planning
    # artifact must NOT have been routed onto it — that was the overturned
    # planning-on-coord contract.
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    coord_branch = meta.get("coordination_branch")
    if coord_branch:
        shown = subprocess.run(
            ["git", "-C", str(tmp_path), "cat-file", "-e", f"{coord_branch}:{plan_rel}"],
            capture_output=True,
        )
        assert shown.returncode != 0, (
            f"plan.md must NOT be committed on the coordination branch "
            f"{coord_branch!r}; planning artifacts land on the primary "
            f"target_branch under the write-surface coherence contract"
        )


def _run_setup_plan_real_resolver(repo: Path, mission_handle: str) -> dict[str, object]:
    """Drive ``setup-plan`` with the REAL ``_find_feature_directory`` resolver.

    ``_run_setup_plan`` stubs ``_find_feature_directory`` (returning
    ``kitty-specs/<handle>`` verbatim), which would MASK the #2122 handle→slug
    bug for a bare-mid8 handle. This harness leaves the resolver unstubbed so a
    bare ``--mission <mid8>`` exercises the real handle-canonicalization on the
    planning-read path (the wrapper at ``mission.py::_planning_read_dir``).
    """
    from specify_cli.cli.commands.agent import mission as mission_module
    from typer.testing import CliRunner

    runner = CliRunner()

    def _fake_show_branch_context(_repo_root: Path, _slug: str, _json: bool) -> tuple[str, str]:
        return ("main", "main")

    with (
        patch.dict(os.environ, {"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"}),
        patch.object(mission_module, "locate_project_root", return_value=repo),
        patch.object(mission_module, "get_main_repo_root", return_value=repo),
        patch.object(mission_module, "_enforce_git_preflight"),
        patch.object(
            mission_module,
            "_show_branch_context",
            side_effect=_fake_show_branch_context,
        ),
        patch.object(mission_module, "get_current_branch", return_value="main"),
        patch.object(mission_module, "_resolve_feature_target_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_module.app,
            ["setup-plan", "--json", "--mission", mission_handle],
            catch_exceptions=False,
        )
    assert result.exit_code in (0, 1), f"unexpected exit {result.exit_code}: {result.output}"
    output = result.output.strip()
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {output!r}"
    payload: dict[str, object] = json.loads(output[start : end + 1])
    return payload


def test_setup_plan_resolves_bare_mid8_handle_to_primary_slug(tmp_path: Path) -> None:
    """#2122 guard: ``setup-plan --mission <mid8>`` canonicalizes the handle to
    the primary slug before the PRIMARY-partition planning read, so a bare mid8
    does not compose ``kitty-specs/<mid8>`` and miss the real spec/plan.

    Drives the REAL ``_find_feature_directory`` resolver (unstubbed) so the
    handle→slug step is exercised, not masked.
    """
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "bare-mid8-plan-guard")
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    mid8 = str(meta["mission_id"])[:8]
    assert mid8 and feature_dir.name.endswith(mid8), "fixture must carry a real mid8 tail"

    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _commit_file(tmp_path, str((feature_dir / "spec.md").relative_to(tmp_path)), "spec")
    (feature_dir / "plan.md").write_text(_SUBSTANTIVE_PLAN, encoding="utf-8")

    # Bare mid8 handle — NOT the full <slug>-<mid8> directory name.
    payload = _run_setup_plan_real_resolver(tmp_path, mid8)

    # The spec/plan reads resolved the real primary dir (not kitty-specs/<mid8>),
    # so the gate sees the committed substantive spec and the populated plan.
    assert payload.get("result") == "success", payload
    assert payload.get("phase_complete") is True, payload
    assert not (tmp_path / "kitty-specs" / mid8).exists(), "setup-plan composed a literal kitty-specs/<mid8> dir (handle-blind primary arm)"


def test_setup_plan_scaffolds_from_doctrine_package_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-package-default")
    handle = feature_dir.name

    monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "empty-global-home"))

    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    spec_rel = str((feature_dir / "spec.md").relative_to(tmp_path))
    _commit_file(tmp_path, spec_rel, "add substantive spec")

    payload = _run_setup_plan(tmp_path, handle)

    doctrine_plan = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions" / "software-dev" / "templates" / "plan-template.md"
    plan_file = feature_dir / "plan.md"

    # #2566/WP06: a pristine scaffold (plan.md byte-equal to the template, not
    # yet committed) is a non-error `success` + `scaffold_only` state — mirroring
    # the specify twin — NOT `blocked`. phase_complete stays False.
    assert payload.get("result") == "success"
    assert payload.get("scaffold_only") is True
    assert payload.get("phase_complete") is False
    assert plan_file.read_text(encoding="utf-8") == doctrine_plan.read_text(encoding="utf-8")
    assert _file_in_head(tmp_path, str(plan_file.relative_to(tmp_path))) is False


def test_setup_plan_scaffolds_and_compares_override_winner(tmp_path: Path) -> None:
    """The live setup-plan path uses the configured ``plan`` mapping and tier winner."""
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-override-plan")
    handle = feature_dir.name
    override = tmp_path / ".kittify" / "overrides" / "templates" / "plan-template.md"
    override.parent.mkdir(parents=True, exist_ok=True)
    override_bytes = b"# Override Plan\n\n## Technical Context\n**Language/Version**: [NEEDS CLARIFICATION]\n"
    override.write_bytes(override_bytes)

    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _commit_file(
        tmp_path,
        str((feature_dir / "spec.md").relative_to(tmp_path)),
        "add substantive spec",
    )

    payload = _run_setup_plan(tmp_path, handle)
    plan_file = feature_dir / "plan.md"

    assert payload.get("result") == "success"
    assert payload.get("scaffold_only") is True
    assert plan_file.read_bytes() == override_bytes
    assert _file_in_head(tmp_path, str(plan_file.relative_to(tmp_path))) is False


def test_setup_plan_resolves_research_plan_template(tmp_path: Path) -> None:
    """research is creatable: setup-plan resolves its authored plan mapping (#2689).

    Before the mission-step-creatability slice research carried a null plan
    mapping and setup-plan failed closed (TEMPLATE_CONFIGURATION_ERROR); it now
    resolves the per-type authored plan template and scaffolds ``plan.md``. The
    fail-closed contract for a genuinely unmapped kind is covered by
    ``tests/runtime/test_resolver_unit.py``.
    """
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-research-plan-mapping")
    handle = feature_dir.name
    meta_file = feature_dir / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["mission_type"] = "research"
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _commit_file(
        tmp_path,
        str((feature_dir / "spec.md").relative_to(tmp_path)),
        "add substantive research spec",
    )

    payload = _run_setup_plan(tmp_path, handle)

    assert payload.get("result") == "success"
    assert payload.get("error_code") is None
    assert (feature_dir / "plan.md").exists()


# ---------------------------------------------------------------------------
# Scenario (e) — committed spec + scaffold plan -> phase_complete=False
# ---------------------------------------------------------------------------


def test_setup_plan_blocks_when_plan_left_as_template(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    feature_dir = _create_mission(tmp_path, "mission-e")
    handle = feature_dir.name

    (feature_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    spec_rel = str((feature_dir / "spec.md").relative_to(tmp_path))
    _commit_file(tmp_path, spec_rel, "add substantive spec")

    # Pre-write a SCAFFOLD plan so setup-plan does NOT overwrite it (C-007),
    # and the exit gate sees it as non-substantive.
    (feature_dir / "plan.md").write_text(_SCAFFOLD_PLAN, encoding="utf-8")

    payload = _run_setup_plan(tmp_path, handle)

    assert payload.get("phase_complete") is False
    assert payload.get("result") == "blocked"
    reason = str(payload.get("blocked_reason", ""))
    assert "Technical Context" in reason or "substantive" in reason
    plan_rel = str((feature_dir / "plan.md").relative_to(tmp_path))
    assert _file_in_head(tmp_path, plan_rel) is False
