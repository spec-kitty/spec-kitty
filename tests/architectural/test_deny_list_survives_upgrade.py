"""No migration and no built-in preset removes a deny entry (WP10: FR-014, SC-003; ADR 2026-10-19-1 Decision 4).

Four halves:

* **Static.** An AST scan of ``src/specify_cli/upgrade/migrations/**`` and
  ``src/charter/activation/preset_application.py`` and a text scan of the
  built-in presets: no ``deactivated_`` string constant (docstrings aside), no
  ``DENY_KEYS`` / ``deny_key`` reference and no non-``None`` ``deny_change=``
  outside an exact allowlist. Over all of ``src/``, the places that mint a
  :class:`DenyListChoice`, the ``deny_change=`` forwards and the modules that
  name a deny key are pinned exactly, in both directions.
* **Classifier.** Which migration modules touch activation (an import from
  ``charter.activation``, the activation-ledger path, a ``LEDGER_KEYS`` key or
  its key-family placeholder, or an import of such a helper). The bare word
  "ledger" never matches: it collides with the Migration Ledger.
* **Dynamic.** Every activation-touching migration runs, inside the upgrade
  scope, on a post-ledger fixture where its ``detect()`` is True, with deny
  entries for a directive, a tactic and a skill and allow lists equal to the
  frozen cutover default snapshots (the #66 reset shape); the deny keys on
  disk are compared before and after. Exemption by ordering (analyze pass 3,
  M3) is allowed only for a migration ordered before ``4.0.0rc8_activation_ledger``
  whose ``detect()`` is False on that fixture. Every built-in preset is planned
  and applied without ``--force`` on a fixture with deny entries.
* **Non-vacuity.** Throwaway offenders fail each half, naming the offender.
"""

from __future__ import annotations

import ast
import functools
import subprocess
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pytest
import yaml

from charter.activation.activation_ledger import DENY_KEYS, LEDGER_KEYS, DenyListWriteRefused, prepare_ledger_write
from charter.activation.preset_application import apply_preset_plan, find_offering_pack, plan_preset_application
from kernel.activation_ledger_store import ACTIVATION_LEDGER, activation_ledger_path
from kernel.paths import get_packs_root_default
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations._charter_pack_cutover_snapshots import DEFAULT_KIND_GATE, DEFAULT_SNAPSHOTS
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult, legacy_upgrade_scope
from specify_cli.upgrade.registry import MigrationRegistry
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
MIGRATIONS_DIR = SRC / "specify_cli" / "upgrade" / "migrations"
PRESET_MODULE = SRC / "charter" / "activation" / "preset_application.py"
PRESETS_DIR = REPO_ROOT / "packs" / "built-in" / "presets"
RC8_MIGRATION_ID = "4.0.0rc8_activation_ledger"

_DENY_PREFIX = "deactivated_"
_ALLOW_PREFIX = "activated_"
_DENY_NAMES = frozenset({"DENY_KEYS", "deny_key"})
_CHOICE_CLASS = "DenyListChoice"
_DENY_CHANGE = "deny_change"


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


# --------------------------------------------------------------------------- #
# The exact allowlists (L4)
# --------------------------------------------------------------------------- #

_PRESET_REL = _rel(PRESET_MODULE)

#: Inside the scanned set, per ``(file, function)``, the findings allowed: the
#: ``--preset --force`` path only (its write and the plan of the exclusions it clears).
STATIC_ALLOWLIST: Mapping[tuple[str, str], frozenset[str]] = {
    (_PRESET_REL, "apply_preset_plan"): frozenset({"DenyListChoice.PRESET_FORCE"}),
    (_PRESET_REL, "_deny_partition"): frozenset({"deny_key"}),
}

#: Every place in ``src/`` that mints a :class:`DenyListChoice` (the four explicit paths of Decision 4).
CHOICE_ORIGINS: frozenset[tuple[str, str, str]] = frozenset(
    {
        (_PRESET_REL, "apply_preset_plan", "PRESET_FORCE"),
        ("src/charter/activation/activation_engine.py", "plan_activation", "ACTIVATE"),
        ("src/charter/activation/activation_engine.py", "plan_deactivation", "DEACTIVATE"),
        ("src/charter/activation/pack_manager.py", "ActiveCharterManager.activate", "ACTIVATE"),
        ("src/specify_cli/cli/commands/charter/activate.py", "_activate_cascade_targets", "ACTIVATE"),
        ("src/specify_cli/cli/commands/charter/activate.py", "_activate_cascade_targets", "CASCADE_INCLUDE_DEACTIVATED"),
    }
)

