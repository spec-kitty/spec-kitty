"""Characterization corpus: today's consolidation verdict for every scenario cell (FR-016, NFR-001, C-008, SC-005).

``characterization/verdict_corpus.json`` records, per cell, the verdict status (``pass`` /
``refuse`` / ``fail`` / ``error``), the refusal codes in the output, the ``Divergence`` fields the
verifier reported, and the exit code. Known-wrong verdicts are recorded as they are today; the
intended verdicts are separate strict ``xfail`` tests (WP05). Every cell is recomputed in process
(``characterization_support.run_in_process``) and compared with the golden file byte for byte.

Regenerate (only when a work package flips its named cells, NFR-002)::

    SPEC_KITTY_REGEN_VERDICT_CORPUS=1 uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py

Cell key: ``{mode}|{shape}|stamp={stamp}|window={window}`` plus ``|{variant}`` for a named cell.
Axes: mode (forecast = ``consolidate --dry-run --json``, fresh = ``consolidate``, resume =
``consolidate --resume`` after a SIGKILL right after the claim anchors were saved) x shape
(single_lane, two_wp_lane, mixed_lane_canceled_wp, fully_canceled_dependency, dependency_chain,
planning_lane, single_branch) x approval stamp of the shape's subject work package (present,
missing, rewritten) x window state of every approved code-lane work package (recorded,
not_recorded, capture_failed, lane_branch_missing, not_on_lane).

Pruning rule (post-tasks squad pedro #5), applied by ``characterization_support.generic_cells``:

- **P1 stamp short-circuit.** A ``missing`` or ``rewritten`` approval stamp refuses before any window
  logic (``check_lane``: stamp refusals first, WW-4). So for stamp in {``missing``, ``rewritten``} the
  window axis collapses to one cell, ``window=any``; the other four window values are not generated.
- **P2 no lane window.** ``planning_lane`` and ``single_branch`` have no lane window: their generic
  window axis collapses to ``window=any``. (The named ``single_branch`` (c) cell of step 2 is separate
  and keeps its window state.)
- **P3 resume topology.** Resume cells exist only for shapes built on the coordination topology (T008
  note); the rest are ``mode_not_applicable``.
- Nothing else is pruned. A pruned combination is not written to the golden file as a cell; the
  docstring states the rule so a reviewer can recompute the cell count.

Recomputing the count: the five lane shapes are built on the coordination topology, give
5 (present x windows) + 2 (missing, rewritten at ``window=any``) = 7 cells per mode, so
5 x 7 x 3 modes = 105; ``planning_lane`` and ``single_branch`` give 3 stamps x ``window=any`` = 3 per
mode, so 2 x 3 x 3 = 18, of which the 6 resume cells are ``mode_not_applicable`` (P3) and the 4
non-resume ``planning_lane`` cells with a missing or rewritten stamp are ``not_applicable`` (a planning
lane is never stamped). Generic cells: 105 + 18 = **123**. Named cells: **29** (NFR-002 (a)-(h) incl.
both (c) cells, the WP06 mutation targets, the exception cells, R-09, WP19's two
canceled-commit-before-window cells, operator ruling 2026-11-09, and the pre-PR fold's declared
dependency ref merged before the window, M9). Total: **152**.
"""

from __future__ import annotations

from collections.abc import Mapping

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.consolidation import characterization_support as cs

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

GENERIC_CELL_COUNT = 123
NAMED_CELL_COUNT = 29
EXCEPTION_CELLS = (
    "x_dependency_chain_exception",
    "x_gap_covers_stray",
    "x_skewed_clock_rework",
    "x_leading_branch_missing",
    "x_canceled_commit_before_window_superseded",
)


class _CorpusSentinel(Exception):
    """Raised by the control's patch on the claim path; it must surface in the cell result."""


