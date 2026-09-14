"""Coverage-focused unit tests for the internalized mission runtime.

These tests target the code paths under
``src/specify_cli/next/_internal_runtime/`` that the parity / decision /
runtime-bridge / query-mode suites do not exercise. The goal is to push
``_internal_runtime`` line coverage to >=90% (NFR-001 of mission
``shared-package-boundary-cutover-01KQ22DS``).

These are pure unit tests — no subprocess, no network, no wall-clock
sensitivity. They drive each module's public surface with carefully
constructed in-memory inputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from pydantic import ValidationError

from kernel.clock import now_utc, now_utc_iso
from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    MissionRunRef,
    NextDecision,
    NullEmitter,
    next_step,
    provide_decision_answer,
    start_mission_run,
)
from runtime.next._internal_runtime import contracts as contracts_mod
from runtime.next._internal_runtime import discovery as discovery_mod
from runtime.next._internal_runtime import emitter as emitter_mod
from runtime.next._internal_runtime import engine as engine_mod
from runtime.next._internal_runtime import events as events_mod
from runtime.next._internal_runtime import lifecycle as lifecycle_mod
from runtime.next._internal_runtime import models as models_mod
from runtime.next._internal_runtime import planner as planner_mod
from runtime.next._internal_runtime import raci as raci_mod
from runtime.next._internal_runtime import schema as schema_mod
from runtime.next._internal_runtime import significance as sig_mod
from runtime.next._internal_runtime.contracts import RemediationPayload
from runtime.next._internal_runtime.discovery import (
    DiscoveryResult,
    DiscoveryWarning,
    ShadowEntry,
    ShadowingDiagnostics,
    diagnose_shadowing,
    discover_missions,
    discover_missions_with_warnings,
    load_mission_template,
)
from runtime.next._internal_runtime.engine import (
    TransitionGate,
    notify_decision_timeout,
    resolve_context,
    validate_binding,
)
from runtime.next._internal_runtime.events import JsonlEventLog
from runtime.next._internal_runtime.planner import plan_next, serialize_decision
from runtime.next._internal_runtime.raci import (
    infer_raci,
    resolve_raci,
    validate_raci_assignment,
)
from runtime.next._internal_runtime.schema import (
    ActorIdentity,
    AuditConfig,
    AuditStep,
    ContextType,
    ContextTypeRegistry,
    DecisionAnswer,
    DecisionRequest,
    MissionMeta,
    MissionRunSnapshot,
    MissionRuntimeError,
    MissionTemplate,
    PromptStep,
    RACIAssignment,
    RACIRoleBinding,
    ResolvedRACIBinding,
    StepContextContract,
    load_mission_template_file,
)
from runtime.next._internal_runtime.significance import (
    DEFAULT_BANDS,
    HARD_TRIGGER_REGISTRY,
    DimensionScoreOverride,
    HardTriggerClass,
    RoutingBand,
    SignificanceDimension,
    SignificanceScore,
    SoftGateDecision,
    TimeoutPolicy,
    compute_escalation_targets,
    evaluate_significance,
    make_routing_bands,
    parse_band_cutoffs_from_policy,
    parse_timeout_from_policy,
    resolve_hard_triggers,
    validate_band_cutoffs,
    validate_dimension_scores,
)


# ---------------------------------------------------------------------------
# Helpers: build a writable mission template + project directory
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _write_simple_mission(root: Path, key: str = "cov-mission") -> Path:
    """Write a minimal mission template at ``<root>/<key>/mission.yaml``."""
    mission_dir = root / key
    mission_dir.mkdir(parents=True, exist_ok=True)
    mission_yaml = mission_dir / "mission.yaml"
    mission_yaml.write_text(
        yaml.safe_dump(
            {
                "mission": {
                    "key": key,
                    "name": "Coverage Mission",
                    "version": "1.0.0",
                },
                "steps": [
                    {
                        "id": "discover",
                        "title": "Discover",
                        "description": "Initial discovery step.",
                        "prompt": "Run discovery.",
                        "requires_inputs": ["topic"],
                    },
                    {
                        "id": "specify",
                        "title": "Specify",
                        "depends_on": ["discover"],
                        "description": "Spec step.",
                        "prompt": "Write the spec.",
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return mission_yaml


def _make_simple_template() -> MissionTemplate:
    return MissionTemplate(
        mission=MissionMeta(key="t", name="T", version="1.0.0"),
        steps=[
            PromptStep(id="s1", title="Step 1", prompt="Do 1."),
            PromptStep(
                id="s2", title="Step 2", depends_on=["s1"], prompt="Do 2."
            ),
        ],
        audit_steps=[],
    )


# ---------------------------------------------------------------------------
# Re-export modules: emitter / lifecycle / models
# ---------------------------------------------------------------------------


def test_emitter_module_re_exports() -> None:
    assert emitter_mod.NullEmitter is events_mod.NullEmitter
    assert emitter_mod.RuntimeEventEmitter is events_mod.RuntimeEventEmitter
    assert emitter_mod.runtime_emitter_for_mission is events_mod.runtime_emitter_for_mission
    assert (
        emitter_mod.register_runtime_emitter_factory
        is events_mod.register_runtime_emitter_factory
    )
    assert emitter_mod.reset_runtime_emitter_factory is events_mod.reset_runtime_emitter_factory
    assert set(emitter_mod.__all__) == {
        "NullEmitter",
        "RuntimeEventEmitter",
        "runtime_emitter_for_mission",
        "register_runtime_emitter_factory",
        "reset_runtime_emitter_factory",
    }
    for name in emitter_mod.__all__:
        assert name in events_mod.__all__, name


# ---------------------------------------------------------------------------
# Runtime emitter seam: factory, registry, NullEmitter.for_mission
# (contracts/emitter-seam.md rules S1-S6, mission dead-port-disposition-01M1VRA2)
# ---------------------------------------------------------------------------

_SEAM_KWARGS: dict[str, str] = {"mission_slug": "m", "mission_type": "software-dev"}
_MISSION_ULID = "01KT3YBDABCDEFGHIJKLMNOP"


@pytest.fixture
def clean_emitter_factory() -> Any:
    """Guarantee no registered factory leaks into or out of a seam test (S4)."""
    events_mod.reset_runtime_emitter_factory()
    yield
    events_mod.reset_runtime_emitter_factory()


@pytest.mark.usefixtures("clean_emitter_factory")
def test_factory_returns_null_emitter_by_default(tmp_path: Path) -> None:
    # S1 + S5 degrade path (no meta.json -> mission_id None)
    result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert isinstance(result, NullEmitter)
    assert result.mission_slug == "m"
    assert result.mission_type == "software-dev"
    assert result.mission_id is None


@pytest.mark.usefixtures("clean_emitter_factory")
def test_factory_honors_registered_factory(tmp_path: Path) -> None:
    # S3: registered callable is invoked with the same keywords, return passed through
    sentinel = object()
    received: list[dict[str, Any]] = []

    def _factory(**kwargs: Any) -> Any:
        received.append(kwargs)
        return sentinel

    events_mod.register_runtime_emitter_factory(_factory)
    result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert result is sentinel
    assert received == [
        {"feature_dir": tmp_path, "mission_slug": "m", "mission_type": "software-dev"}
    ]


@pytest.mark.usefixtures("clean_emitter_factory")
def test_factory_reset_restores_default(tmp_path: Path) -> None:
    # S4
    sentinel = object()
    events_mod.register_runtime_emitter_factory(lambda **_: sentinel)
    assert (
        events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)
        is sentinel
    )

    events_mod.reset_runtime_emitter_factory()
    result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert isinstance(result, NullEmitter)


@pytest.mark.usefixtures("clean_emitter_factory")
@pytest.mark.parametrize(
    "gate_var",
    [
        "SPEC_KITTY_NO_MOMENT_HANDLERS",
        "SPEC_KITTY_SYNC_DISABLE",
        "SPEC_KITTY_SYNC_MINIMAL_IMPORT",  # deprecated alias, honored until post-launch (#3980)
    ],
)
@pytest.mark.parametrize("gate_value", ["1", "true", "yes"])
def test_factory_moment_handler_gate_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate_var: str, gate_value: str
) -> None:
    # S2: env gate read at call time; registered factory must not be called.
    # #3980: the seam consumes the canonical moment-handler gate, so its own
    # name, the kill switch, and the deprecated alias all disarm it.
    def _must_not_be_called(**_: Any) -> Any:
        raise AssertionError("must not be called")

    events_mod.register_runtime_emitter_factory(_must_not_be_called)
    monkeypatch.setenv(gate_var, gate_value)

    result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert isinstance(result, NullEmitter)
    assert result.mission_slug == "m"


@pytest.mark.usefixtures("clean_emitter_factory")
def test_factory_gate_off_value_does_not_shadow_registered_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # S2 complement: a falsy gate value leaves the registry in charge (S3)
    sentinel = object()
    events_mod.register_runtime_emitter_factory(lambda **_: sentinel)
    monkeypatch.setenv("SPEC_KITTY_SYNC_MINIMAL_IMPORT", "0")

    result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert result is sentinel


@pytest.mark.usefixtures("clean_emitter_factory")
def test_register_runtime_emitter_factory_same_object_twice_is_idempotent() -> None:
    """Mirrors ``kernel.glossary_runner.register``: re-registering the exact
    same factory object (e.g. a module re-import) is a no-op, not an error."""

    def _factory(**_: Any) -> Any:
        return object()

    events_mod.register_runtime_emitter_factory(_factory)
    events_mod.register_runtime_emitter_factory(_factory)  # must not raise


@pytest.mark.usefixtures("clean_emitter_factory")
def test_register_runtime_emitter_factory_classmethod_reregistration_is_idempotent() -> None:
    """Red-first regression: the module's own documented registration form is

        register_runtime_emitter_factory(MyProducer.for_mission)

    a *classmethod*. Every attribute access on a classmethod mints a fresh
    bound-method object (``MyProducer.for_mission is MyProducer.for_mission``
    is ``False``), so an identity (``is``) guard treats a benign re-import of
    the exact same producer as a conflicting registrant. This must be a
    no-op, exactly like re-registering the same plain-function object above.
    """

    class ZeitgeistRuntimeEmitterProducer:
        """Realistic producer shape: constructs the seam via a classmethod,
        mirroring the documented registration example at this module's
        registry-seam comment block."""

        def __init__(self, *, mission_slug: str, mission_type: str) -> None:
            self.mission_slug = mission_slug
            self.mission_type = mission_type

        @classmethod
        def for_mission(
            cls, *, feature_dir: Path, mission_slug: str, mission_type: str
        ) -> ZeitgeistRuntimeEmitterProducer:
            del feature_dir
            return cls(mission_slug=mission_slug, mission_type=mission_type)

    # Sanity check on the premise: repeated attribute access on a classmethod
    # is never the same object.
    assert (
        ZeitgeistRuntimeEmitterProducer.for_mission
        is not ZeitgeistRuntimeEmitterProducer.for_mission
    )

    events_mod.register_runtime_emitter_factory(ZeitgeistRuntimeEmitterProducer.for_mission)
    # A second import tail re-running the same registration line must not raise.
    events_mod.register_runtime_emitter_factory(ZeitgeistRuntimeEmitterProducer.for_mission)


@pytest.mark.usefixtures("clean_emitter_factory")
def test_register_runtime_emitter_factory_rejects_a_conflicting_registrant() -> None:
    """Registering a *different* factory while one is already registered is
    almost always an accidental double-registration -- reject it."""

    def _first(**_: Any) -> Any:
        return object()

    def _second(**_: Any) -> Any:
        return object()

    events_mod.register_runtime_emitter_factory(_first)

    with pytest.raises(RuntimeError, match="already registered"):
        events_mod.register_runtime_emitter_factory(_second)


@pytest.mark.usefixtures("clean_emitter_factory")
def test_register_runtime_emitter_factory_rejects_a_conflicting_classmethod_registrant() -> None:
    """Guard against over-correction into last-writer-wins: a genuinely
    *different* producer's classmethod (different ``__module__``/
    ``__qualname__``) must still raise, even though both registrants are
    classmethod-bound methods rather than plain functions."""

    class FirstProducer:
        @classmethod
        def for_mission(
            cls, *, feature_dir: Path, mission_slug: str, mission_type: str
        ) -> FirstProducer:
            del feature_dir, mission_slug, mission_type
            return cls()

    class SecondProducer:
        @classmethod
        def for_mission(
            cls, *, feature_dir: Path, mission_slug: str, mission_type: str
        ) -> SecondProducer:
            del feature_dir, mission_slug, mission_type
            return cls()

    events_mod.register_runtime_emitter_factory(FirstProducer.for_mission)

    with pytest.raises(RuntimeError, match="already registered"):
        events_mod.register_runtime_emitter_factory(SecondProducer.for_mission)


@pytest.mark.usefixtures("clean_emitter_factory")
def test_register_runtime_emitter_factory_rejects_a_non_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        events_mod.register_runtime_emitter_factory(cast(Any, "not-a-callable"))


@pytest.mark.usefixtures("clean_emitter_factory")
def test_runtime_emitter_for_mission_degrades_to_null_when_factory_raises(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A registered factory whose constructor raises must degrade to the
    null seam instead of propagating and killing the caller (e.g.
    ``spec-kitty next``); the failure is logged at WARNING, not silent."""

    def _raising_factory(**_: Any) -> Any:
        raise RuntimeError("producer constructor exploded")

    events_mod.register_runtime_emitter_factory(_raising_factory)

    with caplog.at_level("WARNING"):
        result = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert isinstance(result, NullEmitter)
    assert result.mission_slug == "m"
    assert any("registered factory" in record.message for record in caplog.records)


