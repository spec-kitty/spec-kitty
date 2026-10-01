"""Red-first guards for ``scripts/ci/corpus_select.py`` (FR-009, WP09, #4368).

``packs.yml`` is the SOLE (advisory) owner of the ``-m corpus`` suite. Its
``changes`` job must therefore select the corpus lane on every path that used to
select the router's deleted ``tests (corpus)`` job -- and it must do so through
the ONE gate-selection authority (``gate_selection.select_gates``), never a second
hand-copied glob list (C-003, #2476).

Three layers are pinned here:

1. the pure truth table of :func:`corpus_selected` / :func:`decide`;
2. the ``main`` edge (env in, ``$GITHUB_OUTPUT`` out), exercised in-process;
3. the PRODUCTION CALLER -- the ``packs.yml`` ``changes`` step that shells out to
   the script -- so the wiring cannot rot while the helper stays green in
   isolation (the argv the workflow really passes is fed through ``main``).

The module is imported at the top on purpose: before the helper exists every
test here is red with ``ModuleNotFoundError`` (never ``importorskip``).
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.corpus_select import corpus_selected, decide, main
from scripts.ci.gate_selection import load_router

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKS = _REPO_ROOT / ".github" / "workflows" / "packs.yml"
_ROUTER = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"
_SCRIPT_REL = "scripts/ci/corpus_select.py"

_SELECTED_PATHS = (
    "packs/built-in/missions/x.md",
    "packs/internal/x.yaml",
    "kitty-specs/m/spec.md",
    "kitty-specs/m/plan.md",
    "kitty-specs/m/tasks/WP01.md",
    "kitty-specs/m/contracts/c.md",
    "kitty-specs/m/acceptance-matrix.json",
    ".kittify/charter/charter.md",
    ".kittify/glossaries/g.yaml",
    ".kittify/doctrine/d.yaml",
    # Unmatched-src fan-out (C-008, #4368): an unmapped src/** path selects everything.
    "src/specify_cli/__unmapped_probe__/x.py",
)

_NOT_SELECTED_PATHS = (
    "src/specify_cli/consolidation/x.py",
    "docs/x.md",
    "kitty-specs/m/status.events.jsonl",
    ".github/workflows/ci-router.yml",
)


@pytest.mark.parametrize("path", _SELECTED_PATHS)
def test_corpus_selected_true_for_every_corpus_trigger(path: str) -> None:
    assert corpus_selected([path], router=load_router()) is True


@pytest.mark.parametrize("path", _NOT_SELECTED_PATHS)
def test_corpus_selected_false_for_non_corpus_paths(path: str) -> None:
    assert corpus_selected([path], router=load_router()) is False


def test_corpus_selected_full_mode_selects_even_a_docs_only_diff() -> None:
    router = load_router()
    assert corpus_selected(["docs/x.md"], router=router, mode="full") is True
    assert corpus_selected(["docs/x.md"], router=router, mode="pr") is False


def test_corpus_selected_empty_diff_is_not_selected_in_pr_mode() -> None:
    assert corpus_selected([], router=load_router()) is False


def test_decide_unavailable_diff_fails_closed() -> None:
    selected, reason = decide(None, router=load_router(), mode="pr", event_name="pull_request")
    assert selected is True
    assert "fail-closed" in reason


def test_decide_push_always_selects() -> None:
    selected, reason = decide(["docs/x.md"], router=load_router(), mode="pr", event_name="push")
    assert selected is True
    assert "push" in reason


def test_decide_full_mode_selects() -> None:
    selected, reason = decide(["docs/x.md"], router=load_router(), mode="full", event_name="workflow_dispatch")
    assert selected is True
    assert "full" in reason


def test_decide_names_the_reason_for_each_verdict() -> None:
    router = load_router()
    hit, hit_reason = decide(["kitty-specs/m/spec.md"], router=router, mode="pr", event_name="pull_request")
    miss, miss_reason = decide(["docs/x.md"], router=router, mode="pr", event_name="pull_request")
    fan, fan_reason = decide(["src/specify_cli/__unmapped_probe__/x.py"], router=router, mode="pr", event_name="pull_request")
    assert (hit, miss, fan) == (True, False, True)
    assert "corpus" in hit_reason
    assert "no corpus" in miss_reason
    assert "unmatched" in fan_reason


# --- main(): env in, $GITHUB_OUTPUT out ------------------------------------


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    *,
    files: Any,
    outcome: str,
) -> tuple[int, str]:
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("CHANGED_FILES", files if isinstance(files, str) else json.dumps(files))
    monkeypatch.setenv("CHANGED_OUTCOME", outcome)
    rc = main(argv)
    return rc, out.read_text(encoding="utf-8")


def test_main_writes_selected_true_for_a_corpus_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = _run_main(monkeypatch, tmp_path, ["--mode", "pr", "--event", "pull_request"], files=["kitty-specs/m/spec.md"], outcome="success")
    assert rc == 0
    assert out == "selected=true\n"
    assert capsys.readouterr().out.startswith("corpus selection: true (")


def test_main_writes_selected_false_for_a_docs_only_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rc, out = _run_main(monkeypatch, tmp_path, ["--mode", "pr", "--event", "pull_request"], files=["docs/x.md"], outcome="success")
    assert rc == 0
    assert out == "selected=false\n"


@pytest.mark.parametrize("outcome", ["failure", "cancelled", "", "skipped"])
def test_main_fails_closed_when_the_diff_step_did_not_succeed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: str) -> None:
    _, out = _run_main(monkeypatch, tmp_path, ["--mode", "pr", "--event", "pull_request"], files=["docs/x.md"], outcome=outcome)
    assert out == "selected=true\n"


@pytest.mark.parametrize("files", ["", "not json", '{"a": 1}', '"packs/x"'])
def test_main_fails_closed_on_unparseable_changed_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: str) -> None:
    _, out = _run_main(monkeypatch, tmp_path, ["--mode", "pr", "--event", "pull_request"], files=files, outcome="success")
    assert out == "selected=true\n"


def test_main_push_and_full_always_select(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, pushed = _run_main(monkeypatch, tmp_path, ["--mode", "pr", "--event", "push"], files=["docs/x.md"], outcome="success")
    assert pushed == "selected=true\n"
    (tmp_path / "github_output").unlink()
    _, full = _run_main(monkeypatch, tmp_path, ["--mode", "full", "--event", "workflow_dispatch"], files=["docs/x.md"], outcome="success")
    assert full == "selected=true\n"


def test_main_without_github_output_only_prints(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setenv("CHANGED_FILES", "[]")
    monkeypatch.setenv("CHANGED_OUTCOME", "success")
    assert main(["--mode", "pr", "--event", "pull_request"]) == 0
    assert "corpus selection: false" in capsys.readouterr().out


# --- the production caller: packs.yml `changes` ------------------------------


def _changes_job() -> dict[str, Any]:
    job: dict[str, Any] = yaml.safe_load(_PACKS.read_text(encoding="utf-8"))["jobs"]["changes"]
    return job


def _corpus_step(job: dict[str, Any]) -> dict[str, Any]:
    steps = [s for s in job["steps"] if s.get("id") == "corpus"]
    assert len(steps) == 1, "packs.yml `changes` must carry exactly one `id: corpus` selection step"
    step: dict[str, Any] = steps[0]
    return step


def test_packs_changes_runs_the_shipped_helper_not_an_inlined_glob_list() -> None:
    step = _corpus_step(_changes_job())
    run = step["run"]
    assert f"python3 {_SCRIPT_REL}" in run, "the Packs corpus step must invoke scripts/ci/corpus_select.py"
    # C-003: no second encoding of the corpus globs in the workflow step.
    assert "kitty-specs/" not in run
    assert "packs/" not in run
    assert ".kittify/" not in run


def test_packs_changes_diff_inputs_reach_the_helper_through_env() -> None:
    step = _corpus_step(_changes_job())
    env = step.get("env", {})
    run = step["run"]
    assert {"EVENT_NAME", "BASE_SHA", "HEAD_SHA", "MODE"} <= set(env)
    assert "CHANGED_FILES" in run + json.dumps(env)
    assert "CHANGED_OUTCOME" in run + json.dumps(env)
    # Fail closed: an unusable base (empty / all-zero) must never narrow the selection.
    assert "0000000000000000000000000000000000000000" in run


def test_packs_changes_checkout_has_full_history_and_pyyaml_precedes_the_step() -> None:
    job = _changes_job()
    checkout = next(s for s in job["steps"] if "actions/checkout" in str(s.get("uses", "")))
    assert checkout.get("with", {}).get("fetch-depth") == 0
    names = [s.get("id") or s.get("name", "") for s in job["steps"]]
    pip_idx = next(i for i, s in enumerate(job["steps"]) if "pip install" in str(s.get("run", "")) and "pyyaml" in str(s.get("run", "")).lower())
    assert pip_idx < names.index("corpus"), "PyYAML must be installed (pre-uv-sync pip pattern) before the corpus step"


def test_packs_workflow_argv_is_accepted_by_the_helper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The exact argv the workflow passes parses through ``main`` (no flag drift)."""
    run = _corpus_step(_changes_job())["run"]
    line = next(ln for ln in run.splitlines() if _SCRIPT_REL in ln and not ln.lstrip().startswith("#"))
    argv = shlex.split(line.split(_SCRIPT_REL, 1)[1])
    # Substitute the env-var expansions the shell would perform.
    resolved = [{"$MODE": "pr", "$EVENT_NAME": "pull_request"}.get(a, a) for a in argv]
    assert all(not a.startswith("$") for a in resolved), f"unresolved shell reference in {argv}"
    rc, out = _run_main(monkeypatch, tmp_path, resolved, files=["kitty-specs/m/spec.md"], outcome="success")
    assert (rc, out) == (0, "selected=true\n")


def test_packs_changes_exports_corpus_folding_full_and_push() -> None:
    expr = _changes_job()["outputs"]["corpus"]
    assert "inputs.mode == 'full'" in expr
    assert "github.event_name == 'push'" in expr
    assert "steps.corpus.outputs.selected" in expr


# --- the pin that makes the transitional ungated exemption (D-22) safe ---------


def test_corpus_group_is_live_and_feeds_prose_scan_and_packs() -> None:
    router = load_router()
    assert router.filters.get("corpus"), "the router `corpus` filter group must stay non-empty"
    workflow = yaml.safe_load(_ROUTER.read_text(encoding="utf-8"))
    assert "corpus" in workflow["jobs"]["changes"]["outputs"], "router `changes` must keep exporting `corpus`"
    prose_scan_runs = "\n".join(str(step.get("run", "")) for step in workflow["jobs"]["prose-scan"]["steps"])
    assert 'filters.get("corpus"' in prose_scan_runs, "prose-scan must keep reading the router corpus group"
    source = (_REPO_ROOT / _SCRIPT_REL).read_text(encoding="utf-8")
    assert "select_gates" in source and '"corpus"' in source, "corpus_select must consume the router corpus group"
