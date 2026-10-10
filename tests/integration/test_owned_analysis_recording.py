"""Owned analysis recording must preserve checkout and report-transaction boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.analysis_report import check_analysis_report_current
from tests.integration.test_explicit_checkout_commands import SLUG, checkouts as checkouts, git, snapshot
from tests.integration.test_owned_pr_bound_finalization import pr_bound_checkouts as pr_bound_checkouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
BODY = "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n# Analysis\nNo blocking findings.\n"
REPORT = f"kitty-specs/{SLUG}/analysis-report.md"


@pytest.fixture
def analysis_checkouts(request, monkeypatch, tmp_path, protected):
    from specify_cli.runtime import resolver

    roots = request.getfixturevalue("pr_bound_checkouts" if protected else "checkouts")
    for root, marker in ((roots[0], "canonical"), (roots[1], "owned")):
        charter = root / ".kittify/charter/charter.yaml"
        charter.parent.mkdir(parents=True)
        charter.write_text(f"mission_type_activations: [software-dev]\nmarker: {marker}\n", encoding="utf-8")
        config = root / ".kittify/config.yaml"
        config.write_text(config.read_text(encoding="utf-8") + "charter: .kittify/charter/charter.yaml\n", encoding="utf-8")
        git(root, "add", str(charter), str(config))
        git(root, "commit", "-qm", "fixture: analysis charter")
    monkeypatch.setattr(resolver, "get_kittify_home", lambda: tmp_path / "runtime-home")
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return roots


def record(owned: Path, *, explicit: bool, report_only: bool, claim: Path | None = None):
    args = ["record-analysis", "--mission", SLUG, "--json"]
    if explicit:
        args += ["--owned-checkout", str(claim or owned)]
    if report_only:
        args += ["--report-only"]
    return CliRunner().invoke(app, args, input=BODY)


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("report_only", [False, True])
def test_analysis_records_in_owned_write_branch(analysis_checkouts, monkeypatch, explicit, report_only):
    from specify_cli.core import checkout_ownership
    from specify_cli.frontmatter import FrontmatterManager
    from specify_cli.analysis_report import collect_input_artifact_hashes

    primary, owned, sibling = analysis_checkouts
    monkeypatch.chdir(sibling if explicit else owned)
    before = snapshot(primary), snapshot(sibling)
    head = git(owned, "rev-parse", "HEAD")
    meta_path = owned / "kitty-specs" / SLUG / "meta.json"
    meta_before = meta_path.read_bytes()
    claims = []
    real_claim = checkout_ownership.resolve_ownership_claim

    def count_claim(*args, **kwargs):
        claims.append(args)
        return real_claim(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", count_claim)
    result = record(owned, explicit=explicit, report_only=report_only)
    assert result.exit_code == 0, result.output
    assert len(claims) == 1
    assert (snapshot(primary), snapshot(sibling)) == before
    assert meta_path.read_bytes() == meta_before
    assert git(owned, "rev-parse", "HEAD") != head
    assert git(owned, "show", "--format=", "--name-only", "HEAD") == REPORT
    metadata, _ = FrontmatterManager().read(owned / REPORT)
    assert metadata["artifact_type"] == "spec-kitty.analysis-report"
    assert metadata["verdict"] == "ready"
    assert metadata["input_artifacts"]["charter"] == collect_input_artifact_hashes(meta_path.parent, owned)["charter"]
    assert check_analysis_report_current(meta_path.parent, owned).ok
    assert not git(owned, "status", "--porcelain")
    if report_only:
        qualified_head = git(owned, "rev-parse", "HEAD")
        repeated = record(owned, explicit=explicit, report_only=True)
        assert repeated.exit_code == 0, repeated.output
        assert json.loads(repeated.output)["commit_status"] == "unchanged"
        assert git(owned, "rev-parse", "HEAD") == qualified_head


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
def test_report_only_preserves_unrelated_partial_staging(analysis_checkouts, monkeypatch, explicit):
    primary, owned, sibling = analysis_checkouts
    monkeypatch.chdir(sibling if explicit else owned)
    application = owned / "app.py"
    application.write_text("staged\n", encoding="utf-8")
    git(owned, "add", "app.py")
    application.write_text("staged\nunstaged\n", encoding="utf-8")
    (owned / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    (primary / "primary-unrelated.txt").write_text("primary pending\n", encoding="utf-8")
    (sibling / "sibling-unrelated.txt").write_text("sibling pending\n", encoding="utf-8")
    before = snapshot(primary), snapshot(sibling)
    staged = git(owned, "diff", "--cached")
    result = record(owned, explicit=explicit, report_only=True)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["commit_status"] == "committed"
    assert git(owned, "show", "--format=", "--name-only", "HEAD") == REPORT
    assert git(owned, "diff", "--cached") == staged
    assert application.read_text(encoding="utf-8") == "staged\nunstaged\n"
    assert (owned / "untracked.txt").read_text(encoding="utf-8") == "untracked\n"
    assert (snapshot(primary), snapshot(sibling)) == before
    assert check_analysis_report_current(owned / "kitty-specs" / SLUG, owned).ok


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("where", ["owned_spec", "canonical_charter", "owned_charter", "owned_config"])
def test_report_only_material_dirt_refuses_before_write(analysis_checkouts, monkeypatch, where):
    primary, owned, sibling = analysis_checkouts
    paths = {
        "owned_spec": owned / "kitty-specs" / SLUG / "spec.md",
        "canonical_charter": primary / ".kittify/charter/charter.yaml",
        "owned_charter": owned / ".kittify/charter/charter.yaml",
        "owned_config": owned / ".kittify/config.yaml",
    }
    path = paths[where]
    path.write_text(path.read_text(encoding="utf-8") + "\n# dirty material\n", encoding="utf-8")
    monkeypatch.chdir(owned)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = record(owned, explicit=True, report_only=True)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "DIRTY_ANALYSIS_INPUT"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before
    assert not (owned / REPORT).exists()


@pytest.mark.parametrize("protected", [True])
@pytest.mark.parametrize("report_only", [False, True])
@pytest.mark.parametrize("bad", ["wrong_branch", "detached", "foreign"])
def test_invalid_claim_refuses_before_writes(analysis_checkouts, tmp_path, monkeypatch, report_only, bad):
    primary, owned, sibling = analysis_checkouts
    claim = owned
    if bad == "wrong_branch":
        git(owned, "checkout", "-qb", "codex/wrong")
    elif bad == "detached":
        git(owned, "checkout", "--detach", "-q")
    else:
        claim = tmp_path / "foreign"
        claim.mkdir()
        git(claim, "init", "-qb", "main")
    monkeypatch.chdir(sibling)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = record(owned, explicit=True, report_only=report_only, claim=claim)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"].startswith(("OWNED_", "OWNERSHIP_"))
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("protected", [True])
@pytest.mark.parametrize("where", ["owned_spec", "canonical_charter"])
def test_material_race_keeps_written_report_unqualified(analysis_checkouts, monkeypatch, where):
    from specify_cli.git import report_transaction

    primary, owned, sibling = analysis_checkouts
    path = owned / "kitty-specs" / SLUG / "spec.md" if where == "owned_spec" else primary / ".kittify/charter/charter.yaml"
    original = report_transaction.write_analysis_report

    def race(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_text(path.read_text(encoding="utf-8") + "\n# concurrent material change\n", encoding="utf-8")
        return result

    monkeypatch.setattr(report_transaction, "write_analysis_report", race)
    monkeypatch.chdir(owned)
    head = git(owned, "rev-parse", "HEAD")
    sibling_before = snapshot(sibling)
    result = record(owned, explicit=True, report_only=True)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["commit_status"] == "written_uncommitted"
    assert "concurrent material change" in path.read_text(encoding="utf-8")
    assert git(owned, "rev-parse", "HEAD") == head
    assert snapshot(sibling) == sibling_before
    assert not check_analysis_report_current(owned / "kitty-specs" / SLUG, owned).ok


@pytest.mark.parametrize("protected", [False, True])
def test_ordinary_owned_dirt_refuses_before_write(analysis_checkouts, monkeypatch):
    primary, owned, sibling = analysis_checkouts
    (owned / "app.py").write_text("pending application change\n", encoding="utf-8")
    monkeypatch.chdir(owned)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = record(owned, explicit=False, report_only=False)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "DIRTY_WORKTREE"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("protected", [True])
@pytest.mark.parametrize("report_only", [False, True])
def test_owned_destination_symlink_refuses_before_write(analysis_checkouts, monkeypatch, report_only):
    primary, owned, sibling = analysis_checkouts
    foreign = sibling / "foreign-report.md"
    foreign.write_text("preserve foreign report\n", encoding="utf-8")
    (owned / REPORT).symlink_to(foreign)
    monkeypatch.chdir(owned)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = record(owned, explicit=True, report_only=report_only)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_MISSION_PATH_REFUSED"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("protected", [True])
def test_transaction_rejects_foreign_mission_directory(analysis_checkouts):
    from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt
    from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES
    from specify_cli.git.report_transaction import record_report_transaction

    primary, owned, sibling = analysis_checkouts
    fact = resolve_owned_or_adopt(primary, owned, SLUG, cwd=sibling, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert fact is not None
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    outcome = record_report_transaction(
        repo_root=owned,
        feature_dir=primary / "kitty-specs" / SLUG,
        body=BODY,
        analyzer_agent=None,
        target_branch=fact.write_branch,
        owned=fact,
    )
    assert not outcome.payload["success"]
    assert outcome.payload["commit_status"] == "failed_before_write"
    assert outcome.payload["error_code"] == "OWNED_MISSION_PATH_REFUSED"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("protected", [True])
@pytest.mark.parametrize("fallback", ["markdown", "absent"])
def test_canonical_charter_deletion_refuses_before_write(analysis_checkouts, monkeypatch, fallback):
    primary, owned, sibling = analysis_checkouts
    if fallback == "markdown":
        markdown = primary / ".kittify/charter/charter.md"
        markdown.write_text("# Canonical charter fallback\n", encoding="utf-8")
        git(primary, "add", str(markdown))
        git(primary, "commit", "-qm", "fixture: charter fallback")
    (primary / ".kittify/charter/charter.yaml").unlink()
    monkeypatch.chdir(owned)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = record(owned, explicit=True, report_only=True)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "DIRTY_ANALYSIS_INPUT"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("protected", [True])
def test_unselected_canonical_markdown_dirt_is_unrelated(analysis_checkouts, monkeypatch):
    primary, owned, sibling = analysis_checkouts
    (primary / ".kittify/charter/charter.md").write_text("# Unselected pending charter\n", encoding="utf-8")
    monkeypatch.chdir(owned)
    before = snapshot(primary), snapshot(sibling)
    result = record(owned, explicit=True, report_only=True)
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == before
    assert check_analysis_report_current(owned / "kitty-specs" / SLUG, owned).ok