def test_for_mission_resolves_mission_id_from_meta(tmp_path: Path) -> None:
    # S5 success path
    (tmp_path / "meta.json").write_text(
        '{"mission_id":"' + _MISSION_ULID + '"}', encoding="utf-8"
    )

    emitter = NullEmitter.for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert emitter.mission_id == _MISSION_ULID
    assert emitter.mission_slug == "m"
    assert emitter.mission_type == "software-dev"
    assert emitter.correlation_id == ""


def test_for_mission_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    # S5 degrade path: corrupt meta.json never raises out of the seam
    (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")

    emitter = NullEmitter.for_mission(feature_dir=tmp_path, **_SEAM_KWARGS)

    assert emitter.mission_id is None
    assert emitter.mission_slug == "m"


def test_null_emitter_seed_and_emits_never_raise() -> None:
    # S6: every method is a no-op that tolerates arbitrary input
    emitter = NullEmitter()
    emit_methods = [
        name for name in dir(events_mod.RuntimeEventEmitter) if name.startswith("emit_")
    ]
    assert len(emit_methods) == 8  # (R-2: the Protocol is exactly the eight emit_* methods)

    emitter.seed_from_snapshot(object())
    for name in emit_methods:
        assert getattr(emitter, name)(object()) is None


def test_null_emitter_bare_constructor_unchanged() -> None:
    # Backwards compatibility for the NullEmitter() / NullEmitter("c") call sites
    bare = NullEmitter()
    assert bare.correlation_id == ""
    assert bare.mission_slug == ""
    assert bare.mission_type == ""
    assert bare.mission_id is None

    with_corr = NullEmitter("c")
    assert with_corr.correlation_id == "c"
    assert with_corr.mission_slug == ""
    assert with_corr.mission_type == ""
    assert with_corr.mission_id is None


def test_null_emitter_for_mission_not_on_protocol() -> None:
    # R-2: the Protocol stays at the eight emit_* methods; construction/seeding are
    # bridge-side concerns on the object the factory returns.
    protocol_names = set(vars(events_mod.RuntimeEventEmitter))
    assert "for_mission" not in protocol_names
    assert "seed_from_snapshot" not in protocol_names
    # R-7: ``for_mission`` is the only named constructor; no legacy alias exists.
    classmethods = {
        name for name, value in vars(NullEmitter).items() if isinstance(value, classmethod)
    }
    assert classmethods == {"for_mission"}


def test_lifecycle_module_re_exports() -> None:
    assert lifecycle_mod.next_step is engine_mod.next_step
    assert lifecycle_mod.provide_decision_answer is engine_mod.provide_decision_answer
    assert lifecycle_mod.start_mission_run is engine_mod.start_mission_run


def test_models_module_re_exports() -> None:
    assert models_mod.DiscoveryContext is discovery_mod.DiscoveryContext
    assert models_mod.MissionRunRef is engine_mod.MissionRunRef
    assert models_mod.MissionPolicySnapshot is schema_mod.MissionPolicySnapshot
    assert models_mod.NextDecision is schema_mod.NextDecision


# ---------------------------------------------------------------------------
# contracts.RemediationPayload
# ---------------------------------------------------------------------------


def test_remediation_missing_default_metadata() -> None:
    payload = RemediationPayload.missing("feature_binding")
    assert payload.error_code == "CONTEXT_MISSING"
    assert payload.context_name == "feature_binding"
    assert payload.candidates == []
    assert "feature_binding" in payload.remediation_hint
    assert payload.resolver_metadata == {}


def test_remediation_missing_with_metadata() -> None:
    payload = RemediationPayload.missing(
        "feature_binding", resolver_metadata={"resolver": "explicit_inputs"}
    )
    assert payload.resolver_metadata == {"resolver": "explicit_inputs"}


def test_remediation_ambiguous_with_candidates() -> None:
    candidates = [
        {"source": "ledger", "value": "x"},
        {"source": "discovery", "value": "y"},
    ]
    payload = RemediationPayload.ambiguous("wp_binding", candidates)
    assert payload.error_code == "CONTEXT_AMBIGUOUS"
    assert "ledger" in payload.remediation_hint
    assert "discovery" in payload.remediation_hint
    assert payload.candidates == candidates


def test_remediation_ambiguous_without_candidates() -> None:
    payload = RemediationPayload.ambiguous("wp_binding", [])
    assert "specify which source" in payload.remediation_hint


def test_remediation_invalid_with_validation_failures() -> None:
    payload = RemediationPayload.invalid(
        "spec_artifact",
        candidates=[{"source": "fs"}],
        validation_failures=["artifact missing", "wrong format"],
    )
    assert payload.error_code == "CONTEXT_INVALID"
    assert "artifact missing" in payload.remediation_hint
    assert "wrong format" in payload.remediation_hint


def test_remediation_invalid_without_validation_failures() -> None:
    payload = RemediationPayload.invalid(
        "spec_artifact", candidates=[{"source": "fs"}]
    )
    assert "failed validation against declared rules" in payload.remediation_hint


# ---------------------------------------------------------------------------
# discovery: full traversal of the precedence chain + warnings
# ---------------------------------------------------------------------------


def test_discovery_split_env_paths_handles_empty_string() -> None:
    assert discovery_mod._split_env_paths("") == []
    assert discovery_mod._split_env_paths("   ") == []


def test_discovery_split_env_paths_handles_pathsep_split(monkeypatch: Any) -> None:
    import os

    raw = f"{os.sep}foo{os.pathsep}{os.sep}bar"
    parts = discovery_mod._split_env_paths(raw)
    assert len(parts) == 2
    assert all(isinstance(p, Path) for p in parts)


def test_discovery_scan_root_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    assert discovery_mod._scan_root(tmp_path / "does-not-exist") == []


def test_discovery_scan_root_returns_single_yaml_when_pointed_at_file(
    tmp_path: Path,
) -> None:
    yaml_path = _write_simple_mission(tmp_path)
    found = discovery_mod._scan_root(yaml_path)
    assert found == [yaml_path]


def test_discovery_scan_root_dedupes_canonical_pack_layout(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    missions_dir = pack_root / "missions"
    missions_dir.mkdir(parents=True)
    # Place a mission both as <root>/<key>/mission.yaml AND under missions/
    _write_simple_mission(pack_root, key="alpha")
    _write_simple_mission(missions_dir, key="beta")
    found = discovery_mod._scan_root(pack_root)
    keys = {p.parent.name for p in found}
    assert "alpha" in keys
    assert "beta" in keys


def test_discovery_collect_from_manifest_missing_returns_empty(tmp_path: Path) -> None:
    assert discovery_mod._collect_from_manifest(tmp_path) == []


def test_discovery_collect_from_manifest_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "mission-pack.yaml"
    bad.write_text("- not\n- a mapping\n", encoding="utf-8")
    with pytest.raises(MissionRuntimeError):
        discovery_mod._collect_from_manifest(tmp_path)


def test_discovery_collect_from_manifest_rejects_missing_pack_key(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "mission-pack.yaml"
    bad.write_text("missions: []\n", encoding="utf-8")
    with pytest.raises(MissionRuntimeError, match="missing required 'pack'"):
        discovery_mod._collect_from_manifest(tmp_path)


def test_discovery_collect_from_manifest_resolves_paths(tmp_path: Path) -> None:
    _write_simple_mission(tmp_path / "missions", key="m1")
    manifest = tmp_path / "mission-pack.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "pack": {"name": "my-pack", "version": "1.0.0"},
                "missions": [{"key": "m1", "path": "missions/m1/mission.yaml"}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    found = discovery_mod._collect_from_manifest(tmp_path)
    assert len(found) == 1
    assert found[0].name == "mission.yaml"


def test_discover_missions_returns_empty_for_empty_context(tmp_path: Path) -> None:
    ctx = DiscoveryContext(user_home=tmp_path / "home")
    assert discover_missions(ctx) == []


def test_discover_missions_with_warnings_collects_load_failures(tmp_path: Path) -> None:
    bad_mission = tmp_path / "bad" / "mission.yaml"
    bad_mission.parent.mkdir(parents=True)
    bad_mission.write_text("not: yaml: but {valid}? [\n", encoding="utf-8")
    ctx = DiscoveryContext(
        explicit_paths=[bad_mission], user_home=tmp_path / "home"
    )
    result = discover_missions_with_warnings(ctx)
    assert isinstance(result, DiscoveryResult)
    assert result.warnings, "Expected at least one DiscoveryWarning"
    assert all(isinstance(w, DiscoveryWarning) for w in result.warnings)


def test_discover_missions_marks_shadowed_entries(tmp_path: Path) -> None:
    a = tmp_path / "tier_a"
    b = tmp_path / "tier_b"
    _write_simple_mission(a, key="dup")
    _write_simple_mission(b, key="dup")
    ctx = DiscoveryContext(
        explicit_paths=[a / "dup" / "mission.yaml"],
        builtin_roots=[b / "dup" / "mission.yaml"],
        user_home=tmp_path / "home",
    )
    discovered = discover_missions(ctx)
    selected = [d for d in discovered if d.selected]
    shadowed = [d for d in discovered if not d.selected]
    assert len(selected) == 1
    assert len(shadowed) >= 1


def test_discovery_diagnose_shadowing_returns_structured_report(tmp_path: Path) -> None:
    a = tmp_path / "tier_a"
    b = tmp_path / "tier_b"
    _write_simple_mission(a, key="dup")
    _write_simple_mission(b, key="dup")
    ctx = DiscoveryContext(
        explicit_paths=[a / "dup" / "mission.yaml"],
        builtin_roots=[b / "dup" / "mission.yaml"],
        user_home=tmp_path / "home",
    )
    diag = diagnose_shadowing(ctx)
    assert isinstance(diag, ShadowingDiagnostics)
    assert diag.total_discovered >= 2
    assert diag.total_shadowed >= 1
    assert all(isinstance(e, ShadowEntry) for e in diag.entries)


def test_discovery_load_mission_template_by_path(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path)
    template = load_mission_template(str(yaml_path))
    assert isinstance(template, MissionTemplate)
    assert template.mission.key == "cov-mission"


def test_discovery_load_mission_template_by_dir_path(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path)
    template = load_mission_template(str(yaml_path.parent))
    assert template.mission.key == "cov-mission"


def test_discovery_load_mission_template_by_key(tmp_path: Path) -> None:
    _write_simple_mission(tmp_path, key="by-key")
    ctx = DiscoveryContext(
        explicit_paths=[tmp_path / "by-key" / "mission.yaml"],
        user_home=tmp_path / "home",
    )
    template = load_mission_template("by-key", context=ctx)
    assert template.mission.key == "by-key"


def test_discovery_load_mission_template_missing_raises(tmp_path: Path) -> None:
    ctx = DiscoveryContext(user_home=tmp_path / "home")
    with pytest.raises(MissionRuntimeError, match="not found"):
        load_mission_template("ghost-mission", context=ctx)


def test_discovery_project_config_pack_paths_handles_missing(tmp_path: Path) -> None:
    # No .kittify/config.yaml in tmp_path => empty list
    assert discovery_mod._project_config_pack_paths(tmp_path) == []


def test_discovery_project_config_pack_paths_reads_config(tmp_path: Path) -> None:
    cfg = tmp_path / ".kittify" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        yaml.safe_dump({"mission_packs": ["packs/a", "packs/b"]}, sort_keys=True),
        encoding="utf-8",
    )
    paths = discovery_mod._project_config_pack_paths(tmp_path)
    assert len(paths) == 2
    assert paths[0] == tmp_path / "packs/a"


def test_discovery_project_config_pack_paths_skips_non_list(tmp_path: Path) -> None:
    cfg = tmp_path / ".kittify" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(yaml.safe_dump({"mission_packs": "not-a-list"}), encoding="utf-8")
    assert discovery_mod._project_config_pack_paths(tmp_path) == []


# ---------------------------------------------------------------------------
# discovery: org tier -- Walk A (WP04, FR-007/FR-008, mission
# up-org-template-fsm-01M06F9K). ``org_roots`` is a plain, already-resolved
# list on DiscoveryContext -- this module never calls resolve_org_roots
# itself; the production wiring sites (runtime_bridge_io.py,
# specify_cli/mission_loader/command.py) populate it via the lazy
# charter.drg facade before constructing the context (DEC-004).
# ---------------------------------------------------------------------------


def test_discovery_context_org_roots_defaults_to_empty_list() -> None:
    """FR-007: DiscoveryContext gets an org_roots field, empty by default so
    a project with no org pack configured sees no behavior change (NFR-005)."""
    assert DiscoveryContext().org_roots == []


def test_build_tiers_inserts_org_tier_after_project_legacy_before_user_global(
    tmp_path: Path,
) -> None:
    """FR-007: _build_tiers inserts an ("org", ..., context.org_roots) tier
    immediately after project_legacy and before user_global."""
    org_root = tmp_path / "org-pack"
    ctx = DiscoveryContext(
        project_dir=tmp_path / "project",
        org_roots=[org_root],
        user_home=tmp_path / "home",
    )
    tiers = discovery_mod._build_tiers(ctx)
    names = [t[0] for t in tiers]
    assert names == [
        "explicit",
        "env",
        "project_override",
        "project_legacy",
        "org",
        "user_global",
        "project_config",
        "builtin",
    ]
    org_tier = next(t for t in tiers if t[0] == "org")
    assert org_tier[2] == [org_root]


def test_build_tiers_org_tier_present_even_without_project_dir(tmp_path: Path) -> None:
    """The org tier is always present in the tiers list -- even when
    project_dir is unset -- so the tier shape stays uniform (engine.py:176's
    bare DiscoveryContext() fallback stays out of scope per DEC-006, but the
    tier itself is harmless there since org_roots is empty by construction)."""
    ctx = DiscoveryContext(user_home=tmp_path / "home")
    names = [t[0] for t in discovery_mod._build_tiers(ctx)]
    assert names == ["explicit", "env", "org", "user_global", "builtin"]


def test_discover_missions_with_warnings_selects_org_tier_mission(tmp_path: Path) -> None:
    """User Story 3, Acceptance Scenario 1: an org-pack mission with no
    project override/legacy present is discovered at tier "org",
    selected=True."""
    org_root = tmp_path / "org-pack"
    _write_simple_mission(org_root, key="org-only-mission")
    ctx = DiscoveryContext(
        project_dir=tmp_path / "project",
        org_roots=[org_root],
        user_home=tmp_path / "home",
    )
    discovered = discover_missions(ctx)
    matches = [d for d in discovered if d.key == "org-only-mission"]
    assert len(matches) == 1
    assert matches[0].precedence_tier == "org"
    assert matches[0].selected is True


def test_discover_missions_project_legacy_wins_over_org(tmp_path: Path) -> None:
    """User Story 3, Acceptance Scenario 3 (Walk A half): a project-legacy
    mission.yaml wins over the org-pack file for the same key -- position
    parity, not just tier existence."""
    project_dir = tmp_path / "project"
    org_root = tmp_path / "org-pack"
    _write_simple_mission(project_dir / ".kittify" / "missions", key="dup-mission")
    _write_simple_mission(org_root, key="dup-mission")
    ctx = DiscoveryContext(
        project_dir=project_dir,
        org_roots=[org_root],
        user_home=tmp_path / "home",
    )
    discovered = discover_missions(ctx)
    matches = {d.precedence_tier: d for d in discovered if d.key == "dup-mission"}
    assert matches["project_legacy"].selected is True
    assert matches["org"].selected is False


def test_discover_missions_no_org_roots_configured_is_a_noop(tmp_path: Path) -> None:
    """NFR-005/SC-007: with org_roots unset (the default -- no org packs
    configured, the overwhelmingly common case), discovery is unaffected:
    no "org" tier entries appear, and the pre-existing project_legacy
    mission is still discovered and selected exactly as before this WP."""
    project_dir = tmp_path / "project"
    _write_simple_mission(project_dir / ".kittify" / "missions", key="solo-mission")
    ctx = DiscoveryContext(project_dir=project_dir, user_home=tmp_path / "home")
    discovered = discover_missions(ctx)
    assert [d.key for d in discovered] == ["solo-mission"]
    assert discovered[0].precedence_tier == "project_legacy"
    assert discovered[0].selected is True
    assert all(d.precedence_tier != "org" for d in discovered)


# ---------------------------------------------------------------------------
# events: JsonlEventLog
# ---------------------------------------------------------------------------


def test_jsonl_event_log_appends_and_reads(tmp_path: Path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    log.append({"event": "a", "n": 1})
    log.append({"event": "b", "n": 2})
    records = log.read_all()
    assert len(records) == 2
    assert records[0]["event"] == "a"
    assert records[1]["n"] == 2
    assert log.path == tmp_path / "events.jsonl"


def test_jsonl_event_log_read_all_missing_returns_empty(tmp_path: Path) -> None:
    log = JsonlEventLog(tmp_path / "missing.jsonl")
    assert log.read_all() == []


def test_jsonl_event_log_read_all_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"event":"a"}\n\n{"event":"b"}\n', encoding="utf-8")
    log = JsonlEventLog(path)
    records = log.read_all()
    assert [r["event"] for r in records] == ["a", "b"]


def test_null_emitter_methods_are_no_ops() -> None:
    """Exercise every NullEmitter method so emitter.py's protocol stubs are covered."""
    from spec_kitty_events.mission_next import (
        DecisionInputAnsweredPayload,
        DecisionInputRequestedPayload,
        MissionRunCompletedPayload,
        MissionRunStartedPayload,
        NextStepAutoCompletedPayload,
        NextStepIssuedPayload,
        RuntimeActorIdentity,
    )

    null = NullEmitter(correlation_id="test")
    actor = RuntimeActorIdentity(
        actor_id="a", actor_type="service", provider=None, model=None, tool=None
    )
    null.emit_mission_run_started(
        MissionRunStartedPayload(run_id="r", mission_type="m", actor=actor)
    )
    null.emit_next_step_issued(
        NextStepIssuedPayload(
            run_id="r", step_id="s", agent_id="agent-1", actor=actor
        )
    )
    null.emit_next_step_auto_completed(
        NextStepAutoCompletedPayload(
            run_id="r", step_id="s", agent_id="agent-1", result="success", actor=actor
        )
    )
    null.emit_decision_input_requested(
        DecisionInputRequestedPayload(
            run_id="r", step_id="s", decision_id="d", question="q?", actor=actor
        )
    )
    null.emit_decision_input_answered(
        DecisionInputAnsweredPayload(
            run_id="r",
            decision_id="d",
            answer="x",
            actor=actor,
        )
    )
    null.emit_mission_run_completed(
        MissionRunCompletedPayload(run_id="r", mission_type="m", actor=actor)
    )
    # Assertions: just checking these don't raise; correlation_id stored.
    assert null.correlation_id == "test"


# ---------------------------------------------------------------------------
# planner.plan_next: each branch of the decision tree
# ---------------------------------------------------------------------------


def test_plan_next_blocked_takes_priority() -> None:
    template = _make_simple_template()
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
        blocked_reason="manual block",
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "blocked"
    assert decision.reason == "manual block"


def test_plan_next_template_drift_blocks(tmp_path: Path) -> None:
    template = _make_simple_template()
    live = tmp_path / "mission.yaml"
    live.write_text("key: value\n", encoding="utf-8")
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path=str(live),
        template_hash="0" * 64,  # bogus hash -> drift
    )
    decision = plan_next(
        snap, template, MissionPolicySnapshot(), live_template_path=live
    )
    assert decision.kind == "blocked"
    assert "drift" in (decision.reason or "").lower() or "Template changed" in (
        decision.reason or ""
    )


def test_plan_next_template_drift_skipped_when_live_missing(tmp_path: Path) -> None:
    template = _make_simple_template()
    live = tmp_path / "missing.yaml"
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path=str(live),
        template_hash="0" * 64,
    )
    decision = plan_next(
        snap, template, MissionPolicySnapshot(), live_template_path=live
    )
    # No drift error because live file doesn't exist
    assert decision.kind == "step"


def test_plan_next_pending_decision_audit_branch() -> None:
    template = _make_simple_template()
    pending = {
        "audit:s1": {
            "decision_id": "audit:s1",
            "step_id": "s1",
            "question": "Audit ok?",
            "options": ["approve", "reject"],
            "requested_by": ActorIdentity(
                actor_id="x", actor_type="human", provider=None, model=None, tool=None
            ).model_dump(mode="json"),
            "requested_at": now_utc_iso(),
        }
    }
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
        pending_decisions=pending,
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "decision_required"
    assert decision.decision_id == "audit:s1"
    assert decision.input_key is None  # audit decisions have no input_key


def test_plan_next_pending_decision_input_branch() -> None:
    template = _make_simple_template()
    pending = {
        "input:topic": {
            "decision_id": "input:topic",
            "step_id": "s1",
            "question": "Topic?",
            "options": [],
            "requested_by": ActorIdentity(
                actor_id="x", actor_type="human", provider=None, model=None, tool=None
            ).model_dump(mode="json"),
            "requested_at": now_utc_iso(),
        }
    }
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
        pending_decisions=pending,
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "decision_required"
    assert decision.input_key == "topic"


def test_plan_next_terminal_when_all_steps_completed() -> None:
    template = _make_simple_template()
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
        completed_steps=["s1", "s2"],
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "terminal"


def test_plan_next_blocks_when_dag_unschedulable() -> None:
    # Step s2 depends on s1, but s1 is the issued step (not yet completed).
    template = _make_simple_template()
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
        issued_step_id="s1",
        completed_steps=[],
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    # Both s1 (issued) and s2 (depends_on s1) are filtered out -> blocked.
    assert decision.kind == "blocked"
    assert "unmet dependencies" in (decision.reason or "").lower()


def test_plan_next_audit_blocking_returns_audit_decision() -> None:
    template = MissionTemplate(
        mission=MissionMeta(key="ta", name="TA", version="1.0.0"),
        steps=[],
        audit_steps=[
            AuditStep(
                id="a1",
                title="Audit 1",
                audit=AuditConfig(trigger_mode="manual", enforcement="blocking"),
            )
        ],
    )
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="ta",
        template_path="x",
        template_hash="h",
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "decision_required"
    assert decision.decision_id == "audit:a1"
    assert decision.options == ["approve", "reject"]


def test_plan_next_audit_advisory_returns_step() -> None:
    template = MissionTemplate(
        mission=MissionMeta(key="ta", name="TA", version="1.0.0"),
        steps=[],
        audit_steps=[
            AuditStep(
                id="a1",
                title="Audit advisory",
                audit=AuditConfig(trigger_mode="manual", enforcement="advisory"),
            )
        ],
    )
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="ta",
        template_path="x",
        template_hash="h",
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "step"
    assert decision.step_id == "a1"


def test_plan_next_step_with_missing_input_emits_input_decision() -> None:
    template = MissionTemplate(
        mission=MissionMeta(key="t", name="T", version="1.0.0"),
        steps=[
            PromptStep(
                id="s1", title="S1", requires_inputs=["topic"], prompt="Do."
            )
        ],
    )
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "decision_required"
    assert decision.input_key == "topic"


def test_plan_next_step_default_prompt_falls_back() -> None:
    # PromptStep without explicit prompt uses fallback prompt template.
    template = MissionTemplate(
        mission=MissionMeta(key="t", name="T", version="1.0.0"),
        steps=[PromptStep(id="s1", title="Title")],
    )
    snap = MissionRunSnapshot(
        run_id="r1",
        mission_key="t",
        template_path="x",
        template_hash="h",
    )
    decision = plan_next(snap, template, MissionPolicySnapshot())
    assert decision.kind == "step"
    assert "Title" in (decision.prompt or "")


def test_serialize_decision_is_canonical() -> None:
    decision = NextDecision(
        kind="terminal", run_id="r", mission_key="t", reason="done"
    )
    serialized = serialize_decision(decision)
    assert '"kind":"terminal"' in serialized
    assert '"run_id":"r"' in serialized


# ---------------------------------------------------------------------------
# raci: infer / validate / resolve
# ---------------------------------------------------------------------------


def test_infer_raci_for_prompt_step() -> None:
    step = PromptStep(id="p1", title="P1")
    binding = infer_raci(step, MissionPolicySnapshot())
    assert binding.responsible.actor_type == "llm"
    assert binding.accountable.actor_type == "human"
    assert binding.inferred_rule == "prompt_default"


def test_infer_raci_for_audit_blocking() -> None:
    step = AuditStep(
        id="a1", title="A1", audit=AuditConfig(trigger_mode="manual", enforcement="blocking")
    )
    binding = infer_raci(step, MissionPolicySnapshot())
    assert binding.responsible.actor_type == "human"
    assert binding.accountable.actor_type == "human"
    assert binding.inferred_rule == "audit_blocking"


def test_infer_raci_for_audit_advisory() -> None:
    step = AuditStep(
        id="a1", title="A1", audit=AuditConfig(trigger_mode="manual", enforcement="advisory")
    )
    binding = infer_raci(step, MissionPolicySnapshot())
    assert binding.responsible.actor_type == "llm"
    assert binding.inferred_rule == "audit_advisory"


def test_validate_raci_assignment_passes_for_valid_prompt() -> None:
    assignment = RACIAssignment(
        responsible=RACIRoleBinding(actor_type="llm"),
        accountable=RACIRoleBinding(actor_type="human"),
    )
    step = PromptStep(id="p1", title="P1")
    ok, errors = validate_raci_assignment(assignment, step)
    assert ok
    assert errors == []


def test_validate_raci_assignment_blocks_audit_with_llm_responsible() -> None:
    assignment = RACIAssignment(
        responsible=RACIRoleBinding(actor_type="llm"),
        accountable=RACIRoleBinding(actor_type="human"),
    )
    audit_step = AuditStep(
        id="a1", title="A1", audit=AuditConfig(trigger_mode="manual", enforcement="blocking")
    )
    ok, errors = validate_raci_assignment(assignment, audit_step)
    assert not ok
    assert any("responsible must be human" in e for e in errors)


def test_resolve_raci_inferred_path_with_inputs() -> None:
    step = PromptStep(id="p1", title="P1")
    inputs = {"mission_owner_id": "owner-42", "agent_id": "claude"}
    binding = resolve_raci(step, inputs, MissionPolicySnapshot())
    assert binding.source == "inferred"
    assert binding.responsible.actor_id == "claude"
    assert binding.accountable.actor_id == "owner-42"


def test_resolve_raci_explicit_path() -> None:
    explicit = RACIAssignment(
        responsible=RACIRoleBinding(actor_type="llm", actor_id="claude"),
        accountable=RACIRoleBinding(actor_type="human", actor_id="owner-42"),
    )
    step = PromptStep(
        id="p1",
        title="P1",
        raci=explicit,
        raci_override_reason="domain expert oversight",
    )
    binding = resolve_raci(step, {}, MissionPolicySnapshot())
    assert binding.source == "explicit"
    assert binding.override_reason == "domain expert oversight"


def test_resolve_raci_raises_when_owner_missing() -> None:
    step = PromptStep(id="p1", title="P1")
    with pytest.raises(MissionRuntimeError, match="RACI escalation"):
        resolve_raci(step, {"agent_id": "x"}, MissionPolicySnapshot())


def test_resolve_raci_optional_consulted_passthrough() -> None:
    explicit = RACIAssignment(
        responsible=RACIRoleBinding(actor_type="llm", actor_id="claude"),
        accountable=RACIRoleBinding(actor_type="human", actor_id="o"),
        consulted=[RACIRoleBinding(actor_type="service")],
    )
    step = PromptStep(
        id="p1",
        title="P1",
        raci=explicit,
        raci_override_reason="reason",
    )
    binding = resolve_raci(
        step, {"service_id": "audit-bot"}, MissionPolicySnapshot()
    )
    assert binding.consulted[0].actor_id == "audit-bot"


def test_actor_type_to_input_key_unknown_falls_through() -> None:
    assert raci_mod._actor_type_to_input_key("unknown_actor") == "unknown_actor"


def test_lookup_actor_id_strips_whitespace() -> None:
    assert (
        raci_mod._lookup_actor_id("human", {"mission_owner_id": "  joe  "})
        == "joe"
    )
    assert raci_mod._lookup_actor_id("human", {"mission_owner_id": "   "}) is None
    assert raci_mod._lookup_actor_id("human", {"mission_owner_id": 42}) is None


# ---------------------------------------------------------------------------
# significance: dimension / band / hard-trigger / score / policy parse
# ---------------------------------------------------------------------------


_VALID_DIMS = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}


