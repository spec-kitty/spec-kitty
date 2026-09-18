"""WP03 (#4017): re-assess-under-lock regression coverage.

Companion to ``tests/runtime/test_ensure_runtime_concurrency.py`` (WP01's
flipped interleave test). That module proves the CORE fix (re-assess under
the held lock converges the loser to a no-op + emits the operator signal).
This module covers the remaining WP03 subtasks that need their own,
independent scenarios:

- T009 (FR-003/SC-003): a genuine package-*source* change between assess
  and apply must still be caught -- the fix must not over-narrow away
  legitimate source-drift detection.
- T010 (FR-007 clause b): the LIVE ``managed_skills`` composition apply
  path (``managed_skills.py``'s ``apply_composition``: a ``global_assets``
  ``recheck_assets`` plus ``_recheck_command_completion`` under one lock)
  still succeeds and its #4082 ``recheck_applied()`` YAML-receipt
  suppression still holds -- this path is NOT touched by WP03's fix (it
  never reaches ``bootstrap.ensure_runtime``), so this is a regression
  guard, not a re-assess extension.
- T011 (NFR-002): a warm canonical home performs exactly one assess and
  takes no lock -- instrumented via real call-count spies, not latency.
- T011b (FR-007 clause a / SC-005): the upgrade dry-run preview is
  byte-unchanged by the fix. ``main_callback`` (``specify_cli/__init__.py``)
  early-returns for ``upgrade_intent`` *before* ever calling
  ``ensure_runtime()`` -- proven directly below -- so the preview is
  categorically insulated from WP03's change, and a live dry-run stays
  deterministic across repeats.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli.runtime.asset_preparation as ap
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.bootstrap import assess_runtime, ensure_runtime

pytestmark = [pytest.mark.unit, pytest.mark.fast]

GLOBAL_ASSET_INPUT_CHANGED_SIGNAL = "Global asset input changed"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME`` at a genuinely cold (nonexistent) directory."""
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake package asset root and point discovery at it.

    Mirrors ``tests/runtime/test_bootstrap_unit.py``'s fixture of the same
    name so ``assess_runtime()``/``ensure_runtime()`` can run for real
    without a full installed package layout.
    """
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")

    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")

    (pkg_root / "AGENTS.md").write_text("# Agents")

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


# ---------------------------------------------------------------------------
# T009 -- source-drift guard (FR-003/SC-003)
# ---------------------------------------------------------------------------


class TestSourceDriftStillCaught:
    """Role-tagging (WP02) tolerates DESTINATION drift only; SOURCE drift

    (a genuine package/template file changed between assess and apply)
    must still raise -- both before and after WP03's re-assess-under-lock
    fix, since the fix's re-assess step is only reached once the FIRST
    ``check_assets`` call (computed before any lock, unconditionally) has
    already found the assessment's inputs unchanged.
    """

    def test_genuine_package_source_change_between_assess_and_apply_is_still_caught(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stale_assessment = assess_runtime()
        assert stale_assessment.complete and stale_assessment.effects

        # Genuine SOURCE drift: a package/template asset changes underneath
        # the already-captured assessment, before it is ever applied.
        template = fake_assets / "software-dev" / "templates" / "spec.md"
        original = template.read_bytes()
        template.write_text("mutated package source between assess and apply")
        assert template.read_bytes() != original

        # Every ensure_runtime() call in this test observes the SAME stale,
        # pre-mutation assessment -- exactly what an independent process
        # that assessed before the mutation would carry into its own
        # recheck. The mutation must be caught before WP03's re-assess
        # step is ever reached.
        monkeypatch.setattr(bootstrap, "assess_runtime", lambda **_: stale_assessment)

        with pytest.raises(RuntimeError) as exc_info:
            ensure_runtime()

        message = str(exc_info.value)
        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL in message, f"genuine source drift must still raise the organic #4017 signal, got: {message!r}"
        assert str(template) in message

    def test_source_drift_is_caught_even_though_destination_probe_drift_is_tolerated(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Combine BOTH kinds of drift in one interleave: destination drift

        (a concurrent peer materializing canonical-equal HOME bytes) is
        tolerated per WP02, but source drift in the SAME assessment must
        still refuse the whole batch -- role-tagging must not over-narrow
        when both kinds of drift are present together.
        """
        stale_assessment = assess_runtime()
        assert stale_assessment.complete and stale_assessment.effects

        # A concurrent peer materializes the home for real (destination
        # drift, benign per WP02's role-tagged tolerance)...
        ensure_runtime()
        assert Path(fake_home).is_dir()

        # ...AND the package source ALSO genuinely changed in the same
        # window (source drift, must never be tolerated).
        template = fake_assets / "software-dev" / "templates" / "spec.md"
        template.write_text("mutated package source, concurrently with the peer materializing home")

        monkeypatch.setattr(bootstrap, "assess_runtime", lambda **_: stale_assessment)

        with pytest.raises(RuntimeError) as exc_info:
            ensure_runtime()

        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL in str(exc_info.value)


