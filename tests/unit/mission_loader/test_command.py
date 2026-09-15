"""Unit tests for :mod:`specify_cli.mission_loader.command` (T028).

Locks the exit-code matrix and the wire shape of the JSON envelope per
``contracts/mission-run-cli.md``. The functional core is exercised
directly without the Typer wrapper; the Typer rendering is covered by
the JSON-format test (which calls ``_render_envelope`` directly) and
by the integration tests in WP06.
"""

from __future__ import annotations

import io
import json
import textwrap
from collections.abc import Iterator
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from specify_cli.mission_loader.command import (
    RunCustomMissionResult,
    _resolve_contract_refs,
    run_custom_mission,
)
from specify_cli.mission_loader.errors import LoaderErrorCode
from specify_cli.mission_loader.registry import get_runtime_contract_registry
from runtime.next._internal_runtime.discovery import DiscoveryContext
from runtime.next._internal_runtime.schema import MissionTemplate
from tests.specify_cli.mission_step_contracts.test_executor import (
    ORG_FIXTURE_CONTRACT_ID,
    write_org_pack_config,
    write_org_tier_step_contract_fixture,
)

# Minimal valid custom mission body. Last step is the retrospective marker
# so structural checks pass; the planning step has an agent_profile binding.

pytestmark = [pytest.mark.unit]

_VALID_BODY = """
mission:
  key: {key}
  name: {name}
  version: "1.0.0"
steps:
  - id: plan
    title: Plan
    agent_profile: planner
  - id: retrospective
    title: Retrospective
    agent_profile: retro
"""

# Body with the retrospective marker missing.
_NO_RETRO_BODY = """
mission:
  key: {key}
  name: {name}
  version: "1.0.0"
steps:
  - id: plan
    title: Plan
    agent_profile: planner
  - id: write-report
    title: Write Report
    agent_profile: scribe
"""

# Body with a step that points at a nonexistent contract id. Used to
# exercise the cross-module ``MISSION_CONTRACT_REF_UNRESOLVED`` check.
# The ``plan`` step uses ``contract_ref`` (mutually exclusive with
# ``agent_profile`` per the validator, see test_validator_errors.py),
# and the retrospective marker keeps structural validation happy.
_BAD_CONTRACT_REF_BODY = """
mission:
  key: {key}
  name: {name}
  version: "1.0.0"
steps:
  - id: plan
    title: Plan
    contract_ref: nonexistent-id
  - id: retrospective
    title: Retrospective
    agent_profile: retro
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Clear the singleton registry before and after each test."""
    get_runtime_contract_registry().clear()
    yield
    get_runtime_contract_registry().clear()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip discovery env vars so tests cannot pull in side-channel paths."""
    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)


def _write_mission(repo_root: Path, layer: str, key: str, body: str) -> Path:
    mission_dir = repo_root / layer / key
    mission_dir.mkdir(parents=True, exist_ok=True)
    file = mission_dir / "mission.yaml"
    file.write_text(
        textwrap.dedent(body.format(key=key, name=key.replace("-", " ").title())).lstrip(),
        encoding="utf-8",
    )
    return file


def _isolated_context(
    repo_root: Path, *, builtin_roots: list[Path] | None = None
) -> DiscoveryContext:
    """Build a DiscoveryContext that ignores the user's real ~/.kittify."""
    fake_home = repo_root / ".fake-home"
    fake_home.mkdir(exist_ok=True)
    return DiscoveryContext(
        project_dir=repo_root,
        user_home=fake_home,
        builtin_roots=list(builtin_roots or []),
    )


