"""Package split and retired-tier wording: FR-010, OD-9 (#3732, T008).

Structural tests import lazily (``importlib``) so a missing module is one strict
xfail, never a collection error. Every "absent" assertion has a control that a
module or file which must exist does exist.
"""

from __future__ import annotations

import ast
import fnmatch
import importlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ._requirements import REPO_ROOT, is_living_path
from ._support import covers, describe, load_yaml, pending_until, run_cli
from .legacy_fixtures import project_from_template

RETIRED_IDENTIFIERS = REPO_ROOT / "tests" / "fixtures" / "charter_pack_cutover" / "retired_identifiers.yaml"

PACK_TOOLING_MODULES = ("pack_descriptor", "pack_lineage", "pack_manifest", "builtin_manifest", "pack_validator", "pack_assembler", "extends")


@covers("FR-010", "OD-9")
def test_fr010_pack_tooling_lives_in_charter_offering_packs() -> None:
    assert importlib.import_module("charter.offering").__name__ == "charter.offering"  # control
    for name in PACK_TOOLING_MODULES:
        importlib.import_module(f"charter.offering.packs.{name}")


@covers("FR-010", "OD-9")
def test_fr010_charter_packs_facade_exports() -> None:
    facade = importlib.import_module("charter.packs")
    exported = [name for name in getattr(facade, "__all__", ()) if not name.startswith("_")]
    assert exported, "the facade exports nothing"
    sources = [importlib.import_module(f"charter.offering.packs.{m}") for m in PACK_TOOLING_MODULES]
    for name in exported:
        value = getattr(facade, name)
        origins = [module for module in sources if getattr(module, name, None) is value]
        activation = importlib.import_module("charter.activation")
        assert origins or getattr(value, "__module__", "").startswith(("charter.offering.packs", activation.__name__)), name


@covers("FR-010", "OD-9")
def test_fr010_specify_cli_doctrine_package_deleted() -> None:
    assert importlib.import_module("specify_cli.cli").__name__ == "specify_cli.cli"  # control
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specify_cli.doctrine")
    assert not (REPO_ROOT / "src" / "specify_cli" / "doctrine").exists()


@covers("FR-010", "OD-9")
def test_fr010_org_charter_and_adapters_at_ruled_homes() -> None:
    for name in (
        "charter.activation.org_charter",
        "charter.activation.org_charter_loader",
        "specify_cli.charter_packs.sources",
        "specify_cli.charter_packs.snapshot",
        "specify_cli.charter_packs.template_render",
    ):
        importlib.import_module(name)


#: Kept migration modules whose ids are recorded in consumer projects (occurrence map).
KEPT_DOCTRINE_PATHS = (
    "src/specify_cli/upgrade/migrations/m_2_1_2_fix_charter_doctrine_skill.py",
    "src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_single_owner_doctrine_ids.py",
)


def _doctrine_named_src_paths() -> list[str]:
    tracked = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "src"], check=True, capture_output=True, text=True).stdout.split()
    return sorted(p for p in tracked if "doctrine" in p and p not in KEPT_DOCTRINE_PATHS and "/__pycache__/" not in p)


@covers("FR-010")
@pending_until("WP21", "no src path segment named for the retired tier")
def test_fr010_no_src_module_named_for_retired_tier() -> None:
    assert all((REPO_ROOT / p).exists() for p in KEPT_DOCTRINE_PATHS), "control: the kept migrations exist"
    offenders = [p for p in _doctrine_named_src_paths() if (REPO_ROOT / p).exists()]
    assert offenders == [], "\n".join(offenders)


@covers("FR-010")
@pending_until("WP23", "tests/doctrine/ renamed")
def test_fr010_tests_doctrine_directory_renamed() -> None:
    assert (REPO_ROOT / "tests" / "charter").is_dir()  # control
    assert not (REPO_ROOT / "tests" / "doctrine").exists()


@covers("FR-010", "OD-1", "INV:Activation entry key")
@pytest.mark.integration
@pytest.mark.git_repo
def test_fr010_charter_pack_id_in_project_state(tmp_path: Path) -> None:
    project = project_from_template("doctrine_pack_id_activations", tmp_path / "p")
    charter_yaml = project / ".kittify" / "charter" / "charter.yaml"
    assert "doctrine_pack_id" in charter_yaml.read_text(encoding="utf-8")  # control
    result = run_cli(["upgrade", "--yes", "--no-worktrees"], project)
    assert result.exit_code == 0, describe(result)
    text = charter_yaml.read_text(encoding="utf-8")
    assert "charter_pack_id" in text and "doctrine_pack_id" not in text


