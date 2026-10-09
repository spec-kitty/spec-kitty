"""Gates, latency and messaging: FR-017, FR-018, NFR-002, NFR-003, SC-003, SC-005 (#3732, T009).

Gate modules are loaded by file path inside each test, so a gate that does not
exist yet is one strict xfail, never a collection error.
"""

from __future__ import annotations

import importlib.util
import re
import statistics
import subprocess
import sys
import time
from unittest import mock
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ._requirements import (
    FR018_FLOOR,
    FR018_FLOOR_BASE_SHA,
    FR018_FORBIDDEN_TOKENS,
    MISSION_DIR,
    REMOVED_SKILL_IDS,
    REPO_ROOT,
    SPEC_PATH,
    count_living_text_files,
    is_living_path,
)
from ._support import covers, describe, read_json_output, run_cli
from .legacy_fixtures import project_from_template

ARCH = REPO_ROOT / "tests" / "architectural"
VOCABULARY_GATE = ARCH / "test_retired_charter_vocabulary.py"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "CHANGELOG.md"
RUNBOOK = REPO_ROOT / "docs" / "migrations" / "charter-pack-cutover.md"
SUPERSEDED_RUNBOOKS = (
    REPO_ROOT / "docs" / "migrations" / "doctrine-local-overlay-to-org-layer.md",
    REPO_ROOT / "docs" / "migrations" / "relocate-builtin-doctrine-packs.md",
)
DOCTRINE_PACKAGE_MARKERS = ("specify_cli/doctrine", "specify_cli.doctrine")
C004_NAMES = ("doctrine-daphne", "DIRECTIVE_039")


