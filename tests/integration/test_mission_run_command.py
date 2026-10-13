"""Integration tests for ``spec-kitty mission run`` (WP06 / T030, T031).

Locks the wire-shape of both the success envelope (FR-001, FR-013) and
the operator-fixable validation error envelopes (FR-005, FR-011) by
driving the functional core ``run_custom_mission`` against three real
ERP-style YAML fixtures copied into a tmp project.

The Typer wrapper (`mission_type.run_cmd`) is a thin shim over
``run_custom_mission`` (see ``src/specify_cli/cli/commands/mission_type.py``);
unit-level CliRunner coverage already exists in
``tests/unit/mission_loader/test_command.py`` for the rendering helper.
We exercise the functional core here to keep the suite hermetic — no
``CliRunner`` chdir-state quirks, no real runtime spin-up. The runtime
bridge's ``get_or_start_run`` is monkeypatched to a deterministic stub so
the happy path returns success without writing any runtime state.

NFR-004: this whole module is expected to run in well under one second
on a developer machine; do not introduce any subprocess or DRG load.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_loader.command import (
    RunCustomMissionResult,
    run_custom_mission,
)
from specify_cli.mission_loader.registry import get_runtime_contract_registry
from runtime.next._internal_runtime.discovery import DiscoveryContext


# Path to the on-disk fixtures created by T029.

pytestmark = [pytest.mark.integration]

_FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "missions"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Clear the singleton runtime-contract registry between tests."""
    get_runtime_contract_registry().clear()
    yield
    get_runtime_contract_registry().clear()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip discovery env vars so tests cannot pull in side-channel paths."""
    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)


class _FakeRunRef:
    """Minimal stand-in for ``MissionRunRef`` used by the happy-path stub."""

    def __init__(self, run_id: str, run_dir: str) -> None:
        self.run_id = run_id
        self.run_dir = run_dir


def _setup_project(tmp_path: Path, fixture: str) -> Path:
    """Copy a named fixture into ``<tmp_path>/.kittify/missions/<fixture>/``.

    Returns ``tmp_path`` (the project root). The fixture name must match
    a directory under ``tests/fixtures/missions/``.
    """
    src = _FIXTURES_ROOT / fixture / "mission.yaml"
    if not src.is_file():
        raise FileNotFoundError(f"Test fixture not found: {src}")

    project_missions_dir = tmp_path / ".kittify" / "missions" / fixture
    project_missions_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, project_missions_dir / "mission.yaml")
    return tmp_path


def _isolated_context(repo_root: Path) -> DiscoveryContext:
    """Build a DiscoveryContext that ignores the user's real ``~/.kittify``."""
    fake_home = repo_root / ".fake-home"
    fake_home.mkdir(exist_ok=True)
    return DiscoveryContext(
        project_dir=repo_root,
        user_home=fake_home,
        builtin_roots=[],
    )


def _fake_get_or_start_run_factory(run_dir: Path) -> Any:
    """Return a stub ``get_or_start_run`` that yields a fixed run_dir."""

    def _stub(**kwargs: Any) -> _FakeRunRef:  # noqa: ARG001 - signature compat
        return _FakeRunRef(run_id="fake-run-id", run_dir=str(run_dir))

    return _stub


# ---------------------------------------------------------------------------
# T030 — CLI happy path
# ---------------------------------------------------------------------------


def test_run_command_starts_runtime_with_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-001 / FR-013: success envelope shape locked.

    Drives the functional core directly so the assertion targets the
    exact ``RunCustomMissionResult.envelope`` dict the Typer wrapper
    serializes via ``json.dumps``. Mirrors what
    ``spec-kitty mission run erp-integration --mission erp-q3-rollout
    --json`` would emit.
    """
    repo_root = _setup_project(tmp_path, fixture="erp-integration")

    fake_run_dir = tmp_path / "runs" / "fake-run-id"
    fake_run_dir.mkdir(parents=True)

    from runtime.next import runtime_bridge

    monkeypatch.setattr(
        runtime_bridge,
        "get_or_start_run",
        _fake_get_or_start_run_factory(fake_run_dir),
    )

    result = run_custom_mission(
        "erp-integration",
        "erp-q3-rollout",
        repo_root,
        discovery_context=_isolated_context(repo_root),
    )

    assert isinstance(result, RunCustomMissionResult)
    assert result.exit_code == 0, result.envelope
    envelope = result.envelope
    assert envelope["result"] == "success"
    assert envelope["mission_key"] == "erp-integration"
    assert envelope["mission_slug"] == "erp-q3-rollout"
    # mission_id is None when no kitty-specs/<slug>/meta.json exists yet —
    # the contract permits null and the field MUST be present.
    assert "mission_id" in envelope
    assert envelope["mission_id"] is None
    assert envelope["feature_dir"] == str(repo_root / "kitty-specs" / "erp-q3-rollout")
    assert envelope["run_dir"] == str(fake_run_dir)
    assert envelope["warnings"] == []

    # Round-trip through json.dumps to lock the wire shape end-to-end.
    serialized = json.dumps(envelope)
    reparsed = json.loads(serialized)
    assert reparsed == envelope


# ---------------------------------------------------------------------------
# T031 — Validation error envelopes
# ---------------------------------------------------------------------------


def test_missing_retrospective_returns_error_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-005 / FR-013: missing retrospective marker → exit 2 + structured error."""
    repo_root = _setup_project(tmp_path, fixture="missing-retrospective")

    # A validation error MUST short-circuit before runtime_bridge runs.
    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> _FakeRunRef:  # pragma: no cover - guard
        raise AssertionError(
            "get_or_start_run must not be called when validation fails"
        )

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    result = run_custom_mission(
        "missing-retrospective",
        "x",
        repo_root,
        discovery_context=_isolated_context(repo_root),
    )

    assert result.exit_code == 2
    envelope = result.envelope
    assert envelope["result"] == "error"
    assert envelope["error_code"] == "MISSION_RETROSPECTIVE_MISSING"
    assert "actual_last_step_id" in envelope["details"]
    assert envelope["details"]["actual_last_step_id"] == "write-report"
    assert envelope["details"]["mission_key"] == "missing-retrospective"
    assert envelope["warnings"] == []