def test_validate_dimension_scores_rejects_unknown_dim() -> None:
    bad = {**_VALID_DIMS}
    bad.pop("cross_team_blast_radius")
    bad["made_up_dim"] = 1
    with pytest.raises(ValueError, match="missing|unexpected"):
        validate_dimension_scores(bad)


def test_validate_dimension_scores_rejects_out_of_range() -> None:
    bad = {**_VALID_DIMS, "user_customer_impact": 99}
    with pytest.raises(ValueError, match="must be 0-3"):
        validate_dimension_scores(bad)


def test_validate_dimension_scores_rejects_non_int_via_pydantic() -> None:
    # The bare validate_dimension_scores function only validates the keys+ranges.
    # SignificanceDimension model_validate enforces the int-ness at parse-time.
    with pytest.raises(ValidationError):
        SignificanceDimension(name="user_customer_impact", score="bad")  # type: ignore[arg-type]


def test_validate_band_cutoffs_rejects_missing_band() -> None:
    with pytest.raises(ValueError, match="Expected exactly 3 bands"):
        validate_band_cutoffs({"low": [0, 6], "medium": [7, 18]})


def test_validate_band_cutoffs_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="Overlap"):
        validate_band_cutoffs(
            {"low": [0, 8], "medium": [7, 11], "high": [12, 18]}
        )