def test_runner_computes_the_verdict_in_this_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control (T007): a patch applied here reaches the claim computation, which a subprocess runner could not see.

    WP09 moved the claim build behind ``claim_inputs.build_claim``, so the builder is looked up there.
    """
    from specify_cli.consolidation import claim_inputs

    mission = cs.build_shape(tmp_path / "m", "single_lane")

    def _sentinel(*_args: object, **_kwargs: object) -> object:
        raise _CorpusSentinel("corpus-sentinel reached the claim")

    monkeypatch.setattr(claim_inputs, "build_approved_wp_set", _sentinel)

    result = cs.run_in_process(mission, cs.consolidate_args(mission, "fresh"))

    assert result.status == "error" and result.exception == "_CorpusSentinel", result.output
    assert "corpus-sentinel reached the claim" in result.output


def test_generic_cells_follow_the_pruning_rule() -> None:
    """The enumerator applies P1-P3 and nothing else: the count recomputed in the docstring holds."""
    generic = cs.generic_cells()
    keys = [cell.key for cell in generic]
    assert len(keys) == GENERIC_CELL_COUNT == len(set(keys))
    assert len(cs.named_cells()) == NAMED_CELL_COUNT
    assert len(cs.all_cells()) == GENERIC_CELL_COUNT + NAMED_CELL_COUNT
    stamped_short = [k for k in keys if "|stamp=missing|" in k or "|stamp=rewritten|" in k]
    assert stamped_short and all(k.endswith("|window=any") for k in stamped_short), "P1"
    flat = [k for k in keys if k.split("|")[1] in cs.FLAT_SHAPES]
    assert flat and all(k.endswith("|window=any") for k in flat), "P2"
    computed_resume = [cell for cell in generic if cell.key.startswith("resume|") and cell.templates]
    assert computed_resume and all(cell.key.split("|")[1] in cs.LANE_SHAPES for cell in computed_resume), "P3"


def test_golden_holds_every_cell_and_the_named_ones_by_key() -> None:
    golden = cs.load_golden()
    assert sorted(golden) == sorted(cs.all_cells()), "the golden file must hold exactly the enumerated cells"
    for name, key in cs.NAMED_KEYS.items():
        assert key in golden, f"named cell {name} ({key}) missing from the golden file"
    for name in EXCEPTION_CELLS:
        assert golden[cs.NAMED_KEYS[name]].get("status") == "pass", f"exception cell {name} must record a pass today"
    topology_na = [k for k in golden if k.startswith("resume|") and k.split("|")[1] in cs.FLAT_SHAPES]
    assert topology_na and all(golden[k] == {"mode_not_applicable": cs.MODE_NA_RESUME} for k in topology_na), "P3"
    unreachable = [v for k, v in golden.items() if k.startswith("resume|") and v.get("mode_not_applicable") == cs.RESUME_UNREACHABLE]
    assert all(v["interrupted_run"]["exit_code"] != 0 for v in unreachable), "an unreachable resume names the fresh run's refusal"


def test_changed_cells_compares_the_golden_at_a_ref_with_the_working_tree(tmp_path: Path) -> None:
    """``changed_cells`` reads the committed golden at *base_ref*: one changed and one added key are reported, sorted."""
    repo = tmp_path / "repo"
    golden = repo / "tests" / "consolidation" / "characterization" / "verdict_corpus.json"
    golden.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for key, value in (("user.name", "T"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    cs.write_golden({"a|kept": {"status": "pass"}, "b|changed": {"status": "pass"}}, golden)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "v1"], check=True)
    cs.write_golden({"a|kept": {"status": "pass"}, "b|changed": {"status": "refuse"}, "c|added": {"status": "pass"}}, golden)

    assert cs.changed_cells("HEAD", repo=repo, golden_path=golden) == ["b|changed", "c|added"]
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "v2"], check=True)
    assert cs.changed_cells("HEAD", repo=repo, golden_path=golden) == []
    assert cs.changed_cells("HEAD~1", repo=repo, golden_path=golden) == ["b|changed", "c|added"]


def test_changed_cells_refuses_an_unresolvable_ref_and_reads_a_missing_golden_as_empty(tmp_path: Path) -> None:
    """A ref that names no commit raises; only a valid ref whose tree lacks the golden reads as empty."""
    repo = tmp_path / "repo"
    golden = repo / "tests" / "consolidation" / "characterization" / "verdict_corpus.json"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for key, value in (("user.name", "T"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "no golden yet"], check=True)
    cs.write_golden({"a|new": {"status": "pass"}}, golden)

    assert cs.changed_cells("HEAD", repo=repo, golden_path=golden) == ["a|new"]
    with pytest.raises(ValueError, match="does not resolve to a commit"):
        cs.changed_cells("no-such-ref", repo=repo, golden_path=golden)


def test_axis_commits_of_two_log_copies_are_one_commit_across_a_second_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The WP02 flake: the two event-log copies' axis commits straddling a second must still be one commit.

    ``set_window_state`` commits the repository root copy and the coordination copy separately;
    a clock tick between them used to leave the target branch with a divergent commit, and the
    landing refused with ``TARGET_BRANCH_CONTENT_CONFLICT``. The tick is forced here.
    """
    import time

    mission = cs.build_shape(tmp_path / "m", "mixed_lane_canceled_wp")
    assert cs._git(mission.repo, "rev-parse", mission.target_branch) == cs._git(mission.repo, "rev-parse", mission.mission_branch), "precondition: one shared tip"
    real = cs._rewrite_one

    def _tick_after(log: Path, edit: Callable[[dict[str, Any]], dict[str, Any] | None], message: str) -> None:
        real(log, edit, message)
        time.sleep(1.1)

    monkeypatch.setattr(cs, "_rewrite_one", _tick_after)
    cs.set_window_states(mission, "lane_branch_missing")

    assert cs._git(mission.repo, "rev-parse", mission.target_branch) == cs._git(mission.repo, "rev-parse", mission.mission_branch)


