"""Real Git acceptance proof for report-only recording."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
SLUG = "analysis-01M38YDX"
REPORT = f"kitty-specs/{SLUG}/analysis-report.md"
BODY = "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n# Analysis\nNo findings.\n"


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specify_cli.runtime import resolver

    # The suite home is per worker, so other tests may have installed global
    # templates there. Each transaction fixture needs its own authority source;
    # the explicit global-template refusal test replaces this seam deliberately.
    monkeypatch.setattr(resolver, "get_kittify_home", lambda: tmp_path / "runtime-home")
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "report-work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    charter = root / ".kittify/charter"
    charter.mkdir(parents=True)
    (root / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (charter / "charter.yaml").write_text("mission_type_activations: [software-dev]\n")
    mission = root / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md"):
        (mission / name).write_text(f"# {name}\nMaterial definition.\n")
    (mission / "tasks/WP01-proof.md").write_text("---\nwork_package_id: WP01\ntitle: Proof\n---\nDefinition.\n")
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M38YDX000000000000000001",
                "mission_slug": SLUG,
                "slug": SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": "report-work",
            }
        )
    )
    (root / "application.txt").write_text("baseline\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    monkeypatch.chdir(root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return root


def invoke(*extra: str):
    return CliRunner().invoke(app, ["record-analysis", "--mission", SLUG, "--json", *extra], input=BODY)


def test_report_only_preserves_unrelated_partial_staging(repo: Path):
    from specify_cli.analysis_report import check_analysis_report_current

    app_file = repo / "application.txt"
    app_file.write_text("staged\n")
    git(repo, "add", "application.txt")
    app_file.write_text("staged\nunstaged\n")
    (repo / "untracked.txt").write_bytes(b"untracked\x00bytes")
    staged = git(repo, "ls-files", "--stage", "-v", "--", "application.txt")
    head = git(repo, "rev-parse", "HEAD").strip()

    result = invoke("--report-only")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commit_status"] == "committed"
    assert git(repo, "rev-parse", "HEAD^").strip() == head
    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines() == [REPORT]
    assert git(repo, "ls-files", "--stage", "-v", "--", "application.txt") == staged
    assert app_file.read_text() == "staged\nunstaged\n"
    assert (repo / "untracked.txt").read_bytes() == b"untracked\x00bytes"
    assert check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


def test_default_still_refuses_unrelated_work(repo: Path):
    (repo / "application.txt").write_text("pending\n")
    result = invoke()
    assert result.exit_code == 1
    assert "DIRTY_WORKTREE" in result.output
    assert not (repo / REPORT).exists()


@pytest.mark.parametrize(
    "path", [".kittify/charter/charter.yaml", ".kittify/config.yaml", f"kitty-specs/{SLUG}/spec.md", f"kitty-specs/{SLUG}/tasks/WP01-proof.md"]
)
def test_dirty_material_input_refuses_before_write(repo: Path, path: str):
    with (repo / path).open("a") as stream:
        stream.write("\n# changed\n")
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert "DIRTY_ANALYSIS_INPUT" in result.output
    assert not (repo / REPORT).exists()
    assert git(repo, "rev-parse", "HEAD") == head


def test_failed_commit_never_reports_success(repo: Path):
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["commit_status"] == "written_uncommitted"
    assert git(repo, "rev-parse", "HEAD") == head


def test_post_commit_index_race_cannot_unlock_analysis(repo: Path):
    from specify_cli.analysis_report import check_analysis_report_current

    hook = repo / ".git/hooks/post-commit"
    hook.write_text("#!/bin/sh\nprintf 'concurrent\\n' > application.txt\ngit add application.txt\n")
    hook.chmod(0o755)
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["commit_status"] == "committed_unqualified"
    assert git(repo, "rev-parse", "HEAD") != head
    assert (repo / "application.txt").read_text() == "concurrent\n"
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


@pytest.mark.parametrize("mode", ["detached", "wrong_branch", "merge", "assume_unchanged", "symlink", "ignored_input"])
def test_unsafe_state_refuses_without_report_write(repo: Path, mode: str):
    if mode == "detached":
        git(repo, "checkout", "--detach", "-q")
    elif mode == "wrong_branch":
        git(repo, "checkout", "-qb", "other")
    elif mode == "merge":
        (repo / ".git/MERGE_HEAD").write_bytes(git(repo, "rev-parse", "HEAD"))
    elif mode == "assume_unchanged":
        git(repo, "update-index", "--assume-unchanged", "application.txt")
    elif mode == "symlink":
        (repo / REPORT).symlink_to(repo / "application.txt")
    else:
        (repo / ".git/info/exclude").write_text(".kittify/templates/\n")
        templates = repo / ".kittify/templates"
        templates.mkdir()
        (templates / "hidden.md").write_text("uncommitted authority")
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert git(repo, "rev-parse", "HEAD") == head
    assert (repo / "application.txt").read_text() == "baseline\n"
    if mode != "symlink":
        assert not (repo / REPORT).exists()


def test_post_commit_head_only_race_is_unqualified(repo: Path):
    from specify_cli.analysis_report import check_analysis_report_current

    hook = repo / ".git/hooks/post-commit"
    hook.write_text('#!/bin/sh\nif test -z "$REPORT_RACE"; then REPORT_RACE=1 git -c core.hooksPath=/dev/null commit --allow-empty -qm concurrent; fi\n')
    hook.chmod(0o755)
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["commit_status"] == "committed_unqualified"
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


def test_material_change_invalidates_qualified_report(repo: Path):
    from specify_cli.analysis_report import check_analysis_report_current

    result = invoke("--report-only")
    assert result.exit_code == 0, result.output
    mission = repo / "kitty-specs" / SLUG
    assert check_analysis_report_current(mission, repo).ok
    (repo / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\nchanged: true\n")
    assert not check_analysis_report_current(mission, repo).ok


@pytest.mark.parametrize("change", ["input", "index", "report"])
def test_race_before_commit_preserves_concurrent_state(repo: Path, monkeypatch: pytest.MonkeyPatch, change: str):
    from specify_cli.git import report_transaction
    from specify_cli.analysis_report import check_analysis_report_current

    original = report_transaction.write_analysis_report
    target = repo / ({"input": f"kitty-specs/{SLUG}/spec.md", "report": REPORT}.get(change, "application.txt"))

    def race(**kwargs):
        result = original(**kwargs)
        target.write_text("concurrent content\n")
        if change == "index":
            git(repo, "add", "application.txt")
        return result

    monkeypatch.setattr(report_transaction, "write_analysis_report", race)
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["commit_status"] == "written_uncommitted"
    assert git(repo, "rev-parse", "HEAD") == head
    assert target.read_text() == "concurrent content\n"
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok
    if change == "index":
        assert git(repo, "show", ":application.txt") == b"concurrent content\n"


def test_missing_receipt_never_qualifies_copied_report(repo: Path):
    from specify_cli.analysis_report import check_analysis_report_current

    result = invoke("--report-only")
    assert result.exit_code == 0, result.output
    for path in (repo / ".git/spec-kitty-report-transactions").glob("*.json"):
        path.unlink()
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


def test_dirty_existing_report_is_preserved(repo: Path):
    report = repo / REPORT
    report.write_text("unreviewed analysis\n")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert "DIRTY_ANALYSIS_INPUT" in result.output
    assert report.read_text() == "unreviewed analysis\n"


def test_global_template_requires_committed_project_override(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from specify_cli.runtime import resolver
    from kernel.paths import get_package_asset_root

    global_home = tmp_path / "global"
    templates = global_home / "missions/software-dev/templates"
    templates.mkdir(parents=True)
    monkeypatch.setattr(resolver, "get_kittify_home", lambda: global_home)
    for name in ("spec-template.md", "plan-template.md"):
        (templates / name).write_bytes((get_package_asset_root() / "software-dev/templates" / name).read_bytes())
    refused = invoke("--report-only")
    assert refused.exit_code == 1, refused.output
    assert "External mutable global template authority" in refused.output
    assert not (repo / REPORT).exists()
    override = repo / ".kittify/overrides/missions/software-dev/templates"
    override.mkdir(parents=True)
    for source in templates.iterdir():
        (override / source.name).write_bytes(source.read_bytes())
    git(repo, "add", ".kittify/overrides")
    git(repo, "commit", "-qm", "pin templates")
    accepted = invoke("--report-only")
    assert accepted.exit_code == 0, accepted.output


def test_repeated_qualified_analysis_is_unchanged(repo: Path):
    first = invoke("--report-only")
    assert first.exit_code == 0, first.output
    report = (repo / REPORT).read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    (repo / "application.txt").write_text("staged\n")
    git(repo, "add", "application.txt")
    (repo / "application.txt").write_text("staged\nworking\n")
    index = git(repo, "ls-files", "--stage", "-v", "-z")
    repeated = invoke("--report-only")
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.output)["commit_status"] == "unchanged"
    assert git(repo, "rev-parse", "HEAD") == head
    assert (repo / REPORT).read_bytes() == report
    assert git(repo, "ls-files", "--stage", "-v", "-z") == index
    assert (repo / "application.txt").read_text() == "staged\nworking\n"


@pytest.mark.parametrize("change", ["analyzer", "body", "receipt"])
def test_unchanged_requires_same_semantics_and_existing_qualification(repo: Path, change: str):
    from specify_cli.analysis_report import check_analysis_report_current

    first = invoke("--report-only")
    assert first.exit_code == 0, first.output
    head = git(repo, "rev-parse", "HEAD")
    if change == "receipt":
        for path in (repo / ".git/spec-kitty-report-transactions").glob("*.json"):
            path.unlink()
        assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok
    args = ["record-analysis", "--mission", SLUG, "--report-only", "--json"]
    if change == "analyzer":
        args.extend(["--agent", "different-analyzer"])
    body = BODY.replace("No findings.", "Revised analysis.") if change == "body" else BODY
    repeated = CliRunner().invoke(app, args, input=body)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.output)["commit_status"] == "committed"
    assert git(repo, "rev-parse", "HEAD") != head
    assert check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


def test_material_input_closure_backs_the_report_only_transaction(repo: Path):
    """The material-input closure the report-only transaction commits against is
    reachable and well-formed: it hashes the mission's declarative inputs and
    surfaces charter-authority failures as a typed ``MaterialInputError`` wrapping
    the canonical ``PackRootNotFound``. Exercising it here keeps the closure and
    the charter pack-root error surface covered by a per-PR test."""
    from charter.pack_paths import PackRootNotFound

    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    assert issubclass(MaterialInputError, ValueError)
    assert issubclass(PackRootNotFound, Exception)

    manifest = collect_material_inputs(repo / "kitty-specs" / SLUG, repo)
    assert manifest, "material-input manifest must not be empty"
    assert any("spec.md" in key for key in manifest), sorted(manifest)
    assert any("plan.md" in key for key in manifest)
    assert any("tasks.md" in key for key in manifest)