def test_validate_band_cutoffs_rejects_non_pair() -> None:
    with pytest.raises(ValueError, match="must be a"):
        validate_band_cutoffs(
            {"low": [0], "medium": [7, 11], "high": [12, 18]}
        )


def test_validate_band_cutoffs_rejects_min_gt_max() -> None:
    with pytest.raises(ValueError, match="min_score"):
        validate_band_cutoffs(
            {"low": [6, 0], "medium": [7, 11], "high": [12, 18]}
        )


def test_make_routing_bands_returns_default_when_none() -> None:
    bands = make_routing_bands()
    assert bands == DEFAULT_BANDS


def test_make_routing_bands_uses_custom_cutoffs() -> None:
    bands = make_routing_bands(
        {"low": [0, 5], "medium": [6, 10], "high": [11, 18]}
    )
    assert len(bands) == 3
    band_names = {b.name for b in bands}
    assert band_names == {"low", "medium", "high"}


def test_resolve_hard_triggers_returns_known_classes() -> None:
    valid_id = next(iter(HARD_TRIGGER_REGISTRY))
    resolved = resolve_hard_triggers([valid_id])
    assert len(resolved) == 1
    assert isinstance(resolved[0], HardTriggerClass)


def test_resolve_hard_triggers_raises_for_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown hard-trigger"):
        resolve_hard_triggers(["totally-bogus-trigger-class"])


