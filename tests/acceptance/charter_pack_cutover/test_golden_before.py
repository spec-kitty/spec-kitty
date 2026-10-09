"""The frozen NFR-001 golden "before" sets stay what the base produced (#3732, T003).

No xfail here: these pass at the base and must keep passing through the mission.
Golden data is never recomputed in a test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._effective_set import ALL_BUILTIN, KINDS
from ._requirements import REPO_ROOT
from ._support import active_charter, covers, file_digest, load_yaml
from .legacy_fixtures import (
    BUILDERS,
    LANE_LEGACY_LAYER,
    ORG2_DIRECTIVE_STEM,
    STALE_FIXTURES,
    snapshot_lists,
    stale_documents,
)
from .test_cli_surface import CLI_BEFORE, DOCTRINE_LEAVES

GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "charter_pack_cutover" / "golden_before"
META = GOLDEN_DIR / "_meta.json"
EFFECTIVE_SET_PATH = Path(__file__).resolve().with_name("_effective_set.py")
MINIMAL_GATE = {"directives", "tactics"}


def _meta() -> dict[str, Any]:
    data = json.loads(META.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _golden(name: str) -> dict[str, Any]:
    data = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@covers("NFR-001", "SC-002", "C-006")
def test_effective_set_helper_is_the_one_that_measured_the_golden() -> None:
    """The 'after' measurement must use the helper the frozen 'before' sets were measured with."""
    assert _meta()["effective_set_digest"] == file_digest(EFFECTIVE_SET_PATH), "_effective_set.py changed after the golden data was frozen"


@covers("NFR-001", "INV:Released `minimal` kind gate")
def test_kind_gate_is_measured() -> None:
    """Positive control for the helper applying ``activated_kinds``."""
    minimal = _golden("minimal_equal")["effective"]["kinds"]
    gated_out = [k for k in KINDS if k not in MINIMAL_GATE]
    assert all(minimal[k]["form"] != ALL_BUILTIN and minimal[k]["ids"] == [] for k in gated_out)
    assert minimal["directives"]["ids"], "the gate kept directives"
    legacy = _golden("legacy_keys_only")["effective"]["kinds"]
    assert all(legacy[k]["form"] == ALL_BUILTIN for k in gated_out)


@covers("NFR-001", "INV:Org packs list")
def test_golden_records_org_and_project_ids() -> None:
    """Non-vacuity: the 'before' sets carry the org and project ids the upgrade must keep."""
    assert "ACME-001-REVIEW-GATE" in _golden("legacy_keys_only")["effective"]["kinds"]["directives"]["extra"]
    two = _golden("two_org_packs")["effective"]["kinds"]
    assert "ACME-002-RELEASE-TRAIN" in two["directives"]["extra"], f"id != stem ({ORG2_DIRECTIVE_STEM}) artifact missing"
    assert "acme-release-procedure" in two["procedures"]["extra"]
    assert _golden("synthesized_with_provenance")["effective"]["kinds"]["directives"]["extra"]
    assert _golden("project_pack_skills")["effective"]["skills"] == ["triage"]


@covers("NFR-001")
def test_cli_before_records_every_leaf() -> None:
    data = json.loads(CLI_BEFORE.read_text(encoding="utf-8"))
    assert data["base_sha"] == _meta()["base_sha"]
    assert set(data["leaves"]) == {leaf.key for leaf in DOCTRINE_LEAVES}
    for leaf in DOCTRINE_LEAVES:
        entry = data["leaves"][leaf.key]
        assert entry["argv"] == list(leaf.old)
        if leaf.json_keys:
            assert entry["json_keys"], leaf.key
        else:
            assert len(entry["key_lines"]) == len(leaf.key_patterns), leaf.key


# --------------------------------------------------------------------------------------
# Builders (T002): every fixture builds and carries the legacy shape it claims
# --------------------------------------------------------------------------------------


def _config(project: Path) -> dict[str, Any]:
    data = load_yaml(project / ".kittify" / "config.yaml")
    return data if isinstance(data, dict) else {}


def _has_stale_lists(project: Path) -> bool:
    charter = active_charter(project)
    return any(sorted(v) in snapshot_lists("default", k) for k, v in charter.items() if isinstance(v, list) and k != "mission_type_activations")


def _charter_yaml(project: Path) -> dict[str, Any]:
    data = load_yaml(project / ".kittify" / "charter" / "charter.yaml")
    return data if isinstance(data, dict) else {}


SHAPE_CHECKS: dict[str, Callable[[Path], bool]] = {
    "legacy_keys_only": lambda p: "packs" in _config(p)["doctrine"]["org"] and "doctrine" in _config(p)["governance"],
    "single_pack_legacy_form": lambda p: "local_path" in _config(p)["doctrine"]["org"],
    "organisation_packs": lambda p: bool(_config(p)["organisation_packs"]),
    "legacy_directory_only": lambda p: (p / ".kittify/doctrine/graph.yaml").is_file() and (p / ".kittify/doctrine/overlays").is_dir(),
    "stale_in_pointed_charter_yaml": lambda p: "charter" in _config(p) and _has_stale_lists(p),
    "near_miss_stale": lambda p: sorted(_config(p)["activated_tactics"]) not in snapshot_lists("default", "activated_tactics"),
    "customised_lists": lambda p: "DIRECTIVE_003" in _config(p)["activated_directives"],
    "minimal_equal": lambda p: _config(p)["activated_kinds"] == ["directives", "tactics"],
    "governance_doctrine_in_charter_yaml": lambda p: "doctrine" in _charter_yaml(p)["governance"],
    "two_org_packs": lambda p: len(_config(p)["charter_packs"]["org"]["packs"]) == 2,
    "mixed_stale_and_custom": lambda p: _has_stale_lists(p) and "activated_directives" in _config(p),
    "pre_rc35": lambda p: "3.2.0rc30" in (p / ".kittify/metadata.yaml").read_text(encoding="utf-8") and not active_charter(p),
    "synthesized_with_provenance": lambda p: (p / ".kittify/charter/synthesis-manifest.yaml").is_file() and (p / ".kittify/charter/provenance").is_dir(),
    "project_pack_skills": lambda p: ".kittify/doctrine/skills" in (p / ".kittify/skills-manifest.json").read_text(encoding="utf-8"),
    "normalizer_empty_lists": lambda p: _config(p)["activated_glossary_packs"] == [],
    "doctrine_pack_id_activations": lambda p: "doctrine_pack_id" in _charter_yaml(p)["activations"][0],
    "tracker_doctrine_key": lambda p: "doctrine" in _config(p)["tracker"],
    "answers_doctrine_key": lambda p: "doctrine" in load_yaml(p / ".kittify/charter/interview/answers.yaml"),
    "standalone_governance_yaml": lambda p: (p / ".kittify/charter/governance.yaml").is_file(),
    "both_roots_collision": lambda p: (p / ".kittify/doctrine").is_dir() and (p / ".kittify/charter-packs").is_dir(),
    "both_roots_disjoint": lambda p: (p / ".kittify/doctrine").is_dir() and (p / ".kittify/charter-packs").is_dir(),
    "user_path_value_with_doctrine": lambda p: (p / "packs/doctrine-foo").is_dir(),
    "installed_removed_skills": lambda p: (p / ".claude/skills/spk-doctrine-charter/SKILL.md").is_file() and (p / ".agents/skills").is_dir(),
    "lane_in_approved": lambda p: (
        (p / ".worktrees").is_dir()
        and (p / LANE_LEGACY_LAYER / "graph.yaml").is_file()
        and all((lane / LANE_LEGACY_LAYER / "graph.yaml").is_file() for lane in (p / ".worktrees").iterdir())
    ),
    **dict.fromkeys(STALE_FIXTURES, _has_stale_lists),
}


@covers("NFR-001", "INV:Stale activation lists", "INV:Stale kind gate")
@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_builder_produces_its_legacy_shape(name: str, tmp_path: Path) -> None:
    project = BUILDERS[name](tmp_path / name)
    assert (project / ".git").exists()
    assert SHAPE_CHECKS[name](project), f"{name} does not carry the legacy shape it claims"


@covers("NFR-001", "INV:Stale activation lists")
def test_stale_documents_are_recorded_snapshots() -> None:
    """The rebuilt D1..D5 forms only hold lists the frozen snapshot file records."""
    for name, doc in stale_documents().items():
        for key, ids in doc.items():
            assert sorted(ids) in snapshot_lists("default", key), (name, key)
