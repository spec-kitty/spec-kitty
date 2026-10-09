"""Project pack root, read and write: FR-016 (#3732, T009)."""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from unittest import mock
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from click.testing import Result

from ._requirements import REPO_ROOT
from ._support import covers, describe, load_yaml, output_of, read_json_output, run_cli
from .conftest import MIGRATED_PROJECT_DIRECTIVE, MIGRATED_PROJECT_DIRECTIVE_ID
from .legacy_fixtures import STATIC_ROOT

PATH_AUTHORITY_GATE = REPO_ROOT / "tests" / "architectural" / "test_charter_pack_path_authority.py"
PROJECT_LAYER = "project"


def load_module_by_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    # dataclasses and typing resolve a module through sys.modules while it executes;
    # patch.dict removes the entry again afterwards.
    with mock.patch.dict(sys.modules, {spec.name: module}):
        spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------------
# WP02: one kernel authority; the read side resolves the new root
# --------------------------------------------------------------------------------------


@covers("FR-016", "C-007")
def test_fr016_kernel_module_is_single_authority(tmp_path: Path) -> None:
    paths = importlib.import_module("kernel.charter_pack_paths")
    assert paths.PROJECT_PACK_DIRNAME == "charter-packs"
    assert Path(paths.project_pack_root(tmp_path)) == tmp_path / ".kittify" / "charter-packs"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("kernel.doctrine_root")


@covers("FR-016")
def test_fr016_layer_roots_project_is_pack_root(migrated_project: Path) -> None:
    layer_roots = importlib.import_module("charter.activation.layer_roots")
    roots = layer_roots.resolve_layer_roots(migrated_project)
    assert Path(roots["project"]) == migrated_project / ".kittify" / "charter-packs"


def _project_directive_listed(project: Path) -> bool:
    result = run_cli(["charter", "list", "--all", "--json"], project)
    assert result.exit_code == 0, describe(result)
    rows = {row["kind"]: row for row in read_json_output(result)["kinds"]}
    available = rows["directive"]["available"] or []
    stem = Path(MIGRATED_PROJECT_DIRECTIVE).name.removesuffix(".directive.yaml")
    return any(a["layer"] == PROJECT_LAYER and a["artifact_id"] in {MIGRATED_PROJECT_DIRECTIVE_ID, stem} for a in available)


@covers("FR-016", "US2-1")
@pytest.mark.integration
def test_fr016_migrated_fixture_project_artifact_is_listed(migrated_project: Path) -> None:
    assert _project_directive_listed(migrated_project)
    # Control: once the file is gone the artifact is no longer listed.
    (migrated_project / ".kittify" / "charter-packs" / MIGRATED_PROJECT_DIRECTIVE).unlink()
    assert not _project_directive_listed(migrated_project)


# --------------------------------------------------------------------------------------
# WP03: the write side, the path-authority gate, state contract and ignore rules
# --------------------------------------------------------------------------------------

_MISSING_ARTIFACT = re.compile(r"expectedYAMLat(.+?\.ya?ml)withid'([^']+)'")
_TEMPLATE_KIND_DIRS = {"directive": "directive", "tactic": "tactic", "styleguide": "styleguide"}


def _template(kind: str) -> str:
    folder = STATIC_ROOT / "synthesized" / ".kittify" / "doctrine" / _TEMPLATE_KIND_DIRS.get(kind, "tactic")
    return next(iter(sorted(folder.glob("*.yaml")))).read_text(encoding="utf-8")


def synthesize_with_generated_artifacts(project: Path, attempts: int = 25) -> Result:
    """Run ``charter synthesize``, writing each agent-authored artifact it asks for, until it succeeds."""
    result = run_cli(["charter", "synthesize", "--json", "--skip-code-evidence", "--skip-corpus"], project)
    for _ in range(attempts):
        if result.exit_code == 0:
            return result
        flat = re.sub(r"\s+", "", output_of(result).replace("│", ""))
        match = _MISSING_ARTIFACT.search(flat)
        assert match, describe(result)
        target = Path(match.group(1))
        kind = target.name.split(".")[-2]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(re.sub(r"^id: .*$", f"id: {match.group(2)}", _template(kind), flags=re.MULTILINE), encoding="utf-8")
        result = run_cli(["charter", "synthesize", "--json", "--skip-code-evidence", "--skip-corpus"], project)
    return result


@covers("FR-016")
@pytest.mark.integration
@pytest.mark.git_repo
def test_fr016_synthesize_writes_new_root_only(migrated_project: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_cwd_isolation(migrated_project)
    for argv in (["charter", "interview", "--defaults"], ["charter", "generate", "--from-interview", "--force"]):
        seeded = run_cli(argv, migrated_project)
        assert seeded.exit_code == 0, describe(seeded)
    result = synthesize_with_generated_artifacts(migrated_project)
    assert result.exit_code == 0, describe(result)
    assert not (migrated_project / ".kittify" / "doctrine").exists(), "synthesis recreated the retired root"
    manifest = migrated_project / ".kittify" / "charter" / "synthesis-manifest.yaml"
    if manifest.is_file():
        paths = [entry["path"] for entry in (load_yaml(manifest) or {}).get("artifacts", [])]
        assert all(p.startswith(".kittify/charter-packs/") for p in paths), paths
    # Control: the project layer is readable through the CLI.
    assert _project_directive_listed(migrated_project)


@covers("FR-016")
def test_fr016_path_authority_gate_detects_planted_literal(tmp_path: Path) -> None:
    gate = load_module_by_path(PATH_AUTHORITY_GATE, "charter_pack_path_authority_gate")
    planted = tmp_path / "planted.py"
    planted.write_text('from pathlib import Path\n\nROOT = Path(".kittify") / "doctrine"\n', encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text('from pathlib import Path\n\nROOT = Path(".kittify") / "charter"\n', encoding="utf-8")
    assert len(gate.scan([planted])) == 1
    assert len(gate.scan([clean])) == 0


@covers("FR-016", "INV:Ignore rules")
@pytest.mark.corpus
def test_fr016_state_contract_and_gitignore_use_new_root() -> None:
    contract = importlib.import_module("specify_cli.state.contract")
    paths = importlib.import_module("kernel.charter_pack_paths")
    surfaces = {s.name: s for s in contract.STATE_SURFACES}
    assert surfaces, "control: the state contract lists surfaces"
    assert "project_doctrine_graph" not in surfaces
    graph = surfaces["project_pack_graph"]
    assert graph.path_pattern.startswith(".kittify/charter-packs/")
    assert ".kittify/doctrine" not in " ".join(s.path_pattern for s in contract.STATE_SURFACES)
    assert paths.PROJECT_PACK_DIRNAME in graph.path_pattern
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".kittify/doctrine" not in ignore
    assert ".kittify/charter-packs" in ignore