#: Every ``deny_change=`` keyword in ``src/`` that passes a choice on rather than minting one.
DENY_CHANGE_FORWARDS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("src/charter/activation/activation_engine.py", "_with_deny", "choice"),
        ("src/charter/activation/activation_engine.py", "commit_plan", "plan.deny_change"),
        ("src/charter/activation/pack_manager.py", "ActiveCharterManager.activate", "reinstate"),
        ("src/charter/activation/pack_manager.py", "_save_ledger", "deny_change"),
        ("src/charter/activation/pack_manager.py", "prepare_activation_write", "deny_change"),
        (_PRESET_REL, "_write", "deny_change"),
    }
)

#: The only modules in ``src/`` that name a deny key (``DENY_KEYS`` / ``deny_key``): the seam and the preset plan.
DENY_KEY_MODULES: frozenset[str] = frozenset(
    {
        "src/charter/activation/activation_engine.py",
        "src/charter/activation/activation_ledger.py",
        "src/charter/activation/pack_manager.py",
        _PRESET_REL,
    }
)


# --------------------------------------------------------------------------- #
# Static half (T061)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Finding:
    """One deny-touching construct: where it is and what it is."""

    path: str
    function: str
    what: str
    line: int


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring constant (documentation, not a key)."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _names_the_choice_class(node: ast.expr) -> bool:
    """``DenyListChoice`` itself, or a qualified chain ending in it (``api.DenyListChoice``)."""
    if isinstance(node, ast.Name):
        return node.id == _CHOICE_CLASS
    return isinstance(node, ast.Attribute) and node.attr == _CHOICE_CLASS