@pytest.mark.parametrize(
    ("collect_dependencies", "build_dependencies", "expected_reference"),
    [
        ("[colect-typo]", "[collect]", "colect-typo"),
        ("[build]", "[collect]", "collect"),
    ],
)
def test_invalid_dependencies_refuse_run_before_runtime_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collect_dependencies: str,
    build_dependencies: str,
    expected_reference: str,
) -> None:
    repo_root = tmp_path
    mission_dir = repo_root / ".kittify" / "missions" / "bad"
    mission_dir.mkdir(parents=True)
    (mission_dir / "mission.yaml").write_text(
        "mission: {key: bad, name: Bad, version: 0.1.0}\n"
        "steps:\n"
        f"  - {{id: collect, title: Collect, agent_profile: researcher, depends_on: {collect_dependencies}}}\n"
        f"  - {{id: build, title: Build, agent_profile: implementer, depends_on: {build_dependencies}}}\n"
        "  - {id: retrospective, title: Retro, depends_on: [build]}\n",
        encoding="utf-8",
    )

    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> None:
        raise AssertionError("invalid mission must not start a runtime")

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    result = run_custom_mission(
        "bad", "m-bad", repo_root, discovery_context=_isolated_context(repo_root)
    )

    assert result.exit_code == 2
    assert result.envelope["result"] == "error"
    assert result.envelope["error_code"] == "MISSION_STEP_DEPENDENCY_INVALID"
    assert expected_reference in result.envelope["message"]
    assert not (repo_root / "kitty-specs" / "m-bad").exists()
    assert not (repo_root / ".kittify" / "runtime").exists()


def test_reserved_key_shadow_returns_error_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011 / FR-013: a project mission keyed ``software-dev`` is rejected."""
    repo_root = _setup_project(tmp_path, fixture="reserved-shadow")

    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> _FakeRunRef:  # pragma: no cover - guard
        raise AssertionError(
            "get_or_start_run must not be called when validation fails"
        )

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    # The reserved-shadow fixture lives at .kittify/missions/reserved-shadow/
    # but its mission.yaml declares mission.key: software-dev. We need
    # discovery to walk the project tier and find it; pass builtin_roots
    # empty so the built-in software-dev does not shadow the reserved key
    # detection.
    ctx = _isolated_context(repo_root)
    # Move the fixture to be discoverable under the reserved key. Discovery
    # uses the directory name (key from path) so we copy to a directory
    # named ``software-dev``.
    src = repo_root / ".kittify" / "missions" / "reserved-shadow" / "mission.yaml"
    sw_dir = repo_root / ".kittify" / "missions" / "software-dev"
    sw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, sw_dir / "mission.yaml")

    result = run_custom_mission(
        "software-dev",
        "x",
        repo_root,
        discovery_context=ctx,
    )

    assert result.exit_code == 2
    envelope = result.envelope
    assert envelope["result"] == "error"
    assert envelope["error_code"] == "MISSION_KEY_RESERVED"
    assert envelope["details"]["mission_key"] == "software-dev"
    assert "reserved_keys" in envelope["details"]
    assert "software-dev" in envelope["details"]["reserved_keys"]


def test_unknown_mission_key_returns_error_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-013: unknown key → exit 2 + ``MISSION_KEY_UNKNOWN`` envelope."""
    repo_root = _setup_project(tmp_path, fixture="erp-integration")

    from runtime.next import runtime_bridge

    def _should_not_run(**_: object) -> _FakeRunRef:  # pragma: no cover - guard
        raise AssertionError(
            "get_or_start_run must not be called when validation fails"
        )

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _should_not_run)

    result = run_custom_mission(
        "no-such-key",
        "x",
        repo_root,
        discovery_context=_isolated_context(repo_root),
    )

    assert result.exit_code == 2
    envelope = result.envelope
    assert envelope["result"] == "error"
    assert envelope["error_code"] == "MISSION_KEY_UNKNOWN"
    assert envelope["details"]["mission_key"] == "no-such-key"
    assert "tiers_searched" in envelope["details"]
