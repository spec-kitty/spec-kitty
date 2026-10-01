"""Shared regression test for the FR-014 next-invocation lifecycle seam.

Mission ``design-phase-orchestrator-api-01M1HE6M``, WP02. Operator ruling
SPEC-FRESH2-001 (``kitty-specs/design-phase-orchestrator-api-01M1HE6M/reviews/
spec.ruling.md``) requires that the ``spec-kitty next --answer`` host-CLI path
and orchestrator-api's future ``answer-decision`` verb (WP08, strictly gated
on this WP) reach the SAME three side effects -- ``pair_previous_lifecycle_
record``, ``emit_mission_next_invoked``, ``write_issuance_lifecycle_record``
-- through one extracted, shared seam (``runtime.next.next_invocation_
lifecycle``) rather than two independently-maintained copies.

:func:`assert_lifecycle_seam_effects` is this WP's own deliverable (spec
SC-008): a caller-agnostic regression helper that fails if EITHER caller
stops writing the mission-events log or the issuance-lifecycle-record store.
WP08 imports and reuses this helper UNMODIFIED against its own
``answer-decision`` verb -- do not change its signature without coordinating
with WP08's author.

The module-level import below is this WP's ATDD RED signal: before T005
lands ``src/runtime/next/next_invocation_lifecycle.py``, this import raises
``ModuleNotFoundError`` at collection time -- a genuine RED (real,
not-yet-built behavior), not a vacuous assertion. A test that only drove the
EXISTING ``next_cmd --answer`` path (which already produces these side
effects via the pre-WP02 inline private functions) would NOT be RED
pre-WP02; the import failure is what makes this WP's ATDD test fail first.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

# --- RED signal (T004): this module does not exist until T005 lands it. ---
from runtime.next.next_invocation_lifecycle import (
    emit_mission_next_invoked,
    pair_previous_lifecycle_record,
    write_issuance_lifecycle_record,
)

from specify_cli import app as cli_app
from specify_cli.invocation.lifecycle import read_lifecycle_records
from specify_cli.mission_v1.events import _read_events

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# Referenced directly (not just imported) so a stale re-export or a renamed
# symbol fails loudly here too, not only via the CLI-path exercise below --
# and so ruff does not flag the RED-signal import as unused.
_SEAM_FUNCTIONS: tuple[Callable[..., Any], ...] = (
    pair_previous_lifecycle_record,
    emit_mission_next_invoked,
    write_issuance_lifecycle_record,
)

_MISSION_SLUG = "042-lifecycle-seam-feature"
_MISSION_TYPE = "lifecycle-seam-input-mission"


def assert_lifecycle_seam_effects(
    feature_dir: Path,
    repo_root: Path,
    mission_slug: str,
    run_action: Callable[[], None],
) -> None:
    """Assert ``run_action`` exercised all three lifecycle-seam side effects.

    ``run_action``: zero-arg callable performing the action under test.
    Agnostic to caller -- a ``next_cmd --answer`` invocation here, an
    orchestrator-api ``answer-decision`` call in WP08's extension.

    Snapshots the mission-events log and the issuance-lifecycle-record store
    before and after ``run_action()``, then asserts (via plain ``assert`` --
    this repo's pytest-native style, no bool return) that:

    1. A ``MissionNextInvoked`` entry was appended to ``mission-events.jsonl``
       (``emit_mission_next_invoked``).
    2. The count of paired (``completed``/``failed``) lifecycle records
       increased (``pair_previous_lifecycle_record`` paired an outstanding
       ``started`` record).
    3. The count of ``started`` lifecycle records increased
       (``write_issuance_lifecycle_record`` wrote a new issuance record).

    A failing assertion here points directly at which of the three seam
    functions regressed -- mission_slug is accepted for symmetry with a
    future caller that needs it to scope its own read, even though the CLI
    path here reads via ``repo_root``/``feature_dir`` alone.
    """
    del mission_slug  # accepted for shape-symmetry with WP08's extension

    events_before = _read_events(feature_dir)
    records_before = read_lifecycle_records(repo_root)
    paired_before = sum(1 for r in records_before if r.phase != "started")
    started_before = sum(1 for r in records_before if r.phase == "started")

    run_action()

    events_after = _read_events(feature_dir)
    records_after = read_lifecycle_records(repo_root)
    paired_after = sum(1 for r in records_after if r.phase != "started")
    started_after = sum(1 for r in records_after if r.phase == "started")

    new_events = events_after[len(events_before) :]
    assert any(e.get("type") == "MissionNextInvoked" for e in new_events), (
        f"expected emit_mission_next_invoked to append a MissionNextInvoked entry; new mission-events.jsonl entries: {new_events!r}"
    )
    assert paired_after > paired_before, (
        f"expected pair_previous_lifecycle_record to pair an outstanding `started` record (paired count {paired_before} -> {paired_after})"
    )
    assert started_after > started_before, (
        f"expected write_issuance_lifecycle_record to write a new `started` record (started count {started_before} -> {started_after})"
    )


# ---------------------------------------------------------------------------
# Fixture-mission builders.
#
# Verbatim-pattern reuse of ``tests/next/test_next_command_integration.py``'s
# proven, real (unmocked) fixture builders -- this repo's own established
# convention for this shape of fixture is to duplicate the helper into each
# consuming test file with an attribution comment (see
# ``tests/runtime/test_bridge_parity.py``'s ``_write_runtime_input_mission``,
# which cites the same origin) rather than import across test-suite
# boundaries. This WP's own mission needs a THREE-step chain (a plain first
# step, then an input-requiring step, then a plain last step) rather than
# the two-step ``tests/next`` fixture: see the ``run_action`` design note
# below for why.
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_project(tmp_path: Path, *, mission_slug: str, mission_type: str) -> Path:
    """Scaffold a minimal spec-kitty project with a mission carrying a real
    ``mission_id`` -- the lifecycle seam's PRIMARY-anchoring reads
    (``resolve_mission_identity(...).mission_id``) are a fail-closed no-op
    without one (FR-004/#2278), which would silently defeat this test.
    """
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    kittify = repo_root / ".kittify"
    kittify.mkdir()
    provision_test_charter(repo_root)

    from specify_cli.identity.project import ensure_identity

    ensure_identity(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_type": mission_type,
                "mission_id": "01HSEAMTESTMISSIONULID0001",
            }
        ),
        encoding="utf-8",
    )
    return repo_root


def _write_three_step_input_mission(repo_root: Path, mission_type: str) -> None:
    """A runtime-only mission: a plain first step, an input-requiring second
    step, then a plain third step.

    Deliberately three steps, not the two-step ``tests/next`` fixture shape:
    the runtime engine only registers a pending decision (and therefore only
    accepts ``--answer`` for it) once a PRIOR ``--result``-bearing call has
    revealed it, and that SAME revealing call unconditionally pairs whatever
    ``started`` record preceded it (``pair_previous_lifecycle_record`` runs
    on every ``--result`` call, before ``decide_next``, regardless of what
    ``decide_next`` returns). So for any acyclic linear mission, "pair an
    outstanding `started`" and "reveal input:<key> as pending" always land
    in the SAME call, and "answer input:<key>" and "write the next `started`"
    always land in a LATER, separate call -- an ``--answer`` call alone never
    produces both a pairing and a new `started` write in one shot. A third
    step (which needs no further input) lets the follow-up bare-result call
    made right after the ``--answer`` call both pair the ``--answer``-issued
    step AND issue the next one, so a single ``run_action`` closure of
    [``--answer`` call, follow-up call] genuinely exercises all three seam
    functions with real, observable deltas -- exactly what this test's
    RED-first discipline needs it to prove (T004 Definition of Done: "a
    behavioral assertion", not exercising a code path that happens to be a
    no-op for the fixture shape chosen).
    """
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "steps:\n"
            "  - id: step_one\n"
            "    title: Step One\n"
            "    description: Plain first step, no input required\n"
            "  - id: collect_input\n"
            "    title: Collect Input\n"
            "    description: Gather required answer\n"
            "    depends_on: [step_one]\n"
            "    requires_inputs: [approval]\n"
            "  - id: execute\n"
            "    title: Execute\n"
            "    depends_on: [collect_input]\n"
            "    description: Proceed with mission\n"
        ),
        encoding="utf-8",
    )
    template_dir = repo_root / ".kittify" / "overrides" / "command-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    for action in ("step_one", "collect_input", "execute"):
        (template_dir / f"{action}.md").write_text(
            f"# {action}\n\nRun the synthetic {action} step for the WP02 seam fixture.\n",
            encoding="utf-8",
        )


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate (verbatim pattern from
    ``tests/next/test_next_command_integration.py``): this fixture stages
    minimal mission state and does not run ``spec-kitty charter sync``, so
    the real preflight gate would otherwise block every advancing call this
    test makes before it ever reaches the seam code under test.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only",
        lambda *_args, **_kwargs: result,
    )


class TestNextAnswerLifecycleSeamEffects:
    """Drives the real ``spec-kitty next --answer`` CLI path (T004 step 3)."""

    def test_answer_path_pairs_and_issues_through_the_shared_seam(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path, mission_slug=_MISSION_SLUG, mission_type=_MISSION_TYPE)
        _write_three_step_input_mission(repo_root, mission_type=_MISSION_TYPE)
        monkeypatch.chdir(repo_root)
        feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
        agent = "wp02-seam-test"

        # --- setup: reach a real pending `decision_required`, outside the
        # measured window (see the fixture builder's docstring for why the
        # pairing of `step_one` is inseparable from revealing the decision).
        issue_step_one = runner.invoke(
            cli_app,
            ["next", "--agent", agent, "--mission", _MISSION_SLUG, "--result", "success", "--json"],
        )
        assert issue_step_one.exit_code == 0, issue_step_one.output
        assert json.loads(issue_step_one.stdout)["kind"] == "step"

        reveal_decision = runner.invoke(
            cli_app,
            ["next", "--agent", agent, "--mission", _MISSION_SLUG, "--result", "success", "--json"],
        )
        assert reveal_decision.exit_code == 0, reveal_decision.output
        decision_payload = json.loads(reveal_decision.stdout)
        assert decision_payload["kind"] == "decision_required"
        decision_id = decision_payload["decision_id"]
        assert decision_id == "input:approval"

        # --- run_action: the real `next --answer` invocation named by T004,
        # followed by the bare advancing call that (per the fixture design
        # note) is where the resulting `started` record actually gets paired
        # alongside the next step's own new `started` write.
        def run_action() -> None:
            answer_result = runner.invoke(
                cli_app,
                [
                    "next",
                    "--agent",
                    agent,
                    "--mission",
                    _MISSION_SLUG,
                    "--result",
                    "success",
                    "--answer",
                    "yes",
                    "--decision-id",
                    decision_id,
                    "--json",
                ],
            )
            assert answer_result.exit_code == 0, answer_result.output
            answered_payload = json.loads(answer_result.stdout)
            assert answered_payload["kind"] == "step"
            assert answered_payload["answered"] == decision_id

            advance_result = runner.invoke(
                cli_app,
                ["next", "--agent", agent, "--mission", _MISSION_SLUG, "--result", "success", "--json"],
            )
            assert advance_result.exit_code == 0, advance_result.output
            assert json.loads(advance_result.stdout)["kind"] == "step"

        assert_lifecycle_seam_effects(feature_dir, repo_root, _MISSION_SLUG, run_action)


# ---------------------------------------------------------------------------
# Direct-call branch coverage (diff-coverage 90% floor on
# ``src/runtime/next/*`` -- ci-quality.yml's ``diff-coverage`` critical-path
# job). The CLI-path test above genuinely exercises the seam end-to-end (the
# WP's own real acceptance evidence) but only walks the "happy" branch of
# each function once; these narrower, direct calls into the public seam
# functions themselves (bypassing the CLI) hit the remaining best-effort
# fail-closed branches -- the owned fork, the placement-seam
# exception guard, a corrupt/legacy meta.json, a non-"success" result, and a
# write failure -- without the overhead of a full CLI+git fixture per case.
# Fixture shape (a bare ``repo_root/kitty-specs/<slug>/meta.json``, no git
# init, no charter) is the verbatim pattern already used the same way by
# ``tests/integration/test_next_lifecycle_records.py``'s ``_setup_mission``
# for the pre-extraction private functions.
# ---------------------------------------------------------------------------


def _setup_mission_dir(repo_root: Path, *, mission_slug: str, mission_id: str | None) -> Path:
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"mission_type": "software-dev"}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


class _FakeArtifact:
    def __init__(self, read_dir: Path) -> None:
        self.read_dir = read_dir


class _FakeMissionContext:
    """Stands in for ``mission_runtime.MissionContext`` on the
    owned fork -- only ``.artifact(kind).read_dir``
    is used by the seam functions."""

    def __init__(self, read_dir: Path) -> None:
        self._read_dir = read_dir

    def artifact(self, _kind: object) -> _FakeArtifact:
        return _FakeArtifact(self._read_dir)


def _owned_stand_in(store_root: Path, mission_dir: Path | None = None) -> Any:
    """A stand-in fact whose owned root is the record store under test.

    These tests exercise the seam functions, not the validator, so a
    ``SimpleNamespace`` carrying just the two fields the seam reads is enough.
    """
    return SimpleNamespace(owned_root=store_root, mission_dir=mission_dir)


class TestSeamFunctionsOwnedFork:
    """WP11: the three functions read the fact's own mission dir on the
    owned fork (WP18 re-pointed these from the retired ``effective_root=``
    keyword to ``owned=``)."""

    def test_pair_previous_lifecycle_record_uses_the_owned_fact(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission_slug = "042-effective-root-mission"
        mission_id = "01HSEAMEFFECTIVEROOTULID01"
        feature_dir = _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=mission_id)
        from specify_cli.invocation.lifecycle import write_started

        write_started(
            tmp_path,
            canonical_action_id="step_one::step_one",
            agent="wp02-direct",
            mission_id=mission_id,
        )

        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: _FakeMissionContext(feature_dir),
        )

        pair_previous_lifecycle_record(
            "wp02-direct",
            mission_slug,
            "success",
            tmp_path,
            owned=_owned_stand_in(tmp_path, feature_dir),
        )

        from specify_cli.invocation.lifecycle import read_lifecycle_records

        records = read_lifecycle_records(tmp_path)
        assert any(r.phase == "completed" for r in records), f"expected the owned fork to still pair the outstanding started record; records={records!r}"

    def test_write_issuance_lifecycle_record_uses_the_owned_fact(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission_slug = "042-effective-root-mission-2"
        mission_id = "01HSEAMEFFECTIVEROOTULID02"
        feature_dir = _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=mission_id)
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: _FakeMissionContext(feature_dir),
        )
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)

        write_issuance_lifecycle_record(
            "wp02-direct",
            mission_slug,
            tmp_path,
            decision,
            owned=_owned_stand_in(tmp_path, feature_dir),
        )

        from specify_cli.invocation.lifecycle import read_lifecycle_records

        records = read_lifecycle_records(tmp_path)
        assert any(r.phase == "started" for r in records), f"expected a started record via the owned fork; records={records!r}"

    def test_emit_mission_next_invoked_uses_the_owned_fact(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission_slug = "042-effective-root-mission-3"
        feature_dir = _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id="01HSEAMEFFECTIVEROOTULID03")
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: _FakeMissionContext(feature_dir),
        )
        decision = SimpleNamespace(
            kind="step",
            action="step_one",
            wp_id=None,
            mission_state="step_one",
            mission=mission_slug,
        )

        emit_mission_next_invoked(
            "wp02-direct",
            "success",
            mission_slug,
            tmp_path,
            decision,
            owned=_owned_stand_in(tmp_path, feature_dir),
        )

        events = _read_events(feature_dir)
        assert any(e.get("type") == "MissionNextInvoked" for e in events), f"expected the owned fork to still emit the event; events={events!r}"


class TestOwnedArm:
    """WP11 T063/T060 (review cycle 1 finding 9): on the owned arm the
    lifecycle store is P's (WP18 retired the legacy ``effective_root=`` mint
    arm and its test)."""

    def test_owned_arm_writes_and_pairs_records_in_the_owned_root_store(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = tmp_path / "R"
        owned_root = tmp_path / "P"
        repo_root.mkdir()
        owned_root.mkdir()
        mission_slug = "042-owned-arm-mission"
        feature_dir = _setup_mission_dir(owned_root, mission_slug=mission_slug, mission_id="01HSEAMOWNEDARMULID0001")
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: _FakeMissionContext(feature_dir),
        )
        owned: Any = SimpleNamespace(owned_root=owned_root, mission_dir=feature_dir)
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)

        write_issuance_lifecycle_record("wp11-agent", mission_slug, repo_root, decision, owned=owned)
        assert [r.phase for r in read_lifecycle_records(owned_root)] == ["started"]
        assert read_lifecycle_records(repo_root) == []

        pair_previous_lifecycle_record("wp11-agent", mission_slug, "success", repo_root, owned=owned)
        assert sorted(r.phase for r in read_lifecycle_records(owned_root)) == ["completed", "started"]
        assert read_lifecycle_records(repo_root) == []


class TestSeamFunctionsFailClosedBranches:
    """Every best-effort ``except``/early-return branch, exercised directly."""

    def test_pair_previous_lifecycle_record_swallows_mission_context_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # Must not raise -- best-effort, fail-closed.
        pair_previous_lifecycle_record("agent", "no-such-mission", "success", tmp_path)

    def test_pair_previous_lifecycle_record_swallows_corrupt_meta(self, tmp_path: Path) -> None:
        mission_slug = "042-corrupt-meta-mission"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

        # Must not raise -- MissionMetaReadError is caught, not propagated.
        pair_previous_lifecycle_record("agent", mission_slug, "success", tmp_path)

    def test_pair_previous_lifecycle_record_noop_without_mission_id(self, tmp_path: Path) -> None:
        mission_slug = "042-legacy-no-mission-id"
        _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=None)

        # Must not raise, and must not write anything (fail-closed, #2278).
        pair_previous_lifecycle_record("agent", mission_slug, "success", tmp_path)

        from specify_cli.invocation.lifecycle import read_lifecycle_records

        assert read_lifecycle_records(tmp_path) == []

    def test_pair_previous_lifecycle_record_non_success_result_writes_failed_phase(self, tmp_path: Path) -> None:
        mission_slug = "042-blocked-result-mission"
        mission_id = "01HSEAMBLOCKEDRESULTULID04"
        _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=mission_id)
        from specify_cli.invocation.lifecycle import (
            read_lifecycle_records,
            write_started,
        )

        write_started(
            tmp_path,
            canonical_action_id="step_one::step_one",
            agent="agent",
            mission_id=mission_id,
        )

        pair_previous_lifecycle_record("agent", mission_slug, "blocked", tmp_path)

        records = read_lifecycle_records(tmp_path)
        paired = [r for r in records if r.phase != "started"]
        assert len(paired) == 1
        assert paired[0].phase == "failed"
        assert paired[0].reason == "blocked"

    def test_write_issuance_lifecycle_record_swallows_mission_context_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)
        write_issuance_lifecycle_record("agent", "no-such-mission", tmp_path, decision)

    def test_write_issuance_lifecycle_record_swallows_corrupt_meta(self, tmp_path: Path) -> None:
        mission_slug = "042-corrupt-meta-mission-2"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)

        write_issuance_lifecycle_record("agent", mission_slug, tmp_path, decision)

    def test_write_issuance_lifecycle_record_noop_without_mission_id(self, tmp_path: Path) -> None:
        mission_slug = "042-legacy-no-mission-id-2"
        _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=None)
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)

        write_issuance_lifecycle_record("agent", mission_slug, tmp_path, decision)

        from specify_cli.invocation.lifecycle import read_lifecycle_records

        assert read_lifecycle_records(tmp_path) == []

    def test_write_issuance_lifecycle_record_swallows_canonical_id_value_error(self, tmp_path: Path) -> None:
        mission_slug = "042-whitespace-action-mission"
        mission_id = "01HSEAMWHITESPACEULID05"
        _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=mission_id)
        # Truthy (non-empty) but whitespace-only after strip -- passes the
        # ``if not action or not mission_state`` guard, then
        # ``make_canonical_action_id`` raises ValueError, which must be
        # swallowed (fail-closed), not propagated.
        decision = SimpleNamespace(action=" ", mission_state="step_one", kind="step", wp_id=None)

        write_issuance_lifecycle_record("agent", mission_slug, tmp_path, decision)

        from specify_cli.invocation.lifecycle import read_lifecycle_records

        assert read_lifecycle_records(tmp_path) == []

    def test_write_issuance_lifecycle_record_swallows_write_started_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission_slug = "042-write-started-oserror-mission"
        mission_id = "01HSEAMOSERRORULID06"
        _setup_mission_dir(tmp_path, mission_slug=mission_slug, mission_id=mission_id)
        monkeypatch.setattr(
            "specify_cli.invocation.lifecycle.write_started",
            lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
        )
        decision = SimpleNamespace(action="step_one", mission_state="step_one", kind="step", wp_id=None)

        # Must not raise -- the lifecycle log is observability only.
        write_issuance_lifecycle_record("agent", mission_slug, tmp_path, decision)

    def test_emit_mission_next_invoked_degrades_feature_dir_to_none_on_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "runtime.next.next_invocation_lifecycle.mission_context_for",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        decision = SimpleNamespace(kind="query", action=None, wp_id=None, mission_state=None, mission="no-such-mission")

        # Must not raise -- degrades to an un-persisted (feature_dir=None)
        # emit_event call rather than propagating.
        emit_mission_next_invoked("agent", "success", "no-such-mission", tmp_path, decision)


# ---------------------------------------------------------------------------
# WP08 extension (design-phase-orchestrator-api-01M1HE6M): the orchestrator-
# api ``answer-decision`` verb (FR-013) is the SECOND caller of this seam.
# SC-008 requires ONE shared regression test that fails if EITHER caller --
# the host CLI's ``next --answer`` above, or this verb -- stops writing the
# mission-events log or the issuance-lifecycle-record store. Reuses
# ``assert_lifecycle_seam_effects`` UNMODIFIED (WP02's own deliverable) and
# the SAME fixture-mission builders above (three-step, input-requiring).
#
# Deliberately does NOT follow the CLI-path test's own [answer call, bare
# follow-up call] shape: a follow-up ``next --result`` CLI call would run
# ITS OWN (CLI-side, unaffected) ``pair_previous_lifecycle_record`` call and
# silently compensate for a broken orchestrator-api-side pairing call --
# defeating exactly the half of SC-008's dual-caller proof this test exists
# to carry (disabling ``answer-decision``'s own seam call must fail THIS
# test without any other caller's call masking it). Instead, mirrors spec
# Acceptance Scenario 7 literally ("a PRIOR issuance's started lifecycle
# record still open, not yet paired") by seeding one directly via
# ``write_started`` (real on-disk I/O, not a mock) BEFORE the single
# measured ``answer-decision`` call -- so that ONE call alone is
# responsible for pairing it (step 2), advancing the DAG (step 3), emitting
# the event (step 4), and writing the next issuance record (step 5), with
# no other caller in the measured window to compensate for a broken step.
# ---------------------------------------------------------------------------

_WP08_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.0.1",
        "agent_family": "claude",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)


class TestAnswerDecisionLifecycleSeamEffects:
    """Drives the real orchestrator-api ``answer-decision`` verb (WP08's own
    T036 RED signal: this command does not exist on ``orchestrator_api.
    commands.app`` until T037/T038 land it -- a genuine Typer "no such
    command" RED, not a vacuous assertion).
    """

    def test_answer_decision_path_pairs_and_issues_through_the_shared_seam(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.invocation.lifecycle import write_started
        from specify_cli.orchestrator_api.commands import app as orchestrator_app

        mission_slug = "042-lifecycle-seam-feature-wp08"
        repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=_MISSION_TYPE)
        _write_three_step_input_mission(repo_root, mission_type=_MISSION_TYPE)
        monkeypatch.chdir(repo_root)
        feature_dir = repo_root / "kitty-specs" / mission_slug
        agent = "wp08-seam-test"

        # --- setup: reach a real pending `decision_required`, outside the
        # measured window -- identical shape to the CLI-path test above.
        issue_step_one = runner.invoke(
            cli_app,
            ["next", "--agent", agent, "--mission", mission_slug, "--result", "success", "--json"],
        )
        assert issue_step_one.exit_code == 0, issue_step_one.output
        assert json.loads(issue_step_one.stdout)["kind"] == "step"

        reveal_decision = runner.invoke(
            cli_app,
            ["next", "--agent", agent, "--mission", mission_slug, "--result", "success", "--json"],
        )
        assert reveal_decision.exit_code == 0, reveal_decision.output
        decision_payload = json.loads(reveal_decision.stdout)
        assert decision_payload["kind"] == "decision_required"
        decision_id = decision_payload["decision_id"]
        assert decision_id == "input:approval"

        # --- Acceptance Scenario 7's literal precondition: a PRIOR issuance's
        # `started` lifecycle record still open (not yet paired) at the
        # moment `answer-decision` is called. `step_one`'s own started
        # record was already paired by `reveal_decision` above (every
        # `--result` call pairs unconditionally, real production behaviour),
        # so seed a SECOND one directly (real on-disk I/O, not a mock) --
        # this is what makes the single `answer-decision` call below solely
        # responsible for pairing it.
        write_started(
            repo_root,
            canonical_action_id="synthetic::prior-open-issuance",
            agent=agent,
            mission_id="01HSEAMTESTMISSIONULID0001",
        )

        # --- run_action: ONLY the orchestrator-api `answer-decision` call
        # under test -- no other caller in the measured window, so a broken
        # seam call on THIS verb cannot be masked by a compensating CLI call.
        def run_action() -> None:
            answer_result = runner.invoke(
                orchestrator_app,
                [
                    "answer-decision",
                    "--mission",
                    mission_slug,
                    "--agent",
                    agent,
                    "--result",
                    "success",
                    "--answer",
                    "yes",
                    "--decision-id",
                    decision_id,
                    "--policy",
                    _WP08_POLICY,
                ],
            )
            assert answer_result.exit_code == 0, answer_result.output
            envelope = json.loads(answer_result.output.strip().split("\n")[0])
            assert envelope["success"] is True, envelope
            answered_data = envelope["data"]
            assert answered_data["kind"] == "step"
            assert answered_data["answered_decision_id"] == decision_id
            assert "answer" not in answered_data

        assert_lifecycle_seam_effects(feature_dir, repo_root, mission_slug, run_action)