def test_evaluate_significance_low_band_no_triggers() -> None:
    # All-zero dimensions -> low band, no triggers.
    score = evaluate_significance(_VALID_DIMS)
    assert isinstance(score, SignificanceScore)
    assert score.effective_band.name == "low"
    assert score.composite == 0


def test_evaluate_significance_high_band_via_score() -> None:
    high_dims = {k: 3 for k in _VALID_DIMS}
    score = evaluate_significance(high_dims)
    assert score.composite == 18
    assert score.effective_band.name == "high"


def test_evaluate_significance_with_hard_trigger_promotes() -> None:
    valid_id = next(iter(HARD_TRIGGER_REGISTRY))
    score = evaluate_significance(_VALID_DIMS, hard_trigger_classes=[valid_id])
    # Hard-trigger always promotes effective_band to high regardless of base.
    assert score.effective_band.name == "high"
    assert len(score.hard_trigger_classes) == 1


def test_evaluate_significance_custom_band_cutoffs() -> None:
    cutoffs = {"low": [0, 5], "medium": [6, 11], "high": [12, 18]}
    score = evaluate_significance(_VALID_DIMS, band_cutoffs=cutoffs)
    assert score.effective_band.name == "low"


def test_dimension_score_override_records_audit() -> None:
    override = DimensionScoreOverride(
        decision_id="audit:s1",
        overridden_by=RACIRoleBinding(actor_type="human", actor_id="owner"),
        override_reason="manual review forced this",
        original_scores={"user_customer_impact": 0},
        new_scores={"user_customer_impact": 3},
        override_timestamp=now_utc(),
    )
    assert override.override_reason == "manual review forced this"


