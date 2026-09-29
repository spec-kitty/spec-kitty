#!/usr/bin/env python3
"""NFR-003 compatibility-evidence latency micro-benchmark (WP08 / T037).

A standalone, in-process micro-benchmark (not a pytest suite, not a
performance suite) comparing ``finalize-tasks --validate-only``'s
requirement-mapping phase latency between the mission's merge-base with
``upstream/main`` ("base") and the mission's branch head ("head"), on a
generated 30-work-package fixture.

Two modes, mirroring ``corpus_scan.py``'s isolation model:

* **Driver** (default): builds the fixture once (identical for both sides,
  read-only for the whole run), runs one untimed pass-verdict pre-check per
  side, then 20 ABBA-interleaved rounds -- each round spawning one base
  worker and one head worker as SEPARATE subprocesses (``PYTHONPATH`` set to
  that side's ``src``, a fresh temp ``HOME``) -- and writes ``latency.json``
  plus ``latency.md`` to ``--out-dir``.
* **Worker** (``--worker --side base|head --mode check|bench --fixture-repo
  <path> --mission-slug <slug> --expected-src <side-src>``): runs the
  in-process Typer ``CliRunner`` invocation, times the requirement-mapping
  phase (``_validate_requirement_mapping`` + ``_read_spec_requirement_ids``)
  and the whole call, and prints one JSON object to stdout.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import _patch

_TRACKED_PACKAGES = ("specify_cli", "runtime", "charter", "kernel")
_NFR_003_PHASE_BUDGET_MS = 50.0
_CHARTER_TOTAL_BUDGET_MS = 2000.0
_ROUNDS = 20


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-src", type=Path, help="Driver only: the merge-base worktree's src/ directory.")
    parser.add_argument("--head-src", type=Path, help="Driver only: the head tree's src/ directory.")
    parser.add_argument("--out-dir", type=Path, help="Driver only: scratch output directory.")
    parser.add_argument("--base-sha", help="Driver only: the merge-base commit SHA (for the report).")
    parser.add_argument("--head-sha", help="Driver only: the head commit SHA (for the report).")
    parser.add_argument("--rounds", type=int, default=_ROUNDS, help="Driver only: number of ABBA rounds (default 20).")
    parser.add_argument("--worker", action="store_true", help="Run in worker mode.")
    parser.add_argument("--side", choices=("base", "head"), help="Worker only: which side this worker measures.")
    parser.add_argument("--mode", choices=("check", "bench"), help="Worker only: 'check' (one untimed pass/fail) or 'bench' (warm-up + timed).")
    parser.add_argument("--fixture-repo", type=Path, help="Worker only: the pre-built fixture repository root.")
    parser.add_argument("--mission-slug", help="Worker only: the fixture mission's slug.")
    parser.add_argument("--expected-src", type=Path, help="Worker only: the src/ root this worker must resolve under.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.worker:
        return _run_worker(args)
    return _run_driver(args)


# --------------------------------------------------------------------------- #
# Driver: fixture construction. The 30-WP file layout is modelled on
# tests/integration/test_ac5_hash_guard.py::_build_mission (git repo,
# meta.json, spec.md, tasks.md, WP*.md, committed); the finalize-tasks
# entry-point/patch-seam pattern below (_invoke_finalize) instead follows
# tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py
# ::_run_finalize (patching mission.locate_project_root / run_git_preflight).
# Neither test module is imported: each worker subprocess's PYTHONPATH is
# scoped to one side's src/ only, so this module builds its own fixture and
# entry-point harness directly rather than importing tests.* helpers.
# --------------------------------------------------------------------------- #

_MISSION_SLUG = "latency-bench-fixture"
_WP_COUNT = 30
_NFR_COUNT = 5
_C_COUNT = 3
_SC_COUNT = 4


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)  # noqa: S603, S607 -- fixed argv, no shell


def _spec_md_text() -> str:
    lines = ["# Spec\n", "\n## Functional Requirements\n", "| ID | Requirement | Acceptance Criteria | Status |\n", "| --- | --- | --- | --- |\n"]
    for i in range(1, _WP_COUNT + 1):
        lines.append(f"| FR-{i:03d} | Requirement {i} | AC {i}. | proposed |\n")
    lines.append("\n## Non-Functional Requirements\n")
    lines.append("| ID | Requirement | Category | Priority | Status |\n")
    lines.append("| --- | --- | --- | --- | --- |\n")
    for i in range(1, _NFR_COUNT + 1):
        lines.append(f"| NFR-{i:03d} | Non-functional {i} | Perf | Medium | Open |\n")
    lines.append("\n## Constraints\n")
    for i in range(1, _C_COUNT + 1):
        lines.append(f"- **C-{i:03d}**: Constraint {i}.\n")
    lines.append("\n## Success Criteria\n")
    for i in range(1, _SC_COUNT + 1):
        lines.append(f"- **SC-{i:03d}**: Success criterion {i}.\n")
    return "".join(lines)


def _wp_file_text(wp_id: str, index: int) -> str:
    nfr_index = ((index - 1) % _NFR_COUNT) + 1
    return (
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Work {index}\n"
        "dependencies: []\n"
        f"requirement_refs: [FR-{index:03d}, NFR-{nfr_index:03d}]\n"
        "subtasks: []\n"
        f"owned_files:\n  - src/module_{wp_id.lower()}/**\n"
        f"authoritative_surface: src/module_{wp_id.lower()}/\n"
        "execution_mode: code_change\n"
        "---\n\n"
        f"# {wp_id}\n\n## Activity Log\n"
    )


def build_fixture(root: Path) -> Path:
    """Build the 30-WP finalize-tasks fixture once, committed, read-only from
    here on. Content is identical regardless of which side later reads it --
    only the ``src`` under test differs (see module docstring)."""
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "latency-bench@example.invalid")
    _git(repo, "config", "user.name", "Latency Bench")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    mission_id = "01LATENCYBENCHFIXTURE0000"
    meta = {
        "mission_id": mission_id,
        "mid8": mission_id[:8],
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (feature_dir / "spec.md").write_text(_spec_md_text(), encoding="utf-8")

    wp_sections = []
    for i in range(1, _WP_COUNT + 1):
        wp_id = f"WP{i:02d}"
        wp_sections.append(f"## {wp_id} - Work {i}\n\n**Dependencies**: None\n")
        (tasks_dir / f"{wp_id}-work.md").write_text(_wp_file_text(wp_id, i), encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n" + "\n".join(wp_sections) + "\n", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed latency-bench fixture")
    return repo


# --------------------------------------------------------------------------- #
# Driver: subprocess orchestration
# --------------------------------------------------------------------------- #


def _spawn_worker(
    *,
    side: str,
    mode: str,
    fixture_repo: Path,
    src_root: Path,
    tmp_dir: Path,
    round_index: int,
) -> dict[str, Any]:
    home = tmp_dir / f"home-{side}-{mode}-{round_index}"
    home.mkdir(parents=True, exist_ok=True)
    cwd = tmp_dir / f"cwd-{side}-{mode}-{round_index}"
    cwd.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(src_root),
        "HOME": str(home),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell, trusted interpreter
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--side",
            side,
            "--mode",
            mode,
            "--fixture-repo",
            str(fixture_repo),
            "--mission-slug",
            _MISSION_SLUG,
            "--expected-src",
            str(src_root),
        ],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{side}/{mode} worker failed (exit {completed.returncode}):\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
    try:
        result: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{side}/{mode} worker did not print valid JSON:\n{completed.stdout}") from exc
    if not result.get("finalize_ok") or not result.get("porcelain_clean"):
        raise RuntimeError(f"{side}/{mode} worker produced an invalid sample (not read-only-pass): {result}")
    return result


def _run_precheck(fixture_repo: Path, base_src: Path, head_src: Path, tmp_dir: Path) -> None:
    base_result = _spawn_worker(side="base", mode="check", fixture_repo=fixture_repo, src_root=base_src, tmp_dir=tmp_dir, round_index=-1)
    head_result = _spawn_worker(side="head", mode="check", fixture_repo=fixture_repo, src_root=head_src, tmp_dir=tmp_dir, round_index=-1)
    if base_result["finalize_ok"] != head_result["finalize_ok"]:
        raise RuntimeError(f"pre-check verdict mismatch: base={base_result} head={head_result}")


# --------------------------------------------------------------------------- #
# Driver: rounds + statistics
# --------------------------------------------------------------------------- #


def _run_rounds(*, fixture_repo: Path, base_src: Path, head_src: Path, tmp_dir: Path, rounds: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_samples: list[dict[str, Any]] = []
    head_samples: list[dict[str, Any]] = []
    for round_index in range(rounds):
        order = ("base", "head") if round_index % 2 == 0 else ("head", "base")
        for side in order:
            src_root = base_src if side == "base" else head_src
            result = _spawn_worker(side=side, mode="bench", fixture_repo=fixture_repo, src_root=src_root, tmp_dir=tmp_dir, round_index=round_index)
            (base_samples if side == "base" else head_samples).append(result)
    return base_samples, head_samples


def _stats_ms(samples: list[dict[str, Any]], key: str) -> dict[str, float]:
    values_ms = [sample[key] / 1_000_000 for sample in samples]
    return {"median": median(values_ms), "min": min(values_ms), "max": max(values_ms)}


def _load_average() -> tuple[float, float, float]:
    try:
        return os.getloadavg()
    except OSError:
        return (-1.0, -1.0, -1.0)


def _cpu_model() -> str:
    cpuinfo_path = Path("/proc/cpuinfo")
    if not cpuinfo_path.is_file():
        return "unknown"
    for line in cpuinfo_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _build_verdict(base_phase: dict[str, float], head_phase: dict[str, float], base_total: dict[str, float], head_total: dict[str, float]) -> dict[str, Any]:
    phase_delta_ms = head_phase["median"] - base_phase["median"]
    total_delta_ms = head_total["median"] - base_total["median"]
    phase_pass = phase_delta_ms <= _NFR_003_PHASE_BUDGET_MS
    total_pass = head_total["median"] < _CHARTER_TOTAL_BUDGET_MS
    return {
        "phase_delta_ms": phase_delta_ms,
        "total_delta_ms": total_delta_ms,
        "phase_budget_ms": _NFR_003_PHASE_BUDGET_MS,
        "total_budget_ms": _CHARTER_TOTAL_BUDGET_MS,
        "phase_pass": phase_pass,
        "total_pass": total_pass,
        "overall": "PASS" if (phase_pass and total_pass) else "FAIL",
        "summary": (
            f"NFR-003: {'PASS' if phase_pass and total_pass else 'FAIL'} "
            f"(phase Δ = {phase_delta_ms:+.1f} ms {'<=' if phase_pass else '>'} {_NFR_003_PHASE_BUDGET_MS:.0f} ms; "
            f"total head = {head_total['median']:.1f} ms {'<' if total_pass else '>='} {_CHARTER_TOTAL_BUDGET_MS:.0f} ms)"
        ),
    }


def _sample_table(samples: list[dict[str, Any]], label: str) -> list[str]:
    lines = [f"### {label} samples", "", "| # | phase (ms) | total (ms) |", "| --- | --- | --- |"]
    for index, sample in enumerate(samples, start=1):
        lines.append(f"| {index} | {sample['phase_ns'] / 1_000_000:.4f} | {sample['total_ns'] / 1_000_000:.4f} |")
    lines.append("")
    return lines


def _summary_markdown(report: dict[str, Any]) -> str:
    machine = report["machine"]
    verdict = report["verdict"]
    fixture = report["fixture"]
    lines = [
        "# NFR-003 latency micro-benchmark (WP08 / T037)",
        "",
        "## Method",
        "",
        f"- base SHA: `{report['base_sha']}`",
        f"- head SHA: `{report['head_sha']}`",
        "- command: `.venv/bin/python research/latency_bench.py --base-src <base-worktree>/src "
        "--head-src <head-tree>/src --base-sha <sha> --head-sha <sha> --out-dir <scratch>`",
        f"- rounds: {report['rounds']} (ABBA-interleaved: round order alternates which side runs first)",
        f"- machine: {machine['platform']}",
        f"- CPU: {machine['cpu_model']} ({machine['cpu_count']} logical CPUs)",
        f"- Python: {machine['python_version']}",
        f"- load average before={machine['load_avg_before']} after={machine['load_avg_after']}",
        "",
        "## Fixture",
        "",
        f"- {fixture['wp_count']} work packages (WP01..WP{fixture['wp_count']:02d}), each with `requirement_refs: [FR-0NN, NFR-00x]`",
        f"- spec.md declares FR-001..FR-{fixture['wp_count']:03d}, {fixture['nfr_count']} NFRs, {fixture['c_count']} Cs, {fixture['sc_count']} SCs",
        "- entry point: in-process `typer.testing.CliRunner` on `specify_cli.cli.commands.agent.mission.app`, "
        "`finalize-tasks --mission <slug> --json --validate-only`",
        "- both sides reached the same pass verdict on the untimed pre-check (asserted by the driver before any round ran)",
        "- every sample (warm-up and timed) asserted read-only: `git status --porcelain` empty after the call",
        "",
        "## Phase metric (wrapped functions)",
        "",
        "- `specify_cli.cli.commands.agent.mission_finalize._read_spec_requirement_ids`",
        "- `specify_cli.cli.commands.agent.mission_finalize._validate_requirement_mapping`",
        "- (both exist under the same name and module path at the merge-base; no head rename was needed)",
        "",
        "## Results",
        "",
        f"- base phase (ms): median={report['base_phase_ms']['median']:.4f} min={report['base_phase_ms']['min']:.4f} max={report['base_phase_ms']['max']:.4f}",
        f"- head phase (ms): median={report['head_phase_ms']['median']:.4f} min={report['head_phase_ms']['min']:.4f} max={report['head_phase_ms']['max']:.4f}",
        f"- base total (ms): median={report['base_total_ms']['median']:.4f} min={report['base_total_ms']['min']:.4f} max={report['base_total_ms']['max']:.4f}",
        f"- head total (ms): median={report['head_total_ms']['median']:.4f} min={report['head_total_ms']['min']:.4f} max={report['head_total_ms']['max']:.4f}",
        "",
        *_sample_table(report["base_samples"], "base"),
        *_sample_table(report["head_samples"], "head"),
        "## Verdict",
        "",
        f"**{verdict['summary']}**",
        "",
        f"- phase delta: {verdict['phase_delta_ms']:+.4f} ms (budget: <= {verdict['phase_budget_ms']:.0f} ms) -- {'PASS' if verdict['phase_pass'] else 'FAIL'}",
        f"- total delta (head - base): {verdict['total_delta_ms']:+.4f} ms",
        f"- head total budget: < {verdict['total_budget_ms']:.0f} ms -- {'PASS' if verdict['total_pass'] else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


def _run_driver(args: argparse.Namespace) -> int:
    base_src = Path(args.base_src).resolve()
    head_src = Path(args.head_src).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = out_dir / "tmp"

    if base_src == head_src:
        raise RuntimeError(f"--base-src and --head-src resolve to the same tree ({base_src}) -- isolation would be unproven, not merely unexercised")

    load_before = _load_average()
    # The fixture is read-only for the whole benchmark (every sample asserts
    # git status --porcelain stays empty); a TemporaryDirectory is still used
    # so a crashed run does not leave it behind under --out-dir.
    with tempfile.TemporaryDirectory(prefix="latency-bench-fixture-") as fixture_root:
        fixture_repo = build_fixture(Path(fixture_root))
        _run_precheck(fixture_repo, base_src, head_src, tmp_dir)
        base_samples, head_samples = _run_rounds(fixture_repo=fixture_repo, base_src=base_src, head_src=head_src, tmp_dir=tmp_dir, rounds=args.rounds)
    load_after = _load_average()

    base_phase = _stats_ms(base_samples, "phase_ns")
    head_phase = _stats_ms(head_samples, "phase_ns")
    base_total = _stats_ms(base_samples, "total_ns")
    head_total = _stats_ms(head_samples, "total_ns")
    verdict = _build_verdict(base_phase, head_phase, base_total, head_total)

    report = {
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "rounds": args.rounds,
        "fixture": {"wp_count": _WP_COUNT, "nfr_count": _NFR_COUNT, "c_count": _C_COUNT, "sc_count": _SC_COUNT},
        "machine": {
            "platform": platform.platform(),
            "cpu_model": _cpu_model(),
            "cpu_count": os.cpu_count(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "load_avg_before": load_before,
            "load_avg_after": load_after,
        },
        "base_phase_ms": base_phase,
        "head_phase_ms": head_phase,
        "base_total_ms": base_total,
        "head_total_ms": head_total,
        "base_samples": base_samples,
        "head_samples": head_samples,
        "verdict": verdict,
    }

    (out_dir / "latency.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out_dir / "latency.md").write_text(_summary_markdown(report) + "\n", encoding="utf-8")
    print(_summary_markdown(report))
    return 0 if verdict["overall"] == "PASS" else 1


# --------------------------------------------------------------------------- #
# Worker: import isolation (mirrors corpus_scan.py)
# --------------------------------------------------------------------------- #


def _resolved_relative(module_file: str, expected_src: Path) -> str:
    resolved = Path(module_file).resolve()
    try:
        return resolved.relative_to(expected_src).as_posix()
    except ValueError:
        return f"OUTSIDE_EXPECTED_SRC:{resolved.name}"


def _check_import_isolation(expected_src: Path) -> tuple[bool, dict[str, str | None]]:
    import specify_cli

    resolved: dict[str, str | None] = {}
    ok = True
    for package_name in _TRACKED_PACKAGES:
        try:
            module = specify_cli if package_name == "specify_cli" else __import__(package_name)
        except ImportError:
            resolved[package_name] = None
            continue
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            resolved[package_name] = None
            continue
        rel = _resolved_relative(module_file, expected_src)
        resolved[package_name] = rel
        if rel.startswith("OUTSIDE_EXPECTED_SRC:"):
            ok = False
    return ok, resolved


# --------------------------------------------------------------------------- #
# Worker: the timed invocation
# --------------------------------------------------------------------------- #


@dataclass
class _PreflightStub:
    passed: bool = True


def _wrap_with_timer(accumulator: list[int], original: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap *original* so every call's elapsed ns is appended to *accumulator*."""

    def _timed(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter_ns()
        try:
            return original(*args, **kwargs)
        finally:
            accumulator.append(time.perf_counter_ns() - start)

    return _timed


def _porcelain_clean(repo: Path) -> bool:
    completed = subprocess.run(  # noqa: S603, S607 -- fixed argv, no shell
        ["git", "status", "--porcelain"], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return completed.stdout == ""


def _requirement_mapping_patches(phase_samples: list[int]) -> list[_patch[Any]]:
    """The two ``mission_finalize`` phase functions, wrapped with a shared timer."""
    import specify_cli.cli.commands.agent.mission_finalize as finalize_module
    from unittest.mock import patch

    return [
        patch.object(finalize_module, "_validate_requirement_mapping", side_effect=_wrap_with_timer(phase_samples, finalize_module._validate_requirement_mapping)),
        patch.object(finalize_module, "_read_spec_requirement_ids", side_effect=_wrap_with_timer(phase_samples, finalize_module._read_spec_requirement_ids)),
    ]


def _saas_fan_out_patch() -> _patch[Any] | None:
    import specify_cli.status.emit as emit_module
    from unittest.mock import patch

    if not hasattr(emit_module, "_saas_fan_out"):
        return None
    return patch.object(emit_module, "_saas_fan_out", return_value=None)


def _invoke_finalize(*, fixture_repo: Path, mission_slug: str) -> tuple[int, int, int]:
    """One ``finalize-tasks --validate-only`` call. Returns (phase_ns, total_ns, exit_code)."""
    from typer.testing import CliRunner
    from unittest.mock import patch

    from specify_cli.cli.commands.agent.mission import app

    phase_samples: list[int] = []
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=fixture_repo))
        stack.enter_context(patch("specify_cli.cli.commands.agent.mission.run_git_preflight", return_value=_PreflightStub()))
        for phase_patch in _requirement_mapping_patches(phase_samples):
            stack.enter_context(phase_patch)
        saas_patch = _saas_fan_out_patch()
        if saas_patch is not None:
            stack.enter_context(saas_patch)

        runner = CliRunner()
        total_start = time.perf_counter_ns()
        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json", "--validate-only"], catch_exceptions=False)
        total_ns = time.perf_counter_ns() - total_start

    return sum(phase_samples), total_ns, result.exit_code


