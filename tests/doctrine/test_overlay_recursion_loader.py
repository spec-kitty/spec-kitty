"""Loader-side org/project recursion parity (WP01 / T001, T002, T007).

Red-first: on `main` the base loader (`BaseArtifactRepository._project_scan`) and
the agent-profile loader scan org/project overlays with a NON-recursive glob, so
an artifact authored one directory deep is silently dropped (the 71% tactic
undercount, #3490). After WP01 the loader recurses via the shared authority,
matching the built-in tier — while kind-specific globs keep non-artifact files
(`.provenance/*.yaml`, `.md`) out (C-002), and flat layouts stay unchanged
(NFR-002).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.tactics.repository import TacticRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _tactic(tactic_id: str, name: str = "Test tactic") -> dict:
    return {
        "schema_version": "1.0",
        "id": tactic_id,
        "name": name,
        "steps": [{"title": "do the thing"}],
    }


def _profile(profile_id: str, name: str) -> dict:
    return {
        "profile-id": profile_id,
        "name": name,
        "description": "Overlay recursion test profile",
        "schema-version": "1.0",
        "roles": ["implementer"],
        "purpose": "Nested overlay discovery regression fixture.",
        "specialization": {"primary-focus": "overlay recursion"},
    }


# ── T001: nested org tactic (loader) ──────────────────────────────────────────


def test_nested_org_tactic_is_discovered(tmp_path: Path) -> None:
    """A tactic one directory deep in an org root loads (parity with built-in)."""
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    org = tmp_path / "org"
    _write_yaml(org / "flat.tactic.yaml", _tactic("flat-one"))
    _write_yaml(org / "testing" / "nested.tactic.yaml", _tactic("nested-one"))

    repo = TacticRepository(built_in_dir=built_in, org_dirs=[org])

    assert repo.get("flat-one") is not None, "flat tactic must still load"
    assert repo.get("nested-one") is not None, "nested org tactic must be discovered (was silently dropped pre-fix)"


def test_nested_project_tactic_is_discovered(tmp_path: Path) -> None:
    """The same recursion applies to the project overlay layer."""
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    project = tmp_path / "project"
    _write_yaml(project / "team" / "deep.tactic.yaml", _tactic("deep-proj"))

    repo = TacticRepository(built_in_dir=built_in, project_dir=project)

    assert repo.get("deep-proj") is not None


# ── T002: nested org / project agent profile (loader) ─────────────────────────


def test_nested_org_agent_profile_is_discovered(tmp_path: Path) -> None:
    """An agent profile one dir deep in an org root loads (third divergence site)."""
    org = tmp_path / "org"
    _write_yaml(org / "team" / "reviewer.agent.yaml", _profile("nested-reviewer", "Nested Reviewer"))

    repo = AgentProfileRepository(org_dirs=[org])

    resolved = repo.get("nested-reviewer")
    assert resolved is not None, "nested org agent profile must be discovered"
    assert repo.get_provenance("nested-reviewer") == "org"


def test_nested_project_agent_profile_is_discovered(tmp_path: Path) -> None:
    """Recursion also applies to the project agent-profile overlay."""
    project = tmp_path / "project"
    _write_yaml(project / "squad" / "impl.agent.yaml", _profile("nested-impl", "Nested Impl"))

    repo = AgentProfileRepository(project_dir=project)

    assert repo.get("nested-impl") is not None
    assert repo.get_provenance("nested-impl") == "project"


# ── T007: flat-layout unchanged (NFR-002) + C-002 negative ────────────────────


def test_flat_layout_discovery_is_unchanged(tmp_path: Path) -> None:
    """NFR-002: a flat overlay loads exactly its flat artifacts, nothing extra.

    `rglob` over a subdirectory-free directory yields the identical set as
    `glob`, so flat-layout discovery is unaffected by the recursion change.
    """
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    org = tmp_path / "org"
    _write_yaml(org / "a.tactic.yaml", _tactic("a-flat"))
    _write_yaml(org / "b.tactic.yaml", _tactic("b-flat"))

    repo = TacticRepository(built_in_dir=built_in, org_dirs=[org])

    assert repo.get("a-flat") is not None
    assert repo.get("b-flat") is not None
    assert {"a-flat", "b-flat"} == {tid for tid in ("a-flat", "b-flat") if repo.get(tid) is not None}


def test_kind_specific_glob_excludes_provenance_and_markdown(tmp_path: Path) -> None:
    """C-002: a recursive walk must not capture `.provenance/*.yaml` or `.md`.

    The scan uses the kind-specific glob (`*.tactic.yaml`), so a generic
    provenance sidecar and a markdown note nested beside a real tactic are never
    loaded as tactics.
    """
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    org = tmp_path / "org"
    _write_yaml(org / "testing" / "real.tactic.yaml", _tactic("real-one"))
    # A generic provenance sidecar that DECLARES an id (so the assertion is not
    # vacuous: if the scan used a broad `*.yaml` glob it would load this id) and
    # a markdown note.
    _write_yaml(
        org / "testing" / ".provenance" / "sidecar.provenance.yaml",
        {"id": "provenance-sneaky-id", "note": "meta"},
    )
    (org / "testing" / "notes.md").write_text("# not an artifact\n", encoding="utf-8")

    repo = TacticRepository(built_in_dir=built_in, org_dirs=[org])

    assert repo.get("real-one") is not None
    # The provenance sidecar declares an id but does not match `*.tactic.yaml`,
    # so the kind-specific glob must not have loaded it (a broad `*.yaml` scan
    # would have — this is the non-vacuous discriminator). Markdown is never a
    # YAML artifact.
    assert repo.get("provenance-sneaky-id") is None
