"""Finalize's read-only lane preview must match the stored execution topology."""

from __future__ import annotations

import json

import pytest

from tests.integration.test_explicit_checkout_commands import (
    SLUG,
    checkouts as checkouts,
    git,
    invoke,
    snapshot,
)
from tests.integration.test_owned_pr_bound_finalization import pr_bound_checkouts as pr_bound_checkouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("mixed_kinds", [False, True])
def test_single_branch_preview_matches_real_finalize(request, monkeypatch, explicit, protected, mixed_kinds):
    from specify_cli.lanes import compute

    primary, owned, sibling = request.getfixturevalue("pr_bound_checkouts" if protected else "checkouts")
    mission = owned / "kitty-specs" / SLUG
    wp01 = mission / "tasks/WP01-test.md"
    wp02_text = wp01.read_text(encoding="utf-8").replace("WP01", "WP02").replace("app.py", "app2.py")
    (owned / "app2.py").write_text("VALUE = 2\n", encoding="utf-8")
    (mission / "tasks/WP02-test.md").write_text(wp02_text, encoding="utf-8")
    if mixed_kinds:
        (owned / "docs").mkdir()
        (owned / "docs/plan.md").write_text("# Planning artifact\n", encoding="utf-8")
        wp01.write_text(
            wp01.read_text(encoding="utf-8")
            .replace("owned_files: [app.py]", "owned_files: [docs/plan.md]")
            .replace("authoritative_surface: app.py", "authoritative_surface: docs/")
            .replace("execution_mode: code_change", "execution_mode: planning_artifact"),
            encoding="utf-8",
        )
    (mission / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n## Work Package WP02\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    git(owned, "add", "-A")
    git(owned, "commit", "-qm", "fixture: two disjoint work packages")
    monkeypatch.chdir(sibling if explicit else owned)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    captured = []
    real_compute = compute.compute_lanes

    def capture_real_manifest(*args, **kwargs):
        manifest = real_compute(*args, **kwargs)
        captured.append(manifest)
        return manifest

    monkeypatch.setattr(compute, "compute_lanes", capture_real_manifest)
    result = invoke("finalize-tasks", owned, "--validate-only", opt_in=explicit)
    assert result.exit_code == 0, result.output
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before
    preview = json.loads(result.output)["validation"]["lanes_preview"]
    assert preview["count"] == 1
    assert preview["lane_ids"] == ["lane-planning"]
    assert preview["planning_artifact_wps"] == (["WP01"] if mixed_kinds else [])
    assert len(captured) == 1
    declared = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert captured[0].mission_branch == declared.get("mission_branch", declared["target_branch"])
    assert captured[0].target_branch == declared["target_branch"]
    actual = invoke("finalize-tasks", owned, opt_in=explicit)
    assert actual.exit_code == 0, actual.output
    lanes = json.loads((mission / "lanes.json").read_text(encoding="utf-8"))
    assert preview["lane_ids"] == [lane["lane_id"] for lane in lanes["lanes"]]
    assert lanes["lanes"][0]["wp_ids"] == ["WP01", "WP02"]
    assert captured[0].mission_branch == lanes["mission_branch"]
    assert captured[0].target_branch == lanes["target_branch"]
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])
    finalized = tuple(snapshot(root) for root in (primary, owned, sibling))
    repeated = invoke("finalize-tasks", owned, "--validate-only", opt_in=explicit)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.output)["validation"]["lanes_preview"]["lane_ids"] == preview["lane_ids"]
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == finalized


@pytest.mark.parametrize("stamped", [False, True])
def test_existing_and_unstamped_lanes_keep_preview_parity(tmp_path, monkeypatch, stamped):
    from tests.integration.refinalize_frozen_lanes_support import finalize, setup_mission

    mission = setup_mission(tmp_path, monkeypatch)
    meta_path = mission.feature_dir / "meta.json"
    if not stamped:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        del meta["topology"]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        git(mission.repo, "add", str(meta_path))
        git(mission.repo, "commit", "-qm", "fixture: legacy unstamped topology")
    before = snapshot(mission.repo)
    preview = finalize(mission.slug, "--validate-only")
    assert preview.exit_code == 0, preview.output
    assert snapshot(mission.repo) == before
    lane_ids = preview.payload["validation"]["lanes_preview"]["lane_ids"]
    assert lane_ids == ["lane-a", "lane-b"]
    actual = finalize(mission.slug)
    assert actual.exit_code == 0, actual.output
    manifest = json.loads((mission.feature_dir / "lanes.json").read_text(encoding="utf-8"))
    assert lane_ids == [lane["lane_id"] for lane in manifest["lanes"]]