def test_dimension_score_override_rejects_non_human_actor() -> None:
    with pytest.raises(ValidationError):
        DimensionScoreOverride(
            decision_id="audit:s1",
            overridden_by=RACIRoleBinding(actor_type="llm", actor_id="claude"),
            override_reason="bot override",
            original_scores={"user_customer_impact": 0},
            new_scores={"user_customer_impact": 1},
            override_timestamp=now_utc(),
        )


def test_parse_band_cutoffs_from_policy_returns_none_when_absent() -> None:
    assert parse_band_cutoffs_from_policy(MissionPolicySnapshot()) is None


def test_parse_band_cutoffs_from_policy_extracts_from_extras() -> None:
    policy = MissionPolicySnapshot(
        extras={
            "significance_band_cutoffs": {
                "low": [0, 5],
                "medium": [6, 10],
                "high": [11, 18],
            }
        }
    )
    parsed = parse_band_cutoffs_from_policy(policy)
    assert parsed is not None
    assert parsed["low"] == [0, 5]


def test_parse_band_cutoffs_from_policy_rejects_non_dict() -> None:
    policy = MissionPolicySnapshot(extras={"significance_band_cutoffs": "x"})
    with pytest.raises(ValueError, match="must be a dict"):
        parse_band_cutoffs_from_policy(policy)


