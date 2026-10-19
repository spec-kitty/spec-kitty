"""NFR-003: one IdentityIndex (one scan per kind) per ``build_charter_context*`` call (#6406)."""

from __future__ import annotations

import contextlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from charter.activation import context as context_module
from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A synthetic project: minimal config plus a small charter, no copy of the live repo."""
    kittify = tmp_path / ".kittify"
    (kittify / "charter").mkdir(parents=True)
    (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\ncharter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    (kittify / "charter" / "charter.yaml").write_text(
        "schema_version: 2.0.0\ngovernance:\n  charter:\n"
        "    selected_paradigms:\n    - domain-driven-design\n"
        "    selected_directives:\n    - 010-specification-fidelity-requirement\n",
        encoding="utf-8",
    )
    (kittify / "charter" / "charter.md").write_text(
        "# Project Charter\n\n## Policy Summary\n\n- Intent: synthetic project for the identity-reuse probe.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Counter[ArtifactKind], list[IdentityIndex]]]:
    """Count every ``IdentityIndex`` construction (``build``, ``from_pack_context`` or direct) and each per-kind scan."""
    scans: Counter[ArtifactKind] = Counter()
    built: list[IdentityIndex] = []
    original_scan = IdentityIndex._scan
    original_init = IdentityIndex.__init__

    def _counted_scan(self: IdentityIndex, kind: ArtifactKind) -> Any:
        scans[kind] += 1
        return original_scan(self, kind)

    def _counted_init(self: IdentityIndex, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        built.append(self)

    monkeypatch.setattr(IdentityIndex, "_scan", _counted_scan)
    monkeypatch.setattr(IdentityIndex, "__init__", _counted_init)
    yield scans, built


def test_build_charter_context_scans_each_kind_once(project: Path, probe: tuple[Counter[ArtifactKind], list[IdentityIndex]]) -> None:
    scans, built = probe
    result = context_module.build_charter_context(project, action="implement", mission_type="software-dev", mark_loaded=False, depth=2)
    assert result.mode == "bootstrap"
    assert len(built) == 1, f"expected one IdentityIndex per invocation, got {len(built)}"
    assert scans, "positive control: the probe saw at least one scan"
    assert max(scans.values()) == 1, dict(scans)


def test_build_charter_context_json_scans_each_kind_once(project: Path, probe: tuple[Counter[ArtifactKind], list[IdentityIndex]]) -> None:
    scans, built = probe
    payload = context_module.build_charter_context_json(project, action="implement", mission_type="software-dev")
    assert payload["mode"] == "bootstrap"
    assert len(built) == 1
    assert scans
    assert max(scans.values()) == 1, dict(scans)


@pytest.mark.parametrize("selector", ["agent-profile:python-pedro", "glossary-pack:core-terms"])
def test_gated_include_builds_one_index_for_the_whole_invocation(project: Path, probe: tuple[Counter[ArtifactKind], list[IdentityIndex]], selector: str) -> None:
    """The activation-aware service reuses the invocation's index instead of building a second one."""
    scans, built = probe
    with (project / ".kittify" / "charter" / "charter.yaml").open("a", encoding="utf-8") as stream:
        stream.write("activated_agent_profiles:\n  - python-pedro\nactivated_glossary_packs:\n  - core-terms\n")
    with contextlib.suppress(ValueError):  # a glossary pack that is not there is a miss; the service was built and read
        context_module.build_charter_context_include(project, selector)
    assert len(built) == 1, f"expected one IdentityIndex per include invocation, got {len(built)}"
    assert max(scans.values(), default=0) <= 1, dict(scans)