def load_gate(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"acceptance_gate_{path.stem}", path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    # dataclasses and typing resolve a module through sys.modules while it executes;
    # patch.dict removes the entry again afterwards.
    with mock.patch.dict(sys.modules, {spec.name: module}):
        spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------------
# NFR-002: named gates close with empty exemption structures
# --------------------------------------------------------------------------------------


def _flatten(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Path):
        yield value.as_posix()
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(key)
            yield from _flatten(item)
    elif isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from _flatten(item)


def exemption_structures(module: ModuleType) -> dict[str, object]:
    """Every module-level container or path of a gate (renaming one does not hide it)."""
    return {name: value for name, value in vars(module).items() if not name.startswith("__") and isinstance(value, Path | list | tuple | set | frozenset | dict)}


def _doctrine_package_refs(module: ModuleType) -> list[str]:
    return [
        f"{name}: {text}"
        for name, value in exemption_structures(module).items()
        for text in _flatten(value)
        if any(marker in text for marker in DOCTRINE_PACKAGE_MARKERS)
    ]


def _named_allowlists(module: ModuleType) -> dict[str, object]:
    return {n: v for n, v in exemption_structures(module).items() if re.search(r"ALLOWLIST|BASELINE|EXEMPT|EXCEPTION", n)}


def _census_row() -> None:
    gate = load_gate(ARCH / "test_doctrine_census.py")
    assert exemption_structures(gate), "control: the census gate exposes its structures"
    assert _doctrine_package_refs(gate) == []


def _boundary_row() -> None:
    gate = load_gate(ARCH / "test_runtime_charter_doctrine_boundary.py")
    assert exemption_structures(gate), "control: the boundary gate exposes its structures"
    assert _doctrine_package_refs(gate) == []


def _cr02_row() -> None:
    assert (ARCH / "test_lifted_cli_doctrine_retirement.py").is_file()  # control
    assert not (ARCH / "test_lifted_cli_doctrine_charter_cr02_compat.py").exists()


LIFTED_RETIREMENT_GATE = ARCH / "test_lifted_cli_doctrine_retirement.py"


def _lifted_retirement_row() -> None:
    """The lifted retirement gate closes empty: no exemption structure, no pin of the ``doctrine`` group."""
    gate = load_gate(LIFTED_RETIREMENT_GATE)
    tests = [name for name in vars(gate) if name.startswith("test_")]
    assert tests, "control: the gate defines its tests"
    assert {n: v for n, v in _named_allowlists(gate).items() if v} == {}
    assert _doctrine_package_refs(gate) == []
    source = LIFTED_RETIREMENT_GATE.read_text(encoding="utf-8")
    assert '["doctrine", "--help"]' not in source, "the gate still requires the retired `doctrine` group to be registered"


def _guidance_gate_path() -> Path:
    found = [p for p in sorted(ARCH.glob("test_*.py")) if re.search("guidance|removed", p.name) and "4836" in p.read_text(encoding="utf-8")]
    assert found, "the #4836 guidance gate is missing"
    return found[0]


def _guidance_row() -> None:
    path = _guidance_gate_path()
    source = path.read_text(encoding="utf-8")
    assert "doctrine_app" not in source and "_migrated_doctrine_commands" not in source, path.name
    assert _doctrine_package_refs(load_gate(path)) == []


def _fr016_row() -> None:
    gate = load_gate(ARCH / "test_charter_pack_path_authority.py")
    allowlists = _named_allowlists(gate)
    assert allowlists, "control: the FR-016 gate declares its allowlist"
    assert {n: v for n, v in allowlists.items() if v} == {}


def _fr018_row() -> None:
    gate = load_gate(VOCABULARY_GATE)
    allowlist = gate._ALLOWLIST
    assert all(any(name in " ".join(_flatten(entry)) for name in C004_NAMES) for entry in allowlist), allowlist


def _empty_allowlists(path: Path) -> None:
    gate = load_gate(path)
    assert {n: v for n, v in _named_allowlists(gate).items() if v} == {}


def _dead_paths_row() -> None:
    _empty_allowlists(ARCH / "test_no_dead_doctrine_paths.py")


def _kind_vocabulary_row() -> None:
    _empty_allowlists(ARCH / "test_charter_kind_vocabulary_single_authority.py")


@dataclass(frozen=True)
class GateRow:
    key: str
    check: Callable[[], None]


GATE_ROWS: tuple[GateRow, ...] = (
    GateRow("census_exemptions", _census_row),
    GateRow("boundary_exemptions", _boundary_row),
    GateRow("cr02_compat_test_deleted", _cr02_row),
    GateRow("lifted_retirement_gate_closes_empty", _lifted_retirement_row),
    GateRow("guidance_gate_is_removed_command_gate", _guidance_row),
    GateRow("fr016_allowlist_empty", _fr016_row),
    GateRow("fr018_allowlist_c004_only", _fr018_row),
    GateRow("dead_doctrine_paths_allowlists_empty", _dead_paths_row),
    GateRow("kind_vocabulary_allowlists_empty", _kind_vocabulary_row),
)


@covers("NFR-002")
@pytest.mark.parametrize("row", [pytest.param(r, id=r.key) for r in GATE_ROWS])
def test_nfr002_gates_close_empty(row: GateRow) -> None:
    row.check()


@covers("NFR-002")
def test_nfr002_structure_reader_finds_planted_doctrine_path(tmp_path: Path) -> None:
    """Self-test of the row helpers: a renamed exemption holding the old package is still found."""
    planted = tmp_path / "planted_gate.py"
    planted.write_text('from pathlib import Path\n\n_RENAMED_EXEMPTION = frozenset({"src/specify_cli/doctrine"})\nOK = ()\n', encoding="utf-8")
    module = load_gate(planted)
    assert _doctrine_package_refs(module) == ["_RENAMED_EXEMPTION: src/specify_cli/doctrine"]


# --------------------------------------------------------------------------------------
# NFR-003: CLI latency
# --------------------------------------------------------------------------------------


def _median_seconds(argv: list[str], project: Path, check: Callable[[Any], None], runs: int = 5) -> float:
    samples: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        result = run_cli(argv, project)
        samples.append(time.perf_counter() - start)
        check(result)
    return statistics.median(samples)


@covers("NFR-003")
@pytest.mark.timing
def test_nfr003_preset_and_pack_list_latency(tmp_path: Path) -> None:
    project = project_from_template("two_org_packs", tmp_path / "p")

    def ok(result: Any) -> None:
        assert result.exit_code == 0, describe(result)

    def preset_written(result: Any) -> None:
        ok(result)
        assert "activated_directives" in (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    def lists_both_org_packs(result: Any) -> None:
        ok(result)
        names = {row["name"] for row in read_json_output(result)["packs"]}
        assert {"acme", "acme-two"} <= names, names

    baseline = _median_seconds(["charter", "list"], project, ok)
    preset = _median_seconds(["charter", "activate", "--preset", "minimal", "--force"], project, preset_written)
    pack_list = _median_seconds(["charter", "pack", "list", "--json"], project, lists_both_org_packs)
    assert preset <= 1.5 * baseline, (preset, baseline)
    assert pack_list <= 1.5 * baseline, (pack_list, baseline)


# --------------------------------------------------------------------------------------
# FR-018 / SC-003: the vocabulary gate
# --------------------------------------------------------------------------------------


def _deleted_living_files_since_base() -> int:
    present = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{FR018_FLOOR_BASE_SHA}^{{commit}}"], capture_output=True, check=False)
    if present.returncode != 0:
        return 0
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "--no-renames", "--diff-filter=D", f"{FR018_FLOOR_BASE_SHA}..HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return sum(1 for path in out if is_living_path(path))


def _finding_token(finding: object) -> str:
    token = getattr(finding, "token", None)
    if token is None and isinstance(finding, tuple | list):
        token = finding[1]
    return str(token)


@covers("FR-018", "SC-003", "US4-2")
@pytest.mark.corpus
def test_fr018_vocabulary_gate_zero_findings_over_floor() -> None:
    gate = load_gate(VOCABULARY_GATE)
    paths = list(gate.living_paths(REPO_ROOT))
    floor = FR018_FLOOR - _deleted_living_files_since_base()
    assert len(paths) >= floor, f"scanned {len(paths)} < floor {floor} (base literal {FR018_FLOOR})"
    findings = list(gate.scan(REPO_ROOT, paths))
    assert findings == [], "\n".join(map(str, findings[:50]))


@covers("FR-018", "SC-003")
@pytest.mark.parametrize("token", [pytest.param(t, id=t) for t in FR018_FORBIDDEN_TOKENS])
def test_fr018_planted_token_detected(token: str, tmp_path: Path) -> None:
    gate = load_gate(VOCABULARY_GATE)
    for rel in ("docs/guide.md", "docs/adr/0001-old.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Guide\n\nRun `{token}` here.\n", encoding="utf-8")
    found = {_finding_token(f) for f in gate.scan(tmp_path, ["docs/guide.md"])}
    assert found, f"{token!r} planted on a living surface was not reported"
    assert not list(gate.scan(tmp_path, ["docs/adr/0001-old.md"])), "a historical root was scanned"


@covers("FR-018", "SC-003")
def test_fr018_floor_literal_recorded_at_base() -> None:
    """The floor literal is what the base tree measures (when the base commit is available)."""
    assert FR018_FLOOR > 1000 and re.fullmatch(r"[0-9a-f]{40}", FR018_FLOOR_BASE_SHA)
    present = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{FR018_FLOOR_BASE_SHA}^{{commit}}"], capture_output=True, check=False)
    if present.returncode == 0:
        assert count_living_text_files(REPO_ROOT, FR018_FLOOR_BASE_SHA) == FR018_FLOOR


@covers("FR-018")
@pytest.mark.corpus
def test_fr018_closed_lists_match_spec() -> None:
    """Every backticked token of the spec's FR-018 forbidden-token bullet is in the closed list."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    bullet = next(line for line in text.splitlines() if line.startswith("- **Forbidden tokens**"))
    spec_tokens = set(re.findall(r"`([^`]+)`", bullet))
    assert spec_tokens, "control: the bullet parses"
    assert spec_tokens <= set(FR018_FORBIDDEN_TOKENS), sorted(spec_tokens - set(FR018_FORBIDDEN_TOKENS))
    assert set(REMOVED_SKILL_IDS) <= set(FR018_FORBIDDEN_TOKENS)


# --------------------------------------------------------------------------------------
# FR-017 / SC-005: messaging
# --------------------------------------------------------------------------------------


def unreleased_section(text: str) -> str:
    match = re.search(r"^## \[Unreleased\].*?(?=^## \[)", text, flags=re.MULTILINE | re.DOTALL)
    assert match, "no Unreleased section"
    return match.group(0)


def _contract_before_names() -> list[str]:
    cli = (MISSION_DIR / "contracts" / "cli.md").read_text(encoding="utf-8")
    table = cli.split("## Command map", 1)[1].split("\n## ", 1)[0]
    names: list[str] = []
    for line in table.splitlines():
        if not line.startswith("| `"):
            continue
        before = line.split("|")[1]
        for spelling in re.findall(r"`([^`]+)`", before):
            names.append(re.split(r"\s[<\[]", spelling)[0].strip())
    errors = (MISSION_DIR / "contracts" / "errors.md").read_text(encoding="utf-8")
    for line in errors.splitlines():
        if line.startswith("| `"):
            replaces = line.split("|")[3]
            names += re.findall(r"`([A-Za-z_]+)`", replaces)
    return names


REMOVED_KEYS_AND_PATHS = ("doctrine.org.packs", "organisation_packs", "governance.doctrine", "doctrine_pack_id", ".kittify/doctrine/", "accompanies_doctrine_pack")


@covers("FR-017", "SC-005", "EC:Saved script calling `spec-kitty doctrine fetch`")
@pytest.mark.corpus
def test_fr017_changelog_before_after_lists_every_removed_name() -> None:
    names = _contract_before_names()
    assert len(names) >= 15, "control: the contract tables parse"
    section = unreleased_section(CHANGELOG.read_text(encoding="utf-8"))
    expected = [*names, *REMOVED_SKILL_IDS, *REMOVED_KEYS_AND_PATHS]
    missing = sorted({name for name in expected if not changelog_names(section, name)})
    assert missing == [], missing


_ELLIPSIS = re.compile(r"\s*(?:\u2026|\.\.\.)\s*")


def _plain(text: str) -> str:
    """Lower-cased, backticks dropped, whitespace collapsed."""
    return " ".join(text.replace("`", " ").lower().split())


def changelog_names(section: str, name: str) -> bool:
    """*name* appears in *section*, matched on meaning rather than verbatim spelling.

    Case, backticks and whitespace are ignored, and an elided spelling such as
    ``spec-kitty tracker … --doctrine-mode`` matches when each fragment appears.
    """
    haystack = _plain(section)
    fragments = [_plain(f) for f in _ELLIPSIS.split(name)]
    return all(f in haystack for f in fragments if f)


@covers("FR-017")
def test_fr017_changelog_matching_is_semantic() -> None:
    """Self-test of the matcher used by the changelog check."""
    section = "| `spec-kitty tracker status --doctrine-mode` | removed |\n| `Doctrine.Org.Packs` |"
    assert changelog_names(section, "spec-kitty tracker \u2026 --doctrine-mode")
    assert changelog_names(section, "doctrine.org.packs")
    assert not changelog_names(section, "spec-kitty doctrine fetch")


@covers("FR-017")
@pytest.mark.corpus
def test_fr017_runbook_and_historical_banners() -> None:
    assert all(p.is_file() for p in SUPERSEDED_RUNBOOKS), "control: the superseded runbooks exist"
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "spec-kitty upgrade" in text
    for page in SUPERSEDED_RUNBOOKS:
        body = page.read_text(encoding="utf-8")
        assert "doc_status: superseded" in body and "Superseded" in body and "charter-pack-cutover.md" in body, page.name
