"""#7000 controls: the completeness scan must fail for the right reason, and only then.

``test_gate_scan_scope_completeness.py`` asserts the property over the live tree. A property
test that cannot fail proves nothing -- the #6994 defect was precisely a declaration that
looked fine while routing missed it. These controls mutate one input at a time (a synthetic
gate, a copied registry, the exemption table) and demand the scan names the mutation:

* an undeclared read reds, and the same read declared greens;
* a dynamic read is checked at its literal parent, a fully dynamic one is an indirection;
* dropping a row from a copy of the live registry reds the gate that needed it;
* a shadowed repo-root name is not a repository root;
* a module-level string constant is resolved instead of becoming a wildcard;
* an exemption that is unexplained, wildcard, unknown or stale is a problem.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci import gate_selection as gs
from tests.architectural import _gate_read_scope as scope

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_LIVE_REGISTRY = gs.DEFAULT_REGISTRY_PATH


def _gate_source(read: str) -> str:
    return f"from pathlib import Path\n\n_REPO_ROOT = Path(__file__).resolve().parents[2]\n\n\ndef test_planted() -> None:\n    assert {read}\n"


def _tree(tmp_path: Path, gates: dict[str, str], rows: dict[str, list[str]]) -> Path:
    """A synthetic checkout with `tests/architectural/<gate>.py` files and a registry."""
    battery = tmp_path / scope.BATTERY_TREE
    battery.mkdir(parents=True)
    for name, source in gates.items():
        (battery / name).write_text(source, encoding="utf-8")
    entries = [{"gate": f"{scope.BATTERY_TREE}/{name}", "globs": globs} for name, globs in sorted(rows.items())]
    registry = tmp_path / "registry.yml"
    registry.write_text(
        yaml.safe_dump({"special_tiers": {"architectural": {"scan_scopes": entries}}}, sort_keys=False),
        encoding="utf-8",
    )
    return registry


def _scan(tmp_path: Path, gates: dict[str, str], rows: dict[str, list[str]], *, exemptions: dict[str, dict[str, str]] | None = None):
    registry = _tree(tmp_path, gates, rows)
    return scope.scan(root=tmp_path, registry_path=registry, router=gs.load_router(), exemptions=exemptions or {})


def _targets(defects) -> list[str]:
    return [finding.target for finding in defects]


def test_an_undeclared_read_reds_and_its_declaration_greens(tmp_path: Path) -> None:
    gate = "test_planted_gate.py"
    source = _gate_source('(_REPO_ROOT / "planted-undeclared").exists()')

    undeclared = _scan(tmp_path / "a", {gate: source}, {})
    assert _targets(undeclared.findings) == ["planted-undeclared"], "the undeclared read must be reported by its path"
    assert undeclared.findings[0].gate == f"{scope.BATTERY_TREE}/{gate}"

    declared = _scan(tmp_path / "b", {gate: source}, {gate: ["planted-undeclared/**"]})
    assert declared.findings == ()


def test_a_read_under_code_scope_needs_no_declaration(tmp_path: Path) -> None:
    gates = {"test_under_src.py": _gate_source('(_REPO_ROOT / "src" / "specify_cli").is_dir()')}
    assert _scan(tmp_path, gates, {}).findings == ()


def test_a_dynamic_read_is_checked_at_its_literal_parent(tmp_path: Path) -> None:
    gate = "test_dynamic.py"
    source = _gate_source('(_REPO_ROOT / "kitty-specs" / "some-mission" / "meta.json").is_file()')

    # every component is literal, so the read is the file it names.
    findings = _scan(tmp_path / "a", {gate: source}, {gate: []}).findings
    assert _targets(findings) == ["kitty-specs/some-mission/meta.json"]

    dynamic = _gate_source('(_REPO_ROOT / "kitty-specs" / mission_slug).exists()')
    findings = _scan(tmp_path / "b", {gate: dynamic}, {gate: []}).findings
    assert _targets(findings) == ["kitty-specs"], "a wildcard component is checked at its literal parent"
    assert _scan(tmp_path / "c", {gate: dynamic}, {gate: ["kitty-specs/**"]}).findings == ()


def test_a_fully_dynamic_read_is_an_indirection_not_a_finding(tmp_path: Path) -> None:
    """``_REPO_ROOT / rel`` names no repository path; the scan records it instead of guessing one."""
    gate = "test_indirection.py"
    result = _scan(tmp_path, {gate: _gate_source("(_REPO_ROOT / rel).read_text()")}, {})
    assert result.findings == ()
    assert [read.prefix for read in result.indirections] == ["*"]


def test_a_shadowed_root_name_is_not_a_repository_root(tmp_path: Path) -> None:
    """A fixture that rebinds ``repo_root`` to a tmp dir does not make its joins repository reads."""
    source = (
        "from pathlib import Path\n"
        "import tempfile\n"
        "\n"
        "_REPO_ROOT = Path(__file__).resolve().parents[2]\n"
        "\n"
        "\n"
        "def test_fixture() -> None:\n"
        "    repo_root = _REPO_ROOT\n"
        "    with tempfile.TemporaryDirectory() as td:\n"
        "        repo_root = Path(td)\n"
        "        assert (repo_root / 'kitty-specs' / 'slug').exists()\n"
    )
    assert _scan(tmp_path, {"test_fixture.py": source}, {}).findings == ()


def test_a_module_string_constant_is_resolved(tmp_path: Path) -> None:
    source = (
        "from pathlib import Path\n"
        "_REPO_ROOT = Path(__file__).resolve().parents[2]\n"
        "_NOTES = 'docs/notes.md'\n"
        "def test_planted() -> None:\n"
        "    assert (_REPO_ROOT / _NOTES).is_file()\n"
    )
    findings = _scan(tmp_path, {"test_constant.py": source}, {}).findings
    assert _targets(findings) == ["docs/notes.md"], "a string constant names a path component, not a wildcard"


def test_dropping_a_row_from_the_live_registry_reds_that_gate(tmp_path: Path) -> None:
    """The live registry minus one row: every read that row covered becomes a named failure."""
    live = yaml.safe_load(_LIVE_REGISTRY.read_text(encoding="utf-8"))
    rows = live["special_tiers"]["architectural"]["scan_scopes"]
    dropped = "tests/architectural/test_dead_builtin_doc_paths.py"
    kept = [row for row in rows if row["gate"] != dropped]
    assert len(kept) == len(rows) - 1
    registry = tmp_path / "registry.yml"
    registry.write_text(yaml.safe_dump({"special_tiers": {"architectural": {"scan_scopes": kept}}}), encoding="utf-8")

    findings = scope.scan(registry_path=registry, router=gs.load_router()).findings
    named = {finding.gate for finding in findings}
    assert dropped in named, f"dropping {dropped}'s row must red it; findings: {sorted(named)}"
    assert any(finding.target == "packs/built-in" for finding in findings)


def test_an_exemption_that_is_unexplained_wide_unknown_or_stale_is_a_problem() -> None:
    problems = scope.validate_exemptions(
        exemptions={
            "tests/architectural/test_pyproject_shape.py": {
                "uv.lock": "  ",
                "**": "covers everything",
                "not-a-read": "stale",
            },
            "tests/architectural/test_not_a_gate.py": {"docs": "unknown gate"},
        }
    )
    joined = "\n".join(problems)
    assert "has no reason" in joined
    assert "uses a wildcard" in joined
    assert "is stale" in joined
    assert "not a battery gate" in joined


def test_the_covers_rule_is_the_declared_semantics() -> None:
    assert scope.covers("docs/**", "docs/adr")
    assert scope.covers("docs/adr/**", "docs/adr")
    assert not scope.covers("docs/adr/**", "docs/other")
    assert scope.covers("uv.lock", "uv.lock")
    assert not scope.covers("pytest.ini", "uv.lock")
    assert scope.covers("**", "anything")
    assert not scope.covers("docs/**", ""), "a bare-root read needs '**', not a directory glob"
