"""Aggregate coverage must score the source PR without executing its checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.fast]
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/aggregate_source.py"


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def _init_repo(repo: Path) -> None:
    """Scaffold an empty repo with the minimal registry the preparer reads."""
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / ".github").mkdir()
    (repo / ".github/ci-module-registry.yml").write_text("modules: []\n")


def _finalize_fixture(repo: Path, base: str, head: str) -> dict:
    """Bind ``base``/``head`` as a synthetic PR merge and build the run projection."""
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    merge = git(repo, "commit-tree", tree, "-p", base, "-p", head, "-m", "synthetic PR merge")
    git(repo, "update-ref", "refs/pull/7/merge", merge)
    git(repo, "checkout", "-q", base)
    git(repo, "remote", "add", "origin", str(repo))
    return {
        "id": 42,
        "run_attempt": 1,
        "status": "completed",
        "path": ".github/workflows/ci-modules.yml",
        "event": "pull_request",
        "head_sha": head,
        "repository": {"full_name": "spec-kitty/spec-kitty"},
        "referenced_workflows": [{"path": f"spec-kitty/spec-kitty/.github/workflows/module-tests.yml@{merge}", "sha": merge, "ref": "refs/pull/7/merge"}],
        "pull_requests": [{"number": 7, "head": {"sha": head}, "base": {"sha": base, "repo": {"full_name": "spec-kitty/spec-kitty"}}}],
    }


def source_fixture(tmp_path: Path) -> tuple[Path, dict, str]:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src/kernel").mkdir(parents=True)
    (repo / "src/kernel/example.py").write_text("value = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src/kernel/example.py").write_text("value = 1\nnew_value = 2\n")
    (repo / ".github/ci-module-registry.yml").write_text("modules: [{module: kernel, tier: standard, shard_count: 1}]\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "source")
    head = git(repo, "rev-parse", "HEAD")
    run = _finalize_fixture(repo, base, head)
    return repo, run, base


def prose_and_code_fixture(tmp_path: Path) -> tuple[Path, dict, str]:
    """A critical-path docstring-only edit alongside a critical-path code edit.

    ``src/specify_cli/status/prose_target.py`` only has its module docstring
    reworded between base and head; ``src/kernel/example.py`` gets a genuine
    new statement. Both paths match ``CRITICAL_PATHS`` globs.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    status_dir = repo / "src/specify_cli/status"
    status_dir.mkdir(parents=True)
    (status_dir / "prose_target.py").write_text('"""Old docstring."""\n\nvalue = 1\n')
    kernel_dir = repo / "src/kernel"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "example.py").write_text("value = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    (status_dir / "prose_target.py").write_text('"""New docstring."""\n\nvalue = 1\n')
    (kernel_dir / "example.py").write_text("value = 1\nnew_value = 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "source")
    head = git(repo, "rev-parse", "HEAD")
    run = _finalize_fixture(repo, base, head)
    return repo, run, base


def prose_only_new_file_fixture(tmp_path: Path) -> tuple[Path, dict, str]:
    """A brand-new critical-path file containing only a module docstring.

    No base blob exists for it, so the classifier must fail-closed (``no_base``)
    and the file must stay in ``critical.diff.patch`` even though its only
    content is prose.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src/kernel").mkdir(parents=True)
    (repo / "src/kernel/example.py").write_text("value = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src/kernel/new_module.py").write_text('"""Just a docstring, nothing else."""\n')
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "source")
    head = git(repo, "rev-parse", "HEAD")
    run = _finalize_fixture(repo, base, head)
    return repo, run, base


def run_source(repo: Path, run: dict) -> subprocess.CompletedProcess[str]:
    source = repo / "source-run.json"
    source.write_text(json.dumps(run))
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--repository", "spec-kitty/spec-kitty", "--run-id", "42", "--attempt", "1"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )


def test_source_registry_and_diff_are_from_pr_while_checkout_stays_trusted(tmp_path: Path) -> None:
    repo, run, trusted = source_fixture(tmp_path)
    result = run_source(repo, run)
    assert result.returncode == 0, result.stderr
    out = repo / "out/aggregate/source"
    assert "new_value = 2" in (out / "diff.patch").read_text()
    assert yaml.safe_load((out / "ci-module-registry.yml").read_text())["modules"][0]["module"] == "kernel"
    assert json.loads((out / "source.json").read_text())["head_sha"] == run["head_sha"]
    assert git(repo, "rev-parse", "HEAD") == trusted