def test_parse_band_cutoffs_from_policy_rejects_non_int_bounds() -> None:
    policy = MissionPolicySnapshot(
        extras={
            "significance_band_cutoffs": {
                "low": ["a", "b"],
                "medium": [6, 10],
                "high": [11, 18],
            }
        }
    )
    with pytest.raises(ValueError, match="integers"):
        parse_band_cutoffs_from_policy(policy)


def test_parse_timeout_from_policy_returns_default_when_absent() -> None:
    assert parse_timeout_from_policy(MissionPolicySnapshot()) == 600


def test_parse_timeout_from_policy_extracts_seconds() -> None:
    policy = MissionPolicySnapshot(
        extras={"significance_default_timeout_seconds": 120}
    )
    assert parse_timeout_from_policy(policy) == 120


def test_parse_timeout_from_policy_rejects_non_int() -> None:
    policy = MissionPolicySnapshot(
        extras={"significance_default_timeout_seconds": "120"}
    )
    with pytest.raises(ValueError, match="must be int"):
        parse_timeout_from_policy(policy)


def test_parse_timeout_from_policy_rejects_non_positive() -> None:
    policy = MissionPolicySnapshot(
        extras={"significance_default_timeout_seconds": 0}
    )
    with pytest.raises(ValueError, match="> 0"):
        parse_timeout_from_policy(policy)


def test_compute_escalation_targets_medium_band_returns_accountable_only() -> None:
    raci = ResolvedRACIBinding(
        step_id="s1",
        responsible=RACIRoleBinding(actor_type="llm", actor_id="claude"),
        accountable=RACIRoleBinding(actor_type="human", actor_id="owner-42"),
        consulted=[RACIRoleBinding(actor_type="service", actor_id="audit-bot")],
        source="inferred",
        inferred_rule="prompt_default",
    )
    targets = compute_escalation_targets(raci, "medium")
    assert len(targets) == 1
    assert targets[0].actor_id == "owner-42"


def test_compute_escalation_targets_high_band_includes_consulted() -> None:
    raci = ResolvedRACIBinding(
        step_id="s1",
        responsible=RACIRoleBinding(actor_type="llm", actor_id="claude"),
        accountable=RACIRoleBinding(actor_type="human", actor_id="owner-42"),
        consulted=[RACIRoleBinding(actor_type="service", actor_id="audit-bot")],
        source="inferred",
        inferred_rule="prompt_default",
    )
    targets = compute_escalation_targets(raci, "high")
    actor_ids = {t.actor_id for t in targets}
    assert {"owner-42", "audit-bot"}.issubset(actor_ids)


# ---------------------------------------------------------------------------
# schema: ContextType / ContextTypeRegistry / load_mission_template_file edges
# ---------------------------------------------------------------------------


def test_context_type_registry_lists_builtins() -> None:
    reg = ContextTypeRegistry()
    assert reg.is_registered("feature_binding")
    assert not reg.is_registered("totally-made-up")


def test_step_context_contract_rejects_unknown_type_without_resolver() -> None:
    with pytest.raises(ValidationError):
        StepContextContract(
            requires=[ContextType(type="zzz_unknown_xyz")]
        )


def test_step_context_contract_validate_contract_detects_overlap() -> None:
    contract = StepContextContract(
        requires=[ContextType(type="feature_binding")],
        emits=[ContextType(type="feature_binding")],
    )
    ok, errors = contract.validate_contract()
    assert not ok
    assert any("requires and emits" in e for e in errors)


def test_load_mission_template_file_missing(tmp_path: Path) -> None:
    with pytest.raises(MissionRuntimeError, match="not found"):
        load_mission_template_file(tmp_path / "missing.yaml")


def test_load_mission_template_file_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "mission.yaml"
    bad.write_text("- list\n- here\n", encoding="utf-8")
    with pytest.raises(MissionRuntimeError, match="must be a mapping"):
        load_mission_template_file(bad)


def test_load_mission_template_file_rejects_no_steps(tmp_path: Path) -> None:
    bad = tmp_path / "mission.yaml"
    bad.write_text(
        yaml.safe_dump(
            {"mission": {"key": "x", "name": "X", "version": "1.0.0"}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(MissionRuntimeError, match="no steps"):
        load_mission_template_file(bad)


def test_load_mission_template_file_normalizes_shorthand(tmp_path: Path) -> None:
    bad = tmp_path / "mission.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "name": "Shorthand",
                "version": "1.0.0",
                "steps": [{"id": "s", "title": "S", "prompt": "p"}],
            }
        ),
        encoding="utf-8",
    )
    template = load_mission_template_file(bad)
    assert template.mission.key == "Shorthand"


def test_resolved_raci_binding_explicit_requires_override_reason() -> None:
    with pytest.raises(ValidationError):
        ResolvedRACIBinding(
            step_id="s",
            responsible=RACIRoleBinding(actor_type="llm"),
            accountable=RACIRoleBinding(actor_type="human"),
            source="explicit",
        )


def test_resolved_raci_binding_inferred_requires_rule() -> None:
    with pytest.raises(ValidationError):
        ResolvedRACIBinding(
            step_id="s",
            responsible=RACIRoleBinding(actor_type="llm"),
            accountable=RACIRoleBinding(actor_type="human"),
            source="inferred",
        )


def test_raci_assignment_p0_invariant() -> None:
    with pytest.raises(ValidationError):
        RACIAssignment(
            responsible=RACIRoleBinding(actor_type="llm"),
            accountable=RACIRoleBinding(actor_type="llm"),  # not human
        )


