"""WP04 (#4017): generic-scope VERIFICATION for the "Generic -- all owners" ruling.

WP03 already landed the SOURCE fix (re-assess-under-lock + torn-read retry +
destination role-tagging) generically across every global asset owner --
``bootstrap.ensure_runtime`` (the runtime owner), and
``agent_commands.ensure_global_agent_commands`` /
``agent_skills.ensure_global_agent_skills`` (the two NON-runtime owners) --
and drove both quarantined e2e tests green. This module does not change any
production code (``owned_files`` is this file only); it independently proves
two remaining claims from the mission spec's FR-004/SC-006:

- T012: the SAME deterministic loser/winner interleave that
  ``tests/runtime/test_ensure_runtime_concurrency.py`` uses to prove
  ``ensure_runtime()`` (the RUNTIME owner) converges also converges for a
  genuine NON-runtime owner -- ``agent_skills.ensure_global_agent_skills()``
  and ``agent_commands.ensure_global_agent_commands()`` -- via their own
  re-assess-under-lock mirrors (``agent_skills.py:286-308``,
  ``agent_commands.py:377-399``). It also determines, empirically rather than
  by assumption, whether "the merge.py:94 recheck nesting" is reachable from
  the ``global_assets`` BATCH path at all (it is not -- see
  ``TestMergePyNestingReachabilityFromTheBatch`` below for the mechanism and
  why the existing ``test_ensure_runtime_concurrency.py`` coverage is the
  correct home for that nesting instead).
- T013: whether ``managed_skills.py``'s SEPARATE
  ``_recheck_command_completion`` (line 165, added by #4082's
  ``recheck_applied()`` idempotency) is *also* race-safe against a genuine
  concurrent peer, or whether it is a distinct, uncovered race surface. It is
  the latter -- driven and confirmed below, with the concrete root cause
  recorded rather than silently assumed away (FR-004's explicit instruction).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
from specify_cli.runtime.agent_commands import ensure_global_agent_commands
from specify_cli.runtime.agent_skills import ensure_global_agent_skills
from specify_cli.skills.registry import SkillRegistry

if TYPE_CHECKING:
    from charter.activation.compiler import _PreparedMissionTypeActivations
    from specify_cli.skills.installer import SkillInstallationAssessment
    from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment
    from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Same witness substrings as tests/runtime/test_ensure_runtime_concurrency.py
# and tests/runtime/test_reassess_under_lock.py -- pinned so a regression in
# EITHER non-runtime owner reproduces the exact #4017 signal, never a
# different message that would silently escape these assertions.
GLOBAL_ASSET_INPUT_CHANGED_SIGNAL = "Global asset input changed"
GLOBAL_ASSET_WRITE_FAILED_SIGNAL = "global_asset_write_failed"
TORN_READ_SIGNAL = "Asset changed during preparation"
CONCURRENT_PEER_NO_OP_SIGNAL = "already materialized by a concurrent peer; nothing applied"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME`` (and ``HOME``) at a genuinely cold home."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    return home


@pytest.fixture()
def fake_package_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake package asset root for the RUNTIME family, mirroring the
    identically-named fixture in ``test_ensure_runtime_concurrency.py`` /
    ``test_reassess_under_lock.py`` -- only needed by the merge.py
    reachability test below, which must include ``runtime=True`` in the
    batch to observe how ``assess_global_assets()`` tags its ``owner_key``.
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


@pytest.fixture()
def fake_skill_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillRegistry:
    """A minimal real canonical skill registry, mirroring
    ``tests/runtime/test_agent_skills.py``'s fixture pattern -- lets
    ``agent_skills.assess_global_agent_skills()``/``ensure_global_agent_skills()``
    run for real against a tiny, deterministic catalog instead of the full
    package registry.
    """
    skills_root = tmp_path / "doctrine_skills"
    skill_dir = skills_root / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: spec-kitty-test-skill\ndescription: test\n---\n# test\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_root)
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: registry)
    return registry


# ---------------------------------------------------------------------------
# T012 -- non-runtime owner concurrency (FR-004/SC-006)
# ---------------------------------------------------------------------------


class TestNonRuntimeOwnerConcurrentColdHomeInterleave:
    """The exact deterministic loser/winner interleave from
    ``test_ensure_runtime_concurrency.py``'s
    ``TestEnsureRuntimeConcurrentColdHomeInterleave``, replayed against BOTH
    non-runtime global owners. Each owner's own ``ensure_*`` re-assesses
    under its own held lock (``agent_skills.py:296``,
    ``agent_commands.py:388``), mirroring ``bootstrap.ensure_runtime()``'s
    fix exactly -- these tests prove that mirror actually converges rather
    than merely reading as though it should.
    """

    def test_agent_skills_loser_reassess_against_materialized_home_converges(
        self,
        fake_home: Path,
        fake_skill_registry: SkillRegistry,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        assert not fake_home.exists(), "fixture must start genuinely cold"
        real_assess_global_assets = asset_preparation.assess_global_assets

        # --- Arrange: the loser observes the shared home while cold. ---
        # agent_skills.ensure_global_agent_skills() dispatches through
        # asset_preparation.assess_global_assets(runtime=False, commands=False)
        # (agent_skills.py:281/297), never bootstrap.assess_runtime -- this is
        # a genuinely NON-runtime owner's own assess entry point.
        loser_stale_assessment = real_assess_global_assets(runtime=False, commands=False)
        assert loser_stale_assessment.complete
        assert loser_stale_assessment.effects, (
            "a cold home must produce a non-empty create-plan; an empty-effects plan would take the warm fast-path and could never observe the race"
        )

        # --- Act (winner): materialize the home for real. ---
        ensure_global_agent_skills()
        assert fake_home.is_dir(), "winner must have materialized the shared home"

        # --- Act (loser): force the deterministic interleave -- the SAME
        # mechanism as test_ensure_runtime_concurrency.py, just intercepting
        # asset_preparation.assess_global_assets (the seam this non-runtime
        # owner's ensure_* calls) instead of bootstrap.assess_runtime.
        calls = {"n": 0}

        def _fake_assess_global_assets(**kwargs: object) -> object:
            calls["n"] += 1
            if calls["n"] == 1:
                return loser_stale_assessment
            return real_assess_global_assets(**kwargs)

        monkeypatch.setattr(asset_preparation, "assess_global_assets", _fake_assess_global_assets)

        with caplog.at_level("INFO", logger=agent_skills.logger.name):
            ensure_global_agent_skills()  # must NOT raise

        assert calls["n"] >= 2, "the fix must re-assess under the held lock, not just once up front"
        joined = "\n".join(caplog.messages)
        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL not in joined
        assert GLOBAL_ASSET_WRITE_FAILED_SIGNAL not in joined
        assert TORN_READ_SIGNAL not in joined
        assert CONCURRENT_PEER_NO_OP_SIGNAL in joined, f"expected the OPERATOR_SIGNAL_CONTRACT sentence on the converged-no-op path, got: {caplog.messages!r}"

    def test_agent_commands_loser_reassess_against_materialized_home_converges(
        self,
        fake_home: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        assert not fake_home.exists(), "fixture must start genuinely cold"
        real_assess = agent_commands.assess_global_agent_commands

        # --- Arrange: the loser observes the shared home while cold. This
        # owner's ensure_* re-assesses through its OWN module-level
        # assess_global_agent_commands() (agent_commands.py:412-415), not
        # asset_preparation.assess_global_assets -- a different seam from the
        # agent_skills case above, deliberately, to prove the fix is generic
        # rather than accidentally reusing one working code path twice.
        # WP06 (#6470) re-pin: the no-argument ensure_global_agent_commands()
        # is now scoped to the project at the working directory, so this
        # test names one agent explicitly on both sides; the convergence it
        # pins does not depend on the agent set.
        loser_stale_assessment = real_assess(agent_keys=["claude"])
        assert loser_stale_assessment.complete
        assert loser_stale_assessment.effects, (
            "a cold home must produce a non-empty create-plan; an empty-effects plan would take the warm fast-path and could never observe the race"
        )

        # --- Act (winner): materialize the home for real. ---
        ensure_global_agent_commands(agent_keys=["claude"])
        assert fake_home.is_dir(), "winner must have materialized the shared home"

        # --- Act (loser): force the deterministic interleave. ---
        calls = {"n": 0}

        def _fake_assess(**kwargs: object) -> object:
            calls["n"] += 1
            if calls["n"] == 1:
                return loser_stale_assessment
            return real_assess(**kwargs)

        monkeypatch.setattr(agent_commands, "assess_global_agent_commands", _fake_assess)

        with caplog.at_level("INFO", logger=agent_commands.logger.name):
            ensure_global_agent_commands(agent_keys=["claude"])  # must NOT raise

        assert calls["n"] >= 2, "the fix must re-assess under the held lock, not just once up front"
        joined = "\n".join(caplog.messages)
        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL not in joined
        assert GLOBAL_ASSET_WRITE_FAILED_SIGNAL not in joined
        assert TORN_READ_SIGNAL not in joined
        assert CONCURRENT_PEER_NO_OP_SIGNAL in joined, f"expected the OPERATOR_SIGNAL_CONTRACT sentence on the converged-no-op path, got: {caplog.messages!r}"


class TestMergePyNestingReachabilityFromTheBatch:
    """T012's second clause: is "the merge.py:94 recheck nesting"
    (``runtime/merge.py``'s ``_merge_prepared_assets``, entered from
    ``asset_preparation.apply_assets`` when ``owner_key == "runtime_bootstrap"``)
    reachable from the ``assess_global_assets()`` BATCH path (the thing this
    module's other tests, and #4017's "generic -- all owners" framing, are
    about)?

    Empirically: no. ``_GlobalAssetPreparation.finish()``
    (``asset_preparation.py:517``) unconditionally stamps
    ``owner_key="global_assets"`` on EVERY assessment produced through
    ``assess_global_assets()``, including a runtime-only batch of one family
    -- ``apply_assets()``'s ``if assessment.owner_key == "runtime_bootstrap"``
    gate (``asset_preparation.py:711``) can therefore never fire for a batch
    assessment. It only fires for the STANDALONE
    ``bootstrap.assess_runtime()`` object ``ensure_runtime()`` builds and
    applies directly (never wrapped in a batch) -- a path already driven
    concurrently by ``test_ensure_runtime_concurrency.py`` (WP01/WP03). This
    class proves the negative directly (real objects, not source-text
    matching) so the absence is evidenced, not assumed.
    """

    def test_batch_owner_key_is_never_runtime_bootstrap(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        fake_skill_registry: SkillRegistry,
    ) -> None:
        assessment = asset_preparation.assess_global_assets(runtime=True, commands=False, skills=True)
        assert assessment.complete, assessment.diagnostics
        assert assessment.owner_key == "global_assets"
        assert assessment.owner_key != "runtime_bootstrap"

    def test_apply_assets_never_dispatches_to_merge_py_for_a_batch_assessment(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        fake_skill_registry: SkillRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Directly applying a real, cold, runtime-including BATCH assessment
        must complete via the ordinary retained-asset writer
        (``_apply_retained_assets``), never touching
        ``bootstrap.populate_from_package`` / ``runtime.merge`` at all.
        """
        import specify_cli.runtime.bootstrap as bootstrap
        from specify_cli.tool_surface.operations import ApplyConsent

        def _poisoned(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("populate_from_package/merge.py must not be reached from a batch assessment")

        monkeypatch.setattr(bootstrap, "populate_from_package", _poisoned)

        assessment = asset_preparation.assess_global_assets(runtime=True, commands=False, skills=True)
        assert assessment.complete and assessment.effects

        result = asset_preparation.apply_assets(assessment, ApplyConsent(automatic=True))

        assert result.outcome == "applied", result.diagnostics


# ---------------------------------------------------------------------------
# T013 -- _recheck_command_completion concurrent-peer verdict (FR-004)
# ---------------------------------------------------------------------------


def _assess_cold_managed_skills_composition(
    project: Path,
) -> tuple[
    _PreparedMissionTypeActivations,
    ApplyConsent,
    SkillInstallationAssessment,
    OwnerAssessment,
    ManagedSkillsProvider,
]:
    """Build one real, cold ``SkillCommandComposition`` for a "codex" project.

    Mirrors ``test_reassess_under_lock.py``'s
    ``_drive_cold_skill_command_composition`` at the fidelity T013 needs, but
    factored so the SAME still-cold ``project``/environment can be assessed
    TWICE independently (an environment-setup/assess-call split that helper
    does not offer, since it also creates the home/project directories).
    """
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.skills.registry import SkillRegistry
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider
    from specify_cli.tool_surface.service import build_providers, build_registry

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
    return provisioning, consent, installation, commands, provider


class TestRecheckCommandCompletionConcurrentPeerVerdict:
    """T013 (FR-004): ``managed_skills.py``'s ``_recheck_command_completion``
    (line 165) is explicitly called out in the spec as a SEPARATE recheck
    from ``asset_preparation.check_assets`` -- it never calls it, and #4082
    gave it its own ``recheck_applied()`` idempotency for the provisioning
    YAML write specifically. WP03's re-assess-under-lock fix never touched
    this function or its caller (``ManagedSkillsProvider.apply_composition``,
    which dispatches to the project-skill-installer surface, not to any of
    the three ``ensure_*`` global owners WP03 fixed).

    VERDICT (recorded here rather than assumed): it still races against a
    genuine concurrent peer, for a DIFFERENT and more fundamental reason than
    the #4017 stale-observation race WP02/WP03 fixed. The command-skills
    manifest (``.kittify/command-skills-manifest.json``) that
    ``command_installer`` builds embeds a wall-clock ``installed_at``
    timestamp per entry, so two independently-computed "canonical" batches
    for the exact same cold project NEVER produce byte-identical manifest
    content -- there is no role-tagged/canonical-content tolerance (WP02's
    fix) that could converge this, because the two sides' "canonical" bytes
    genuinely differ by design, not merely by a transient stale read. The
    test below drives this empirically (real installer, real filesystem, two
    independently-built compositions against the same cold project) and pins
    the CURRENT behavior -- a raised ``ValueError`` -- as a confirmed,
    scoped-out-of-WP04 finding, not a silent assumption of safety.

    Scoped follow-up recorded for the operator: `_recheck_command_completion`
    (and/or the manifest writer feeding it) needs either (a) an
    ``installed_at``-tolerant content comparison analogous to WP02's
    ``_content_equal``, or (b) its own re-assess-under-lock mirror, before
    the concurrent-installer race this WP intentionally scoped as "generic
    -- all owners" can be called closed for the managed-skills composition
    path specifically. This is out of WP04's ``tests/runtime/`` scope
    (owned_files is this test file only; the fix belongs to
    ``src/specify_cli/tool_surface/providers/managed_skills.py`` and/or
    ``src/specify_cli/skills/command_installer.py``, neither of which WP04
    may edit).
    """

    def test_concurrent_peer_manifest_timestamp_still_races(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from specify_cli.tool_surface.providers.managed_skills import _recheck_command_completion

        home = tmp_path / "home"
        home.mkdir()
        for key in ("HOME", "USERPROFILE"):
            monkeypatch.setenv(key, str(home))
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
        project = tmp_path / "project"
        config = project / ".kittify/config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("agents:\n  available: [codex]\n")

        # --- Two independent, concurrent processes each assess the SAME
        # still-cold project. Both computed compositions are structurally
        # equal (same catalog, same target bytes) but object-distinct --
        # exactly like two real concurrent `spec-kitty init`-style
        # invocations racing on one fresh project.
        _, consent, installation_loser, commands_loser, provider = _assess_cold_managed_skills_composition(project)
        composition_loser = provider.compose_installation(installation_loser, commands_loser)
        assert composition_loser.parents, "fixture must exercise a genuinely shared parent (.agents/.agents/skills)"

        provisioning_winner, _, installation_winner, commands_winner, _ = _assess_cold_managed_skills_composition(project)
        composition_winner = provider.compose_installation(installation_winner, commands_winner)

        # --- Winner applies for real, materializing the shared parents and
        # the command-skills manifest with ITS OWN installed_at timestamp.
        with provider.preflight_composition(composition_winner, consent) as errors:
            assert not errors, errors
            assert provisioning_winner.apply() is True
            results = provider.apply_composition(composition_winner, consent)
        assert all(r.outcome in {"applied", "skipped"} for r in results), results

        # --- Loser: drive the SEPARATE _recheck_command_completion directly
        # against ITS OWN (now-stale) composition, with an honest empty
        # `created` dict -- this loser process performed no mkdir of its own
        # for a shared parent a concurrent peer already materialized, so it
        # never populated its own _record_command_parent_creations() receipt
        # for that path either.
        with pytest.raises(ValueError) as exc_info:
            _recheck_command_completion(composition_loser, {})

        # The loser's provisioning now creates the activation ledger
        # (``.kittify/charter/activation.yaml``, absent on a cold project), so
        # its never-applied YAML write is rechecked first and refuses for want
        # of a completion receipt; before the ledger it rewrote the existing
        # ``config.yaml`` and the command-output check refused instead. Either
        # refusal is the loser failing closed against the peer's landing; the
        # manifest-content gap itself is pinned by the root-cause check below.
        message = str(exc_info.value)
        race_signatures = ("Completed command output changed", "precondition_changed: YAML write has no completion receipt")
        assert message.startswith(race_signatures), f"expected the loser to refuse against the peer's landing (confirming the race), got: {message!r}"

        # Root-cause confirmation: the two sides' own planned manifest bytes
        # for the identical logical outcome genuinely differ (not a filesystem
        # race window) -- proving this is a content-generation gap, not a
        # timing fluke this test got unlucky with.
        def _manifest_sha(commands: OwnerAssessment) -> str | None:
            for effect in commands.effects:
                if effect.destination.name == "command-skills-manifest.json":
                    sha256 = effect.after.sha256
                    return sha256 if isinstance(sha256, str) else None
            return None

        loser_sha = _manifest_sha(commands_loser)
        winner_sha = _manifest_sha(commands_winner)
        assert loser_sha is not None and winner_sha is not None
        assert loser_sha != winner_sha, (
            "expected the two independently-assessed manifests to differ by "
            "installed_at alone -- if they now match, #4082/a later change "
            "may have already made the manifest content-deterministic and "
            "this recorded race may be stale; re-verify before trusting the "
            "scoped follow-up above"
        )
