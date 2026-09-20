"""WP03 capstone — projection-honesty e2e across BOTH seams (real objects).

This integration test proves the mission's honesty invariant end-to-end against
real product objects (no mocks of the repair machinery), spanning:

* **Seam A (#4782, SC-001/SC-004)** — a stale root-level orientation file
  (``GEMINI.md`` / ``LLXPRT.md``) with **no** harness command dir is refreshed by
  a single ``doctor tool-surfaces --fix`` pass, and every detected-stale surface
  is repaired (detect-applicable == repair-applicable — none silently skipped).
* **Seam B (#4776/#4777/#4134, SC-002/SC-003/SC-006)** — under the Windows
  directory-mode condition a single ``upgrade``/apply converges including the
  doctrine skills, with no phantom ``--dry-run`` repairs; on a POSIX host a
  genuinely wrong directory mode still refuses.
* **Honest failure (FR-009, SC-005)** — a selected, detected-stale surface that
  repair genuinely cannot write is reported ``failed`` naming the file, never
  swallowed to a silent ``skipped``/exit-0.

Seam A drives the real assembled ``run_tool_surfaces`` service (registry ->
providers -> plan builder -> status service -> repair service -> owning
provider). Seam B reuses the shared cold-owner harness that exercises the real
command + doctrine owners against a real project tree, toggling the canonical
patchable ``kernel.paths.is_windows`` host seam (never faking ``os.name``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import paths as kernel_paths
from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.operations import (
    ApplyConsent,
    AssessmentInputs,
    OperationRoot,
    OwnerApplyResult,
)
from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider
from specify_cli.tool_surface.service import run_tool_surfaces
from specify_cli.tool_surface.status import STATE_STALE, _surface_id

# Reuse the real cold-owner harness (real command + doctrine owners, real tree).
from tests.specify_cli.tool_surface.providers.test_managed_skills import (
    _shared_parent_case,
)

pytestmark = [pytest.mark.integration]

_ROOT_CONTEXT_HARNESSES: tuple[tuple[str, str], ...] = (
    ("gemini", "GEMINI.md"),
    ("llxprt", "LLXPRT.md"),
)
_STALE_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Seam A helpers
# ---------------------------------------------------------------------------


def _seed_stale_root_context(project: Path, context_file: str) -> None:
    """Write a canonical orientation block stamped at an outdated version."""
    block = SessionPresenceContent(
        version=_STALE_VERSION,
        project_slug="unknown",
        health="healthy",
        available_version=None,
    ).render()
    (project / context_file).write_text(block, encoding="utf-8")


def _seed_seam_a_project(tmp_path: Path, harnesses: tuple[tuple[str, str], ...]) -> tuple[Path, list[str]]:
    """Seed a project with stale root context files and NO harness command dirs."""
    project = tmp_path / "project"
    project.mkdir()
    tool_keys = [harness for harness, _ in harnesses]
    for _harness, context_file in harnesses:
        _seed_stale_root_context(project, context_file)
    (project / ".kittify").mkdir()
    (project / ".kittify" / "config.yaml").write_text(
        "agents:\n  available: [" + ", ".join(tool_keys) + "]\n",
        encoding="utf-8",
    )
    return project, tool_keys


# ---------------------------------------------------------------------------
# Seam B helpers
# ---------------------------------------------------------------------------


def _simulate_windows_dir_modes(monkeypatch: pytest.MonkeyPatch, *, windows: bool) -> None:
    """Force freshly-created directories to a mode the plan (0o755) cannot match.

    Directories created during ``apply`` land at ``0o700`` and ``chmod`` becomes a
    no-op, so the observed directory mode can never equal the planned ``0o755`` --
    exactly the #4776 precondition. Regular files still receive their exact mode
    (the installer chmods them by file descriptor, not via ``Path.chmod``).
    ``windows`` toggles the canonical host seam so the identical divergence can be
    exercised on either host.
    """
    real_mkdir = Path.mkdir

    def forced_mkdir(self: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        real_mkdir(self, mode=0o700, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: windows)
    monkeypatch.setattr(Path, "mkdir", forced_mkdir)
    monkeypatch.setattr(Path, "chmod", lambda self, mode, *, follow_symlinks=True: None)


def _apply_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    windows: bool,
) -> tuple[dict[str, Path], ManagedSkillsProvider, tuple[OwnerApplyResult, ...]]:
    """Compose + preflight + apply the real command/doctrine owners in one pass."""
    roots, _before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    _simulate_windows_dir_modes(monkeypatch, windows=windows)
    composition = provider.compose_installation(installation, commands)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        provisioning.apply()
        results = provider.apply_composition(composition, consent)
    return roots, provider, results


# ---------------------------------------------------------------------------
# Seam A — SC-001 (refresh) + SC-004 (detect == repair parity)
# ---------------------------------------------------------------------------


def test_seam_a_stale_root_context_refreshed_and_parity(tmp_path: Path) -> None:
    """SC-001/SC-004: stale GEMINI.md + LLXPRT.md with no harness dir refresh in one --fix.

    Every detected-stale root-level context surface is repaired (never silently
    skipped), so the set the detect path flags equals the set the repair path
    fixes -- detect-applicable == repair-applicable (parity).
    """
    project, tool_keys = _seed_seam_a_project(tmp_path, _ROOT_CONTEXT_HARNESSES)
    assert not (project / ".gemini").exists()
    assert not (project / ".llxprt").exists()

    # Detect: both root context files are observed STALE.
    detect = run_tool_surfaces(project, tool_keys, kinds=[ToolSurfaceKind.CONTEXT_FILE], fix=False)
    stale_ids = {_surface_id(s.instance) for s in detect.report.surfaces if s.state == STATE_STALE}
    assert stale_ids == {"gemini.context_file.GEMINI.md", "llxprt.context_file.LLXPRT.md"}

    # Repair: one --fix pass refreshes every detected-stale surface.
    outcome = run_tool_surfaces(project, tool_keys, kinds=[ToolSurfaceKind.CONTEXT_FILE], fix=True)
    assert outcome.repair is not None
    repaired = set(outcome.repair.repaired)

    # Parity (SC-004): detected-stale == repaired; nothing detected-stale is skipped.
    assert repaired == stale_ids, outcome.repair.to_json()
    assert not outcome.repair.failed, outcome.repair.failed
    assert stale_ids.isdisjoint(set(outcome.repair.skipped))

    # The harness command dirs are still absent -- writability judged by repo root.
    assert not (project / ".gemini").exists()
    assert not (project / ".llxprt").exists()

    # Converged: an immediate second detect reports no stale surface (NFR-001).
    after = run_tool_surfaces(project, tool_keys, kinds=[ToolSurfaceKind.CONTEXT_FILE], fix=False)
    assert all(s.state != STATE_STALE for s in after.report.surfaces), [(s.instance.owner, s.state) for s in after.report.surfaces]


# ---------------------------------------------------------------------------
# Seam B — SC-002 (Windows single-pass convergence incl. doctrine)
# ---------------------------------------------------------------------------


def test_seam_b_windows_single_pass_converges_including_doctrine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-002 (#4776/#4777): one Windows-simulated pass converges incl. doctrine skills.

    BOTH host-gated seams must accept a freshly-created shared parent whose only
    divergence is the host-unrepresentable POSIX mode: the managed-skills
    completion re-check AND the doctrine apply's command-parent receipt check.
    With both fixed, every owner applies/skips in a single pass, neither abort
    fires, and ``.agents/skills/*/SKILL.md`` doctrine skills actually land.
    """
    roots, _provider, results = _apply_once(tmp_path, monkeypatch, windows=True)

    assert results, results
    # Full single-pass convergence: no owner refused.
    assert all(r.outcome in {"applied", "skipped"} for r in results), results
    command_result = next(r for r in results if r.owner_key == "command_skills")
    assert command_result.outcome == "applied", results

    # Neither host-unaware gate aborted (managed_skills:179 / installer:498).
    messages = [d.message for r in results for d in r.diagnostics]
    assert not any("Completed command output changed" in m for m in messages), messages
    assert not any("Invalid command-created skill parent" in m for m in messages), messages

    # Doctrine skills actually landed on disk under the shared root (SC-002).
    doctrine_files = list((roots["project"] / ".agents/skills").glob("*/SKILL.md"))
    assert doctrine_files, f"doctrine skills did not apply; tree={list((roots['project'] / '.agents/skills').iterdir())}"