# ---------------------------------------------------------------------------
# T010 -- FR-007 clause (b): live managed_skills composition apply path
# ---------------------------------------------------------------------------


def _drive_cold_skill_command_composition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Assess + compose a real, cold installation/commands pair.

    Mirrors the DEFAULT-parameter case of
    ``tests.specify_cli.tool_surface.providers.test_managed_skills``'s
    ``_shared_parent_case`` (not imported -- that helper is private to that
    module) at the minimum fidelity T010 needs: a real
    ``prepare_mission_type_activations`` provisioning (its YAML write is
    the #4082 receipt ``_recheck_command_completion`` consults), a real
    ``SkillInstallationAssessment``, and real command effects sharing the
    ``.agents/skills`` parent.
    """
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.skills.registry import SkillRegistry
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider
    from specify_cli.tool_surface.service import build_providers, build_registry

    home = tmp_path / "home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex]\n")

    provisioning = prepare_mission_type_activations(project)
    consent = ApplyConsent(automatic=True)
    root = OperationRoot("project", "project", project)
    registry = SkillRegistry.from_package()
    installation = assess_skill_installation(
        AssessmentInputs(root, projected=provisioning, consent=consent),
        registry,
        ("codex",),
        runtime=True,
        commands=True,
        command_agent_keys=[],
    )
    providers = build_providers()
    builder = SurfacePlanBuilder(build_registry(("codex",)), providers)
    commands = builder.assess(
        ("codex",),
        AssessmentInputs(root, projected=provisioning, consent=consent),
        kinds=(ToolSurfaceKind.COMMAND_SKILL,),
    ).assessments[0]
    assert installation.global_assets.complete and installation.project_skills.complete and commands.complete
    provider = next(p for p in providers if isinstance(p, ManagedSkillsProvider))
    return project, provisioning, consent, installation, commands, provider


class TestManagedSkillsCompositionRegressionFR007ClauseB:
    """FR-007 clause (b): the live ``managed_skills`` composition apply path

    (``apply_composition``: a ``global_assets`` ``recheck_assets`` plus
    ``_recheck_command_completion`` under one held lock) is NOT touched by
    WP03's fix -- it dispatches through ``assess_global_assets``/
    ``recheck_assets`` directly, never through ``bootstrap.ensure_runtime``.
    This is a regression guard proving the #4082 ``recheck_applied()``
    YAML-receipt suppression still holds, driven end to end.
    """

    def test_live_composition_apply_succeeds_and_yaml_receipt_suppression_holds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project, provisioning, consent, installation, commands, provider = _drive_cold_skill_command_composition(tmp_path, monkeypatch)

        composition = provider.compose_installation(installation, commands)
        with provider.preflight_composition(composition, consent) as errors:
            assert not errors, errors
            assert provisioning.apply() is True  # Real YAML write -- #4082's receipt is minted here.
            results = provider.apply_composition(composition, consent)

        assert all(r.outcome in {"applied", "skipped"} for r in results), results
        assert {i for r in results for i in r.succeeded} == {e.id for e in composition.effects}
        assert (project / ".kittify/config.yaml").is_file()

        # A second, ordinary preparation after success must be a true no-op --
        # the #4082 YAML receipt must not force a spurious re-write, and
        # WP03's fix (scoped to bootstrap.ensure_runtime) must not have
        # perturbed this owner's own recheck/apply convergence.
        from specify_cli.skills.command_installer import prepare_commands
        from specify_cli.skills.installer import assess_skill_installation
        from specify_cli.skills.registry import SkillRegistry
        from specify_cli.tool_surface.operations import AssessmentInputs

        ordinary = AssessmentInputs(commands.root, consent=consent)
        next_installation = assess_skill_installation(ordinary, SkillRegistry.from_package(), ("codex",), runtime=True, commands=True, command_agent_keys=[])
        next_commands = prepare_commands(ordinary, ("codex",), prune=True)
        repeat = provider.compose_installation(next_installation, next_commands)
        assert not repeat.effects
        with provider.preflight_composition(repeat, consent) as errors:
            assert not errors, errors
            assert all(r.outcome == "skipped" for r in provider.apply_composition(repeat, consent))


# ---------------------------------------------------------------------------
# T011 -- warm-path spy (NFR-002)
# ---------------------------------------------------------------------------


class TestWarmPathUnaffectedByReassess:
    """The re-assess fix is scoped to the cold/effects path only. On an

    already-warm canonical home, ``ensure_runtime()`` must still perform
    exactly ONE ``assess_runtime()`` call and take NO lock -- instrumented
    via real call-count spies (a structural guarantee), not latency.
    """

    def test_warm_home_takes_exactly_one_assess_and_no_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ensure_runtime()  # cold materialize -- home is now warm/canonical.
        assert Path(fake_home).is_dir()

        real_assess_runtime = bootstrap.assess_runtime
        assess_calls = {"n": 0}

        def _counting_assess(**kwargs: object) -> object:
            assess_calls["n"] += 1
            return real_assess_runtime(**kwargs)

        # WP04: bootstrap._lock_exclusive is retired; the lock is now
        # acquired via asset_preparation's own machine_file_lock name, so
        # count calls to that factory instead of the retired raw helper.
        lock_calls = {"n": 0}
        real_machine_file_lock = ap.machine_file_lock

        def _counting_lock(*args: object, **kwargs: object) -> object:
            lock_calls["n"] += 1
            return real_machine_file_lock(*args, **kwargs)  # pragma: no cover -- must never be reached on warm

        monkeypatch.setattr(bootstrap, "assess_runtime", _counting_assess)
        monkeypatch.setattr(ap, "machine_file_lock", _counting_lock)

        ensure_runtime()

        assert assess_calls["n"] == 1, "warm ensure_runtime() must perform exactly one assess"
        assert lock_calls["n"] == 0, "warm ensure_runtime() must never acquire a lock"

    def test_warm_home_repeat_calls_stay_single_assess_no_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Repeat the warm check across several calls -- never drifts to two."""
        ensure_runtime()

        real_assess_runtime = bootstrap.assess_runtime
        real_machine_file_lock = ap.machine_file_lock
        counts = {"assess": 0, "lock": 0}

        def _counting_assess(**kwargs: object) -> object:
            counts["assess"] += 1
            return real_assess_runtime(**kwargs)

        def _counting_lock(*args: object, **kwargs: object) -> object:
            counts["lock"] += 1
            return real_machine_file_lock(*args, **kwargs)  # pragma: no cover

        monkeypatch.setattr(bootstrap, "assess_runtime", _counting_assess)
        monkeypatch.setattr(ap, "machine_file_lock", _counting_lock)

        for _ in range(3):
            ensure_runtime()

        assert counts["assess"] == 3, "each warm call must be exactly one assess, no accumulation"
        assert counts["lock"] == 0


# ---------------------------------------------------------------------------
# T011b -- FR-007 clause (a): upgrade dry-run preview byte-unchanged
# ---------------------------------------------------------------------------


class TestUpgradeDryRunPreviewInsulatedFromReassess:
    """FR-007 clause (a) / SC-005: the upgrade dry-run repair-disclosure

    preview must be byte-unchanged by WP03's fix. ``main_callback``
    (``specify_cli/__init__.py``) never calls ``ensure_runtime()`` for an
    ``upgrade_intent`` invocation -- it returns immediately, before the
    bootstrap sequence -- so the preview is categorically insulated from
    the changed code. This is proven directly (not inferred) by driving
    the real callback with ``ensure_runtime`` poisoned to raise.
    """

    def test_main_callback_never_bootstraps_for_upgrade_intent(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import click

        from specify_cli import main_callback

        def _poisoned() -> None:
            raise AssertionError("ensure_runtime() must not run for an upgrade_intent invocation")

        monkeypatch.setattr(bootstrap, "ensure_runtime", _poisoned)

        ctx = click.Context(click.Command("spec-kitty"))
        ctx.meta["upgrade_intent"] = object()

        # Must return cleanly -- the poisoned ensure_runtime must never fire.
        main_callback(ctx, version=None)

    def test_live_upgrade_dry_run_preview_is_deterministic_across_repeats(
        self,
        tmp_path: Path,
    ) -> None:
        """Drive the real ``upgrade --dry-run --json`` twice against an

        identical starting state (this worktree's own editable install,
        the canonical test infra already used by
        ``tests/upgrade/test_upgrade_cli_contract.py``) and assert the
        JSON payload is byte-for-byte identical -- the fix must not have
        introduced any instability into a path it never touches.
        """
        from tests.upgrade.preview_support.fixtures import prepare_case

        checkout = Path(__file__).resolve().parents[2]
        if not (checkout / ".venv/bin/spec-kitty").is_file():
            pytest.skip("No editable .venv/bin/spec-kitty available for the live preview drive")

        case = prepare_case(tmp_path / "case", checkout, global_state="G0")
        first = case.run("upgrade", "--dry-run", "--json", "--no-worktrees")
        second = case.run("upgrade", "--dry-run", "--json", "--no-worktrees")

        assert first.returncode == second.returncode == 0, (first, second)
        # #4704 made an explicit ``upgrade --dry-run --json`` query resolve the
        # live latest version, so the preview now legitimately carries a real
        # ``cli.fetched_at`` lookup timestamp that differs between two runs.
        # Everything else must remain identical, so normalize that one volatile
        # field out before asserting the preview is otherwise stable.
        import json

        def _without_fetch_timestamp(raw: str) -> object:
            payload = json.loads(raw)
            cli = payload.get("cli")
            if isinstance(cli, dict):
                cli["fetched_at"] = None
            return payload

        assert _without_fetch_timestamp(first.stdout) == _without_fetch_timestamp(second.stdout), (
            "dry-run preview must be identical across repeats apart from the live fetch timestamp"
        )
