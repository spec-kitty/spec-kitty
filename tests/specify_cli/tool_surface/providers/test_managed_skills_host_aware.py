"""Host-aware managed-skills completion re-check (Seam B, #4776 / #4777 / #4134).

The managed-skill completion re-check (``_recheck_command_completion``) asserts
that every command destination's observed state equals the plan. On Windows a
freshly-created ``.agents/skills`` directory cannot carry the planned POSIX
``mode`` of ``0o755`` (``os.chmod`` cannot represent those bits), so the plain
equality raised ``Completed command output changed`` (#4776) or re-planned the
``chmod`` forever, surfacing as a phantom ``upgrade --dry-run`` repair (#4777).

These tests pin the surgical relaxation: gated on the canonical patchable
``kernel.paths.is_windows`` seam, scoped to same-kind effects whose *only*
divergence from the plan is ``mode``. Originally directory-only, the
relaxation was generalized to file/symlink kinds under the same authority
(#4927, T005) so a converged Windows project's managed *files* also stop
phantom-repairing (see ``test_helper_windows_only_dir_mode`` below). POSIX
mode correctness is never weakened (NFR-003).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kernel import paths as kernel_paths
from specify_cli.skills.command_installer import windows_dir_mode_only_divergence
from specify_cli.tool_surface.operations import FileState, OwnerApplyResult
from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider

# The shared cold-owner harness already exercises the real command + doctrine
# owners against a real project tree; reuse it rather than rebuild the fixture.
from tests.specify_cli.tool_surface.providers.test_managed_skills import _shared_parent_case

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _simulate_windows_dir_modes(monkeypatch: pytest.MonkeyPatch, *, windows: bool) -> None:
    """Force freshly-created directories to a mode the plan (0o755) cannot match.

    Directories created during ``apply`` land at ``0o700`` and ``chmod`` is a
    no-op, so the observed directory mode can never equal the planned ``0o755``
    -- exactly the #4776 precondition. Regular files still receive their exact
    mode because the installer chmods them by file descriptor, not via
    ``Path.chmod``. ``windows`` toggles the host seam (``kernel.paths.is_windows``)
    so the same divergence can be tested on both hosts.
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
) -> tuple[dict[str, Path], ManagedSkillsProvider, tuple[OwnerApplyResult, ...]]:
    roots, _before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    _simulate_windows_dir_modes(monkeypatch, windows=True)
    composition = provider.compose_installation(installation, commands)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        provisioning.apply()
        results = provider.apply_composition(composition, consent)
    return roots, provider, results


def test_windows_single_pass_converges_including_doctrine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T007/T008 (FR-005/006, SC-002, #4776): one pass converges end-to-end on Windows.

    Under the Windows directory-mode condition BOTH host-gated seams must accept a
    freshly-created shared parent whose only divergence is the host-unrepresentable
    POSIX mode: the managed-skills completion re-check (managed_skills :179) AND the
    doctrine apply's command-parent receipt check (installer ``_command_parent_receipts``,
    ~:498). With both fixed, every owner applies/skips in a single pass, the #4776
    ``Completed command output changed`` abort is gone, and doctrine skills actually
    land on disk (before the twin-gate fix the doctrine apply returned
    ``precondition_changed`` at installer :498 -- doctrine skills never applied).
    """
    roots, _provider, results = _apply_once(tmp_path, monkeypatch)

    assert results, results
    # Full single-pass convergence: no owner refused.
    assert all(r.outcome in {"applied", "skipped"} for r in results), results
    command_result = next(r for r in results if r.owner_key == "command_skills")
    assert command_result.outcome == "applied", results
    # Neither gate aborted.
    assert not any("Completed command output changed" in d.message for r in results for d in r.diagnostics), results
    assert not any("Invalid command-created skill parent" in d.message for r in results for d in r.diagnostics), results
    # Doctrine skills actually landed on disk under the shared root (FR-006/SC-002).
    doctrine_files = list((roots["project"] / ".agents/skills").glob("*/SKILL.md"))
    assert doctrine_files, f"doctrine skills did not apply; tree={list((roots['project'] / '.agents/skills').iterdir())}"


def test_windows_command_surface_no_phantom_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T009 (FR-007/#4777): the command surface forecasts zero repairs once written.

    ``upgrade --dry-run`` forecasts the effects a fresh assessment would apply. A
    freshly-created ``.agents/skills`` at a non-0o755 mode must NOT re-plan a
    ``chmod`` (nor a manifest rewrite for a wall-clock ``installed_at``), so a
    fresh command preparation over the written tree plans zero command effects.
    """
    from specify_cli.skills.command_installer import prepare_commands
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    roots, _provider, results = _apply_once(tmp_path, monkeypatch)
    command_result = next(r for r in results if r.owner_key == "command_skills")
    assert command_result.outcome == "applied", results

    root = OperationRoot("project", "project", roots["project"])
    ordinary = AssessmentInputs(root, consent=ApplyConsent(automatic=True))
    next_commands = prepare_commands(ordinary, ("codex",), prune=True)

    # Zero re-planned command effects: no phantom chmod, no installed_at churn.
    assert next_commands.effects == (), next_commands.effects