def test_prompt_step_raci_override_reason_required() -> None:
    explicit = RACIAssignment(
        responsible=RACIRoleBinding(actor_type="llm", actor_id="x"),
        accountable=RACIRoleBinding(actor_type="human", actor_id="y"),
    )
    with pytest.raises(ValidationError):
        PromptStep(id="p", title="P", raci=explicit)


def test_prompt_step_raci_override_reason_orphan_rejected() -> None:
    with pytest.raises(ValidationError):
        PromptStep(id="p", title="P", raci_override_reason="orphan")


# ---------------------------------------------------------------------------
# engine: validate_binding + lifecycle integration
# ---------------------------------------------------------------------------


def test_validate_binding_artifact_exists_pass(tmp_path: Path) -> None:
    f = tmp_path / "spec.md"
    f.write_text("hi", encoding="utf-8")
    ctx = ContextType(type="spec_artifact", validation={"artifact_exists": True})
    ok, err = validate_binding(str(f), ctx)
    assert ok
    assert err is None


def test_validate_binding_artifact_exists_fail(tmp_path: Path) -> None:
    ctx = ContextType(type="spec_artifact", validation={"artifact_exists": True})
    ok, err = validate_binding(str(tmp_path / "missing.md"), ctx)
    assert not ok
    assert err is not None


def test_validate_binding_no_validation_rules_passes() -> None:
    ctx = ContextType(type="feature_binding")
    ok, err = validate_binding("anything", ctx)
    assert ok
    assert err is None


def test_validate_binding_path_exists_pass(tmp_path: Path) -> None:
    ctx = ContextType(type="feature_binding", validation={"path_exists": True})
    ok, err = validate_binding(str(tmp_path), ctx)
    assert ok


def test_validate_binding_path_exists_fail(tmp_path: Path) -> None:
    ctx = ContextType(type="feature_binding", validation={"path_exists": True})
    ok, err = validate_binding(str(tmp_path / "no-dir"), ctx)
    assert not ok


def test_validate_binding_slug_format_pass() -> None:
    ctx = ContextType(
        type="feature_binding", validation={"slug_format": r"[a-z0-9-]+"}
    )
    ok, err = validate_binding("my-feature-01", ctx)
    assert ok


def test_validate_binding_slug_format_fail() -> None:
    ctx = ContextType(
        type="feature_binding", validation={"slug_format": r"[a-z0-9-]+"}
    )
    ok, err = validate_binding("INVALID Slug!", ctx)
    assert not ok


def test_validate_binding_unknown_rule_returns_error() -> None:
    ctx = ContextType(
        type="feature_binding", validation={"made_up_rule": True}
    )
    ok, err = validate_binding("x", ctx)
    assert not ok
    assert err is not None
    assert "Unknown validation rule" in err


def test_validate_binding_artifact_exists_disabled() -> None:
    ctx = ContextType(
        type="spec_artifact", validation={"artifact_exists": False}
    )
    # Disabled rule -> always passes.
    ok, err = validate_binding("/no/such/path", ctx)
    assert ok


def test_start_mission_run_then_next_step_full_flow(tmp_path: Path) -> None:
    """Walk a real mission template through the full lifecycle.

    This exercises start_mission_run (engine.py:180-220), next_step's pending
    decision branch (line 295+), provide_decision_answer's input branch, and
    next_step's step-issuance branch.
    """
    yaml_path = _write_simple_mission(tmp_path / "missions")
    run_store = tmp_path / "runs"
    ctx = DiscoveryContext(
        explicit_paths=[yaml_path],
        builtin_roots=[yaml_path],
        user_home=tmp_path / "home",
    )
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=run_store,
        emitter=NullEmitter(),
    )
    assert isinstance(run_ref, MissionRunRef)

    # First step: should produce input:topic decision.
    decision = next_step(run_ref, agent_id="cov-agent", emitter=NullEmitter())
    assert decision.kind == "decision_required"
    assert decision.decision_id == "input:topic"

    # Answer the decision.
    actor = ActorIdentity(
        actor_id="user-1",
        actor_type="human",
        provider=None,
        model=None,
        tool=None,
    )
    provide_decision_answer(
        run_ref,
        decision.decision_id,
        "test-topic",
        actor,
        emitter=NullEmitter(),
    )

    # Next step: now should issue the discover step.
    decision2 = next_step(run_ref, agent_id="cov-agent", emitter=NullEmitter())
    assert decision2.kind == "step"
    assert decision2.step_id == "discover"


def test_provide_decision_answer_without_pending_raises(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path / "missions")
    run_store = tmp_path / "runs"
    ctx = DiscoveryContext(
        explicit_paths=[yaml_path],
        builtin_roots=[yaml_path],
        user_home=tmp_path / "home",
    )
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={"topic": "preset"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=run_store,
        emitter=NullEmitter(),
    )
    actor = ActorIdentity(
        actor_id="u",
        actor_type="human",
        provider=None,
        model=None,
        tool=None,
    )
    with pytest.raises(MissionRuntimeError):
        provide_decision_answer(
            run_ref,
            "input:nonexistent",
            "value",
            actor,
            emitter=NullEmitter(),
        )


def test_next_step_failed_result_blocks_run(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path / "missions")
    run_store = tmp_path / "runs"
    ctx = DiscoveryContext(
        explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home"
    )
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={"topic": "x"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=run_store,
        emitter=NullEmitter(),
    )
    # Issue first step (success path).
    next_step(run_ref, agent_id="a", emitter=NullEmitter())
    # Mark current step as failed -> blocked.
    decision = next_step(
        run_ref, agent_id="a", result="failed", emitter=NullEmitter()
    )
    assert decision.kind == "blocked"
    assert "failed" in (decision.reason or "").lower()


def test_next_step_blocked_result_blocks_run(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path / "missions")
    run_store = tmp_path / "runs"
    ctx = DiscoveryContext(
        explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home"
    )
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={"topic": "x"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=run_store,
        emitter=NullEmitter(),
    )
    next_step(run_ref, agent_id="a", emitter=NullEmitter())
    decision = next_step(
        run_ref, agent_id="a", result="blocked", emitter=NullEmitter()
    )
    assert decision.kind == "blocked"
    assert "blocked" in (decision.reason or "").lower()


# ---------------------------------------------------------------------------
# engine.notify_decision_timeout
# ---------------------------------------------------------------------------


def test_notify_decision_timeout_raises_for_unknown_decision(tmp_path: Path) -> None:
    yaml_path = _write_simple_mission(tmp_path / "missions")
    run_store = tmp_path / "runs"
    ctx = DiscoveryContext(
        explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home"
    )
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={"topic": "x", "mission_owner_id": "owner-9"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=run_store,
        emitter=NullEmitter(),
    )
    actor = RACIRoleBinding(actor_type="service", actor_id="runtime")
    with pytest.raises(MissionRuntimeError, match="No RACI binding|No significance"):
        notify_decision_timeout(
            run_ref,
            decision_id="audit:nonexistent",
            actor=actor,
            emitter=NullEmitter(),
        )


# ---------------------------------------------------------------------------
# Architectural invariants spot-check (kept here so coverage suite also
# verifies we didn't accidentally re-introduce a quarantined import).
# ---------------------------------------------------------------------------


def test_internal_runtime_does_not_import_quarantined_runtime() -> None:
    """Cheap regression guard: scan the internalized runtime source tree
    for stray ``spec_kitty_runtime`` imports.
    """
    runtime_dir = Path(engine_mod.__file__).parent
    offenders: list[str] = []
    for py_file in runtime_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if "spec_kitty_runtime" in stripped:
                offenders.append(f"{py_file.name}: {stripped}")
    assert offenders == [], (
        "_internal_runtime must not import spec_kitty_runtime: " + "; ".join(offenders)
    )
