"""Red-first twin for the default-on charter preflight safe-heal (#6366, WP01).

A fresh checkout whose synthesis manifest ``bundle_content_hash`` lags a clean
recompute -- while every manifest artifact still verifies -- must not terminally
block ``next``/``implement``. A genuinely inconsistent manifest must still block.

Contracts: C-HEAL-1 (heal + non-vacuity control), C-HEAL-2 (query is read-only),
C-HEAL-3 (advancing consumer unblocks), C-TWIN-1.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
from charter.bundle import compute_bundle_content_hash
from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.charter_runtime.preflight import run_charter_preflight
from specify_cli.charter_runtime.preflight.hook import (
    run_preflight_or_abort,
    run_preflight_warn_only,
)

from .test_boundary_heal import _git_commit_all, _seed_synthesized_and_gone_stale

pytestmark = [pytest.mark.git_repo]


@pytest.fixture
def stale_consistent_repo(tmp_path: Path) -> Path:
    """Stamp lags the recompute, but every manifest artifact verifies."""
    _seed_synthesized_and_gone_stale(tmp_path)
    return tmp_path


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Fail the heavy generate/synthesize chain loudly if the light heal shells out."""
    real_run = subprocess.run
    seen: list[list[str]] = []

    def guarded(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            passthrough: subprocess.CompletedProcess[str] = real_run(cmd, **kwargs)
            return passthrough
        seen.append(list(cmd))
        raise AssertionError(f"safe-heal must not spawn a subprocess: {cmd}")

    monkeypatch.setattr(subprocess, "run", guarded)
    return seen


def _manifest_bytes(repo: Path) -> bytes:
    data: bytes = (repo / MANIFEST_PATH).read_bytes()
    return data


def _break_an_artifact(repo: Path) -> None:
    manifest = load_yaml(repo / MANIFEST_PATH)
    artifact = repo / manifest.artifacts[0].path
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")


def test_stale_stamp_with_consistent_artifacts_heals_without_auto_refresh(stale_consistent_repo: Path, no_subprocess: list[list[str]]) -> None:
    repo = stale_consistent_repo
    assert compute_freshness(repo).synthesized_drg.state == "stale"

    result = run_charter_preflight(repo, auto_refresh=False, allow_missing_charter=True, allow_heal=True)

    assert result.passed is True, result.blocked_reason
    assert no_subprocess == []
    manifest = load_yaml(repo / MANIFEST_PATH)
    assert manifest.bundle_content_hash == compute_bundle_content_hash(repo)
    assert compute_freshness(repo).synthesized_drg.state == "fresh"


def test_heal_is_idempotent(stale_consistent_repo: Path) -> None:
    repo = stale_consistent_repo
    run_charter_preflight(repo, allow_heal=True)
    after_first = _manifest_bytes(repo)
    second = run_charter_preflight(repo, allow_heal=True)
    assert second.passed is True
    assert _manifest_bytes(repo) == after_first


def test_heal_changes_only_bundle_hash_and_manifest_hash(stale_consistent_repo: Path) -> None:
    repo = stale_consistent_repo
    before = load_yaml(repo / MANIFEST_PATH).model_dump(mode="python")
    run_charter_preflight(repo, allow_heal=True)
    after = load_yaml(repo / MANIFEST_PATH).model_dump(mode="python")
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"bundle_content_hash", "manifest_hash"}


def test_heal_is_off_by_default(stale_consistent_repo: Path) -> None:
    repo = stale_consistent_repo
    before = _manifest_bytes(repo)
    result = run_charter_preflight(repo)
    assert result.passed is False
    assert _manifest_bytes(repo) == before


def test_positive_control_inconsistent_manifest_still_blocks(stale_consistent_repo: Path, no_subprocess: list[list[str]]) -> None:
    repo = stale_consistent_repo
    _break_an_artifact(repo)
    before = _manifest_bytes(repo)

    result = run_charter_preflight(repo, allow_heal=True)

    assert result.passed is False
    assert result.blocked_reason
    assert _manifest_bytes(repo) == before, "a genuine inconsistency must never be re-stamped"
    assert no_subprocess == []


def test_query_mode_does_not_mutate(stale_consistent_repo: Path) -> None:
    repo = stale_consistent_repo
    before = _manifest_bytes(repo)
    result = run_preflight_warn_only(repo, consumer="next")
    assert result.passed is False
    assert _manifest_bytes(repo) == before


def test_advancing_consumer_unblocks(stale_consistent_repo: Path) -> None:
    result = run_preflight_or_abort(stale_consistent_repo, consumer="next")
    assert result.passed is True
    assert compute_freshness(stale_consistent_repo).synthesized_drg.state == "fresh"


def _edit_catalog_section(repo: Path) -> None:
    """A SUBSTANTIVE (non-comment) ``catalog:``-section edit to ``charter.yaml``.

    Trips ``synthesized_drg`` stale the same way an authoring-only edit does,
    because the stamp is ``hash(charter.yaml)`` — but this touches a
    catalog-identity field, i.e. the "catalog-affecting" shape the #6366 review
    singled out, not a trailing comment.
    """
    charter_yaml = repo / ".kittify" / "charter" / "charter.yaml"
    text = charter_yaml.read_text(encoding="utf-8")
    assert "template_set: default" in text, "fixture charter.yaml lost its catalog.template_set anchor"
    charter_yaml.write_text(text.replace("template_set: default", "template_set: changed-after-synthesis"), encoding="utf-8")


def test_catalog_affecting_charter_edit_with_intact_artifacts_is_healed(stale_consistent_repo: Path, no_subprocess: list[list[str]]) -> None:
    """Accepted-boundary negative control for the #6366 review (finding #1).

    The read-path heal gates on manifest artifact integrity (``verify``), NOT on
    any classification of the ``charter.yaml`` edit. A substantive
    ``catalog:``-section edit whose committed derived artifacts still verify is
    therefore healed exactly like an authoring-only edit. Detecting a
    catalog-affecting hand-edit committed WITHOUT re-synthesis is out of the
    read-path heal's scope by design — it is the synthesize / write-side
    re-stamp path's responsibility — so this is the explicitly-accepted boundary,
    not a greenwash the heal is expected to catch.
    """
    repo = stale_consistent_repo
    _edit_catalog_section(repo)
    _git_commit_all(repo, "catalog-affecting charter.yaml edit")
    assert compute_freshness(repo).synthesized_drg.state == "stale"

    result = run_charter_preflight(repo, auto_refresh=False, allow_missing_charter=True, allow_heal=True)

    assert result.passed is True, result.blocked_reason
    assert no_subprocess == []
    assert compute_freshness(repo).synthesized_drg.state == "fresh"


def test_catalog_affecting_edit_does_not_bypass_the_artifact_integrity_gate(stale_consistent_repo: Path, no_subprocess: list[list[str]]) -> None:
    """The complement: a catalog-affecting edit must not let a GENUINE artifact
    inconsistency slip through the heal. With the catalog edit present AND an
    artifact tampered, ``verify`` fails and the heal still blocks without
    re-stamping — proving the integrity gate is unconditional, so the accepted
    boundary above does not widen into a greenwash of real corruption.
    """
    repo = stale_consistent_repo
    _edit_catalog_section(repo)
    _break_an_artifact(repo)
    before = _manifest_bytes(repo)

    result = run_charter_preflight(repo, allow_heal=True)

    assert result.passed is False
    assert result.blocked_reason
    assert _manifest_bytes(repo) == before, "a tampered artifact must never be re-stamped, even alongside a catalog edit"
    assert no_subprocess == []
