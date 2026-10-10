"""#5878: map requirements through one validated owned-checkout authority."""

from __future__ import annotations
import json
import shutil
import pytest
from typer.testing import CliRunner
from specify_cli.cli.commands.agent import tasks
from specify_cli.status.wp_metadata import read_wp_frontmatter
from tests.integration.conftest import OwnedCheckouts
from tests.integration.test_owned_protected_single_branch import protected_mint as protected_mint, _git
from tests.integration.test_explicit_checkout_commands import snapshot

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def invoke(f: OwnedCheckouts, *, explicit: bool, auto: bool, extra: list[str] | None = None):
    args = ["map-requirements", "--mission", f.mission_slug, "--json", "--auto-commit" if auto else "--no-auto-commit"]
    if explicit:
        args += ["--owned-checkout", str(f.owned_root)]
    args += extra if extra is not None else ["--batch", '{"WP01":["FR-001"]}']
    return CliRunner().invoke(tasks.app, args)


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("auto", [False, True])
def test_mapping_stays_owned(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, explicit: bool, auto: bool):
    f = protected_mint
    monkeypatch.chdir(f.sibling if explicit else f.owned_root)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    before = (snapshot(f.repository_root), snapshot(f.sibling))
    owned_head = _git(f.owned_root, "rev-parse", "HEAD")
    calls = []
    original = tasks._resolve_task_owned

    def counted(*args, **kwargs):
        fact = original(*args, **kwargs)
        calls.append(fact)
        return fact

    monkeypatch.setattr(tasks, "_resolve_task_owned", counted)
    result = invoke(f, explicit=explicit, auto=auto)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mapped"]["WP01"] == ["FR-001"]
    assert len(calls) == 1 and calls[0] is not None
    meta, _ = read_wp_frontmatter(next((f.mission_dir / "tasks").glob("WP01*.md")))
    assert meta.requirement_refs == ["FR-001"]
    assert (snapshot(f.repository_root), snapshot(f.sibling)) == before
    if auto:
        assert data["committed"] is True
        assert _git(f.owned_root, "rev-parse", "HEAD") != owned_head
        assert _git(f.owned_root, "status", "--porcelain") == ""
        assert data["commit_result"]["destination_ref"] == calls[0].write_branch
    else:
        assert data["committed"] is False
        assert _git(f.owned_root, "rev-parse", "HEAD") == owned_head


@pytest.mark.parametrize("replace", [False, True])
def test_tracker_reference_ignores_stale_primary(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, replace: bool):
    f = protected_mint
    stale = f.repository_root / "kitty-specs" / f.mission_slug
    shutil.copytree(f.mission_dir, stale)
    (stale / "spec.md").write_text("# stale\n\n## Functional Requirements\n\n- **FR-999**: foreign requirement\n")
    monkeypatch.chdir(f.owned_root)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    before = (snapshot(f.repository_root), snapshot(f.sibling))
    extra = ["--wp", "WP01", "--refs", "FR-001", "--tracker-ref", "#5878"]
    if replace:
        extra += ["--replace"]
    result = invoke(f, explicit=False, auto=True, extra=extra)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mapped"]["WP01"] == ["FR-001"]
    assert data["stale_repository_root_copy"] is not None
    assert "#5878" in (f.mission_dir / "status.events.jsonl").read_text()
    assert (snapshot(f.repository_root), snapshot(f.sibling)) == before
    assert _git(f.owned_root, "status", "--porcelain") == ""


@pytest.mark.parametrize("auto", [False, True])
def test_tracker_only_preserves_refs(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, auto: bool):
    f = protected_mint
    monkeypatch.chdir(f.owned_root)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    path = next((f.mission_dir / "tasks").glob("WP01*.md"))
    before = path.read_bytes()
    result = invoke(f, explicit=False, auto=auto, extra=["--wp", "WP01", "--tracker-ref", "#5878"])
    assert result.exit_code == 0, result.output
    assert path.read_bytes() == before
    assert "#5878" in (f.mission_dir / "status.events.jsonl").read_text()
    if auto:
        assert json.loads(result.output)["committed"] is True
        assert _git(f.owned_root, "status", "--porcelain") == ""


@pytest.mark.parametrize("bad_claim", ["wrong_branch", "primary", "nested", "detached"])
def test_invalid_owned_claim_refused_before_writes(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, bad_claim: str):
    f = protected_mint
    claim = f.owned_root
    if bad_claim == "wrong_branch":
        _git(f.owned_root, "checkout", "-qb", "codex/wrong")
    if bad_claim == "detached":
        _git(f.owned_root, "checkout", "--detach", "-q")
    if bad_claim == "primary":
        claim = f.repository_root
    if bad_claim == "nested":
        claim = f.mission_dir
    monkeypatch.chdir(f.sibling)
    before = tuple(snapshot(r) for r in (f.repository_root, f.owned_root, f.sibling))
    result = CliRunner().invoke(
        tasks.app, ["map-requirements", "--mission", f.mission_slug, "--owned-checkout", str(claim), "--wp", "WP01", "--refs", "FR-001", "--json"]
    )
    assert result.exit_code != 0
    assert json.loads(result.output)["error_code"].startswith(("OWNED_", "OWNERSHIP_"))
    assert tuple(snapshot(r) for r in (f.repository_root, f.owned_root, f.sibling)) == before


@pytest.mark.parametrize("foreign", ["path", "slug"])
def test_owned_annotation_refuses_foreign_mission(protected_mint: OwnedCheckouts, foreign: str):
    from specify_cli.core.owned_mission import resolve_owned_mission
    from specify_cli.status.emit import emit_inner_state_changed
    from specify_cli.status.models import WPInnerStateDelta

    f = protected_mint
    owned = resolve_owned_mission(f.repository_root, f.owned_root, f.mission_slug)
    before = tuple(snapshot(r) for r in (f.repository_root, f.owned_root, f.sibling))
    with pytest.raises(ValueError, match="validated mission"):
        emit_inner_state_changed(
            f.repository_root if foreign == "path" else f.mission_dir,
            "WP01",
            WPInnerStateDelta(tracker_refs=["#5878"]),
            actor="test",
            mission_slug="foreign" if foreign == "slug" else f.mission_slug,
            owned=owned,
        )
    assert tuple(snapshot(r) for r in (f.repository_root, f.owned_root, f.sibling)) == before