# --------------------------------------------------------------------------------------
# Retired identifiers per subsystem slice (WP19..WP22)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Slice:
    key: str
    pending: str
    kind: str
    dirs: tuple[str, ...]
    files_glob: tuple[str, ...]
    exclude: tuple[str, ...]
    identifiers: tuple[str, ...]
    floor: int


def load_slices() -> dict[str, Slice]:
    data = load_yaml(RETIRED_IDENTIFIERS)
    out: dict[str, Slice] = {}
    for key, raw in data["slices"].items():
        out[key] = Slice(
            key=key,
            pending=str(raw["pending"]),
            kind=str(raw["kind"]),
            dirs=tuple(raw["dirs"]),
            files_glob=tuple(raw["files_glob"]),
            exclude=tuple(raw["exclude_patterns"]),
            identifiers=tuple(raw["identifiers"]),
            floor=int(raw["floor"]),
        )
    return out


def _python_names(source: str) -> set[str]:
    """Every identifier a module defines, binds, imports, accesses or names as a parameter."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.update(node.name.split("."))
            if node.asname:
                names.add(node.asname)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(node.module.split("."))
        elif isinstance(node, ast.arg | ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def _slice_files(slice_: Slice, root: Path) -> list[Path]:
    pattern = "*.py" if slice_.kind == "python" else "*"
    files: set[Path] = set()
    for rel in slice_.dirs:
        files.update(p for p in (root / rel).rglob(pattern) if p.is_file())
    for glob in slice_.files_glob:
        files.update(p for p in root.glob(glob) if p.is_file())

    def keep(path: Path) -> bool:
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in rel or any(fnmatch.fnmatch(rel, pat) for pat in slice_.exclude):
            return False
        if slice_.kind == "prose":
            return (rel == "AGENTS.md" or is_living_path(rel)) and not path.is_symlink() and _is_text(path)
        return True

    return sorted(p for p in files if keep(p))


def _is_text(path: Path) -> bool:
    data = path.read_bytes()
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def scan_slice(slice_: Slice, root: Path) -> tuple[int, list[str]]:
    """``(files scanned, findings)`` for *slice_* under *root*."""
    files = _slice_files(slice_, root)
    findings: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if slice_.kind == "python":
            hits = sorted(set(slice_.identifiers) & _python_names(text))
        else:
            lowered = text.lower()
            hits = [token for token in slice_.identifiers if token.lower() in lowered]
        findings += [f"{path.relative_to(root).as_posix()}: {hit}" for hit in hits]
    return len(files), findings


def _plant(slice_: Slice, root: Path) -> None:
    target_dir = root / slice_.dirs[0]
    target_dir.mkdir(parents=True, exist_ok=True)
    token = slice_.identifiers[0]
    if slice_.kind == "python":
        (target_dir / "planted.py").write_text(f"from somewhere import {token}\n\nvalue = {token}\n", encoding="utf-8")
    else:
        (target_dir / "planted.md").write_text(f"Use the {token} here.\n", encoding="utf-8")


_SLICE_PENDING = {
    "WP20": pending_until("WP20", "FR-010 r2 identifiers renamed (activation)"),
    "WP21": pending_until("WP21", "FR-010 r3/r4 identifiers renamed (specify_cli)"),
    "WP22": pending_until("WP22", "FR-010 prose renamed (packs, living docs)"),
}


def _slice_param(key: str, slice_: Slice) -> Any:
    return pytest.param(key, id=key, marks=_SLICE_PENDING.get(slice_.pending, ()))


SLICES = load_slices()


@covers("FR-010")
@pytest.mark.corpus
@pytest.mark.parametrize("key", [_slice_param(k, s) for k, s in SLICES.items()])
def test_fr010_retired_identifiers_absent(key: str, tmp_path: Path) -> None:
    slice_ = SLICES[key]
    _plant(slice_, tmp_path)
    planted_count, planted = scan_slice(slice_, tmp_path)
    assert planted_count == 1 and planted, "self-test: a planted identifier is found"
    scanned, findings = scan_slice(slice_, REPO_ROOT)
    assert scanned >= slice_.floor, f"scope narrowed: scanned {scanned} < floor {slice_.floor}"
    assert findings == [], "\n".join(findings)