class _DenyVisitor(ast.NodeVisitor):
    """Collect deny-touching constructs with their qualified enclosing function."""

    def __init__(self, path: str, docstrings: set[int]) -> None:
        self.path = path
        self.docstrings = docstrings
        self.scope: list[str] = []
        self.params: list[frozenset[str]] = []
        self.findings: list[Finding] = []

    def _add(self, what: str, node: ast.AST) -> None:
        self.findings.append(Finding(self.path, ".".join(self.scope), what, getattr(node, "lineno", 0)))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        arguments = node.args
        names = [arg.arg for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
        self.scope.append(node.name)
        self.params.append(frozenset(names))
        self.generic_visit(node)
        self.params.pop()
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and _DENY_PREFIX in node.value and id(node) not in self.docstrings:
            self._add(f"string {node.value!r}", node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _DENY_NAMES:
            self._add(node.id, node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _DENY_NAMES:
            self._add(node.attr, node)
        elif _names_the_choice_class(node.value):
            self._add(f"{_CHOICE_CLASS}.{node.attr}", node)
        self.generic_visit(node)

    def visit_alias(self, node: ast.alias) -> None:
        if node.name in _DENY_NAMES or node.name == _CHOICE_CLASS:
            self._add(f"import {node.name}", node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == _DENY_CHANGE and not (isinstance(node.value, ast.Constant) and node.value.value is None):
            self._add(f"{_DENY_CHANGE}={ast.unparse(node.value)}", node.value)
        self.generic_visit(node)


def scan_source(source: str, path: str) -> list[Finding]:
    """Every deny-touching construct of one module (docstrings excluded)."""
    tree = ast.parse(source)
    visitor = _DenyVisitor(path, _docstring_nodes(tree))
    visitor.visit(tree)
    return visitor.findings


def _is_import(finding: Finding) -> bool:
    return finding.what.startswith("import ")


def static_violations(source: str, path: str, *, migration: bool) -> list[Finding]:
    """The findings the gate refuses: any in a migration; outside the allowlist (imports aside) elsewhere."""
    findings = scan_source(source, path)
    if migration:
        return findings
    return [
        finding
        for finding in findings
        if not _is_import(finding)
        and not finding.what.startswith(f"{_DENY_CHANGE}=")  # a forward; the src-wide scan pins those
        and finding.what not in STATIC_ALLOWLIST.get((finding.path, finding.function), frozenset())
    ]


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.rglob("*.py"))


def test_no_migration_names_a_deny_key_or_passes_a_deny_change() -> None:
    violations = [finding for path in _migration_files() for finding in static_violations(path.read_text(encoding="utf-8"), _rel(path), migration=True)]
    assert violations == [], violations


def test_the_preset_writer_touches_the_deny_list_only_on_the_force_path() -> None:
    violations = static_violations(PRESET_MODULE.read_text(encoding="utf-8"), _PRESET_REL, migration=False)
    assert violations == [], violations
    found = {(finding.path, finding.function) for finding in scan_source(PRESET_MODULE.read_text(encoding="utf-8"), _PRESET_REL) if not _is_import(finding)}
    assert set(STATIC_ALLOWLIST) <= found, sorted(set(STATIC_ALLOWLIST) - found)  # the allowlist is not stale


def _preset_files() -> list[Path]:
    return sorted(PRESETS_DIR.glob("*.yaml"))


def test_no_built_in_preset_names_a_deny_key() -> None:
    presets = _preset_files()
    assert presets
    offenders = [path.name for path in presets if _DENY_PREFIX in path.read_text(encoding="utf-8")]
    assert offenders == [], offenders


#: A module that holds none of these substrings has no finding; it is not parsed (speed only).
_PREFILTER = (*_DENY_NAMES, _CHOICE_CLASS, _DENY_CHANGE, _DENY_PREFIX)


@functools.cache
def _src_findings() -> tuple[Finding, ...]:
    found: list[Finding] = []
    for path in sorted(SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if any(marker in source for marker in _PREFILTER):
            found.extend(scan_source(source, _rel(path)))
    return tuple(found)


def test_the_choice_origins_and_forwards_in_src_are_exact() -> None:
    findings = [finding for finding in _src_findings() if not _is_import(finding)]
    origins = {(f.path, f.function, f.what.split(".", 1)[1]) for f in findings if f.what.startswith(f"{_CHOICE_CLASS}.")}
    forwards = {
        (f.path, f.function, f.what.split("=", 1)[1])
        for f in findings
        if f.what.startswith(f"{_DENY_CHANGE}=") and not f.what.split("=", 1)[1].startswith(f"{_CHOICE_CLASS}.")
    }
    assert origins == CHOICE_ORIGINS, (sorted(origins - CHOICE_ORIGINS), sorted(CHOICE_ORIGINS - origins))
    assert forwards == DENY_CHANGE_FORWARDS, (sorted(forwards - DENY_CHANGE_FORWARDS), sorted(DENY_CHANGE_FORWARDS - forwards))


def test_only_the_seam_and_the_preset_plan_name_a_deny_key() -> None:
    modules = {finding.path for finding in _src_findings() if finding.what in _DENY_NAMES}
    assert modules == DENY_KEY_MODULES, (sorted(modules - DENY_KEY_MODULES), sorted(DENY_KEY_MODULES - modules))


# --------------------------------------------------------------------------- #
# Classifier (T061.3)
# --------------------------------------------------------------------------- #

#: The exact activation keys plus their key-family placeholders (``activated_<kind>``), derived from LEDGER_KEYS.
_FAMILY_MARKERS = tuple(sorted({f"{prefix}<" for prefix in (_ALLOW_PREFIX, _DENY_PREFIX) if any(key.startswith(prefix) for key in LEDGER_KEYS)}))
_LEDGER_PATH_MARKERS = (ACTIVATION_LEDGER.name, "ACTIVATION_LEDGER")


def _imports_charter_activation(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[:2] == ["charter", "activation"]:
            return True
        if isinstance(node, ast.Import) and any(alias.name.split(".")[:2] == ["charter", "activation"] for alias in node.names):
            return True
    return False


def _relative_imports(tree: ast.AST) -> set[str]:
    return {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module}


def touches_activation(source: str) -> bool:
    """Directly activation-touching: imports ``charter.activation``, names the ledger path, a key or a key family."""
    if _imports_charter_activation(ast.parse(source)):
        return True
    strings = [node.value for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    if any(value in LEDGER_KEYS for value in strings):
        return True
    return any(marker in source for marker in (*_LEDGER_PATH_MARKERS, *_FAMILY_MARKERS))


def classify(sources: Mapping[str, str]) -> set[str]:
    """Module stems that touch activation, directly or through a classified sibling helper module."""
    touching = {stem for stem, source in sources.items() if touches_activation(source)}
    imports = {stem: _relative_imports(ast.parse(source)) for stem, source in sources.items()}
    grown = True
    while grown:
        added = {stem for stem, imported in imports.items() if stem not in touching and imported & touching}
        touching |= added
        grown = bool(added)
    return touching


def _migration_sources() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS_DIR.glob("*.py"))}


def activation_touching_modules() -> set[str]:
    return classify(_migration_sources())


def test_the_classifier_finds_the_activation_touching_migrations() -> None:
    touching = activation_touching_modules()
    assert touching
    assert {"_charter_pack_cutover_snapshots", "m_4_0_0rc8_activation_ledger", "m_3_2_x_normalize_activation_absence"} <= touching, sorted(touching)


def test_a_migration_ledger_mention_is_not_activation() -> None:
    source = '"""Records the run in the migration ledger."""\nLEDGER = ".kittify/migration-ledger.jsonl"\n'
    assert not touches_activation(source)
    assert not classify({"m_x_ledger_only": source})
    assert touches_activation('KEY = "mission_type_activations"\n')  # positive control


def test_a_helper_import_makes_a_migration_activation_touching() -> None:
    sources = {"_helper": 'KEY = "activated_tactics"\n', "m_user": "from ._helper import KEY\n", "m_other": "X = 1\n"}
    assert classify(sources) == {"_helper", "m_user"}


# --------------------------------------------------------------------------- #
# Dynamic half (T062)
# --------------------------------------------------------------------------- #

#: Deny entries of the post-ledger fixture: a directive, a tactic and a skill.
FIXTURE_DENY: Mapping[str, list[str]] = {
    "deactivated_directives": ["003-decision-documentation-requirement"],
    "deactivated_tactics": ["acceptance-test-first"],
    "deactivated_skills": ["fixture-skill"],
}
_SURFACES = (ACTIVATION_LEDGER, Path(".kittify", "config.yaml"), Path(".kittify", "charter", "charter.yaml"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def post_ledger_fixture(root: Path, *, omit: tuple[str, ...] = ()) -> Path:
    """A ledger project: the #66 reset-shape allow lists (frozen default snapshots), the default kind gate and deny entries."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _write(root / ".kittify" / "config.yaml", "{}\n")
    _write(root / ".kittify" / "charter" / "charter.yaml", "{}\n")
    values: dict[str, list[str]] = {
        "mission_type_activations": ["software-dev"],
        "activated_kinds": sorted(DEFAULT_KIND_GATE),
        **{key: sorted(snapshots[0]) for key, snapshots in DEFAULT_SNAPSHOTS.items()},
        **FIXTURE_DENY,
    }
    seed_activation_ledger(root, **{key: value for key, value in values.items() if key not in omit})
    return root


def _catalog_charter(reference: Mapping[str, str]) -> str:
    catalog = {"mission": "software-dev", "template_set": "software-dev-default", "languages": [], "references": [dict(reference)]}
    document = {
        "schema_version": "2.0.0",
        "governance": {"testing": {}},
        "directives": [],
        "catalog": catalog,
        "overrides": {},
        "metadata": {"bundle_schema_version": 2},
    }
    return yaml.safe_dump(document, sort_keys=False)


def _absolute_built_in_reference(ref_id: str, kind: str, relative: str) -> dict[str, str]:
    source = get_packs_root_default() / "built-in" / relative
    return {"id": ref_id, "kind": kind, "title": ref_id, "summary": "fixture", "source_path": str(source), "local_path": "_LIBRARY/fixture.md"}


def _references(root: Path, ref_id: str, kind: str) -> None:
    _write(root / ".kittify" / "charter" / "references.yaml", yaml.safe_dump({"references": [{"id": ref_id, "kind": kind}]}))


def _build_plain(root: Path) -> None:
    post_ledger_fixture(root)


def _build_mission_types_missing(root: Path) -> None:
    post_ledger_fixture(root, omit=("mission_type_activations",))


def _build_retired_toolguide(root: Path) -> None:
    post_ledger_fixture(root)
    _references(root, "TOOLGUIDE:rtk-search-tooling", "toolguide")


def _build_retired_tactic(root: Path) -> None:
    post_ledger_fixture(root)
    _references(root, "TACTIC:bug-fixing-checklist", "tactic")


def _build_answers_only_selection(root: Path) -> None:
    post_ledger_fixture(root)
    _write(root / ".kittify" / "config.yaml", "agents:\n  available: [claude]\n")
    _write(root / ".kittify" / "charter" / "interview" / "answers.yaml", "selected_directives:\n- DIRECTIVE_024\n")


def _build_legacy_bundle_file(root: Path) -> None:
    post_ledger_fixture(root)
    _write(root / ".kittify" / "charter" / "governance.yaml", "doctrine: {}\n")


def _build_absolute_provenance(root: Path) -> None:
    post_ledger_fixture(root)
    reference = _absolute_built_in_reference("PARADIGM:atomic-design", "paradigm", "paradigms/atomic-design.paradigm.yaml")
    _write(root / ".kittify" / "charter" / "charter.yaml", _catalog_charter(reference))


def _build_absolute_template_set(root: Path) -> None:
    post_ledger_fixture(root)
    reference = _absolute_built_in_reference("TEMPLATE_SET:software-dev-default", "template_set", "missions/software-dev/mission.yaml")
    _write(root / ".kittify" / "charter" / "charter.yaml", _catalog_charter(reference))


def _build_retired_project_layer(root: Path) -> None:
    post_ledger_fixture(root)
    _write(root / ".kittify" / "doctrine" / "directives" / "fixture.directive.yaml", "id: fixture\n")


def _build_stray_equal_legacy_key(root: Path) -> None:
    post_ledger_fixture(root)
    _write(root / ".kittify" / "config.yaml", "charter: .kittify/charter/charter.yaml\n")
    _write(root / ".kittify" / "charter" / "charter.yaml", "mission_type_activations:\n- software-dev\n")


def _build_legacy_project_intent_stem(root: Path) -> None:
    """The ledger allow list still names the pre-#6443 stem, so the rename's token step applies."""
    post_ledger_fixture(root)
    allowed = read_activation_ledger(root).get("activated_directives") or []
    seed_activation_ledger(root, activated_directives=[*allowed, "001-mission-type-scope-directive"])


#: migration id -> builder of a post-ledger fixture on which its ``detect()`` is True.
BUILDERS: Mapping[str, Callable[[Path], None]] = {
    "3.2.0rc35_activate_builtin_mission_types": _build_mission_types_missing,
    "3.2.0rc35_unified_bundle": _build_plain,
    "3.2.6_retire_rtk_search_tooling": _build_retired_toolguide,
    "unify_charter_activation_promote_answers": _build_answers_only_selection,
    "consolidate_charter_bundle_fold": _build_legacy_bundle_file,
    "3.2.7_heal_provenance_paths": _build_absolute_provenance,
    "4_0_0rc5_heal_template_set_provenance": _build_absolute_template_set,
    "4.0.0rc5_retire_single_owner_doctrine_ids": _build_retired_tactic,
    "charter_pack_cutover": _build_retired_project_layer,
    "4.0.0rc8_project_intent_directive_rename": _build_legacy_project_intent_stem,
    RC8_MIGRATION_ID: _build_stray_equal_legacy_key,
}

#: Exempt by ordering (M3): ``detect()`` cannot be made True once a ledger exists (proven below).
ORDER_EXEMPT: Mapping[str, str] = {
    "normalize_activation_absence": "SupersededMigration: detect() is always False",
}


def deny_snapshot(root: Path) -> dict[str, bytes]:
    """The deny keys of every activation surface, as canonical bytes per file."""
    snapshot: dict[str, bytes] = {}
    for rel in _SURFACES:
        path = root / rel
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            deny = {key: value for key, value in loaded.items() if str(key).startswith(_DENY_PREFIX)}
            snapshot[rel.as_posix()] = yaml.safe_dump(deny, sort_keys=True).encode("utf-8")
    return snapshot


def _scope(root: Path) -> AbstractContextManager[None]:
    scope: AbstractContextManager[None] = legacy_upgrade_scope(root)
    return scope


class _Migration(Protocol):
    """What the dynamic check calls: a registered migration, or a throwaway offender."""

    @property
    def migration_id(self) -> str: ...

    def detect(self, project_path: Path) -> bool: ...

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult: ...


def run_and_compare_deny(migration: _Migration, root: Path) -> MigrationResult:
    """Run *migration* as the runner would and fail, naming it, when a deny entry changed."""
    with _scope(root):
        assert migration.detect(root), f"{migration.migration_id}: the builder no longer makes detect() True"
        before = deny_snapshot(root)
        result = migration.apply(root)
    after = deny_snapshot(root)
    assert after == before, f"{migration.migration_id} changed deny entries: before={before!r} after={after!r}"
    return result


def _registered() -> list[BaseMigration]:
    auto_discover_migrations()
    return list(MigrationRegistry.get_all())


def _activation_touching() -> list[BaseMigration]:
    touching = activation_touching_modules()
    return [migration for migration in _registered() if type(migration).__module__.rsplit(".", 1)[-1] in touching]


def _migration(migration_id: str) -> BaseMigration:
    auto_discover_migrations()
    return MigrationRegistry.get_by_id(migration_id) or pytest.fail(f"{migration_id} is not registered")


def test_the_registry_holds_every_manifest_entry() -> None:
    assert len(_registered()) == len(load_order_manifest())


def test_every_activation_touching_migration_is_built_or_exempt() -> None:
    ids = {migration.migration_id for migration in _activation_touching()}
    assert set(BUILDERS).isdisjoint(ORDER_EXEMPT)
    assert set(BUILDERS) | set(ORDER_EXEMPT) == ids, (sorted(ids - set(BUILDERS) - set(ORDER_EXEMPT)), sorted(set(BUILDERS) | set(ORDER_EXEMPT) - ids))


@pytest.mark.parametrize("migration_id", sorted(BUILDERS))
def test_a_migration_leaves_the_deny_entries_unchanged(migration_id: str, tmp_path: Path) -> None:
    migration = _migration(migration_id)
    BUILDERS[migration_id](tmp_path)
    result = run_and_compare_deny(migration, tmp_path)
    assert result.success, (migration_id, result.errors)
    assert read_activation_ledger(tmp_path).items() >= FIXTURE_DENY.items()


@pytest.mark.parametrize("migration_id", sorted(ORDER_EXEMPT))
def test_an_order_exempt_migration_cannot_select_once_a_ledger_exists(migration_id: str, tmp_path: Path) -> None:
    migration = _migration(migration_id)
    manifest = load_order_manifest()
    assert manifest.index(migration_id) < manifest.index(RC8_MIGRATION_ID)
    post_ledger_fixture(tmp_path)
    with _scope(tmp_path):
        assert migration.detect(tmp_path) is False


def _preset_names() -> list[str]:
    return [path.stem for path in _preset_files()]


def test_the_offering_ships_exactly_the_globbed_presets(tmp_path: Path) -> None:
    root = post_ledger_fixture(tmp_path)
    shipped = sorted(path.stem for path in (find_offering_pack(root, "built-in").root / "presets").glob("*.yaml"))
    assert shipped == _preset_names() and shipped


def _listed_denied(preset: str) -> dict[str, list[str]]:
    """``activated_<plural>`` key -> the fixture-denied ids the preset lists (read from the preset file)."""
    document = yaml.safe_load((PRESETS_DIR / f"{preset}.yaml").read_text(encoding="utf-8"))
    listed: dict[str, list[str]] = {}
    for deny_key, denied in FIXTURE_DENY.items():
        allow = _ALLOW_PREFIX + deny_key.removeprefix(_DENY_PREFIX)
        hit = sorted(set(document.get(allow) or ()) & set(denied))
        if hit:
            listed[allow] = hit
    return listed


@pytest.mark.parametrize("preset", _preset_names())
def test_a_built_in_preset_without_force_keeps_the_deny_entries(preset: str, tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    _write(tmp_path / ".kittify" / "config.yaml", "{}\n")
    seed_activation_ledger(tmp_path, **FIXTURE_DENY)
    before = deny_snapshot(tmp_path)

    plan = plan_preset_application(tmp_path, "built-in", preset)
    apply_preset_plan(tmp_path, plan)

    assert deny_snapshot(tmp_path) == before
    assert plan.denied_listed == _listed_denied(preset)
    assert _denied_in_allow_lists(tmp_path) == {}, f"{preset}: a preset without --force wrote a denied id into an allow list"


def _denied_in_allow_lists(root: Path) -> dict[str, list[str]]:
    """``activated_<plural>`` key -> the fixture-denied ids the ledger's allow list holds (T2, FR-014)."""
    ledger = read_activation_ledger(root)
    found: dict[str, list[str]] = {}
    for deny_key, denied in FIXTURE_DENY.items():
        allow = _ALLOW_PREFIX + deny_key.removeprefix(_DENY_PREFIX)
        hit = sorted(set(ledger.get(allow) or ()) & set(denied))
        if hit:
            found[allow] = hit
    return found


# --------------------------------------------------------------------------- #
# Non-vacuity (T063)
# --------------------------------------------------------------------------- #


class _RogueDenyDroppingMigration:
    """A throwaway offender: drops a deny entry with a raw YAML write."""

    migration_id = "test_rogue_drops_deny"

    def detect(self, project_path: Path) -> bool:
        return activation_ledger_path(project_path).is_file()

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        del dry_run
        path = activation_ledger_path(project_path)
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.pop("deactivated_directives")
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return MigrationResult(success=True)


def test_a_deny_dropping_migration_fails_the_dynamic_check(tmp_path: Path) -> None:
    post_ledger_fixture(tmp_path)
    with pytest.raises(AssertionError, match="test_rogue_drops_deny changed deny entries"):
        run_and_compare_deny(_RogueDenyDroppingMigration(), tmp_path)


def test_a_seam_write_without_a_choice_is_refused(tmp_path: Path) -> None:
    post_ledger_fixture(tmp_path)
    with pytest.raises(DenyListWriteRefused):
        prepare_ledger_write(tmp_path, {"deactivated_directives": None})


def test_a_choice_in_a_migration_path_fails_the_static_check() -> None:
    snippet = "from charter.activation.api import DenyListChoice\ndef apply(root):\n    write(root, deny_change=DenyListChoice.ACTIVATE)\n"
    violations = static_violations(snippet, "src/specify_cli/upgrade/migrations/m_rogue.py", migration=True)
    assert {finding.what for finding in violations} >= {"deny_change=DenyListChoice.ACTIVATE", "DenyListChoice.ACTIVATE"}
    assert all(finding.path.endswith("m_rogue.py") for finding in violations)


def test_a_qualified_choice_in_a_migration_path_fails_the_static_check() -> None:
    """A choice reached through a qualified chain (``api.DenyListChoice.X``) is an origin too (WP10 review LOW)."""
    snippet = "from charter.activation import api\ndef apply(root):\n    write(root, choice=api.DenyListChoice.ACTIVATE)\n"
    whats = {finding.what for finding in static_violations(snippet, "src/specify_cli/upgrade/migrations/m_rogue.py", migration=True)}
    assert whats == {"DenyListChoice.ACTIVATE"}
    deeper = "def apply(root):\n    write(root, choice=charter.activation.api.DenyListChoice.DEACTIVATE)\n"
    assert {finding.what for finding in static_violations(deeper, "m_rogue.py", migration=True)} == {"DenyListChoice.DEACTIVATE"}


def test_a_deny_key_string_or_reference_in_a_migration_path_fails() -> None:
    snippet = '"""Docstrings that say deactivated_<kind> are documentation."""\nKEY = "deactivated_tactics"\nkeys = DENY_KEYS\n'
    whats = {finding.what for finding in static_violations(snippet, "m_rogue.py", migration=True)}
    assert whats == {"string 'deactivated_tactics'", "DENY_KEYS"}


def test_an_unlisted_preset_function_touching_the_deny_list_fails() -> None:
    snippet = "def sneaky(plan):\n    return plan_write(deny_key(kind), choice=DenyListChoice.PRESET_FORCE)\n"
    whats = {finding.what for finding in static_violations(snippet, _PRESET_REL, migration=False)}
    assert whats == {"deny_key", "DenyListChoice.PRESET_FORCE"}


def test_classify_keys_derive_from_the_ledger_vocabulary() -> None:
    assert set(DENY_KEYS) <= set(LEDGER_KEYS)
    assert _FAMILY_MARKERS == ("activated_<", "deactivated_<")
