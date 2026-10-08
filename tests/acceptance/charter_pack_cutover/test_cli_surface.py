"""CLI-surface acceptance tests: FR-005, FR-006, FR-007, FR-011, US3, SC-004 (#3732).

``DOCTRINE_LEAVES`` is data only: the golden generator imports it to record the old
leaves' output at the base (``tests/fixtures/charter_pack_cutover/cli_before.json``),
and ``test_fr006_charter_home_matches_recorded_output`` replays the new spelling on
the same fixture against that record.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import Result

from ._requirements import REPO_ROOT
from ._support import covers, describe, output_of, pending_until, read_json_output, run_cli
from .legacy_fixtures import build_doctrine_command_fixture, project_from_template, upgraded_copy, write_doctrine_pack

FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "charter_pack_cutover"
CLI_BEFORE = FIXTURES_ROOT / "cli_before.json"

UNKNOWN_COMMAND = "No such command"
LEGACY_CODE = "LEGACY_CHARTER_STATE"
RUNBOOK = "docs/migrations/charter-pack-cutover.md"


@dataclass(frozen=True)
class Leaf:
    """One former ``spec-kitty doctrine`` leaf (or a moved ``charter``/``doctor`` command)."""

    key: str
    old: tuple[str, ...]
    new: tuple[str, ...]
    key_patterns: tuple[str, ...]
    pending: str | None
    json_keys: bool = False


#: research/runtime-seams.md §4 + contracts/cli.md command map. Data only (imported by the generator).
DOCTRINE_LEAVES: tuple[Leaf, ...] = (
    Leaf("fetch", ("doctrine", "fetch"), ("charter", "fetch"), (r"Pack 'acme': \d+ artifacts",), None),
    Leaf("regenerate_graph", ("doctrine", "regenerate-graph", "--check"), ("charter", "pack", "regenerate-graph", "--check"), (r"DRG graph is fresh",), "WP15"),
    Leaf("new", ("doctrine", "new", "tactic", "fixture-new-tactic"), ("charter", "new", "tactic", "fixture-new-tactic"), (r"Created stub artifact",), None),
    Leaf(
        "validate",
        ("doctrine", "validate", "authoring/fixture-tactic.tactic.yaml"),
        ("charter", "validate", "authoring/fixture-tactic.tactic.yaml"),
        (r"\d+ artifact\(s\) passed validation",),
        None,
    ),
    Leaf("pack_validate", ("doctrine", "pack", "validate", "orgpack"), ("charter", "pack", "validate", "orgpack"), (r"Pack validation: 0 errors",), "WP15"),
    Leaf(
        "pack_assemble",
        ("doctrine", "pack", "assemble", "assembled", "orgpack"),
        ("charter", "pack", "assemble", "assembled", "orgpack"),
        (r"Assembled 1 pack",),
        "WP15",
    ),
    Leaf("org_init", ("doctrine", "org", "init", "scaffolded-pack"), ("charter", "org", "init", "scaffolded-pack"), (r"Org pack scaffolded at",), None),
    Leaf("org_validate", ("doctrine", "org", "validate", "orgpack"), ("charter", "org", "validate", "orgpack"), (r"Pack validation: 0 errors",), None),
    Leaf(
        "mission_type_list",
        ("doctrine", "mission-type", "list"),
        ("charter", "mission-type", "list", "--include-inactive"),
        (r"software-dev", r"documentation", r"research", r"plan"),
        None,
    ),
    Leaf("asset_list", ("doctrine", "asset", "list"), ("charter", "pack", "asset", "list"), (r"common-docs-structural-lint",), "WP15"),
    Leaf(
        "asset_path",
        ("doctrine", "asset", "path", "common-docs-structural-lint"),
        ("charter", "pack", "asset", "path", "common-docs-structural-lint"),
        (r"docs_structural_lint\.py",),
        "WP15",
    ),
    Leaf("consistency_check", ("charter", "pack", "consistency-check"), ("charter", "consistency-check"), (r"coherent",), "WP15"),
    Leaf("doctor", ("doctor", "doctrine", "--json"), ("doctor", "charter-packs", "--json"), (), "WP15", json_keys=True),
)


# --------------------------------------------------------------------------------------
# Output normalisation (shared with the generator)
# --------------------------------------------------------------------------------------


def normalise(text: str, root: Path) -> str:
    """Strip ANSI, replace the fixture root and repository root, collapse whitespace."""
    from ._support import strip_ansi

    plain = strip_ansi(text).replace(str(root), "<ROOT>").replace(str(REPO_ROOT), "<REPO>")
    return " ".join(plain.split())


def compact(text: str) -> str:
    """Remove all whitespace (Rich wraps long lines at the console width)."""
    return "".join(text.split())


def key_lines(text: str, patterns: Sequence[str]) -> list[str]:
    """The first match of each pattern in normalised *text* (missing patterns are skipped)."""
    found: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            found.append(match.group(0))
    return found


def json_key_set(payload: object) -> list[str]:
    return sorted(payload) if isinstance(payload, dict) else []


#: Literal markers (test_traceability requires a literal WP id at every call site).
_FR006_PENDING = {"WP15": pending_until("WP15", "charter home of a former doctrine leaf (FR-006)")}
_FR007_PENDING = {
    "WP13": pending_until("WP13", "`charter pack apply` removed (FR-005)"),
    "WP15": pending_until("WP15", "old spelling removed with its charter home (FR-006)"),
    "WP16": pending_until("WP16", "`spec-kitty doctrine` group removed (FR-007)"),
}


def _leaf_param(leaf: Leaf) -> object:
    marks = [_FR006_PENDING[leaf.pending]] if leaf.pending else []
    return pytest.param(leaf, id=leaf.key, marks=marks)


def _recorded() -> dict[str, dict[str, object]]:
    data = json.loads(CLI_BEFORE.read_text(encoding="utf-8"))
    leaves = data["leaves"]
    assert isinstance(leaves, dict)
    return leaves


# --------------------------------------------------------------------------------------
# FR-006 / SC-004: every leaf has a charter home doing the same job
# --------------------------------------------------------------------------------------


@covers("FR-006", "SC-004", "US3-1", "OD-8")
@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("leaf", [_leaf_param(leaf) for leaf in DOCTRINE_LEAVES])
def test_fr006_charter_home_matches_recorded_output(leaf: Leaf, tmp_path: Path) -> None:
    record = _recorded()[leaf.key]
    project = build_doctrine_command_fixture(tmp_path / "doctrine-commands")
    result = run_cli(list(leaf.new), project)
    assert result.exit_code == record["exit_code"], describe(result)
    if leaf.json_keys:
        assert json_key_set(read_json_output(result)) == record["json_keys"], describe(result)
        return
    expected = record["key_lines"]
    assert isinstance(expected, list) and expected, f"no recorded key line for {leaf.key}: the record is vacuous"
    produced = compact(normalise(result.output, project))
    missing = [line for line in expected if compact(str(line)) not in produced]
    assert not missing, f"key output missing: {missing}\n{describe(result)}"


@covers("FR-006", "FR-004")
@pytest.mark.integration
def test_fr006_pack_path_takes_a_pack_name(tmp_path: Path) -> None:
    project = project_from_template("two_org_packs", tmp_path / "p")
    result = run_cli(["charter", "pack", "path", "built-in", "--json"], project)
    assert result.exit_code == 0, describe(result)
    payload = read_json_output(result)
    assert payload["pack"] == "built-in"
    assert Path(payload["path"]).name == "built-in" and Path(payload["path"]).is_dir()
    # Control: an unknown pack is refused with PACK_NOT_FOUND on the same fixture.
    missing = run_cli(["charter", "pack", "path", "no-such-pack"], project)
    assert missing.exit_code == 1 and "PACK_NOT_FOUND" in output_of(missing), describe(missing)


#: In-repo callers that must use the charter spellings (FR-006).
IN_REPO_CALLERS: tuple[str, ...] = (".github/workflows/packs.yml", "Makefile", "packs/built-in/pack-manifest.yaml", "AGENTS.md")
OLD_SPELLINGS = ("spec-kitty doctrine", "doctor doctrine")


@covers("FR-006", "EC:Saved script calling `spec-kitty doctrine fetch`")
@pytest.mark.corpus
@pending_until("WP15", "in-repo callers move to the charter spellings")
def test_fr006_in_repo_callers_use_charter_spellings() -> None:
    files = [REPO_ROOT / rel for rel in IN_REPO_CALLERS]
    files += sorted(p for p in (REPO_ROOT / "packs" / "internal").rglob("*") if p.is_file() and p.suffix in {".md", ".yaml", ".yml", ".py"})
    offenders = [f"{p.relative_to(REPO_ROOT)}: {s}" for p in files for s in OLD_SPELLINGS if s in p.read_text(encoding="utf-8", errors="replace")]
    assert not offenders, "old spellings remain:\n" + "\n".join(offenders)
    # Positive control: each named caller spells the new command.
    assert "charter pack regenerate-graph" in (REPO_ROOT / ".github/workflows/packs.yml").read_text(encoding="utf-8")
    assert "charter pack regenerate-graph" in (REPO_ROOT / "packs/built-in/pack-manifest.yaml").read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# FR-007: every old spelling hits the unknown-command path (exit 2), the new one runs
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Removed:
    key: str
    old: tuple[str, ...]
    new: tuple[str, ...]
    pending: str


def _removed_rows() -> list[Removed]:
    rows = [Removed("doctrine_group", ("doctrine",), ("charter", "--help"), "WP16")]
    for leaf in DOCTRINE_LEAVES:
        if leaf.key in {"doctor", "consistency_check"}:
            rows.append(Removed(leaf.key, leaf.old, leaf.new, "WP15"))
        else:
            rows.append(Removed(leaf.key, leaf.old, leaf.new, "WP16"))
    rows.append(Removed("charter_pack_apply", ("charter", "pack", "apply", "minimal"), ("charter", "activate", "--preset", "minimal", "--force"), "WP13"))
    return rows


def _expected_replacement_exit(row: Removed) -> int:
    """The recorded base exit code of a former leaf (``cli_before.json``); 0 for the other rows."""
    record = _recorded().get(row.key)
    if record is None:
        return 0
    code = record["exit_code"]
    assert isinstance(code, int), (row.key, code)
    return code


@covers("FR-007", "US3-2", "OD-3", "FR-005")
@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    "row",
    [pytest.param(r, id=r.key, marks=_FR007_PENDING[r.pending]) for r in _removed_rows()],
)
def test_fr007_old_spelling_exits_2(row: Removed, tmp_path: Path) -> None:
    project = build_doctrine_command_fixture(tmp_path / "doctrine-commands")
    old = run_cli(list(row.old), project)
    assert old.exit_code == 2, describe(old)
    assert UNKNOWN_COMMAND in output_of(old), describe(old)
    # Control: the replacement runs on the same fixture (a hidden alias would exit 0 above). A
    # former leaf must exit with the code recorded for it at base (SC-004; `doctor doctrine` exits 1
    # on this fixture because its org pack is not fetched); the other rows exit 0.
    new = run_cli(list(row.new), project)
    assert UNKNOWN_COMMAND not in output_of(new), describe(new)
    assert new.exit_code == _expected_replacement_exit(row), describe(new)


# --------------------------------------------------------------------------------------
# FR-005: the preset registry is retired
# --------------------------------------------------------------------------------------

RETIRED_REGISTRY_MODULES = ("specify_cli.charter_pack_registry", "charter.activation.packs", "charter.activation.default_pack")
RETIRED_REGISTRY_IMPORTS = ("charter.activation.default_pack", "charter_pack_registry", "charter.activation.packs")


def _module_defines_or_imports(source: str, names: Sequence[str], modules: Sequence[str]) -> list[str]:
    """Definitions/imports of *names* and imports of *modules* in Python *source*."""
    hits: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            hits += [t.id for t in targets if isinstance(t, ast.Name) and t.id in names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            hits += [module for m in modules if module == m or module.endswith(m)]
            hits += [a.name for a in node.names if a.name in names]
        elif isinstance(node, ast.Import):
            hits += [a.name for a in node.names if any(a.name == m or a.name.endswith(m) for m in modules)]
    return hits


def _scan_src(names: Sequence[str], modules: Sequence[str], root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        hits = _module_defines_or_imports(path.read_text(encoding="utf-8"), names, modules)
        findings += [f"{path}: {h}" for h in hits]
    return findings


@covers("FR-005")
@pending_until("WP13", "preset registry modules retired")
def test_fr005_registry_modules_not_importable(tmp_path: Path) -> None:
    # Positive control for the scan: a planted definition is found.
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "m.py").write_text("BUILTIN_PACKS = {}\n", encoding="utf-8")
    assert _scan_src(("BUILTIN_PACKS",), (), planted)
    for name in RETIRED_REGISTRY_MODULES:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
    assert _scan_src(("BUILTIN_PACKS",), (), REPO_ROOT / "src") == []


def _retired_reader_findings(root: Path) -> list[str]:
    findings = _scan_src(("BUILTIN_PACKS",), RETIRED_REGISTRY_IMPORTS, root)
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "charter/activation/packs/" in text or "activation/packs/default.yaml" in text:
            findings.append(f"{path}: src/charter/activation/packs/ path")
    return findings


@covers("FR-005")
@pending_until("WP13", "no reader of the retired default.yaml surfaces")
def test_fr005_no_default_yaml_reader_outside_migration_data(tmp_path: Path) -> None:
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "bad.py").write_text("from charter.activation.default_pack import load_default_pack_activation_ids\n", encoding="utf-8")
    (planted / "ok.py").write_text('PRESET = "presets/default.yaml"\n', encoding="utf-8")
    planted_findings = _retired_reader_findings(planted)
    assert any("bad.py" in f for f in planted_findings) and not any("ok.py" in f for f in planted_findings)
    src = REPO_ROOT / "src"
    findings = [f for f in _retired_reader_findings(src) if "_charter_pack_cutover" not in f and "charter_pack_cutover" not in f]
    assert findings == [], "\n".join(findings)
    assert not (src / "charter" / "activation" / "packs").exists()


@covers("US3-4", "OD-2", "FR-005")
@pytest.mark.integration
@pending_until("WP15", "`charter pack validate` rejects accompanies_doctrine_pack")
def test_us3_4_accompanies_field_rejected(tmp_path: Path) -> None:
    good = write_doctrine_pack(tmp_path / "good")
    (good / "pack.yaml").write_text("pack_id: acme\npack_version: 1.0.0\nname: acme\n", encoding="utf-8")
    ok = run_cli(["charter", "pack", "validate", str(good)], tmp_path)
    assert ok.exit_code == 0, describe(ok)
    bad = write_doctrine_pack(tmp_path / "bad")
    (bad / "pack.yaml").write_text("pack_id: acme\npack_version: 1.0.0\nname: acme\naccompanies_doctrine_pack: null\n", encoding="utf-8")
    refused = run_cli(["charter", "pack", "validate", str(bad)], tmp_path)
    assert refused.exit_code != 0, describe(refused)
    text = output_of(refused)
    assert "RETIRED_PACK_FIELD" in text and "accompanies_doctrine_pack" in text, describe(refused)


# --------------------------------------------------------------------------------------
# FR-011: read-side shims removed; one CLI-root gate on unmigrated projects
# --------------------------------------------------------------------------------------

#: Exempt from the legacy gate (contracts/cli.md "Unmigrated project").
EXEMPT_COMMANDS = frozenset({"upgrade", "init", "live-work", "session-start", "session-stop", "commit-guard-hook"})
HOT_PATHS: tuple[tuple[str, ...], ...] = (
    ("charter", "list"),
    ("charter", "status"),
    ("doctor", "charter-packs"),
    ("agent", "tasks", "status"),
    ("next",),
    ("implement", "WP01"),
)


def _gated_groups() -> list[tuple[str, ...]]:
    from specify_cli import app

    names = {g.name or g.typer_instance.info.name for g in app.registered_groups}
    return [(str(n),) for n in sorted(n for n in names if n and n not in EXEMPT_COMMANDS and not n.startswith("merge-driver"))]


#: Internal entry points never typed by an operator (hidden Typer plumbing).
_INTERNAL_COMMANDS = frozenset({"__force_multi_command_mode__"})
_EXEMPT_PREFIXES = ("merge-driver-", "session-")


def _is_exempt(name: str) -> bool:
    return name in EXEMPT_COMMANDS or name in _INTERNAL_COMMANDS or name.startswith(_EXEMPT_PREFIXES)


def _command_name(command: object) -> str:
    """The CLI spelling of a registered top-level command (Typer derives it from the callback)."""
    name = getattr(command, "name", None)
    if name:
        return str(name)
    callback = getattr(command, "callback", None)
    return str(getattr(callback, "__name__", "")).replace("_", "-")


def _gated_commands() -> list[tuple[str, ...]]:
    """Every non-exempt top-level command, so a new command is gated automatically."""
    from specify_cli import app

    names = {_command_name(c) for c in app.registered_commands}
    return [(n,) for n in sorted(n for n in names if n and not _is_exempt(n))]


def _legacy_invocations() -> list[object]:
    covered = {*_gated_groups(), *_gated_commands()}
    rows = [*_gated_groups(), *_gated_commands(), *(p for p in HOT_PATHS if p not in covered)]
    return [pytest.param(argv, id="-".join(argv), marks=pending_until("WP14", "CLI-root legacy gate")) for argv in rows]


def _assert_names_upgrade(result: Result) -> None:
    text = output_of(result)
    assert LEGACY_CODE in text, describe(result)
    assert "spec-kitty upgrade" in text and RUNBOOK in text, describe(result)


@covers("FR-011", "US2-5", "FR-017")
@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("argv", _legacy_invocations())
def test_fr011_legacy_project_fails_naming_upgrade(argv: tuple[str, ...], tmp_path: Path) -> None:
    project = project_from_template("legacy_keys_only", tmp_path / "legacy")
    result = run_cli(list(argv), project)
    assert result.exit_code == 1, describe(result)
    _assert_names_upgrade(result)
    # Control: the same fixture after `spec-kitty upgrade` no longer hits the gate (the upgrade
    # runs once per session on a template of this fixture; each row gets its own upgraded copy).
    upgraded, outcome = upgraded_copy("legacy_keys_only", tmp_path / "upgraded")
    assert outcome.exit_code == 0, outcome.output
    after = run_cli(list(argv), upgraded)
    assert LEGACY_CODE not in output_of(after), describe(after)


@covers("FR-011", "US2-5")
@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("argv", [("--version",), ("--help",), ("init", "--help"), ("upgrade", "--dry-run", "--json")], ids=["version", "help", "init", "upgrade"])
def test_fr011_exempt_invocations(argv: tuple[str, ...], tmp_path: Path) -> None:
    """Regression guard (passes at base): the exempt invocations never hit the legacy gate."""
    project = project_from_template("legacy_keys_only", tmp_path / "legacy")
    result = run_cli(list(argv), project)
    assert result.exit_code == 0, describe(result)
    assert LEGACY_CODE not in output_of(result), describe(result)


@covers("FR-011", "EC:Lane worktrees created before the upgrade")
@pytest.mark.integration
@pytest.mark.git_repo
@pending_until("WP14", "the gate also checks the current checkout root")
def test_fr011_stale_worktree_checkout_detected(tmp_path: Path) -> None:
    project = project_from_template("two_org_packs", tmp_path / "root")
    from ._support import git

    worktree = tmp_path / "lane"
    git(project, "worktree", "add", "-q", "-b", "lane", str(worktree))
    (worktree / ".kittify" / "doctrine" / "directive").mkdir(parents=True)
    (worktree / ".kittify" / "doctrine" / "directive" / "x.directive.yaml").write_text("id: X\n", encoding="utf-8")
    # Control: the migrated root itself does not hit the gate.
    clean = run_cli(["charter", "list"], project)
    assert LEGACY_CODE not in output_of(clean), describe(clean)
    stale = run_cli(["charter", "list"], worktree)
    assert stale.exit_code == 1, describe(stale)
    _assert_names_upgrade(stale)
    assert "merge" in output_of(stale) and "rebase" in output_of(stale), describe(stale)


KNOWN_SRC_DEFINITION = "def emit_status_transition("
RETIRED_SHIM_NAMES = ("LegacyDoctrineRootWarning", "LegacyTrackerOwnershipKeyWarning", "apply_legacy_governance_selection_key_compat")


@covers("FR-011")
@pytest.mark.integration
@pending_until("WP14", "read-side shims removed")
def test_fr011_shims_removed(tmp_path: Path) -> None:
    src_text = "\n".join(p.read_text(encoding="utf-8") for p in sorted((REPO_ROOT / "src").rglob("*.py")))
    # Control: the scan reads real source (a definition no work package of this mission touches).
    assert KNOWN_SRC_DEFINITION in src_text
    present = [name for name in RETIRED_SHIM_NAMES if name in src_text]
    assert present == [], present
    project = project_from_template("tracker_doctrine_key", tmp_path / "p")
    flag = run_cli(["tracker", "status", "--doctrine-mode", "external_authoritative"], project)
    assert flag.exit_code == 2, describe(flag)
    assert "doctrine_mode" not in src_text


@covers("FR-011")
@pending_until("WP14", "load_governance_config fails closed on governance.doctrine")
def test_fr011_load_governance_config_fails_closed(tmp_path: Path) -> None:
    project = project_from_template("governance_doctrine_in_charter_yaml", tmp_path / "p")
    sync = importlib.import_module("charter.activation.sync")
    with pytest.raises(Exception, match="spec-kitty upgrade"):
        sync.load_governance_config(project)
    # Control: the canonical key loads.
    canonical = project_from_template("two_org_packs", tmp_path / "c")
    assert sync.load_governance_config(canonical) is not None


@covers("FR-011")
@pending_until("WP14", "PackContext.from_config stays total on a legacy project")
def test_fr011_pack_context_from_config_total(tmp_path: Path) -> None:
    pack_context = importlib.import_module("charter.activation.pack_context")
    legacy = project_from_template("legacy_keys_only", tmp_path / "legacy")
    ctx = pack_context.PackContext.from_config(legacy)  # must not raise
    assert tuple(ctx.org_pack_names) == ()
    # Control: the canonical two-pack project returns both packs.
    both = pack_context.PackContext.from_config(project_from_template("two_org_packs", tmp_path / "two"))
    assert len(tuple(both.org_pack_names)) == 2