def _run_worker(args: argparse.Namespace) -> int:
    expected_src = Path(args.expected_src).resolve()
    isolation_ok, resolved_relative = _check_import_isolation(expected_src)
    if not isolation_ok:
        print(json.dumps({"error": "import isolation violated", "resolved": resolved_relative}), file=sys.stderr)
        return 1

    fixture_repo = Path(args.fixture_repo).resolve()

    # Untimed warm-up (every mode gets one, per the spec's "each worker does
    # one untimed warm-up invocation, then one timed invocation").
    _phase_ns, _total_ns, warmup_exit = _invoke_finalize(fixture_repo=fixture_repo, mission_slug=args.mission_slug)
    warmup_clean = _porcelain_clean(fixture_repo)

    if args.mode == "check":
        output = {"side": args.side, "finalize_ok": warmup_exit == 0, "porcelain_clean": warmup_clean, "isolation_ok": isolation_ok}
        print(json.dumps(output, sort_keys=True))
        return 0

    phase_ns, total_ns, exit_code = _invoke_finalize(fixture_repo=fixture_repo, mission_slug=args.mission_slug)
    porcelain_clean = _porcelain_clean(fixture_repo)
    output = {
        "side": args.side,
        "phase_ns": phase_ns,
        "total_ns": total_ns,
        "finalize_ok": exit_code == 0 and warmup_exit == 0,
        "porcelain_clean": porcelain_clean and warmup_clean,
        "isolation_ok": isolation_ok,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
