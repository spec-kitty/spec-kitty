"""Issue-pinned regression for #702 — DERIVED command-skill projections regenerate on drift.

The `.agents/skills/spec-kitty.<command>/SKILL.md` command-skill projection (codex / vibe /
pi / letta) is declared ``authority=DERIVED``, ``git_class=IGNORED`` by the state contract
(`specify_cli.state.contract` — ``shared_skills_projection``): it is never committed and is
always safe to regenerate from the canonical render. Across two checkouts of one project the
tracked ``.kittify/command-skills-manifest.json`` and the ignored projection legitimately
disagree — an upgrade in checkout A rewrites the manifest hash while checkout B's ignored
bytes never travel — so checkout B's *untouched* generated output reads as a drifted user
edit.

Before the fix, the command-skill installer classified such a manifest-owned drift as
``consent_required`` ("Managed command content has drifted") and kept the stale bytes, so
`.agents/skills` stayed out of sync with the manifest after ``upgrade`` / ``sync`` / ``init``
(and ``install()`` raised ``InstallerError`` on the collision). This module exercises the two
real reconcile entry points — ``command_installer.install`` and the exact
``prepare_commands(..., prune=True)`` + ``apply_commands`` call the ``command_skills``
tool-surface provider makes for ``upgrade`` — and asserts the drifted *manifest-owned*
projection is regenerated to the canonical render while non-manifest / third-party paths stay
untouched.

RED before the fix (drift is kept / ``install`` raises); GREEN after
``command_installer._Plan.preserve`` regenerates drift for this DERIVED surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.command_installer import install, verify
from specify_cli.state import contract as state_contract
from specify_cli.tool_surface.operations import (
    ApplyConsent,
    AssessmentInputs,
    OperationRoot,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.regression]

_SHARED_ROOT_AGENTS = ("codex", "vibe")


def _write_config(repo_root: Path) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - codex\n    - vibe\n",
        encoding="utf-8",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _write_config(tmp_path)
    return tmp_path


def _skill_path(repo_root: Path, command: str) -> Path:
    return repo_root / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md"


def _introduce_drift(repo_root: Path, command: str) -> tuple[Path, bytes]:
    """Make a manifest-owned projection's on-disk bytes differ from the recorded hash and the
    current render (the cross-checkout / stale-build condition). Return (path, canonical bytes).
    """
    path = _skill_path(repo_root, command)
    canonical = path.read_bytes()
    path.write_bytes(canonical + b"\n<!-- stale output written by an older build in another checkout -->\n")
    assert path.read_bytes() != canonical
    return path, canonical


def _reconcile_via_provider_call(repo_root: Path, agents: tuple[str, ...]) -> tuple[object, object]:
    """Drive the EXACT installer call the command_skills tool-surface provider makes for
    ``upgrade`` — ``prepare_commands(..., prune=True)`` under automatic (non-overwrite)
    consent — then apply it. Returns (assessment, apply_result).
    """
    inputs = AssessmentInputs(
        OperationRoot("project", "project", repo_root.absolute()),
        consent=ApplyConsent(automatic=True),
    )
    assessment = command_installer.prepare_commands(inputs, agents, prune=True)
    result = command_installer.apply_commands(assessment, inputs.consent)
    return assessment, result


# ---------------------------------------------------------------------------
# Premise guard (C-003): the fix is justified by the state contract's class.
# ---------------------------------------------------------------------------


def test_702_shared_skills_projection_is_derived_and_ignored() -> None:
    surface = next(s for s in state_contract.STATE_SURFACES if s.name == "shared_skills_projection")
    assert surface.path_pattern == ".agents/skills/<skill_name>/"
    assert surface.authority is state_contract.AuthorityClass.DERIVED
    assert surface.git_class is state_contract.GitClass.IGNORED


# ---------------------------------------------------------------------------
# install() — the real install / `agent config sync` reconcile entry point.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent", _SHARED_ROOT_AGENTS)
def test_702_drifted_manifest_owned_projection_regenerates_on_install(repo: Path, agent: str) -> None:
    install(repo, agent)
    drift_path, canonical = _introduce_drift(repo, "plan")
    rel = drift_path.relative_to(repo).as_posix()

    # Pre-fix: install() raises InstallerError (the drift lands in consent_required /
    # unexpected_collision). Post-fix: it regenerates the derived projection.
    install(repo, agent)

    assert drift_path.read_bytes() == canonical, "drifted DERIVED projection must be regenerated"
    report = verify(repo)
    assert report.drift == [], f"no residual drift expected, got {report.drift}"
    entry = manifest_store.load(repo).find(rel)
    assert entry is not None and entry.content_hash == manifest_store.fingerprint(canonical)


def test_702_regeneration_is_idempotent(repo: Path) -> None:
    install(repo, "codex")
    drift_path, canonical = _introduce_drift(repo, "specify")

    install(repo, "codex")  # regenerate
    assert drift_path.read_bytes() == canonical
    mtime_after_fix = drift_path.stat().st_mtime_ns

    install(repo, "codex")  # second reconcile: clean, no rewrite
    assert drift_path.read_bytes() == canonical
    assert drift_path.stat().st_mtime_ns == mtime_after_fix, "clean reconcile must not rewrite the file"
    assert verify(repo).drift == []


def test_702_third_party_paths_preserved_during_regeneration(repo: Path) -> None:
    install(repo, "codex")
    drift_path, canonical = _introduce_drift(repo, "plan")

    # A user's own skill directory under .agents/skills/ (never manifest-owned, NFR-002).
    third_party = repo / ".agents" / "skills" / "my-custom-skill"
    third_party.mkdir(parents=True)
    (third_party / "SKILL.md").write_bytes(b"---\nname: my-custom-skill\n---\nmine\n")

    install(repo, "codex")

    assert drift_path.read_bytes() == canonical, "manifest-owned drift regenerated"
    assert (third_party / "SKILL.md").read_bytes() == b"---\nname: my-custom-skill\n---\nmine\n", (
        "third-party content must stay untouched while manifest-owned projections regenerate"
    )


# ---------------------------------------------------------------------------
# The exact provider reconcile call `upgrade` uses (automatic, non-overwrite consent).
# ---------------------------------------------------------------------------


def test_702_upgrade_reconcile_regenerates_without_consent(repo: Path) -> None:
    install(repo, "codex")
    drift_path, canonical = _introduce_drift(repo, "review")
    rel = drift_path.relative_to(repo).as_posix()

    assessment, result = _reconcile_via_provider_call(repo, ("codex",))

    states = {d.state for d in assessment.dispositions if d.path == rel}
    assert "consent_required" not in states, "a drifted DERIVED command-skill projection must not require consent on the upgrade reconcile"
    assert result.outcome == "applied"
    assert drift_path.read_bytes() == canonical
    assert verify(repo).drift == []


def test_702_in_sync_projection_is_not_rewritten(repo: Path) -> None:
    """Negative control: with no drift the reconcile is a pure no-op — the regenerate path
    only fires on genuine drift, so the fix is non-vacuous."""
    install(repo, "codex")
    path = _skill_path(repo, "plan")
    mtime_before = path.stat().st_mtime_ns

    _assessment, result = _reconcile_via_provider_call(repo, ("codex",))

    assert result.outcome in {"applied", "skipped"}
    assert path.stat().st_mtime_ns == mtime_before
    assert verify(repo).drift == []