def test_prose_only_critical_change_excluded_from_diff_while_real_change_remains(tmp_path: Path) -> None:
    """T011 (red-first, WP03): a docstring-only critical-path file must not
    appear in ``critical.diff.patch`` — there is no coverable changed line to
    false-fail the diff-cover gate on (squad Paula F1) — while a real code
    change on another critical-path file in the SAME PR is untouched (T013:
    a mixed PR still scores the real code)."""
    repo, run, _ = prose_and_code_fixture(tmp_path)
    result = run_source(repo, run)
    assert result.returncode == 0, result.stderr
    critical_patch = (repo / "out/aggregate/source/critical.diff.patch").read_text()
    assert "src/specify_cli/status/prose_target.py" not in critical_patch
    assert "New docstring" not in critical_patch
    assert "src/kernel/example.py" in critical_patch
    assert "new_value = 2" in critical_patch
    # The full (non-critical-scoped) diff still records both changes: the
    # exclusion is scoped to the diff-cover-scored patch only (T012).
    full_diff = (repo / "out/aggregate/source/diff.patch").read_text()
    assert "New docstring" in full_diff
    assert "new_value = 2" in full_diff


def test_prose_only_new_critical_file_stays_in_diff_fail_closed(tmp_path: Path) -> None:
    """A brand-new critical-path file has no base blob to prove prose-only
    against, so the classifier fails closed (``no_base``) and the file must
    remain scored, even though its only content is a docstring."""
    repo, run, _ = prose_only_new_file_fixture(tmp_path)
    result = run_source(repo, run)
    assert result.returncode == 0, result.stderr
    critical_patch = (repo / "out/aggregate/source/critical.diff.patch").read_text()
    assert "src/kernel/new_module.py" in critical_patch
    assert "Just a docstring, nothing else." in critical_patch


@pytest.mark.parametrize(
    "mutation,diagnostic",
    [
        ("in_progress", "source run attempt has not completed"),
        ("stale_attempt", "source run identity, attempt, repository or workflow does not match"),
        ("wrong_run", "source run identity, attempt, repository or workflow does not match"),
        ("wrong_repo", "source run identity, attempt, repository or workflow does not match"),
        ("wrong_workflow", "source run identity, attempt, repository or workflow does not match"),
        ("missing_reference", "source run lacks one immutable PR merge workflow reference"),
        ("bad_sha", "source head is not a full commit SHA"),
        ("foreign_reference", "source run lacks one immutable PR merge workflow reference"),
        ("duplicate_reference", "source run lacks one immutable PR merge workflow reference"),
        ("bad_reference_sha", "source run lacks one immutable PR merge workflow reference"),
        ("unsupported_event", "unsupported source event"),
    ],
)
def test_source_rejects_ambiguous_or_stale_evidence(tmp_path: Path, mutation: str, diagnostic: str) -> None:
    repo, run, trusted = source_fixture(tmp_path)
    if mutation == "in_progress":
        run["status"] = "in_progress"
    elif mutation == "stale_attempt":
        run["run_attempt"] = 2
    elif mutation == "wrong_run":
        run["id"] = 43
    elif mutation == "wrong_repo":
        run["repository"]["full_name"] = "other/repo"
    elif mutation == "wrong_workflow":
        run["path"] = ".github/workflows/untrusted.yml"
    elif mutation == "missing_reference":
        run["referenced_workflows"] = []
    elif mutation == "bad_sha":
        run["head_sha"] = "--upload-pack=evil"
    elif mutation == "foreign_reference":
        reference = run["referenced_workflows"][0]
        reference["path"] = f"other/repo/.github/workflows/module-tests.yml@{reference['sha']}"
    elif mutation == "duplicate_reference":
        run["referenced_workflows"].append(dict(run["referenced_workflows"][0]))
    elif mutation == "bad_reference_sha":
        run["referenced_workflows"][0].update(
            sha="--upload-pack=evil",
            path="spec-kitty/spec-kitty/.github/workflows/module-tests.yml@--upload-pack=evil",
        )
    else:
        run["event"] = "schedule"
    result = run_source(repo, run)
    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert not (repo / "out/aggregate/source/source.json").exists()
    assert git(repo, "rev-parse", "HEAD") == trusted