def test_started_lane_membership_preview_matches_real_finalize(tmp_path, monkeypatch):
    from tests.integration.refinalize_frozen_lanes_support import (
        amend_overlap,
        commit_amendment,
        finalize,
        setup_mission,
        start_wp,
    )

    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    amend_overlap(mission, joiner="WP01", owner="WP02")
    commit_amendment(mission)
    before = snapshot(mission.repo)
    preview = finalize(mission.slug, "--validate-only")
    assert preview.exit_code == 0, preview.output
    assert snapshot(mission.repo) == before
    assert preview.payload["validation"]["lanes_preview"]["lane_ids"] == ["lane-b"]
    actual = finalize(mission.slug)
    assert actual.exit_code == 0, actual.output
    manifest = json.loads((mission.feature_dir / "lanes.json").read_text(encoding="utf-8"))
    assert [lane["lane_id"] for lane in manifest["lanes"]] == ["lane-b"]
    assert set(manifest["lanes"][0]["wp_ids"]) == {"WP01", "WP02"}


def test_nonowned_single_branch_preview_matches_real_finalize(checkouts, monkeypatch):
    import shutil

    primary, owned, sibling = checkouts
    mission = primary / "kitty-specs" / SLUG
    shutil.copytree(owned / "kitty-specs" / SLUG, mission)
    git(primary, "checkout", "-qb", "codex/nonowned")
    meta_path = mission / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["target_branch"] = "codex/nonowned"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    (primary / "app2.py").write_text("VALUE = 2\n", encoding="utf-8")
    wp01 = mission / "tasks/WP01-test.md"
    (mission / "tasks/WP02-test.md").write_text(
        wp01.read_text(encoding="utf-8").replace("WP01", "WP02").replace("app.py", "app2.py"),
        encoding="utf-8",
    )
    (mission / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n## Work Package WP02\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    git(primary, "add", "-A")
    git(primary, "commit", "-qm", "fixture: nonowned single-branch mission")
    monkeypatch.chdir(primary)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(primary))
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    result = invoke("finalize-tasks", owned, "--validate-only", opt_in=False)
    assert result.exit_code == 0, result.output
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before
    preview = json.loads(result.output)["validation"]["lanes_preview"]
    assert preview["lane_ids"] == ["lane-planning"]
    actual = invoke("finalize-tasks", owned, opt_in=False)
    assert actual.exit_code == 0, actual.output
    manifest = json.loads((mission / "lanes.json").read_text(encoding="utf-8"))
    assert preview["lane_ids"] == [lane["lane_id"] for lane in manifest["lanes"]]
    assert manifest["lanes"][0]["wp_ids"] == ["WP01", "WP02"]
    assert (snapshot(owned), snapshot(sibling)) == (before[1], before[2])


def test_meta_less_legacy_preview_keeps_default_lanes(tmp_path, monkeypatch):
    from specify_cli.cli.commands.agent import mission_finalize
    from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
    from specify_cli.status.wp_metadata import WPMetadata

    reports = []
    monkeypatch.setattr(mission_finalize, "_emit_json", reports.append)
    monkeypatch.setattr(
        mission_finalize,
        "_bootstrap_canonical_state_via_mission",
        lambda *args, **kwargs: mission_finalize.BootstrapResult(2, 0, 2),
    )
    frontmatter = {
        wp: WPMetadata(work_package_id=wp, title=wp, execution_mode="code_change", owned_files=[name], authoritative_surface=name)
        for wp, name in (("WP01", "app.py"), ("WP02", "app2.py"))
    }
    ownership = {
        wp: OwnershipManifest(execution_mode=WorkProductKind.CODE_CHANGE, owned_files=(name,), authoritative_surface=name)
        for wp, name in (("WP01", "app.py"), ("WP02", "app2.py"))
    }
    before = list(tmp_path.iterdir())
    mission_finalize._emit_validate_only_report(
        tmp_path,
        "legacy-mission",
        None,
        mission_finalize._BootstrapState(inmemory_frontmatter=frontmatter),
        ownership,
        {"WP01": [], "WP02": []},
        {},
        "main",
        json_output=True,
    )
    assert reports[0]["validation"]["lanes_preview"]["lane_ids"] == ["lane-a", "lane-b"]
    assert list(tmp_path.iterdir()) == before
