"""Consumer census builder guards (#6173, mission derived-consumer-census-01M4V5P5).

The census (``scripts/ci/consumer_census.py``) is the committed, regenerable map of
which test module consumes which ``src/**``/``packs/**`` path — static import/read
PLUS runtime resolver capture. These tests pin:

* determinism / freshness — a rebuild reproduces the committed artifact byte-for-byte;
* the three historical #6166 pins are recorded, each with the right provenance;
* the runtime half is non-vacuous — the ``tests/next`` prompt edge is captured as
  ``runtime`` (a grep of ``tests/next`` would miss it), proving the audit-hook
  capture does work the static scan cannot;
* module-set agnosticism (#6164 robustness) — every census module is a registry
  module, derived at build time, never hardcoded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import consumer_census as cc
from scripts.ci.gate_selection import _registry_module_names

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def census() -> dict[str, object]:
    return cc.build_census()


def _consumes(census: dict[str, object], module: str) -> list[dict[str, str]]:
    modules = census["modules"]
    assert isinstance(modules, dict)
    entry = modules.get(module, {})
    return list(entry.get("consumes", [])) if isinstance(entry, dict) else []


def _find(census: dict[str, object], module: str, needle: str) -> dict[str, str] | None:
    for e in _consumes(census, module):
        if needle in e["path"]:
            return e
    return None


# ---------------------------------------------------------------------------
# Determinism / freshness (FR-004 / NFR-003)
# ---------------------------------------------------------------------------
def test_committed_census_matches_a_rebuild(census: dict[str, object]) -> None:
    """The committed artifact equals a fresh build (regenerate with ``--write``)."""
    committed = cc.load_census()
    assert committed == census, "committed .github/ci-consumer-census.json is stale — run `python scripts/ci/consumer_census.py --write`"


def test_rebuild_is_deterministic() -> None:
    """Two builds on an unchanged tree are byte-identical (sorted, offline)."""
    assert cc._serialize(cc.build_census()) == cc._serialize(cc.build_census())


def test_cli_check_passes() -> None:
    """The ``--check`` CLI agrees the committed artifact is up to date (exit 0)."""
    assert cc.main(["--check"]) == 0


# ---------------------------------------------------------------------------
# The three #6166 historical pins are recorded with the right provenance
# ---------------------------------------------------------------------------
def test_next_consumes_the_mission_step_prompt_at_runtime(census: dict[str, object]) -> None:
    """``tests/next`` resolves the mission-step prompt through the CLI/resolver
    without naming its path — captured as ``runtime`` (the #6156 canonical case)."""
    entry = _find(census, "next", "packs/built-in/missions/mission-steps")
    assert entry is not None, "census did not record next consuming a mission-steps prompt"
    assert entry["provenance"] == "runtime", f"expected runtime provenance, got {entry!r}"


def test_agent_consumes_lifecycle_via_static_import(census: dict[str, object]) -> None:
    """``tests/agent`` imports ``cli/commands/lifecycle.py`` (a dynamic
    ``importlib.import_module`` string) — captured as a static import (#6161)."""
    entry = _find(census, "agent", "specify_cli/cli/commands/lifecycle.py")
    assert entry is not None, "census did not record agent consuming lifecycle.py"
    assert entry["provenance"] == "static-import"


def test_dossier_consumes_the_manifest_at_runtime(census: dict[str, object]) -> None:
    """``tests/*dossier*`` loads ``expected-artifacts.yaml`` through ``index_feature``
    without naming the pack path — captured as ``runtime`` (#6153)."""
    entry = _find(census, "dossier", "expected-artifacts.yaml")
    assert entry is not None, "census did not record dossier consuming the manifest"
    assert entry["provenance"] == "runtime"


# ---------------------------------------------------------------------------
# Runtime capture non-vacuity: the prompt path is NOT statically named in
# tests/next, so only the runtime half can have found it (the grep-miss case).
# ---------------------------------------------------------------------------
def test_runtime_capture_finds_a_grep_invisible_read(census: dict[str, object]) -> None:
    """The next->prompt edge is runtime-only: no ``tests/next`` file names the
    captured prompt path as a string literal, so a static-only census misses it.

    Positive control for the audit-hook capture (FR-003): proves the runtime half
    adds real edges the static half cannot, rather than being a no-op.
    """
    entry = _find(census, "next", "packs/built-in/missions/mission-steps")
    assert entry is not None and entry["provenance"] == "runtime"
    captured_path = entry["path"]
    # The captured representative path is not written verbatim in any tests/next file.
    named = [p for p in (_REPO_ROOT / "tests" / "next").rglob("*.py") if captured_path in p.read_text(encoding="utf-8")]
    assert not named, f"{captured_path} IS named in {named}; pick a runtime-only representative"


# ---------------------------------------------------------------------------
# Module-set agnosticism (NFR-002): derived from the registry, never hardcoded.
# ---------------------------------------------------------------------------
def test_every_census_module_is_a_registry_module(census: dict[str, object]) -> None:
    modules = census["modules"]
    assert isinstance(modules, dict)
    registry = _registry_module_names()
    stray = set(modules) - set(registry)
    assert not stray, f"census names non-registry modules (not #6164-robust): {sorted(stray)}"


def test_census_is_non_empty_and_well_formed(census: dict[str, object]) -> None:
    assert census["schema_version"] == 1
    modules = census["modules"]
    assert isinstance(modules, dict) and modules
    for _module, data in modules.items():
        assert isinstance(data, dict) and data["consumes"]
        for entry in data["consumes"]:
            assert set(entry) == {"path", "provenance", "via"}
            assert entry["provenance"] in {"static-import", "runtime"}
