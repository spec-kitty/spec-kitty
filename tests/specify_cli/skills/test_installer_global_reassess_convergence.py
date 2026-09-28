"""#4174 landing-pass Concern 3 (external-caller extension): apply_skill_installation
must converge on a concurrent-peer race, exactly like the three ``ensure_*``
global owners it dispatches through.

``bootstrap.ensure_runtime()`` (and its ``agent_commands.py`` /
``agent_skills.py`` mirrors) re-assess under the held lock before applying,
so a concurrent peer that already materialized the plan converges to a
no-op instead of replaying a stale, non-idempotent create-plan.
``skills/installer.py::apply_skill_installation`` is a DIRECT-CALL boundary
outside that ``ensure_*`` graph: it builds its own ``global_assets``
assessment, calls ``recheck_assets`` + ``apply_assets`` directly, and never
re-assesses. Two independent, concurrent installer invocations racing the
SAME cold home reproduced the residual symptom the #4017 mission notes
recorded: the winner applies first and materializes the global command
bundle for real; the loser's OWN (now-stale) assessment still carries
"create" actions for paths the winner already created, and ``apply_assets``
replayed them non-idempotently -- ``mkdir()`` raised ``FileExistsError``
("File exists"), surfaced as a ``global_asset_write_failed`` diagnostic.

This module isolates the race to the GLOBAL side only (project skill
selection is empty, producing zero project effects, so
``recheck_project_skills`` never has state of its own to race on) and drives
the fix: ``apply_skill_installation`` gains an optional
``rebuild_global_assets`` callable that, mirroring
``asset_preparation.apply_with_reassess``, re-assesses the GLOBAL half
under the held lock and converges to a no-op when the peer already did the
work -- without touching the project half's own, unrelated
``recheck_project_skills`` boundary or its strict object-identity contract
with ``apply_project_skills``.

**#5279 re-pin.** Commit ``ed6d34e75`` ("fix(local-write-safety): symlink-safe
locks, atomic decision index, non-destructive init, 0600 credentials",
#4756 WP02) separately hardened ``asset_preparation._write_asset`` to
tolerate a ``FileExistsError`` on a directory ``mkdir()`` when the
already-present path is an ordinary, non-symlink directory -- exactly the
shape this race hits for directory-creation effects. Bisected via
``git archive`` snapshots of ``ed6d34e75`` and its parent: the ORIGINAL
(pre-#5279) version of this file's ``..._still_crashes_the_loser`` test
passes unmodified at the parent (the crash still fires, so the test
asserting it fires passes) and fails at ``ed6d34e75`` itself (the loser's
own ``apply_skill_installation`` call, with NO ``rebuild_global_assets``,
now comes back all-``applied`` -- the crash this test pinned no longer
occurs). The WITHOUT-rebuild test below is therefore RE-PINNED to the new
converges-too contract rather than deleted -- deleting it would leave
nothing proving the loser's outcome, and the ``rebuild_global_assets`` seam
this module still adds remains real and exercised: it is the general
convergence mechanism for races ``_write_asset``'s directory-only tolerance
does not cover (e.g. file-content effects), proven below by a call-count
spy on the with-rebuild test.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from specify_cli.skills.installer import apply_skill_installation, assess_skill_installation
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
from tests.upgrade.preview_support.snapshot import Snapshot, snapshot

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _mtime_neutral(snap: Snapshot) -> Snapshot:
    """Drop ``mtime_ns`` so two snapshots can be compared for byte/mode
    identity without caring which one is physically newer on disk."""
    return {key: dataclasses.replace(node, mtime_ns=None) for key, node in snap.items()}


@pytest.fixture
def owner_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    return home


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


def _build(inputs: AssessmentInputs, registry: SkillRegistry):
    """Isolate the race to the GLOBAL commands family: an empty skill
    selection produces zero project effects, so the project half never has
    state of its own to race on.
    """
    return assess_skill_installation(
        inputs,
        registry,
        (),
        commands=True,
        command_agent_keys=["claude"],
        persist_manifest=False,
    )


class TestApplySkillInstallationConcurrentPeerConvergence:
    def test_without_rebuild_a_concurrent_peer_now_also_converges(
        self,
        owner_home: Path,
        project: Path,
    ) -> None:
        """RE-PIN (bisected to ``ed6d34e75``, #5279 -- see module docstring
        for the ``git archive`` bisection evidence): ``_write_asset``'s
        directory-``mkdir`` ``FileExistsError`` tolerance (#4756 WP02) means
        the loser's stale "create" replay for a directory effect no longer
        crashes even WITHOUT ``rebuild_global_assets``. The loser must
        converge, and the tree it produces must be byte-identical to the one
        the winner already materialized -- proving this is real convergence,
        not merely "didn't raise".
        """
        consent = ApplyConsent(automatic=True)
        inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
        registry = SkillRegistry.from_package()

        winner = _build(inputs, registry)
        loser = _build(inputs, registry)
        assert winner.global_assets.complete and winner.global_assets.effects
        assert loser.project_skills.complete and not loser.project_skills.effects, (
            "fixture must isolate the race to the global side -- project effects must be empty"
        )

        winner_results = apply_skill_installation(winner, consent)
        assert all(r.outcome in {"applied", "skipped"} for r in winner_results), winner_results
        winner_tree = _mtime_neutral(snapshot({"home": owner_home}))

        loser_results = apply_skill_installation(loser, consent)

        assert all(r.outcome in {"applied", "skipped"} for r in loser_results), loser_results
        # Non-vacuity: the stale replay really ran and was tolerated -- a loser
        # that skipped every action would also leave the winner's tree intact.
        assert any(r.outcome == "applied" for r in loser_results), loser_results
        loser_tree = _mtime_neutral(snapshot({"home": owner_home}))
        assert loser_tree == winner_tree, "the loser's replay must converge to the SAME installed tree the winner produced"

    def test_with_rebuild_a_concurrent_peer_converges_to_a_no_op(
        self,
        owner_home: Path,
        project: Path,
    ) -> None:
        """GREEN: passing rebuild_global_assets converges the loser instead
        of replaying its stale plan. A call-count spy proves the seam is
        actually invoked (never merely accepted as a no-op parameter) --
        mirrors ``test_rebuild_is_never_invoked_on_a_genuinely_cold_install``'s
        spy style below.
        """
        consent = ApplyConsent(automatic=True)
        inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
        registry = SkillRegistry.from_package()

        winner = _build(inputs, registry)
        loser = _build(inputs, registry)

        winner_results = apply_skill_installation(winner, consent)
        assert all(r.outcome in {"applied", "skipped"} for r in winner_results), winner_results

        calls = {"n": 0}

        def _counting_rebuild():
            calls["n"] += 1
            return _build(inputs, registry).global_assets

        loser_results = apply_skill_installation(
            loser,
            consent,
            rebuild_global_assets=_counting_rebuild,
        )

        assert all(r.outcome in {"applied", "skipped"} for r in loser_results), loser_results
        assert calls["n"] == 1, "rebuild_global_assets must be invoked exactly once to converge the loser"

    def test_rebuild_is_never_invoked_on_a_genuinely_cold_install(
        self,
        owner_home: Path,
        project: Path,
    ) -> None:
        """The warm/no-race fast path must not be perturbed: on a genuinely
        cold, uncontested install, ``rebuild_global_assets`` still converges
        (there is no peer, so the SECOND assess -- taken under the lock --
        will just be another equally-cold plan, applied normally).
        """
        consent = ApplyConsent(automatic=True)
        inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
        registry = SkillRegistry.from_package()

        calls = {"n": 0}

        def _counting_rebuild():
            calls["n"] += 1
            return _build(inputs, registry).global_assets

        installation = _build(inputs, registry)
        results = apply_skill_installation(installation, consent, rebuild_global_assets=_counting_rebuild)

        assert all(r.outcome in {"applied", "skipped"} for r in results), results
        assert calls["n"] == 1, "rebuild must run exactly once under the held lock on a genuinely cold install"