class _FakeRunRef:
    """Minimal stand-in for ``MissionRunRef`` used in monkeypatch paths."""

    def __init__(self, run_id: str, run_dir: str) -> None:
        self.run_id = run_id
        self.run_dir = run_dir


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_returns_zero_and_success_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_mission(repo_root, ".kittify/missions", "erp-integration", _VALID_BODY)

    # meta.json with a mission_id so the envelope reflects the real value.
    feature_dir = repo_root / "kitty-specs" / "erp-q3-rollout-01KQABC"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KQABCDEFGHJKMNPQRSTVWXYZ"}),
        encoding="utf-8",
    )

    fake_run_dir = tmp_path / "runs" / "abc"
    fake_run_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    def fake_get_or_start_run(*, mission_slug: str, repo_root: Path, mission_type: str) -> _FakeRunRef:
        captured["mission_slug"] = mission_slug
        captured["repo_root"] = repo_root
        captured["mission_type"] = mission_type
        return _FakeRunRef(run_id="abc", run_dir=str(fake_run_dir))

    from runtime.next import runtime_bridge

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", fake_get_or_start_run)

    ctx = _isolated_context(repo_root)
    result = run_custom_mission(
        "erp-integration",
        "erp-q3-rollout-01KQABC",
        repo_root,
        discovery_context=ctx,
    )

    assert isinstance(result, RunCustomMissionResult)
    assert result.exit_code == 0
    env = result.envelope
    assert env["result"] == "success"
    assert env["mission_key"] == "erp-integration"
    assert env["mission_slug"] == "erp-q3-rollout-01KQABC"
    assert env["mission_id"] == "01KQABCDEFGHJKMNPQRSTVWXYZ"
    assert env["feature_dir"] == str(feature_dir)
    assert env["run_dir"] == str(fake_run_dir)
    assert env["warnings"] == []

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["mission_id"] == "01KQABCDEFGHJKMNPQRSTVWXYZ"
    assert meta["mission_type"] == "erp-integration"
    assert meta["mission_key"] == "erp-integration"

    # Bridge invoked with the right wiring.
    assert captured["mission_slug"] == "erp-q3-rollout-01KQABC"
    assert captured["mission_type"] == "erp-integration"
    assert captured["repo_root"] == repo_root

    # Synthesized contracts registered in the shadow.
    registry = get_runtime_contract_registry()
    assert registry.lookup("custom:erp-integration:plan") is not None


def test_happy_path_with_no_meta_json_returns_null_mission_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_mission(repo_root, ".kittify/missions", "erp-integration", _VALID_BODY)

    fake_run_dir = tmp_path / "runs" / "x"
    fake_run_dir.mkdir(parents=True)

    from runtime.next import runtime_bridge

    monkeypatch.setattr(
        runtime_bridge,
        "get_or_start_run",
        lambda **_: _FakeRunRef(run_id="x", run_dir=str(fake_run_dir)),
    )

    ctx = _isolated_context(repo_root)
    result = run_custom_mission(
        "erp-integration", "tracked-mission-slug", repo_root, discovery_context=ctx
    )
    assert result.exit_code == 0
    assert result.envelope["mission_id"] is None
    meta_path = repo_root / "kitty-specs" / "tracked-mission-slug" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["mission_type"] == "erp-integration"
    assert meta["mission_key"] == "erp-integration"


# ---------------------------------------------------------------------------
# Validation errors (exit code 2)
# ---------------------------------------------------------------------------


def test_validation_error_returns_two_with_error_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_mission(repo_root, ".kittify/missions", "no-retro", _NO_RETRO_BODY)

    # If runtime_bridge is invoked we want the test to fail fast.
    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> _FakeRunRef:  # pragma: no cover - guard
        raise AssertionError("get_or_start_run must not be called on validation error")

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    ctx = _isolated_context(repo_root)
    result = run_custom_mission("no-retro", "any-slug", repo_root, discovery_context=ctx)

    assert result.exit_code == 2
    env = result.envelope
    assert env["result"] == "error"
    assert env["error_code"] == "MISSION_RETROSPECTIVE_MISSING"
    assert env["details"]["mission_key"] == "no-retro"
    assert env["details"]["expected"] == "retrospective"
    assert env["details"]["actual_last_step_id"] == "write-report"
    assert env["warnings"] == []

    # Registry stays untouched on validation error.
    assert not get_runtime_contract_registry()._contracts  # type: ignore[attr-defined]