def test_shipped_diff_cover_rejects_uncovered_pr_line_on_trusted_checkout(tmp_path: Path) -> None:
    repo, run, _trusted = source_fixture(tmp_path)
    assert run_source(repo, run).returncode == 0
    git(repo, "update-ref", "refs/remotes/origin/main", run["pull_requests"][0]["base"]["sha"])
    coverage = repo / "out/aggregate/coverage"
    coverage.mkdir(parents=True)
    (coverage / "coverage-standard-kernel-shard1-of-1.xml").write_text(
        '<coverage><sources><source>.</source></sources><packages><package name="kernel">'
        '<classes><class name="example" filename="src/kernel/example.py"><lines>'
        '<line number="1" hits="1"/><line number="2" hits="0"/>'
        "</lines></class></classes></package></packages></coverage>"
    )
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci-aggregate.yml").read_text())
    gate = next(s["run"] for s in workflow["jobs"]["diff-cover"]["steps"] if s.get("name", "").startswith("diff-cover —"))
    gate = gate.replace("${{ steps.census.outputs.exclude-flags }}", "")
    gate = gate.replace("scripts/ci/validate_diff_coverage.py", str(ROOT / "scripts/ci/validate_diff_coverage.py"))
    (repo / ".venv").symlink_to(Path(sys.executable).parent.parent)
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["bash", "-c", gate], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "0%" in result.stdout, result.stdout + result.stderr


