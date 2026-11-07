"""Focused per-helper tests for ``_sparse_checkout_doctor`` (WP08, #2059).

Cover the decomposed helpers: repo-root resolution, clean-state emission,
consent prompt (incl. EOF), per-path result rendering, the dirty-tree refusal,
and the entrypoint's detection / CI-refusal / no-state exit contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands import _sparse_checkout_doctor as sc

pytestmark = [pytest.mark.fast]


# --- _resolve_repo_root ------------------------------------------------------


def test_resolve_repo_root_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc, "locate_project_root", lambda: None)
    with pytest.raises(typer.Exit) as exc:
        sc._resolve_repo_root()
    assert exc.value.exit_code == 1


def test_resolve_repo_root_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> Path:
        raise RuntimeError("x")

    monkeypatch.setattr(sc, "locate_project_root", _boom)
    with pytest.raises(typer.Exit) as exc:
        sc._resolve_repo_root()
    assert exc.value.exit_code == 1


def test_resolve_repo_root_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sc, "locate_project_root", lambda: tmp_path)
    assert sc._resolve_repo_root() == tmp_path


# --- _emit_clean_state -------------------------------------------------------


def test_emit_clean_state_fix() -> None:
    with pytest.raises(typer.Exit) as exc:
        sc._emit_clean_state(fix=True)
    assert exc.value.exit_code == 0


def test_emit_clean_state_no_fix() -> None:
    with pytest.raises(typer.Exit) as exc:
        sc._emit_clean_state(fix=False)
    assert exc.value.exit_code == 0


# --- _prompt_consent ---------------------------------------------------------


def test_prompt_consent_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *_a: "Y")
    assert sc._prompt_consent() is True


def test_prompt_consent_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *_a: "n")
    assert sc._prompt_consent() is False


def test_prompt_consent_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    def _eof(*_a: Any) -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", _eof)
    assert sc._prompt_consent() is False


# --- _render_remediation_results / _emit_dirty_refusal -----------------------


@dataclass
class _Result:
    path: str = "/nonexistent/x"
    success: bool = True
    steps_completed: list[str] = field(default_factory=lambda: ["a", "b"])
    error_detail: str | None = None
    error_step: str | None = None
    dirty_before_remediation: bool = False


def test_render_results_success() -> None:
    assert sc._render_remediation_results([_Result(success=True)]) is False


def test_render_results_failure() -> None:
    failed = _Result(success=False, error_detail="bad", error_step="step1")
    assert sc._render_remediation_results([failed]) is True


def test_emit_dirty_refusal() -> None:
    with pytest.raises(typer.Exit) as exc:
        sc._emit_dirty_refusal([_Result(dirty_before_remediation=True)])
    assert exc.value.exit_code == 1


# --- run_sparse_checkout entrypoint ------------------------------------------


@dataclass
class _Primary:
    is_active: bool = True
    path: str = "/repo"
    pattern_file_present: bool = False
    pattern_file_path: str | None = None
    pattern_line_count: int = 0


@dataclass
class _Worktree:
    path: str = "/repo/.worktrees/m-lane-a"
    is_blocking: bool = True


@dataclass
class _ScanReport:
    any_blocking: bool
    primary: _Primary = field(default_factory=_Primary)
    worktrees: list[_Worktree] = field(default_factory=list)


def test_run_sparse_checkout_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sc, "locate_project_root", lambda: tmp_path)
    import specify_cli.git.sparse_checkout as scan_mod

    monkeypatch.setattr(scan_mod, "scan_repo", lambda _r: _ScanReport(any_blocking=False))
    with pytest.raises(typer.Exit) as exc:
        sc.run_sparse_checkout(fix=False)
    assert exc.value.exit_code == 0


def test_run_sparse_checkout_detection_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sc, "locate_project_root", lambda: tmp_path)
    import specify_cli.git.sparse_checkout as scan_mod

    report = _ScanReport(any_blocking=True, worktrees=[_Worktree()])
    monkeypatch.setattr(scan_mod, "scan_repo", lambda _r: report)
    # Render finding asserts the report is a real SparseCheckoutScanReport, so
    # stub the renderer to isolate the exit-code contract.
    monkeypatch.setattr(sc, "_render_sparse_finding", lambda _r: None)
    with pytest.raises(typer.Exit) as exc:
        sc.run_sparse_checkout(fix=False)
    assert exc.value.exit_code == 1


def test_run_sparse_checkout_ci_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sc, "locate_project_root", lambda: tmp_path)
    import specify_cli.git.sparse_checkout as scan_mod

    report = _ScanReport(any_blocking=True)
    monkeypatch.setattr(scan_mod, "scan_repo", lambda _r: report)
    monkeypatch.setattr(sc, "_is_interactive_environment", lambda: False)
    with pytest.raises(typer.Exit) as exc:
        sc.run_sparse_checkout(fix=True)
    assert exc.value.exit_code == 1
    assert "requires an interactive terminal" in capsys.readouterr().out


def test_sparse_checkout_doctor_does_not_import_doctor() -> None:
    import ast

    source = Path(sc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    relative: list[str] = []
    absolute: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                relative.append(node.module or "")
            elif node.module:
                absolute.append(node.module)
        elif isinstance(node, ast.Import):
            absolute.extend(alias.name for alias in node.names)
    assert "specify_cli.cli.commands.doctor" not in absolute
    assert set(relative) <= {"_doctor_shared"}


def test_run_sparse_checkout_fix_scans_after_the_lane_exclusion_fix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#7276: the scan reads each lane as --fix's exclusion step left it, never as it was.

    A scan taken first would hand the remediation a stale verdict and let it
    disable a managed lane (and its operator patterns).
    """
    monkeypatch.setattr(sc, "locate_project_root", lambda: tmp_path)
    import specify_cli.git.sparse_checkout as scan_mod

    order: list[str] = []

    def _lane_findings(_root: Path, fix: bool) -> bool:
        order.append(f"lane_findings(fix={fix})")
        return False

    def _scan(_root: Path) -> _ScanReport:
        order.append("scan")
        return _ScanReport(any_blocking=False)

    monkeypatch.setattr(sc, "_report_lane_findings", _lane_findings)
    monkeypatch.setattr(scan_mod, "scan_repo", _scan)
    with pytest.raises(typer.Exit):
        sc.run_sparse_checkout(fix=True)
    assert order == ["lane_findings(fix=True)", "scan"]