def test_normalization_and_code_extraction_are_stable() -> None:
    sha = "0123456789abcdef0123456789abcdef01234567"
    text = f"LANE_MOVED_AFTER_APPROVAL: commit {sha[:7]} on /tmp/x/repo after {sha} at 2026-11-08T10:00:00+00:00; SPEC_KITTY_HOME"
    assert cs.refusal_codes(text) == ("LANE_MOVED_AFTER_APPROVAL",)
    assert cs.normalize_text(text, (Path("/tmp/x"),)) == "LANE_MOVED_AFTER_APPROVAL: commit <sha:1> on <root0>/repo after <sha:2> at <ts>; SPEC_KITTY_HOME"


def test_refusal_codes_reads_a_code_after_a_json_escape() -> None:
    """A combined refusal's second code follows a literal backslash-n in raw ``--json`` output."""
    text = r"LANE_MOVED_AFTER_APPROVAL: x\nAPPROVAL_STAMP_MISSING: y\r\tAPPROVAL_STAMP_NOT_ON_LANE"
    assert cs.refusal_codes(text) == ("APPROVAL_STAMP_MISSING", "APPROVAL_STAMP_NOT_ON_LANE", "LANE_MOVED_AFTER_APPROVAL")


def test_corpus_workers_default_to_one_inside_an_xdist_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """M10: under ``-n auto`` each xdist worker computes its corpus in process; the explicit setting still wins."""
    monkeypatch.delenv(cs.WORKERS_ENV, raising=False)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    assert cs.corpus_workers() == 1
    monkeypatch.setenv(cs.WORKERS_ENV, "4")
    assert cs.corpus_workers() == 4
    monkeypatch.delenv(cs.WORKERS_ENV)
    monkeypatch.delenv("PYTEST_XDIST_WORKER")
    assert cs.corpus_workers() >= 1


#: Codes only one mode can print, never a verdict of the claim: the forecast's own refusal wrapper, and the
#: post-landing remote notice a real run prints after it lands (the forecast never lands).
_MODE_ONLY_CODES = frozenset({"CLAIM_REFUSED_FORECAST", "NOT_LANDED_ON_NAMED_REMOTE"})


def _mode_verdict(value: Mapping[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    """``(status, underlying codes)`` of one recorded cell, or ``None`` when the mode does not apply to it."""
    if "status" in value:
        return str(value["status"]), tuple(sorted(set(value["codes"]) - _MODE_ONLY_CODES))
    return None


def test_modes_agree_wherever_they_apply() -> None:
    """SC-003 (pre-PR fold L9): one scenario judged by the forecast, the fresh run and the resume gets one verdict.

    Over the golden file: cells are grouped by everything after the mode; wherever two or more modes apply,
    their status and their codes (less the mode-only codes) are equal. A resume that never got an
    interrupted state records the fresh run's codes under ``interrupted_run``; they must match too.
    """
    groups: dict[str, dict[str, Mapping[str, Any]]] = {}
    for key, value in cs.load_golden().items():
        mode, _, scenario = key.partition("|")
        groups.setdefault(scenario, {})[mode] = value
    compared, disagreements = 0, {}
    for scenario, modes in sorted(groups.items()):
        verdicts = {mode: verdict for mode, value in modes.items() if (verdict := _mode_verdict(value)) is not None}
        interrupted = {mode: tuple(sorted(value["interrupted_run"]["codes"])) for mode, value in modes.items() if "interrupted_run" in value}
        if interrupted and "fresh" in verdicts and any(codes != verdicts["fresh"][1] for codes in interrupted.values()):
            disagreements[scenario] = {"fresh": verdicts["fresh"], **interrupted}
        if len(verdicts) < 2:
            continue
        compared += 1
        if len(set(verdicts.values())) > 1:
            disagreements[scenario] = verdicts
    assert compared >= 40, f"only {compared} scenarios had two or more applicable modes; the parity check would be vacuous"
    assert not disagreements, f"modes disagree on one scenario: {disagreements}"


@pytest.mark.timeout(600)  # the corpus budget (10 min serial); on >=8 cores the forked workers finish it in about a minute
def test_verdict_corpus_matches_the_golden_file(tmp_path: Path) -> None:
    """Every cell recomputed; byte equality with the golden file (or a deterministic rewrite under the switch)."""
    names = list(cs.all_cells())
    computed = cs.compute_cells(names, tmp_path, workers=cs.corpus_workers())
    if os.environ.get(cs.REGEN_ENV) == "1":
        cs.write_golden(computed)
        return
    golden_text = cs.GOLDEN_PATH.read_text(encoding="utf-8")
    if cs.dump_golden(computed) != golden_text:
        diff = cs.cell_diff(json.loads(golden_text), computed)
        raise AssertionError(f"verdict corpus differs from the golden file; regenerate with {cs.REGEN_ENV}=1 only for named cells:\n{diff or 'formatting only'}")