def test_base_line_insertions_use_tested_merge_line_numbers(tmp_path: Path) -> None:
    repo, run, _trusted = source_fixture(tmp_path)
    filename = repo / "src/kernel/example.py"
    original = "".join(f"value_{i} = {i}\n" for i in range(80))
    filename.write_text(original)
    git(repo, "add", "src/kernel/example.py")
    git(repo, "commit", "-qm", "common eighty line base")
    common = git(repo, "rev-parse", "HEAD")
    filename.write_text(original + "new_uncovered = 1\n")
    git(repo, "add", "src/kernel/example.py")
    git(repo, "commit", "-qm", "PR uncovered line")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", common)
    filename.write_text("base_prefix = 1\n" + original)
    git(repo, "add", "src/kernel/example.py")
    git(repo, "commit", "-qm", "base inserted line")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "merge", "--no-ff", "-qm", "synthetic merge", head)
    merged = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/pull/7/merge", merged)
    git(repo, "checkout", "-q", base)
    run["head_sha"] = run["pull_requests"][0]["head"]["sha"] = head
    run["pull_requests"][0]["base"]["sha"] = base
    run["referenced_workflows"][0].update(sha=merged, path=f"spec-kitty/spec-kitty/.github/workflows/module-tests.yml@{merged}")
    assert run_source(repo, run).returncode == 0
    diff = (repo / "out/aggregate/source/diff.patch").read_text()
    assert "+79,4" in diff, diff
    coverage = repo / "coverage.xml"
    coverage.write_text(
        '<coverage><packages><package name="kernel"><classes>'
        '<class filename="src/kernel/example.py"><lines>'
        '<line number="81" hits="1"/><line number="82" hits="0"/>'
        "</lines></class></classes></package></packages></coverage>"
    )
    result = subprocess.run(
        [str(Path(sys.executable).parent / "diff-cover"), str(coverage), "--diff-file=out/aggregate/source/diff.patch", "--fail-under=90"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "0%" in result.stdout
    assert json.loads((repo / "out/aggregate/source/source.json").read_text())["tested_sha"] == merged
    assert git(repo, "rev-parse", "HEAD") == base


def test_live_pr_and_merge_ref_movement_do_not_replace_immutable_tested_source(tmp_path: Path) -> None:
    repo, run, trusted = source_fixture(tmp_path)
    tested = run["referenced_workflows"][0]["sha"]
    git(repo, "update-ref", "refs/pull/7/merge", trusted)
    run["pull_requests"][0]["head"]["sha"] = "f" * 40
    result = run_source(repo, run)
    assert result.returncode == 0, result.stderr
    assert json.loads((repo / "out/aggregate/source/source.json").read_text())["tested_sha"] == tested


def test_immutable_reference_must_bind_the_source_head(tmp_path: Path) -> None:
    repo, run, trusted = source_fixture(tmp_path)
    run["referenced_workflows"][0].update(sha=trusted, path=f"spec-kitty/spec-kitty/.github/workflows/module-tests.yml@{trusted}")
    result = run_source(repo, run)
    assert result.returncode != 0
    assert "tested merge parents" in result.stderr


CRITICAL_EXAMPLES = (
    "src/kernel/nested/example.py",
    "src/charter/activation/example.py",
    "src/specify_cli/status/nested/example.py",
    "src/specify_cli/lanes/branch_naming.py",
    "src/specify_cli/dashboard/handlers/nested/example.py",
    "src/specify_cli/dashboard/scanner.py",
    "src/specify_cli/merge/nested/example.py",
    "src/runtime/next/nested/example.py",
    "src/mission_runtime/nested/example.py",
)


def score_source_change(
    tmp_path: Path,
    filename: str,
    *,
    new_file: bool,
    hits: int = 0,
    comment: bool = False,
    omit_statement: bool = False,
    omit_file: bool = False,
    bad_manifest: str = "",
    excluded: bool = False,
    pragma: bool = False,
    deletion: bool = False,
    multiline: str = "",
) -> subprocess.CompletedProcess[str]:
    """Run the shipped source preparer and scoring shell over producer-shaped XML."""
    repo, run, _ = source_fixture(tmp_path)
    target = repo / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if not new_file:
        initial = "existing = 1\n"
        if multiline == "code":
            initial = "value = (\n    1 +\n    2\n)\n"
        elif multiline == "comment":
            initial = "value = (\n    # original\n    1 + 2\n)\n"
        elif multiline == "docstring":
            initial = '"""original\nsecond\n"""\nvalue = 1\n'
        target.write_text(initial)
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "existing critical file")
    base = git(repo, "rev-parse", "HEAD")
    if multiline:
        old, new = {"code": ("    2", "    3"), "comment": ("original", "updated"), "docstring": ("second", "changed")}[multiline]
        target.write_text(target.read_text().replace(old, new))
    elif deletion:
        target.unlink()
    else:
        change = "# comment only\n" if comment else "changed = 2\n"
        if pragma:
            change = "changed = 2  # pragma: no cover\n"
        target.write_text(("" if new_file else "existing = 1\n") + change)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "source change")
    head = git(repo, "rev-parse", "HEAD")
    merged = git(repo, "commit-tree", "HEAD^{tree}", "-p", base, "-p", head, "-m", "tested PR merge")
    run["head_sha"] = head
    run["referenced_workflows"][0].update(sha=merged, path=f"spec-kitty/spec-kitty/.github/workflows/module-tests.yml@{merged}")
    git(repo, "checkout", "-q", base)
    assert target.exists() is not new_file
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    prepared = run_source(repo, run)
    assert prepared.returncode == 0, prepared.stderr
    sources_file = repo / "out/aggregate/source/critical-sources.json"
    if bad_manifest:
        sources = json.loads(sources_file.read_text())
        if bad_manifest == "missing":
            sources.pop(filename)
        else:
            sources[filename] = "not base64!"
        sources_file.write_text(json.dumps(sources))
    # The preflight must not inherit a checkout's ambient coverage exclusions.
    (repo / ".coveragerc").write_text("[report]\nexclude_lines = .\n")
    coverage = repo / "out/aggregate/coverage"
    coverage.mkdir(parents=True)
    lines = "" if new_file else '<line number="1" hits="1"/>'
    if not comment and not omit_statement and not pragma and not deletion:
        lines += f'<line number="{1 if new_file else 2}" hits="{hits}"/>'
    if multiline:
        line = 4 if multiline == "docstring" else 1
        lines = "" if omit_statement else f'<line number="{line}" hits="{hits}"/>'
    (coverage / "coverage-standard-critical-shard1-of-1.xml").write_text(
        '<coverage><sources><source /></sources><packages><package name="critical"><classes>'
        f'<class filename="{"other.py" if omit_file else filename}"><lines>{lines}</lines></class>'
        "</classes></package></packages></coverage>"
    )
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci-aggregate.yml").read_text())
    gate = next(s["run"] for s in workflow["jobs"]["diff-cover"]["steps"] if s.get("name", "").startswith("diff-cover —"))
    (repo / ".venv").symlink_to(Path(sys.executable).parent.parent)
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    exclude_flags = ""
    if excluded:
        census = next(step["run"] for step in workflow["jobs"]["diff-cover"]["steps"] if step.get("id") == "census")
        census = census.replace(
            "from tests.architectural._p1_census_oracle import denominator_excluded_surfaces",
            "def denominator_excluded_surfaces(): return {'charter.activation'}",
        )
        output = repo / "census-output"
        result = subprocess.run(["bash", "-c", census], cwd=repo, env=dict(env, GITHUB_OUTPUT=str(output)), capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        exclude_flags = output.read_text().strip().removeprefix("exclude-flags=")
    gate = gate.replace("${{ steps.census.outputs.exclude-flags }}", exclude_flags)
    gate = gate.replace("scripts/ci/validate_diff_coverage.py", str(ROOT / "scripts/ci/validate_diff_coverage.py"))
    result = subprocess.run(["bash", "-c", gate], cwd=repo, env=env, capture_output=True, text=True)
    assert git(repo, "rev-parse", "HEAD") == base
    assert target.exists() is not new_file
    return result


@pytest.mark.git_repo
@pytest.mark.parametrize("filename", CRITICAL_EXAMPLES)
@pytest.mark.parametrize("new_file", [False, True], ids=["existing", "new-absent-from-checkout"])
def test_shipped_gate_scores_all_critical_paths_from_git_trees(tmp_path: Path, filename: str, new_file: bool) -> None:
    result = score_source_change(tmp_path, filename, new_file=new_file)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Total:   1 line" in result.stdout
    assert "Coverage: 0%" in result.stdout


@pytest.mark.git_repo
@pytest.mark.parametrize("new_file", [False, True])
def test_shipped_gate_accepts_covered_nested_critical_changes(tmp_path: Path, new_file: bool) -> None:
    result = score_source_change(tmp_path, "src/charter/activation/example.py", new_file=new_file, hits=1)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Total:   1 line" in result.stdout
    assert "Coverage: 100%" in result.stdout


@pytest.mark.git_repo
@pytest.mark.parametrize("filename,comment", [("docs/example.py", False), ("src/charter/activation/example.py", True)])
def test_shipped_gate_preserves_genuinely_empty_comparisons(tmp_path: Path, filename: str, comment: bool) -> None:
    result = score_source_change(tmp_path, filename, new_file=False, comment=comment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No lines with coverage information in this diff." in result.stdout


@pytest.mark.git_repo
def test_shipped_gate_rejects_missing_statement_evidence(tmp_path: Path) -> None:
    result = score_source_change(tmp_path, "src/charter/activation/example.py", new_file=True, omit_statement=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "missing coverage evidence" in result.stdout + result.stderr


@pytest.mark.git_repo
@pytest.mark.parametrize("failure", ["missing-file", "missing-statement", "missing-manifest", "invalid-manifest"])
def test_shipped_gate_refuses_incomplete_source_or_report_evidence(tmp_path: Path, failure: str) -> None:
    result = score_source_change(
        tmp_path,
        "src/charter/activation/example.py",
        new_file=False,
        omit_file=failure == "missing-file",
        omit_statement=failure == "missing-statement",
        bad_manifest=failure.removesuffix("-manifest") if failure.endswith("-manifest") else "",
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Coverage: 100%" not in result.stdout


@pytest.mark.git_repo
@pytest.mark.parametrize("control", ["pragma", "deletion", "census-exclusion"])
def test_shipped_gate_preserves_statement_and_census_exclusions(tmp_path: Path, control: str) -> None:
    result = score_source_change(
        tmp_path,
        "src/charter/activation/example.py",
        new_file=False,
        pragma=control == "pragma",
        deletion=control == "deletion",
        excluded=control == "census-exclusion",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No lines with coverage information in this diff." in result.stdout


@pytest.mark.git_repo
@pytest.mark.parametrize("evidence,expected", [("missing", 1), ("uncovered", 1), ("covered", 0)])
def test_shipped_gate_maps_continuation_edits_to_statement_origins(tmp_path: Path, evidence: str, expected: int) -> None:
    result = score_source_change(
        tmp_path,
        "src/charter/activation/example.py",
        new_file=False,
        multiline="code",
        omit_statement=evidence == "missing",
        hits=int(evidence == "covered"),
    )
    assert result.returncode == expected, result.stdout + result.stderr
    if evidence == "missing":
        assert "missing coverage evidence" in result.stdout + result.stderr
    else:
        assert "Total:   1 line" in result.stdout
        assert f"Coverage: {100 if evidence == 'covered' else 0}%" in result.stdout


@pytest.mark.git_repo
@pytest.mark.parametrize("control", ["comment", "docstring"])
def test_shipped_gate_keeps_multiline_noncode_edits_empty(tmp_path: Path, control: str) -> None:
    result = score_source_change(tmp_path, "src/charter/activation/example.py", new_file=False, multiline=control)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No lines with coverage information in this diff." in result.stdout


@pytest.mark.git_repo
def test_shipped_gate_preserves_quoted_git_paths(tmp_path: Path) -> None:
    result = score_source_change(tmp_path, "src/charter/activation/with space.py", new_file=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Coverage: 0%" in result.stdout
