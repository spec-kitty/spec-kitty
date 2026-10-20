"""Issue-pinned regression for #702 — DERIVED command-skill projections regenerate on drift.

The `.agents/skills/spec-kitty-<command>/SKILL.md` command-skill projection (codex / vibe /
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

import dataclasses
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
    return repo_root / ".agents" / "skills" / f"spec-kitty-{command}" / "SKILL.md"


def _introduce_drift(repo_root: Path, command: str) -> tuple[Path, bytes]:
    """Make a manifest-owned projection's on-disk bytes differ from the recorded hash and the
    current render (the cross-checkout / stale-build condition). Return (path, canonical bytes).
    """
    path = _skill_path(repo_root, command)
    canonical = path.read_bytes()
    path.write_bytes(canonical + b"\n<!-- stale output written by an older build in another checkout -->\n")
    assert path.read_bytes() != canonical
    return path, canonical


def _reconcile_via_provider_call(
    repo_root: Path,
    agents: tuple[str, ...],
    *,
    overwrite_paths: tuple[str, ...] = (),
) -> tuple[object, object]:
    """Drive the EXACT installer call the command_skills tool-surface provider makes for
    ``upgrade`` — ``prepare_commands(..., prune=True)`` under automatic consent — then apply
    it. ``overwrite_paths`` supplies explicit exact-path operator consent (the fall-through
    path revived by #6155). Returns (assessment, apply_result).
    """
    inputs = AssessmentInputs(
        OperationRoot("project", "project", repo_root.absolute()),
        consent=ApplyConsent(automatic=True, overwrite_paths=overwrite_paths),
    )
    assessment = command_installer.prepare_commands(inputs, agents, prune=True)
    result = command_installer.apply_commands(assessment, inputs.consent)
    return assessment, result


def _surfaces_with_shared_skills_tracked() -> tuple[object, ...]:
    """A ``STATE_SURFACES`` copy where ``shared_skills_projection`` is TRACKED, not git-IGNORED.

    Monkeypatching this onto ``state_contract.STATE_SURFACES`` makes the runtime
    DERIVED/IGNORED gate (#6155, item 2) read the surface as *not* regenerable, so the
    installer must fall through to the consent branch instead of clobbering drift.
    """
    return tuple(
        dataclasses.replace(surface, git_class=state_contract.GitClass.TRACKED) if surface.name == "shared_skills_projection" else surface
        for surface in state_contract.STATE_SURFACES
    )


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


def test_702_unowned_file_at_canonical_path_is_not_regenerated(repo: Path) -> None:
    """The boundary of the fix: only manifest-owned projections regenerate.

    An unowned file at a canonical ``spec-kitty-<cmd>`` path is skipped as a collision
    (FR-019, #6475) and never rewritten, while the drifted owned projection regenerates.
    """
    install(repo, "codex")
    drift_path, _canonical = _introduce_drift(repo, "plan")
    drifted_bytes = drift_path.read_bytes()
    unowned = repo / ".agents" / "skills" / "spec-kitty-status" / "SKILL.md"
    unowned_rel = unowned.relative_to(repo).as_posix()
    manifest = manifest_store.load(repo)
    manifest.remove_path(unowned_rel)
    manifest_store.save(repo, manifest)
    unowned.write_bytes(b"mine")

    report = install(repo, "codex")

    assert report.collisions == [unowned_rel]
    assert unowned.read_bytes() == b"mine"
    assert manifest_store.load(repo).find(unowned_rel) is None
    assert drift_path.read_bytes() != drifted_bytes  # the owned projection still regenerates


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


# ===========================================================================
# #6155 item 2 — the regenerate reads the DERIVED/IGNORED class at runtime.
# ===========================================================================


def test_6155_non_derived_class_keeps_drift_as_consent_required(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED on the merged-#6113 base: the regenerate was unconditional, so a monkeypatched
    non-git-IGNORED class still clobbered drift. After #6155 the installer reads
    ``shared_skills_projection`` from the state contract and, when it is not DERIVED/IGNORED,
    falls through to the pre-#6113 ``consent_required`` behaviour (the drift is kept)."""
    install(repo, "codex")
    drift_path, _canonical = _introduce_drift(repo, "review")
    rel = drift_path.relative_to(repo).as_posix()
    drifted_bytes = drift_path.read_bytes()

    monkeypatch.setattr(state_contract, "STATE_SURFACES", _surfaces_with_shared_skills_tracked())
    assessment, _result = _reconcile_via_provider_call(repo, ("codex",))

    states = {d.state for d in assessment.dispositions if d.path == rel}
    assert "consent_required" in states, f"non-DERIVED class must keep drift pending consent, got {states}"
    kinds = {c.report_kind for c in assessment.prepared.commands if c.path == rel}
    assert "regenerated" not in kinds, f"the gate is off, so nothing may be reported regenerated, got {kinds}"
    assert drift_path.read_bytes() == drifted_bytes, "drift must be kept, not clobbered, when the class is not DERIVED/IGNORED"


def _surfaces_without_shared_skills() -> tuple[object, ...]:
    """A ``STATE_SURFACES`` copy with no ``shared_skills_projection`` entry at all."""
    return tuple(surface for surface in state_contract.STATE_SURFACES if surface.name != "shared_skills_projection")


def test_6155_missing_surface_fails_closed_to_consent(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed: when ``shared_skills_projection`` is absent from ``STATE_SURFACES`` the gate
    reads as off, so a drifted projection falls through to ``consent_required`` and is kept."""
    install(repo, "codex")
    drift_path, _canonical = _introduce_drift(repo, "review")
    rel = drift_path.relative_to(repo).as_posix()
    drifted_bytes = drift_path.read_bytes()

    monkeypatch.setattr(state_contract, "STATE_SURFACES", _surfaces_without_shared_skills())
    assessment, _result = _reconcile_via_provider_call(repo, ("codex",))

    states = {d.state for d in assessment.dispositions if d.path == rel}
    assert "consent_required" in states, f"a missing surface must fail closed to consent, got {states}"
    kinds = {c.report_kind for c in assessment.prepared.commands if c.path == rel}
    assert "regenerated" not in kinds
    assert drift_path.read_bytes() == drifted_bytes


def test_6155_real_derived_class_regenerates_drift(repo: Path) -> None:
    """Under the REAL DERIVED/IGNORED class the drifted projection is still regenerated and the
    per-path ``regenerated`` report_kind is recorded on its PreparedCommand (US2 scenario 1;
    US1 signal origin)."""
    install(repo, "codex")
    drift_path, canonical = _introduce_drift(repo, "review")
    rel = drift_path.relative_to(repo).as_posix()

    assessment, result = _reconcile_via_provider_call(repo, ("codex",))

    kinds = {c.report_kind for c in assessment.prepared.commands if c.path == rel}
    assert "regenerated" in kinds, f"the real DERIVED/IGNORED class must regenerate drift, got {kinds}"
    states = {d.state for d in assessment.dispositions if d.path == rel}
    assert "consent_required" not in states
    assert result.outcome == "applied"
    assert drift_path.read_bytes() == canonical
    assert verify(repo).drift == []


def test_6155_overwrite_consent_overwrites_on_non_derived_fall_through(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: on the non-DERIVED fall-through the revived ``overwrite_paths`` check is live —
    explicit exact-path operator consent overwrites the drift rather than keeping it."""
    install(repo, "codex")
    drift_path, canonical = _introduce_drift(repo, "plan")
    rel = drift_path.relative_to(repo).as_posix()

    monkeypatch.setattr(state_contract, "STATE_SURFACES", _surfaces_with_shared_skills_tracked())
    assessment, result = _reconcile_via_provider_call(repo, ("codex",), overwrite_paths=(rel,))

    states = {d.state for d in assessment.dispositions if d.path == rel}
    assert "consent_required" not in states, "explicit overwrite consent must be honoured on the fall-through path"
    assert result.outcome == "applied"
    assert drift_path.read_bytes() == canonical


# ===========================================================================
# #6155 item 1 — install()-leg report names each regenerated path.
# ===========================================================================


@pytest.mark.parametrize("agent", _SHARED_ROOT_AGENTS)
def test_6155_install_report_names_regenerated_path(repo: Path, agent: str) -> None:
    """RED on the base (``InstallReport`` has no ``regenerated`` field / the regenerate was
    silently counted as ``added``). After #6155 a drifted projection regenerated by ``install``
    (the init / ``agent config sync`` leg) is named under ``report.regenerated`` exactly once
    and is NOT double-counted in ``report.added``."""
    install(repo, agent)
    drift_path, canonical = _introduce_drift(repo, "plan")
    rel = drift_path.relative_to(repo).as_posix()

    report = install(repo, agent)

    assert report.regenerated == [rel], f"regenerated path named once, got {report.regenerated}"
    assert rel not in report.added, "a regenerated path must not also be counted as added"
    assert drift_path.read_bytes() == canonical


# ===========================================================================
# #6155 item 3 — prune a retired command's drifted projection.
# ===========================================================================

_RETIRED_REL = ".agents/skills/spec-kitty.legacy-opener/SKILL.md"
_RETIRED_HASH = "a" * 64


def _record_retired_entry(repo_root: Path, rel: str, *, agents: tuple[str, ...] = ("codex",)) -> None:
    manifest = manifest_store.load(repo_root)
    manifest.upsert(
        manifest_store.ManifestEntry(
            path=rel,
            content_hash=_RETIRED_HASH,
            agents=agents,
            installed_at="2024-01-01T00:00:00+00:00",
            spec_kitty_version="3.2.0a4",
        )
    )
    manifest_store.save(repo_root, manifest)


def test_6155_retired_command_drifted_projection_is_pruned(repo: Path) -> None:
    """RED on the base: ``remove_entry`` reported a drifted manifest-owned projection as
    ``consent_required``, so ``prune_stale`` raised ``file_mutation_detected`` and kept the
    stale file. After #6155 the same DERIVED/IGNORED gate prunes the file AND its manifest
    entry (US3 scenario 1)."""
    install(repo, "codex")
    retired = repo / ".agents" / "skills" / "spec-kitty.legacy-opener" / "SKILL.md"
    retired.parent.mkdir(parents=True, exist_ok=True)
    retired.write_bytes(b"# stale retired-command output from another checkout\n")
    assert manifest_store.fingerprint_file(retired) != _RETIRED_HASH  # drifted vs recorded hash
    _record_retired_entry(repo, _RETIRED_REL)

    pruned = command_installer.prune_stale(repo)

    assert _RETIRED_REL in pruned
    assert not retired.exists(), "the drifted retired projection must be removed"
    assert manifest_store.load(repo).find(_RETIRED_REL) is None, "its manifest entry must be dropped"


def test_6155_prune_preserves_unowned_spec_kitty_path(repo: Path) -> None:
    """US3 scenario 2 / NFR-002: an unowned (non-manifest) file at a ``spec-kitty.*`` path is
    structurally never reached by ``remove_entry`` and is preserved by the prune."""
    install(repo, "codex")
    unowned = repo / ".agents" / "skills" / "spec-kitty.my-custom" / "SKILL.md"
    unowned.parent.mkdir(parents=True, exist_ok=True)
    unowned.write_bytes(b"mine\n")

    command_installer.prune_stale(repo)

    assert unowned.read_bytes() == b"mine\n"


def test_6155_prune_still_refuses_directory_at_projection_path(repo: Path) -> None:
    """US3 scenario 3: a DIRECTORY at the projection path is still refused (unchanged); only a
    drifted regular FILE is pruned under the gate."""
    install(repo, "codex")
    dir_at_path = repo / ".agents" / "skills" / "spec-kitty.legacy-dir" / "SKILL.md"
    dir_at_path.mkdir(parents=True, exist_ok=True)
    _record_retired_entry(repo, ".agents/skills/spec-kitty.legacy-dir/SKILL.md")

    with pytest.raises(command_installer.InstallerError, match="file_mutation_detected"):
        command_installer.prune_stale(repo)

    assert dir_at_path.is_dir(), "a directory at the projection path must be refused, never removed"


def test_6155_prune_refuses_retired_drift_when_gate_is_off(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The retired-command prune rides the SAME DERIVED/IGNORED gate: with the surface read as
    TRACKED the drifted retired projection is refused (``file_mutation_detected``) and survives.
    Kills the ``not (retired and self._regenerate_derived)`` -> ``not retired`` mutant."""
    install(repo, "codex")
    retired = repo / ".agents" / "skills" / "spec-kitty.legacy-opener" / "SKILL.md"
    retired.parent.mkdir(parents=True, exist_ok=True)
    stale = b"# stale retired-command output from another checkout\n"
    retired.write_bytes(stale)
    _record_retired_entry(repo, _RETIRED_REL)

    monkeypatch.setattr(state_contract, "STATE_SURFACES", _surfaces_with_shared_skills_tracked())
    with pytest.raises(command_installer.InstallerError, match="file_mutation_detected"):
        command_installer.prune_stale(repo)

    assert retired.read_bytes() == stale, "the drifted retired projection must survive while the gate is off"
    assert manifest_store.load(repo).find(_RETIRED_REL) is not None, "its manifest entry must be kept"


def test_6155_retired_drift_with_other_owners_keeps_entry_and_file(repo: Path) -> None:
    """A retired drifted entry still owned by another agent is narrowed, not pruned: the entry is
    kept with the remaining owner and the file is left byte-unchanged."""
    install(repo, "codex")
    retired = repo / ".agents" / "skills" / "spec-kitty.legacy-opener" / "SKILL.md"
    retired.parent.mkdir(parents=True, exist_ok=True)
    stale = b"# stale retired-command output from another checkout\n"
    retired.write_bytes(stale)
    _record_retired_entry(repo, _RETIRED_REL, agents=("codex", "vibe"))

    assessment, result = _reconcile_via_provider_call(repo, ("codex",))

    kinds = {c.report_kind for c in assessment.prepared.commands if c.path == _RETIRED_REL}
    assert kinds == {"kept"}, kinds
    assert result.outcome == "applied"
    assert retired.read_bytes() == stale, "a retired projection another owner still holds must be left alone"
    entry = manifest_store.load(repo).find(_RETIRED_REL)
    assert entry is not None and entry.agents == ("vibe",), entry