def test_posix_wrong_dir_mode_still_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T012 (NFR-003): the same divergence on a POSIX host still refuses.

    The relaxation is host-gated: with ``is_windows()`` False the mode divergence
    is a genuine drift and the completion re-check must refuse, never converge.
    """
    roots, _before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    # POSIX host, but force freshly-created directories to a wrong mode.
    _simulate_windows_dir_modes(monkeypatch, windows=False)

    composition = provider.compose_installation(installation, commands)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        provisioning.apply()
        results = provider.apply_composition(composition, consent)

    # The command writer applies; the owners gated behind the completion re-check
    # are refused because the POSIX mode is genuine drift, not a host artifact.
    assert any(r.outcome == "precondition_changed" for r in results), results
    assert any(d.code == "shared_parent_changed" for r in results for d in r.diagnostics), results


def test_helper_is_dir_scoped_and_host_gated() -> None:
    """T012 (NFR-003): the gate never relaxes on POSIX, regardless of kind."""
    dir_755 = FileState("directory", mode=0o755)
    dir_700 = FileState("directory", mode=0o700)
    file_644 = FileState("file", sha256="a" * 64, mode=0o644)
    file_600 = FileState("file", sha256="a" * 64, mode=0o600)

    # On POSIX (the real test host, is_windows False) nothing is ever excused --
    # for a directory OR a file. Pinning the file kind here keeps FR-007 (a
    # genuine mode divergence on a real POSIX host still repairs) regression-proof
    # rather than implied only by the unconditional is_windows early return.
    assert windows_dir_mode_only_divergence(dir_700, dir_755) is False
    assert windows_dir_mode_only_divergence(file_600, file_644) is False


def test_helper_windows_only_dir_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """T005/T007/T012 (FR-007/NFR-003): under Windows, mode-only divergence is excused
    for directory, file, and symlink kinds alike -- but a kind mismatch or an
    additional (non-mode) divergence is still refused.
    """
    dir_755 = FileState("directory", mode=0o755)
    dir_700 = FileState("directory", mode=0o700)
    file_644 = FileState("file", sha256="a" * 64, mode=0o644)
    file_600 = FileState("file", sha256="a" * 64, mode=0o600)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    # Directory diverging only by mode: excused.
    assert windows_dir_mode_only_divergence(dir_700, dir_755) is True
    # T005 (#4927): file modes are relaxed too, once the sole divergence is
    # the host-unrepresentable POSIX mode (the contract changed here --
    # delete-the-assertion-not-the-test, DIRECTIVE_041).
    assert windows_dir_mode_only_divergence(file_600, file_644) is True
    # A kind mismatch (dir vs file) is not a mode-only divergence.
    assert windows_dir_mode_only_divergence(dir_700, file_644) is False
    # A directory that also diverges by content-kind is not mode-only.
    assert windows_dir_mode_only_divergence(dir_755, FileState("absent")) is False


def test_helper_calls_is_windows_through_module_attribute(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host check resolves ``kernel.paths.is_windows`` at call time.

    Monkeypatching the module attribute (never faking ``os.name``) must flip the
    gate, proving the seam is patchable per the canonical contract.
    """
    dir_700 = FileState("directory", mode=0o700)
    dir_755 = FileState("directory", mode=0o755)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    assert windows_dir_mode_only_divergence(dir_700, dir_755) is False
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    assert windows_dir_mode_only_divergence(dir_700, dir_755) is True

    # Guard: no test in this module fakes os.name (that flips pathlib on Windows).
    assert os.name in {"posix", "nt"}