# ---------------------------------------------------------------------------
# Seam B — SC-003 (no phantom dry-run repairs after convergence)
# ---------------------------------------------------------------------------


def test_seam_b_no_phantom_dry_run_repairs_after_convergence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003 (#4777): a fresh command preparation over the written tree plans nothing.

    ``upgrade --dry-run`` forecasts what a fresh assessment would apply. A
    freshly-created ``.agents/skills`` at a non-0o755 mode must NOT re-plan a
    ``chmod`` (nor a manifest rewrite for a wall-clock ``installed_at``), so a
    second/dry-run command preparation over the converged tree plans zero effects.
    """
    from specify_cli.skills.command_installer import prepare_commands

    roots, _provider, results = _apply_once(tmp_path, monkeypatch, windows=True)
    command_result = next(r for r in results if r.owner_key == "command_skills")
    assert command_result.outcome == "applied", results

    root = OperationRoot("project", "project", roots["project"])
    ordinary = AssessmentInputs(root, consent=ApplyConsent(automatic=True))
    next_commands = prepare_commands(ordinary, ("codex",), prune=True)

    # Zero re-planned command effects: no phantom chmod, no installed_at churn.
    assert next_commands.effects == (), next_commands.effects


# ---------------------------------------------------------------------------
# Seam B — SC-006 (POSIX correctness preserved: wrong dir mode still refuses)
# ---------------------------------------------------------------------------


def test_seam_b_posix_wrong_dir_mode_still_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-006 (NFR-003): the same divergence on a POSIX host still refuses.

    The relaxation is host-gated: with ``is_windows()`` False a directory-mode
    divergence is genuine drift and the completion re-check must refuse -- it
    never converges by weakening POSIX correctness.
    """
    roots, _before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    # POSIX host, but force freshly-created directories to a wrong (0o700) mode.
    _simulate_windows_dir_modes(monkeypatch, windows=False)

    composition = provider.compose_installation(installation, commands)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        provisioning.apply()
        results = provider.apply_composition(composition, consent)

    assert any(r.outcome == "precondition_changed" for r in results), results
    assert any(d.code == "shared_parent_changed" for r in results for d in r.diagnostics), results


# ---------------------------------------------------------------------------
# Honest failure — FR-009 / SC-005 (T013)
# ---------------------------------------------------------------------------


def test_honest_failure_names_file_never_silent_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-009/SC-005: a selected+stale surface repair cannot write -> failed, naming the file.

    The surface is genuinely detected stale and selected, but the leaf write
    raises (simulated unwritability). The honest contract: it is reported
    ``failed`` (naming the offending file), never dispositioned into a silent
    ``skipped``/exit-0, and it is not counted as repaired.
    """
    project, tool_keys = _seed_seam_a_project(tmp_path, (("gemini", "GEMINI.md"),))

    detect = run_tool_surfaces(project, tool_keys, kinds=[ToolSurfaceKind.CONTEXT_FILE], fix=False)
    stale_ids = {_surface_id(s.instance) for s in detect.report.surfaces if s.state == STATE_STALE}
    assert stale_ids == {"gemini.context_file.GEMINI.md"}

    def _unwritable(self: MarkdownRulesWriter, root: Path, member: object) -> None:
        raise OSError("simulated read-only filesystem: cannot write GEMINI.md")

    monkeypatch.setattr(MarkdownRulesWriter, "apply_prepared", _unwritable)

    outcome = run_tool_surfaces(project, tool_keys, kinds=[ToolSurfaceKind.CONTEXT_FILE], fix=True)
    assert outcome.repair is not None
    repair = outcome.repair

    # Honest failure: reported failed, naming the file; never a silent skip/exit-0.
    assert repair.failed, repair.to_json()
    assert any("GEMINI.md" in message for message in repair.failed), repair.failed
    assert "gemini.context_file.GEMINI.md" not in repair.repaired
    assert "gemini.context_file.GEMINI.md" not in repair.skipped
