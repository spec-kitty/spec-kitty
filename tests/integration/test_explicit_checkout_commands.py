"""Explicit checkout commands must not cross-read or mutate another checkout."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.accept import accept
from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
runner = CliRunner()
commit_app = typer.Typer()
commit_app.command("spec-commit")(spec_commit_command)
accept_app = typer.Typer()
accept_app.command()(accept)
SLUG = "owned-01M1A900"
MID = "01M1A900000000000000000001"
TARGET = "codex/owned"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def snapshot(root: Path) -> tuple[str, str, str, dict[str, str]]:
    files = {}
    for directory, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name != ".git"]
        for name in names:
            path = Path(directory) / name
            if name != ".git":
                # File-integrity fingerprint, not a charter-content digest.
                files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251
    return git(root, "rev-parse", "HEAD"), git(root, "status", "--porcelain"), git(root, "diff", "--cached"), files


@pytest.fixture
def checkouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    primary = tmp_path / "primary"
    primary.mkdir()
    git(primary, "init", "-q", "-b", "main")
    git(primary, "config", "user.name", "Test")
    git(primary, "config", "user.email", "test@example.invalid")
    git(primary, "config", "commit.gpgsign", "false")
    (primary / ".kittify").mkdir()
    (primary / ".kittify/config.yaml").write_text("agents:\n  available: [codex]\n", encoding="utf-8")
    (primary / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(primary, "add", ".")
    git(primary, "commit", "-qm", "seed")
    git(primary, "update-ref", "refs/remotes/origin/main", "main")
    git(primary, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    owned, sibling = tmp_path / "owned", tmp_path / "sibling"
    git(primary, "worktree", "add", "-qb", TARGET, str(owned))
    git(primary, "worktree", "add", "-qb", "codex/sibling", str(sibling))
    mission = owned / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MID,
                "mission_slug": SLUG,
                "slug": SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": TARGET,
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    (mission / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "|---|---|---|---|\n| FR-001 | Use owned checkout | Correct path | proposed |\n",
        encoding="utf-8",
    )
    (mission / "plan.md").write_text("# Plan\n\nUse the owned checkout.\n", encoding="utf-8")
    (mission / "tasks.md").write_text("# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n", encoding="utf-8")
    (mission / "tasks/WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Local task\ndependencies: []\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [app.py]\n"
        "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n# Task\n",
        encoding="utf-8",
    )
    git(owned, "add", ".")
    git(owned, "commit", "-qm", "owned mission")
    monkeypatch.chdir(owned)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(owned))
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    return primary, owned, sibling


def invoke(command: str, owned: Path, *extra: str, opt_in: bool = True):
    args = ["--mission", SLUG, "--json"]
    if opt_in:
        args += ["--owned-checkout", str(owned)]
    if command == "spec-commit":
        args += ["-m", "update owned spec", f"kitty-specs/{SLUG}/spec.md", *extra]
        return runner.invoke(commit_app, args)
    if command == "accept":
        return runner.invoke(accept_app, [*args, "--diagnose", *extra])
    return runner.invoke(mission_app, [command, *args, *extra])


def test_check_reads_owned_documents(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("check-prerequisites", owned, "--include-tasks")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert Path(payload["paths"]["feature_dir"]) == owned / "kitty-specs" / SLUG
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_no_opt_in_keeps_primary_resolution(checkouts):
    _primary, owned, _sibling = checkouts
    result = invoke("check-prerequisites", owned, opt_in=False)
    assert result.exit_code == 1
    assert "FEATURE_CONTEXT_UNRESOLVED" in result.output


def test_validate_only_is_readonly(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("finalize-tasks", owned, "--validate-only")
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_spec_commit_is_local_and_idempotent(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(sibling)
    spec = owned / "kitty-specs" / SLUG / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nOwned edit.\n", encoding="utf-8")
    result = invoke("spec-commit", owned)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["committed"] is True
    assert payload["placement_ref"] == TARGET
    assert git(owned, "show", "--format=", "--name-only", "HEAD") == f"kitty-specs/{SLUG}/spec.md"
    head = git(owned, "rev-parse", "HEAD")
    again = invoke("spec-commit", owned)
    assert again.exit_code == 0, again.output
    assert json.loads(again.output)["committed"] is False
    assert git(owned, "rev-parse", "HEAD") == head
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("command", ["check-prerequisites", "finalize-tasks", "spec-commit"])
def test_nested_checkout_refused_before_writes(checkouts, command):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, owned / "kitty-specs")
    assert result.exit_code == 1, result.output
    assert "OWNERSHIP_NESTED" in result.output
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_finalize_seeds_owned_status_only(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(sibling)
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    mission = owned / "kitty-specs" / SLUG
    assert (mission / "lanes.json").is_file()
    assert (mission / "acceptance-matrix.json").is_file()
    assert git(owned, "ls-files", f"kitty-specs/{SLUG}/acceptance-matrix.json")
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(row.get("wp_id") == "WP01" and row.get("to_lane") == "planned" for row in events) == 1
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(row.get("wp_id") == "WP01" and row.get("to_lane") == "planned" for row in events) == 1
    assert (snapshot(primary), snapshot(sibling)) == before


COMMANDS = ["check-prerequisites", "finalize-tasks", "spec-commit", "accept"]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("topology", ["lanes", "coord", "lanes_with_coord"])
def test_unsupported_topology_is_readonly(checkouts, command, topology):
    primary, owned, sibling = checkouts
    meta_path = owned / "kitty-specs" / SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = topology
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_TOPOLOGY_UNSUPPORTED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("branch_state", ["detached", "mismatch", "protected"])
def test_branch_refusal_has_no_side_effects(checkouts, command, branch_state):
    primary, owned, sibling = checkouts
    if branch_state == "detached":
        git(owned, "checkout", "--detach", "-q")
    elif branch_state == "mismatch":
        git(owned, "checkout", "-qb", "codex/other")
    else:
        # Only the primary declares protection: the linked checkout cannot weaken it.
        with (primary / ".kittify/config.yaml").open("a", encoding="utf-8") as config:
            config.write("\nprotection:\n  protected_branches: [main, codex/owned]\n")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_BRANCH_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("command", ["finalize-tasks", "spec-commit"])
def test_staged_changes_are_never_stashed_or_committed(checkouts, command):
    primary, owned, sibling = checkouts
    (owned / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(owned, "add", "app.py")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_INDEX_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before
    assert not git(owned, "stash", "list")


@pytest.mark.parametrize("command", COMMANDS)
def test_foreign_repository_is_refused(checkouts, tmp_path, command):
    primary, owned, sibling = checkouts
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    git(foreign, "init", "-q", "-b", "main")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, foreign)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNERSHIP_FOREIGN"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_same_slug_in_primary_is_not_read_or_written(checkouts, command):
    primary, owned, sibling = checkouts
    source = owned / "kitty-specs" / SLUG
    shadow = primary / "kitty-specs" / SLUG
    shutil.copytree(source, shadow)
    (shadow / "spec.md").write_text("Primary-only sentinel; no requirements\n", encoding="utf-8")
    before = snapshot(primary), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("extra_path", ["app.py", "../primary/app.py", "kitty-specs/another/spec.md"])
def test_whole_commit_batch_is_validated_before_staging(checkouts, extra_path):
    primary, owned, sibling = checkouts
    spec = owned / "kitty-specs" / SLUG / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nOwned edit.\n", encoding="utf-8")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("spec-commit", owned, extra_path)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_MISSION_PATH_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_resume_probe_cannot_opt_in(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("check-prerequisites", owned, "--resume-probe")
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_OPTION_UNSUPPORTED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_finalize_issue_matrix_uses_owned_writer(checkouts):
    primary, owned, sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    spec = mission / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nFix #123.\n", encoding="utf-8")
    before = snapshot(primary), snapshot(sibling)
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    matrix = mission / "issue-matrix.json"
    assert matrix.is_file()
    assert git(owned, "ls-files", f"kitty-specs/{SLUG}/issue-matrix.json")
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("caller", ["primary", "sibling"])
def test_explicit_checkout_is_independent_of_cwd(checkouts, monkeypatch, command, caller):
    primary, owned, sibling = checkouts
    cwd = primary if caller == "primary" else sibling
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(cwd))
    before = snapshot(primary), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_broken_pointer_is_refused_before_effects(checkouts, command):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    pointer = owned / ".git"
    original = pointer.read_text(encoding="utf-8")
    try:
        # Preserve Git's hidden-file attribute on Windows.
        with pointer.open("r+", encoding="utf-8") as file:
            file.write("gitdir: /does-not-exist/owned-worktree\n")
            file.truncate()
        result = invoke(command, owned)
        assert result.exit_code == 1, result.output
        assert json.loads(result.output)["error_code"] == "OWNERSHIP_BROKEN_POINTER"
    finally:
        with pointer.open("r+", encoding="utf-8") as file:
            file.write(original)
            file.truncate()
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_symlink_escape_is_refused_before_effects(checkouts, command):
    primary, owned, sibling = checkouts
    link = owned / "kitty-specs" / SLUG / "escaped.txt"
    try:
        link.symlink_to(primary / "app.py")
    except OSError as exc:
        pytest.skip(f"File symlinks unavailable on this host: {exc}")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke(command, owned)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_MISSION_PATH_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_accept_without_opt_in_keeps_primary_resolution(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("accept", owned, opt_in=False)
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "MISSION_NOT_FOUND"
    assert payload["handle"] == SLUG
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_accept_diagnosis_reads_owned_documents_without_writes(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("accept", owned)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["diagnose"] is True
    assert Path(payload["feature_dir"]) == owned / "kitty-specs" / SLUG
    assert payload["lanes"]["planned"] == ["WP01"]
    assert payload["ok"] is False
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_accept_diagnosis_refuses_encoding_repair(checkouts):
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("accept", owned, "--normalize-encoding")
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_OPTION_UNSUPPORTED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_accept_missing_owned_mission_does_not_fall_back(checkouts):
    primary, owned, sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    shutil.copytree(mission, primary / "kitty-specs" / SLUG)
    mission.rename(mission.with_name("unrelated-01M1B900"))
    moved_meta = mission.with_name("unrelated-01M1B900") / "meta.json"
    meta = json.loads(moved_meta.read_text(encoding="utf-8"))
    meta.update(mission_slug="unrelated-01M1B900", slug="unrelated-01M1B900", mission_id="01M1B900000000000000000001")
    moved_meta.write_text(json.dumps(meta), encoding="utf-8")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = invoke("accept", owned)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "FEATURE_CONTEXT_UNRESOLVED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.fixture
def ready_accept_checkouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from tests.specify_cli.cli.commands.test_accept_clean_tree import _create_lane_feature

    primary = tmp_path / "primary"
    primary.mkdir()
    original = _create_lane_feature(primary, with_negative_invariant=True)
    slug = original.name
    git(primary, "update-ref", "refs/remotes/origin/main", "main")
    git(primary, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    owned, sibling = tmp_path / "owned", tmp_path / "sibling"
    git(primary, "worktree", "add", "-qb", TARGET, str(owned))
    git(primary, "worktree", "add", "-qb", "codex/sibling", str(sibling))
    mission = owned / "kitty-specs" / slug
    meta_path = mission / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(topology="single_branch", target_branch=TARGET)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    lanes_path = mission / "lanes.json"
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes["mission_branch"] = TARGET
    lanes["target_branch"] = TARGET
    lanes_path.write_text(json.dumps(lanes), encoding="utf-8")
    (mission / "contracts").mkdir()
    (mission / "contracts/.gitkeep").touch()
    git(owned, "add", ".")
    git(owned, "commit", "-qm", "owned acceptance inputs")
    # Same identity but different topology and content must not influence owned IO.
    original_meta = json.loads((original / "meta.json").read_text(encoding="utf-8"))
    original_meta.update(topology="coord", coordination_branch="kitty/coordination/other")
    (original / "meta.json").write_text(json.dumps(original_meta), encoding="utf-8")
    (original / "spec.md").write_text("[NEEDS CLARIFICATION: primary sentinel]\n", encoding="utf-8")
    monkeypatch.chdir(sibling)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(sibling))
    return primary, owned, sibling, slug


def run_owned_accept(owned: Path, slug: str, *extra: str):
    return runner.invoke(accept_app, ["--mission", slug, "--owned-checkout", str(owned), "--json", *extra])


def test_accept_diagnosis_preserves_matrix_and_uses_owned_status(ready_accept_checkouts):
    primary, owned, sibling, slug = ready_accept_checkouts
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = run_owned_accept(owned, slug, "--diagnose")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert Path(payload["feature_dir"]) == owned / "kitty-specs" / slug
    assert payload["lanes"]["done"] == ["WP01"]
    assert not payload["needs_clarification"]
    assert any(item["check"] == "negative_invariants" and "diagnose" in item["detail"] for item in payload["skipped_checks"])
    assert not payload["blocked_checks"]
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_accept_no_commit_updates_only_owned_matrix(ready_accept_checkouts):
    primary, owned, sibling, slug = ready_accept_checkouts
    before = snapshot(primary), snapshot(sibling)
    head = git(owned, "rev-parse", "HEAD")
    meta = owned / "kitty-specs" / slug / "meta.json"
    meta_before = meta.read_bytes()
    result = run_owned_accept(owned, slug, "--no-commit")
    assert result.exit_code == 0, result.output
    assert git(owned, "rev-parse", "HEAD") == head
    assert meta.read_bytes() == meta_before
    matrix = json.loads((meta.parent / "acceptance-matrix.json").read_text(encoding="utf-8"))
    assert matrix["negative_invariants"][0]["result"] == "confirmed_absent"
    assert matrix["overall_verdict"] == "pass"
    assert (snapshot(primary), snapshot(sibling)) == before


def test_accept_commits_metadata_matrix_and_cutover_only_in_owned(ready_accept_checkouts, monkeypatch):
    from specify_cli.migration import runtime_state_cutover
    from specify_cli.core.owned_mission import resolve_owned_mission

    cutovers = []
    real_stamp = runtime_state_cutover.stamp_accept_cutover

    def capture_stamp(*args, **kwargs):
        result = real_stamp(*args, **kwargs)
        cutovers.append(result)
        return result

    monkeypatch.setattr(runtime_state_cutover, "stamp_accept_cutover", capture_stamp)
    primary, owned, sibling, slug = ready_accept_checkouts
    before = snapshot(primary), snapshot(sibling)
    head = git(owned, "rev-parse", "HEAD")
    event_path = owned / "kitty-specs" / slug / "status.events.jsonl"
    events_before = event_path.read_bytes()
    result = run_owned_accept(owned, slug)
    assert (snapshot(primary), snapshot(sibling)) == before
    assert result.exit_code == 0, result.output
    assert git(owned, "rev-parse", "HEAD") != head
    assert not git(owned, "status", "--porcelain")
    meta = json.loads(git(owned, "show", f"HEAD:kitty-specs/{slug}/meta.json"))
    assert meta["acceptance_history"]
    assert meta["accept_commit"]
    assert meta.get("status_phase") == "1", cutovers
    assert event_path.read_bytes() != events_before
    assert cutovers[0].seeded_count > 0
    matrix = json.loads(git(owned, "show", f"HEAD:kitty-specs/{slug}/acceptance-matrix.json"))
    assert matrix["negative_invariants"][0]["result"] == "confirmed_absent"
    assert (snapshot(primary), snapshot(sibling)) == before
    accepted = snapshot(primary), snapshot(owned), snapshot(sibling)
    repeated = real_stamp(event_path.parent, owned=resolve_owned_mission(primary, owned, slug))
    assert repeated.flipped and repeated.seeded_count == 0
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == accepted


@pytest.mark.parametrize("wrong_leg", ["metadata", "status"])
def test_owned_cutover_refuses_foreign_anchor_before_seed(ready_accept_checkouts, wrong_leg):
    from mission_runtime import ActionContextError
    from specify_cli.core.owned_mission import resolve_owned_mission
    from specify_cli.migration.runtime_state_cutover import stamp_accept_cutover

    primary, owned, sibling, slug = ready_accept_checkouts
    context = resolve_owned_mission(primary, owned, slug)
    own_dir = context.directory
    foreign = primary / "kitty-specs" / slug
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    with pytest.raises(ActionContextError) as refused:
        stamp_accept_cutover(
            foreign if wrong_leg == "metadata" else own_dir,
            status_feature_dir=foreign if wrong_leg == "status" else own_dir,
            owned=context,
        )
    assert refused.value.code == "OWNED_MISSION_PATH_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("failure", ["verification", "exception"])
def test_owned_accept_reports_unsuccessful_cutover(ready_accept_checkouts, monkeypatch, failure):
    from specify_cli.migration import runtime_state_cutover
    from specify_cli.migration.backfill_runtime_state import VerifyResult

    primary, owned, sibling, slug = ready_accept_checkouts

    def failed_stamp(*args, **kwargs):
        if failure == "exception":
            raise OSError("synthetic stamp failure")
        return runtime_state_cutover.CutoverResult(
            slug=slug,
            flipped=False,
            verify=VerifyResult(ok=False, wp_count=1, mismatches=("synthetic stamp failure",)),
        )

    monkeypatch.setattr(runtime_state_cutover, "stamp_accept_cutover", failed_stamp)
    before = snapshot(primary), snapshot(sibling)
    result = run_owned_accept(owned, slug)
    assert result.exit_code == 1, result.output
    assert "synthetic stamp failure" in json.loads(result.output)["error"]
    assert (snapshot(primary), snapshot(sibling)) == before


def test_accept_owned_dirty_document_is_not_hidden_by_primary_topology(ready_accept_checkouts):
    primary, owned, sibling, slug = ready_accept_checkouts
    spec = owned / "kitty-specs" / slug / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nLocal change\n", encoding="utf-8")
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = run_owned_accept(owned, slug, "--diagnose")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert any(line.endswith("/spec.md") for line in payload["git_dirty"])
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


@pytest.mark.parametrize("extra", [[], ["--no-commit"], ["--mode", "checklist"]])
def test_accept_writing_modes_refuse_staged_changes(ready_accept_checkouts, extra):
    primary, owned, sibling, slug = ready_accept_checkouts
    spec = owned / "kitty-specs" / slug / "spec.md"
    spec.write_text("Staged user edit\n", encoding="utf-8")
    git(owned, "add", str(spec))
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    result = run_owned_accept(owned, slug, *extra)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_INDEX_REFUSED"
    assert (snapshot(primary), snapshot(owned), snapshot(sibling)) == before


def test_nested_symlink_escape_is_refused_at_write_time_not_resolve(checkouts):
    """#3866: resolve no longer stats the whole mission tree per call.

    The resolve-time validation is a top-level boundary tripwire only, so a
    symlink nested deeper than the mission root no longer fails the resolve
    (the old O(tree) scan's only unique catch) — it is refused by
    ``OwnedMission.files`` at write time, which re-validates the actual
    written paths.
    """
    from mission_runtime import ActionContextError
    from specify_cli.core.owned_mission import resolve_owned_mission

    primary, owned, _sibling = checkouts
    link = owned / "kitty-specs" / SLUG / "tasks" / "escaped.txt"
    try:
        link.symlink_to(primary / "app.py")
    except OSError as exc:
        pytest.skip(f"File symlinks unavailable on this host: {exc}")

    context = resolve_owned_mission(primary, owned, SLUG)
    assert context.directory == owned / "kitty-specs" / SLUG

    with pytest.raises(ActionContextError) as refused:
        context.files([Path("tasks") / "escaped.txt"])
    assert refused.value.code == "OWNED_MISSION_PATH_REFUSED"