def test_unknown_key_returns_two_with_MISSION_KEY_UNKNOWN(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # No mission YAMLs at all.
    ctx = _isolated_context(repo_root)
    result = run_custom_mission("nope", "any-slug", repo_root, discovery_context=ctx)
    assert result.exit_code == 2
    assert result.envelope["error_code"] == "MISSION_KEY_UNKNOWN"
    assert result.envelope["details"]["mission_key"] == "nope"
    assert "tiers_searched" in result.envelope["details"]


def test_unresolved_contract_ref_returns_two_with_MISSION_CONTRACT_REF_UNRESOLVED(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-2 regression: a step's ``contract_ref`` that does not resolve in
    the on-disk :class:`MissionStepContractRepository` produces a
    structured ``MISSION_CONTRACT_REF_UNRESOLVED`` envelope (exit 2)
    BEFORE ``runtime_bridge.get_or_start_run`` is invoked.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    file = _write_mission(
        repo_root, ".kittify/missions", "bad-ref", _BAD_CONTRACT_REF_BODY
    )

    # Seed an empty doctrine project_dir so the repository points at a real
    # location with zero contracts. The shipped (built-in) repository never
    # carries a contract called "nonexistent-id", so the resolution must fail.
    (repo_root / ".kittify" / "doctrine" / "mission_step_contracts").mkdir(
        parents=True
    )

    # If the bridge is invoked, we want the test to fail loudly: the unresolved
    # contract_ref check must short-circuit before ``get_or_start_run`` runs.
    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> _FakeRunRef:  # pragma: no cover - guard
        raise AssertionError(
            "get_or_start_run must not be called when contract_ref is unresolved"
        )

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    ctx = _isolated_context(repo_root)
    result = run_custom_mission(
        "bad-ref", "tracked-slug", repo_root, discovery_context=ctx
    )

    assert result.exit_code == 2
    env = result.envelope
    assert env["result"] == "error"
    assert env["error_code"] == "MISSION_CONTRACT_REF_UNRESOLVED"
    details = env["details"]
    assert details["mission_key"] == "bad-ref"
    assert details["step_id"] == "plan"
    assert details["contract_ref"] == "nonexistent-id"
    assert details["file"] == str(file)
    assert env["warnings"] == []

    # Registry must not have been populated for an unresolved contract_ref --
    # the check runs BEFORE synthesis is registered.
    assert not get_runtime_contract_registry()._contracts  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FR-006a org-tier resolution (T014, SC-003) + identical-absent-failure proof
# shared with tests/runtime/test_bridge_composition.py's T013 (User Story 2,
# Acceptance Scenario 3).
#
# SC-003 calls for ONE synthetic org-pack fixture reused by three test
# functions (WP02's executor/gate_bindings tests plus this WP's runtime/
# mission-load pair) -- the SAME ``write_org_tier_step_contract_fixture`` /
# ``write_org_pack_config`` / ``ORG_FIXTURE_CONTRACT_ID`` that
# tests/specify_cli/mission_step_contracts/test_executor.py (T008) and
# tests/review/test_gate_bindings.py (T010) already import, not a
# locally-duplicated copy. A prior revision of this file (and
# tests/runtime/test_bridge_composition.py) duplicated a smaller
# ``_write_org_step_contract_fixture`` verbatim in both files because WP02
# had not yet landed when this WP was authored; that duplication was
# retired here in favor of the canonical shared fixture now that it exists,
# per this mission's pre-merge review.
# ---------------------------------------------------------------------------


def _org_tier_template() -> MissionTemplate:
    return MissionTemplate.model_validate(
        {
            "mission": {
                "key": "custom-mission",
                "name": "Custom Mission",
                "version": "1.0.0",
            },
            "steps": [
                {
                    "id": "step1",
                    "title": "Step One",
                    "contract_ref": ORG_FIXTURE_CONTRACT_ID,
                }
            ],
        }
    )


def test_resolve_contract_refs_resolves_org_tier_contract_ref(
    tmp_path: Path,
) -> None:
    """FR-006a / T014 / SC-003: mission-load validation resolves the same
    org-tier ``contract_ref`` FR-006's runtime dispatch resolves (T013 in
    tests/runtime/test_bridge_composition.py), now that
    ``_resolve_contract_refs`` threads
    ``resolve_org_dirs(repo_root, "mission_step_contracts")`` into the
    ``MissionStepContractRepository`` it constructs."""
    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(tmp_path, org_root)

    error = _resolve_contract_refs(
        mission_key="custom-mission",
        template=_org_tier_template(),
        source_path="irrelevant.yaml",
        repo_root=tmp_path,
    )

    assert error is None


def test_resolve_contract_refs_returns_error_when_org_pack_absent(
    tmp_path: Path,
) -> None:
    """User Story 2, Acceptance Scenario 3 -- identical-failure half, paired
    with ``test_resolve_runtime_contract_for_step_returns_none_when_org_pack_absent``
    in tests/runtime/test_bridge_composition.py. With the org pack not
    configured at all (no ``.kittify/config.yaml``), the SAME org-tier
    ``contract_ref`` used by the success test above fails to resolve at
    mission-load validation time too, with the documented
    ``MISSION_CONTRACT_REF_UNRESOLVED`` error code -- proving the lockstep
    pair's FAILURE mode is identical to FR-006's runtime dispatch failure
    mode, not merely that both happen to pass independently in the success
    case."""
    error = _resolve_contract_refs(
        mission_key="custom-mission",
        template=_org_tier_template(),
        source_path="irrelevant.yaml",
        repo_root=tmp_path,
    )

    assert error is not None
    assert error.code == LoaderErrorCode.MISSION_CONTRACT_REF_UNRESOLVED
    assert error.details["contract_ref"] == ORG_FIXTURE_CONTRACT_ID


# ---------------------------------------------------------------------------
# Run-start exception (exit code 1)
# ---------------------------------------------------------------------------


def test_run_start_failure_returns_one_with_RUN_START_FAILED(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_mission(repo_root, ".kittify/missions", "ok-mission", _VALID_BODY)

    from runtime.next import runtime_bridge

    def _boom(**_: object) -> _FakeRunRef:
        raise RuntimeError("disk full")

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _boom)

    ctx = _isolated_context(repo_root)
    result = run_custom_mission(
        "ok-mission", "tracked-slug", repo_root, discovery_context=ctx
    )
    assert result.exit_code == 1
    env = result.envelope
    assert env["result"] == "error"
    assert env["error_code"] == "RUN_START_FAILED"
    assert "disk full" in env["message"]
    assert env["details"] == {
        "mission_key": "ok-mission",
        "mission_slug": "tracked-slug",
    }
    assert env["warnings"] == []

    # Registry was cleared after the failure to avoid stale shadow state.
    assert not get_runtime_contract_registry()._contracts  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Warnings pass through
# ---------------------------------------------------------------------------


def test_warnings_pass_through_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two tiers define the same key; the higher tier wins and a shadow
    warning surfaces in the success envelope."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Both tiers carry the same key so we trigger MISSION_KEY_SHADOWED.
    _write_mission(repo_root, ".kittify/missions", "shadowy", _VALID_BODY)
    _write_mission(repo_root, ".kittify/overrides/missions", "shadowy", _VALID_BODY)

    fake_run_dir = tmp_path / "runs" / "y"
    fake_run_dir.mkdir(parents=True)

    from runtime.next import runtime_bridge

    monkeypatch.setattr(
        runtime_bridge,
        "get_or_start_run",
        lambda **_: _FakeRunRef(run_id="y", run_dir=str(fake_run_dir)),
    )

    ctx = _isolated_context(repo_root)
    result = run_custom_mission(
        "shadowy", "tracked-slug", repo_root, discovery_context=ctx
    )
    assert result.exit_code == 0
    warnings = result.envelope["warnings"]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "MISSION_KEY_SHADOWED"
    assert warnings[0]["details"]["mission_key"] == "shadowy"
    assert warnings[0]["details"]["selected_tier"] == "project_override"


# ---------------------------------------------------------------------------
# JSON rendering
# ---------------------------------------------------------------------------


def test_render_envelope_json_format() -> None:
    """``_render_envelope`` with ``json_output=True`` writes parseable JSON."""
    from specify_cli.cli.commands.mission_type import _render_envelope

    envelope = {
        "result": "success",
        "mission_key": "erp",
        "mission_slug": "slug",
        "mission_id": None,
        "feature_dir": "/nonexistent/feature",
        "run_dir": "/nonexistent/run",
        "warnings": [],
    }
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        _render_envelope(envelope, json_output=True)
    output = buffer.getvalue()
    parsed = json.loads(output)
    assert parsed == envelope


def test_render_envelope_human_format_success() -> None:
    """``_render_envelope`` with ``json_output=False`` does not raise and
    renders something to the rich console."""
    from specify_cli.cli.commands.mission_type import _render_envelope

    envelope = {
        "result": "success",
        "mission_key": "erp",
        "mission_slug": "slug",
        "mission_id": "01KV7SFD0123456789ABCDEFGH",
        "feature_dir": "/nonexistent/feature",
        "run_dir": "/nonexistent/run",
        "warnings": [{"code": "MISSION_KEY_SHADOWED", "message": "hi", "details": {}}],
    }
    # No stdout assertion -- just that the call completes without error.
    _render_envelope(envelope, json_output=False)


def test_render_envelope_human_format_error() -> None:
    from specify_cli.cli.commands.mission_type import _render_envelope

    envelope = {
        "result": "error",
        "error_code": "MISSION_RETROSPECTIVE_MISSING",
        "message": "boom",
        "details": {"mission_key": "x", "expected": "retrospective"},
        "warnings": [],
    }
    _render_envelope(envelope, json_output=False)


# ---------------------------------------------------------------------------
# Default discovery context construction
# ---------------------------------------------------------------------------


def test_default_discovery_context_is_built_when_none_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``discovery_context`` is not provided we fall back to the
    repo-root-derived context. Exercises the `_build_discovery_context`
    helper without requiring a real built-in tree."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Place a custom mission in the project tier so the builtin tree is
    # irrelevant for resolution.
    _write_mission(repo_root, ".kittify/missions", "ok-mission", _VALID_BODY)

    fake_run_dir = tmp_path / "runs" / "z"
    fake_run_dir.mkdir(parents=True)

    from runtime.next import runtime_bridge

    monkeypatch.setattr(
        runtime_bridge,
        "get_or_start_run",
        lambda **_: _FakeRunRef(run_id="z", run_dir=str(fake_run_dir)),
    )
    # Make sure the user-home tier cannot leak in real missions.
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(exist_ok=True)

    result = run_custom_mission("ok-mission", "tracked-slug", repo_root)
    assert result.exit_code == 0
    assert result.envelope["mission_key"] == "ok-mission"


def test_org_tier_mission_discovered_via_third_wiring_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-006 / User Story 3 Acceptance Scenario 4: this module's own,
    independently-duplicated `_build_discovery_context` (the "third wiring
    site" the originating research missed) populates `org_roots` and
    discovers a mission there -- proving `mission run <key>` sees the org
    tier, not just the generic `spec-kitty next` engine.

    Uses the REAL discovery context (no `discovery_context=` override) so
    `resolve_org_roots` actually runs through this module's own code path,
    not a test-injected shortcut.
    """
    from runtime.next._internal_runtime.discovery import discover_missions_with_warnings
    from specify_cli.mission_loader import command as command_mod

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    org_root = tmp_path / "org-pack"
    _write_mission(org_root, "missions", "org-custom-mission", _VALID_BODY)

    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: acme\n"
        f"        local_path: {org_root}\n",
        encoding="utf-8",
    )

    # Isolate the user-home tier so it cannot leak a real mission in.
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(exist_ok=True)

    # Unit-level proof: this module's own _build_discovery_context (not an
    # injected override) resolves the org root and surfaces the mission at
    # tier "org".
    ctx = command_mod._build_discovery_context(repo_root)
    assert org_root in ctx.org_roots
    discovered = discover_missions_with_warnings(ctx).missions
    match = next(d for d in discovered if d.key == "org-custom-mission")
    assert match.precedence_tier == "org"
    assert match.selected is True

    # End-to-end proof: run_custom_mission (no discovery_context override)
    # succeeds using this same org-tier mission.
    fake_run_dir = tmp_path / "runs" / "org-run"
    fake_run_dir.mkdir(parents=True)

    from runtime.next import runtime_bridge

    monkeypatch.setattr(
        runtime_bridge,
        "get_or_start_run",
        lambda **_: _FakeRunRef(run_id="org-run", run_dir=str(fake_run_dir)),
    )

    result = run_custom_mission("org-custom-mission", "org-tracked-slug", repo_root)
    assert result.exit_code == 0, result.envelope
    assert result.envelope["result"] == "success"
    assert result.envelope["mission_key"] == "org-custom-mission"


def test_build_discovery_context_malformed_config_emits_no_warning_stream(
    tmp_path: Path,
) -> None:
    """Regression guard (pre-merge lens, mission
    ``up-org-template-fsm-01M06F9K``): this module's own
    `_build_discovery_context` -- the "third wiring site" (DEC-006) -- is a
    resolution hot path that may run many times per invocation. A project
    with no readable org-pack intent (this config can't even be parsed by
    `load_pack_registry`) must see ZERO new warning output: NFR-005/SC-007
    requires byte-identical behaviour, explicitly including "same log
    output, no new warnings", for a project with no org pack configured."""
    import warnings

    from specify_cli.mission_loader import command as command_mod

    repo_root = tmp_path / "repo"
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "not: [valid, doctrine.org.packs shape\n", encoding="utf-8"
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ctx = command_mod._build_discovery_context(repo_root)

    assert caught == []
    assert ctx.org_roots == []
    assert ctx.project_dir == repo_root


def test_build_discovery_context_declared_but_broken_org_pack_still_warns(
    tmp_path: Path,
) -> None:
    """Positive case for the fix above: a config that DOES declare
    ``doctrine.org.packs`` but fails schema validation (here, two packs
    sharing the same ``name``) is a genuinely misconfigured org pack -- the
    operator demonstrably opted in and deserves to know it's broken. That
    signal must remain diagnosable through this same resolution hot path,
    unlike the "can't even parse the file" case above."""
    import warnings

    from specify_cli.mission_loader import command as command_mod

    repo_root = tmp_path / "repo"
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    acme_one = tmp_path / "acme-one"
    acme_two = tmp_path / "acme-two"
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: acme\n"
        f"        local_path: {acme_one}\n"
        "      - name: acme\n"
        f"        local_path: {acme_two}\n",
        encoding="utf-8",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ctx = command_mod._build_discovery_context(repo_root)

    assert len(caught) == 1
    assert "Invalid org-pack config; ignoring org layer:" in str(caught[0].message)
    # Fails soft to zero org roots -- resolution still proceeds, it just
    # can't trust the broken declaration.
    assert ctx.org_roots == []
