"""Explicit owned charter authoring keeps every write and staged path in P."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner
from ruamel.yaml import YAML

from specify_cli.cli.commands.charter import app
from tests.integration.test_explicit_checkout_commands import SLUG, checkouts as checkouts, git, snapshot

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def generate(owned, *, claim=None, handle=SLUG, explicit=True, alias=False):
    args = ["generate", "--force", "--no-from-interview", "--json", "--mission" if alias else "--mission-type", "software-dev"]
    if explicit:
        args += ["--owned-checkout", str(claim or owned), "--mission-handle", handle]
    return CliRunner().invoke(app, args)


@pytest.mark.parametrize("alias", [False, True])
def test_explicit_generation_stays_in_owned_checkout(checkouts, monkeypatch, alias):
    from specify_cli.core import checkout_ownership

    primary, owned, sibling = checkouts
    monkeypatch.chdir(sibling)
    (primary / "unrelated.txt").write_text("pending primary\n")
    (owned / "app.py").write_text("pending owned\n")
    git(owned, "add", "app.py")
    staged = git(owned, "diff", "--cached")
    before = snapshot(primary), snapshot(sibling)
    metadata = (owned / "kitty-specs" / SLUG / "meta.json").read_bytes()
    real_claim = checkout_ownership.resolve_ownership_claim
    claims = []

    def count(*args, **kwargs):
        claims.append(args)
        return real_claim(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", count)
    result = generate(owned, alias=alias)
    assert result.exit_code == 0, result.output
    assert len(claims) == 1
    assert (snapshot(primary), snapshot(sibling)) == before
    assert (owned / "kitty-specs" / SLUG / "meta.json").read_bytes() == metadata
    assert staged in git(owned, "diff", "--cached")
    charter_path = owned / ".kittify/charter/charter.yaml"
    charter = YAML(typ="safe").load(charter_path.read_text())
    assert charter["catalog"]["mission"] == "software-dev"
    assert ".kittify/charter/charter.yaml" in git(owned, "diff", "--cached", "--name-only")
    charter["governance"]["custom_note"] = "preserve authored intent"
    charter["directives"] = {"custom_note": "preserve authored directive"}
    with charter_path.open("w") as stream:
        YAML().dump(charter, stream)
    repeated = generate(owned)
    assert repeated.exit_code == 0, repeated.output
    refreshed = YAML(typ="safe").load(charter_path.read_text())
    assert refreshed["governance"]["custom_note"] == "preserve authored intent"
    assert refreshed["directives"]["custom_note"] == "preserve authored directive"
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("bad", ["wrong_branch", "detached", "foreign", "root", "wrong_identity"])
def test_invalid_owned_generation_claim_writes_nothing(checkouts, tmp_path, monkeypatch, bad):
    primary, owned, sibling = checkouts
    claim, handle = owned, SLUG
    if bad == "wrong_branch":
        git(owned, "checkout", "-qb", "codex/wrong")
    elif bad == "detached":
        git(owned, "checkout", "--detach", "-q")
    elif bad == "foreign":
        claim = tmp_path / "foreign"
        claim.mkdir()
        git(claim, "init", "-qb", "main")
    elif bad == "root":
        claim = primary
    else:
        handle = "foreign-01M1A999"
    monkeypatch.chdir(sibling)
    before = tuple(snapshot(root) for root in checkouts)
    result = generate(owned, claim=claim, handle=handle)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"].startswith(("OWNED_", "OWNERSHIP_", "FEATURE_CONTEXT_"))
    assert tuple(snapshot(root) for root in checkouts) == before


def test_default_linked_generation_remains_refused(checkouts, monkeypatch):
    _, owned, _ = checkouts
    monkeypatch.chdir(owned)
    before = tuple(snapshot(root) for root in checkouts)
    result = generate(owned, explicit=False)
    assert result.exit_code == 1
    assert "linked git worktree" in result.output
    assert tuple(snapshot(root) for root in checkouts) == before


@pytest.mark.parametrize("destination", ["charter_dir", "charter_yaml", "config", "gitignore", "library", "pointer_escape", "pointer_symlink"])
def test_owned_generation_destination_refuses_before_writes(checkouts, tmp_path, monkeypatch, destination):
    _, owned, sibling = checkouts
    foreign = tmp_path / "foreign-destination"
    foreign.mkdir()
    (foreign / "file").write_text("agents: {available: [codex]}\n")
    config = owned / ".kittify/config.yaml"
    if destination.startswith("pointer"):
        target = foreign / "file"
        if destination == "pointer_symlink":
            target = owned / "pointer.yaml"
            target.symlink_to(foreign / "file")
        config.write_text(config.read_text() + f"charter: {target}\n")
    else:
        relative = {
            "charter_dir": ".kittify/charter", "charter_yaml": ".kittify/charter/charter.yaml",
            "config": ".kittify/config.yaml", "gitignore": ".gitignore", "library": ".kittify/charter/library",
        }[destination]
        target = owned / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        target.symlink_to(foreign if destination in ("charter_dir", "library") else foreign / "file")
    monkeypatch.chdir(sibling)
    before = tuple(snapshot(root) for root in checkouts)
    result = generate(owned)
    assert result.exit_code == 1, result.output
    assert "symlink" in result.output or "outside" in result.output
    assert tuple(snapshot(root) for root in checkouts) == before
    assert (foreign / "file").read_text() == "agents: {available: [codex]}\n"


def test_mission_handle_requires_explicit_owned_checkout(checkouts, monkeypatch):
    primary, _, _ = checkouts
    monkeypatch.chdir(primary)
    before = tuple(snapshot(root) for root in checkouts)
    result = CliRunner().invoke(app, ["generate", "--no-from-interview", "--json", "--mission-handle", SLUG])
    assert result.exit_code == 1, result.output
    assert "--owned-checkout" in result.output
    assert tuple(snapshot(root) for root in checkouts) == before


@pytest.mark.parametrize("destination", ["charter_dir", "gitignore", "library"])
def test_nonregular_owned_destination_refuses_before_writes(checkouts, monkeypatch, destination):
    _, owned, sibling = checkouts
    path = owned / {"charter_dir": ".kittify/charter", "gitignore": ".gitignore", "library": ".kittify/charter/library"}[destination]
    path.parent.mkdir(parents=True, exist_ok=True)
    if destination == "gitignore":
        path.mkdir()
    else:
        path.write_text("preserve nonregular destination\n")
    monkeypatch.chdir(sibling)
    before = tuple(snapshot(root) for root in checkouts)
    result = generate(owned)
    assert result.exit_code == 1, result.output
    assert tuple(snapshot(root) for root in checkouts) == before
