"""Red-first unit + execution-grounded wiring guards for source-eligibility.

Mission ci-aggregate-source-eligibility WP01 (FR-001..FR-006, FR-008; NFR-003/4).

``scripts/ci/source_eligibility.py`` replaces the untested, provenance-blind
inline-shell source-selection in ``.github/workflows/ci-aggregate.yml``'s
``last-success`` step. The pure decision ``resolve_source`` is unit-tested over
injected inputs (no network, no git, no clock — NFR-003); the workflow wiring is
proven by executing the real extracted ``run:`` block against a stubbed ``gh``
(a grep-only guard is fakeable — reviewer D-05 anti-laziness rule).

The module is loaded by file path (``scripts/ci`` is not an importable
package), mirroring ``tests/ci/test_sonar_project_version.py``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "source_eligibility.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci-aggregate.yml"

# INV-6 / C-001: the fail-closed reconcile guard is a FROZEN boundary. Pinned
# byte-for-byte here so any edit to its run-block reds this test loudly.
_FROZEN_GUARD_RUN = (
    'echo "::error::ci-aggregate: reconciled coverage set is INCOMPLETE '
    "(missing: $MISSING_SHARDS) -- refusing to score diff-cover over data "
    'missing from both the current and fallback runs (C-005)"\n'
    "exit 1\n"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("source_eligibility", _SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise RuntimeError(f"cannot build an import spec for {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve field annotations against sys.modules[__module__];
    # register before exec so `@dataclass` on this file-loaded module works.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load_module()


def _trigger(mod: ModuleType, *, event: str, head_branch: str, conclusion: str) -> object:
    return mod.TriggerMeta(event=event, head_branch=head_branch, conclusion=conclusion)


def _candidate(mod: ModuleType, database_id: int, conclusion: str, head_branch: str, event: str = "push") -> object:
    return mod.CandidateRun(database_id=database_id, conclusion=conclusion, head_branch=head_branch, event=event)


# --------------------------------------------------------------------------- #
# Pure decision — assert the REJECTIONS, not a happy string (reviewer D-05).   #
# --------------------------------------------------------------------------- #


def test_pr_head_trigger_is_not_a_main_source_even_with_a_successful_main_candidate(mod: ModuleType) -> None:
    """INV-B/FR: a PR-head trigger NEVER resolves a main run-id, success or not."""
    trigger = _trigger(mod, event="pull_request", head_branch="topic-branch", conclusion="success")
    candidates = [_candidate(mod, 999, "success", "main")]  # an eligible main run EXISTS
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NotAMainSource)
    run_id, slug = mod.render_outputs(decision)
    assert run_id == ""  # rejected despite the successful main candidate
    assert slug == "pr-head-trigger"


def test_failed_trigger_is_not_a_main_source(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="main", conclusion="failure")
    candidates = [_candidate(mod, 999, "success", "main")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NotAMainSource)
    run_id, slug = mod.render_outputs(decision)
    assert run_id == ""
    assert slug == "failed-trigger"


def test_dispatch_yields_no_fallback_without_consulting_the_ledger(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="workflow_dispatch", head_branch="main", conclusion="success")
    candidates = [_candidate(mod, 999, "success", "main")]  # present but must be ignored
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NoFallback)
    run_id, slug = mod.render_outputs(decision)
    assert run_id == ""
    assert slug == "dispatch-no-fallback"


def test_eligible_push_main_resolves_the_success_run_id(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="main", conclusion="success")
    candidates = [_candidate(mod, 555, "success", "main")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.EligibleSource)
    run_id, slug = mod.render_outputs(decision)
    assert run_id == "555"
    assert slug == "eligible-source"


def test_eligible_source_branch_resolves_a_success_run_on_the_source_branch(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="release-1", conclusion="success")
    candidates = [_candidate(mod, 777, "success", "release-1")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.EligibleSource)
    assert mod.render_outputs(decision) == ("777", "eligible-source")


def test_no_success_candidate_yields_no_eligible_source(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="main", conclusion="success")
    candidates = [_candidate(mod, 1, "failure", "main"), _candidate(mod, 2, "cancelled", "main")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NoEligibleSource)
    run_id, slug = mod.render_outputs(decision)
    assert run_id == ""
    assert slug == "no-success-source"


def test_unrelated_branch_success_is_rejected(mod: ModuleType) -> None:
    """INV-B: a success on a branch outside {source, default} never resolves."""
    trigger = _trigger(mod, event="push", head_branch="main", conclusion="success")
    candidates = [_candidate(mod, 888, "success", "some-unrelated-branch")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NoEligibleSource)
    assert mod.render_outputs(decision)[0] == ""  # NOT resolved


def test_red_source_branch_run_is_rejected(mod: ModuleType) -> None:
    """INV-A: a non-success run on the source branch never resolves."""
    trigger = _trigger(mod, event="push", head_branch="release-1", conclusion="success")
    candidates = [_candidate(mod, 444, "failure", "release-1")]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.NoEligibleSource)
    assert mod.render_outputs(decision)[0] == ""  # red run NOT resolved


def test_source_branch_success_is_preferred_over_default_branch_success(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="release-1", conclusion="success")
    candidates = [
        _candidate(mod, 100, "success", "main"),
        _candidate(mod, 200, "success", "release-1"),
    ]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.EligibleSource)
    assert mod.render_outputs(decision)[0] == "200"  # source branch wins over default


def test_default_branch_success_backfills_when_source_branch_has_none(mod: ModuleType) -> None:
    trigger = _trigger(mod, event="push", head_branch="release-1", conclusion="success")
    candidates = [_candidate(mod, 300, "success", "main")]  # no success on release-1
    decision = mod.resolve_source(trigger, candidates, "main")
    assert isinstance(decision, mod.EligibleSource)
    assert mod.render_outputs(decision)[0] == "300"


def test_most_recent_success_on_a_branch_wins(mod: ModuleType) -> None:
    """gh run list returns most-recent first; the first matching success wins."""
    trigger = _trigger(mod, event="push", head_branch="main", conclusion="success")
    candidates = [
        _candidate(mod, 900, "success", "main"),  # most recent
        _candidate(mod, 800, "success", "main"),
    ]
    decision = mod.resolve_source(trigger, candidates, "main")
    assert mod.render_outputs(decision)[0] == "900"


def test_every_variant_maps_to_a_non_empty_slug(mod: ModuleType) -> None:
    """INV-C: run-id='' always co-occurs with a named slug; no silent empty."""
    variants = [
        mod.EligibleSource(run_id=1),
        mod.NoEligibleSource(reason="x"),
        mod.NotAMainSource(reason="x", slug="pr-head-trigger"),
        mod.NoFallback(),
    ]
    for decision in variants:
        _run_id, slug = mod.render_outputs(decision)
        assert slug != ""


# --------------------------------------------------------------------------- #
# Malformed input is the ONLY case that raises (INV-E / NFR-004).              #
# --------------------------------------------------------------------------- #


def test_non_int_database_id_raises_value_error(mod: ModuleType) -> None:
    with pytest.raises(ValueError):
        mod.CandidateRun.from_payload({"databaseId": "not-an-int", "conclusion": "success", "headBranch": "main", "event": "push"})


def test_missing_candidate_field_raises_value_error(mod: ModuleType) -> None:
    with pytest.raises(ValueError):
        mod.CandidateRun.from_payload({"conclusion": "success", "headBranch": "main"})  # no databaseId


def test_boolean_database_id_is_rejected(mod: ModuleType) -> None:
    # bool is an int subclass in Python; a JSON true must not pass as a run id.
    with pytest.raises(ValueError):
        mod.CandidateRun.from_payload({"databaseId": True, "conclusion": "success", "headBranch": "main", "event": "push"})


def test_parse_candidates_rejects_a_non_list(mod: ModuleType) -> None:
    with pytest.raises(ValueError):
        mod.parse_candidates({"databaseId": 1})  # an object, not the expected array


def test_missing_trigger_field_raises_value_error(mod: ModuleType) -> None:
    with pytest.raises(ValueError):
        mod.TriggerMeta.from_payload({"event": "push", "head_branch": "main"})  # no conclusion


# --------------------------------------------------------------------------- #
# Execution-grounded wiring guard (mirror test_aggregate_source.py:146,309).   #
# --------------------------------------------------------------------------- #


def _last_success_step() -> dict:
    workflow = yaml.safe_load(_WORKFLOW.read_text())
    return next(s for s in workflow["jobs"]["collect"]["steps"] if s.get("id") == "last-success")


def test_last_success_step_invokes_the_helper_and_drops_the_inline_decision() -> None:
    run = _last_success_step()["run"]
    assert "scripts/ci/source_eligibility.py" in run
    # The inline shell DECISION logic must be gone — the helper decides now.
    assert "--status success" not in run  # LEAK-A: success filter moved into the helper
    assert "run_id=$(" not in run  # no inline capture-and-branch decision
    assert 'echo "run-id=' not in run  # the helper emits run-id, not the shell
    assert 'if [ -z "$run_id" ]' not in run  # no inline default-branch fallback


def test_workflow_dispatch_gate_and_output_name_are_preserved() -> None:
    step = _last_success_step()
    # NoFallback belt-and-braces: the dispatch gate stays (FR-006).
    assert step["if"] == "github.event_name != 'workflow_dispatch'"
    # download-previous reads steps.last-success.outputs.run-id — name unchanged.
    assert "$GITHUB_OUTPUT" in step["run"]


def test_extracted_last_success_step_emits_empty_run_id_and_named_slug_on_no_source(tmp_path: Path) -> None:
    """Execute the REAL extracted run-block against a stubbed no-source gh.

    An eligible push-main provenance whose ledger holds no success candidate
    must resolve to run-id='' + a named eligibility slug (never a hard exit,
    so reconcile stays the fail-closed terminus — NFR-004).
    """
    run_block = _last_success_step()["run"].replace("${{ github.repository }}", "spec-kitty/spec-kitty")

    # Stub gh: return an inventory with NO eligible (success on {source,default})
    # run, regardless of arguments.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_stub = bin_dir / "gh"
    gh_stub.write_text('#!/usr/bin/env bash\necho \'[{"databaseId": 12, "conclusion": "failure", "headBranch": "main", "event": "push"}]\'\n')
    gh_stub.chmod(0o755)

    output_file = tmp_path / "github_output"
    output_file.touch()
    env = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        GH_TOKEN="stub-token",
        TRIGGER_JSON='{"event": "push", "head_branch": "main", "conclusion": "success"}',
        DEFAULT_BRANCH="main",
        GITHUB_OUTPUT=str(output_file),
    )
    result = subprocess.run(["bash", "-c", run_block], cwd=_REPO_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr

    emitted = dict(line.split("=", 1) for line in output_file.read_text().splitlines() if "=" in line)
    assert emitted.get("run-id") == ""  # no eligible source → empty run-id
    assert emitted.get("eligibility") == "no-success-source"  # named, never silent
    # C-003 / INV-D: the helper writes ONLY run-id + eligibility.
    assert set(emitted) == {"run-id", "eligibility"}


def test_extracted_last_success_step_resolves_a_success_run_id(tmp_path: Path) -> None:
    """The happy path also runs through the real extracted block end to end."""
    run_block = _last_success_step()["run"].replace("${{ github.repository }}", "spec-kitty/spec-kitty")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_stub = bin_dir / "gh"
    gh_stub.write_text('#!/usr/bin/env bash\necho \'[{"databaseId": 4242, "conclusion": "success", "headBranch": "main", "event": "push"}]\'\n')
    gh_stub.chmod(0o755)
    output_file = tmp_path / "github_output"
    output_file.touch()
    env = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        GH_TOKEN="stub-token",
        TRIGGER_JSON='{"event": "push", "head_branch": "main", "conclusion": "success"}',
        DEFAULT_BRANCH="main",
        GITHUB_OUTPUT=str(output_file),
    )
    result = subprocess.run(["bash", "-c", run_block], cwd=_REPO_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    emitted = dict(line.split("=", 1) for line in output_file.read_text().splitlines() if "=" in line)
    assert emitted["run-id"] == "4242"
    assert emitted["eligibility"] == "eligible-source"


def test_fail_closed_guard_step_run_is_byte_identical() -> None:
    """INV-6 / C-001: the reconcile fail-closed guard is a frozen boundary."""
    workflow = yaml.safe_load(_WORKFLOW.read_text())
    guard = next(s for s in workflow["jobs"]["diff-cover"]["steps"] if s.get("name", "").startswith("Fail loudly if the reconciled shard set is incomplete"))
    assert guard["run"] == _FROZEN_GUARD_RUN


def test_helper_module_and_workflow_paths_exist() -> None:
    # Guards against a rename silently orphaning the wiring the tests execute.
    assert _SCRIPT_PATH.exists()
    assert _WORKFLOW.exists()
    assert sys.version_info >= (3, 11)
