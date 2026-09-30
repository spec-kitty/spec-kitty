"""Tests for ``scripts/docs/version_leakage_check.py`` and helpers."""

from __future__ import annotations

import contextlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

from scripts.docs._inventory import (
    DivioType,
    LoadError,
    VersionTag,
    load_inventory,
)
from scripts.docs._render import (
    FINDING_COLUMNS,
    FreshnessFinding,
    render_table_plain,
    render_table_rich,
)
from scripts.docs.version_leakage_check import (
    DEFAULT_BANNER_REGEX,
    _has_banner,
    _resolve_link_target,
    _to_repo_relative,
    build_parser,
    main,
    run_checks,
)


pytestmark = [pytest.mark.architectural]

# --- helpers ----------------------------------------------------------------

#: Temporarily change cwd to ``path`` (Python 3.11+ scoped cwd context manager).
chdir = contextlib.chdir


def _findings_by_rule(findings: list[FreshnessFinding]) -> Counter[str]:
    return Counter(finding.rule_id for finding in findings)


# --- _inventory.py ---------------------------------------------------------


def test_load_inventory_clean(clean_workspace: Path) -> None:
    entries = load_inventory(clean_workspace / "inventory.yaml")
    assert frozenset(e.path for e in entries) == frozenset({"docs/current/index.md", "docs/archive/legacy.md", "docs/migrations/from-2x.md"})
    assert entries[0].path == "docs/current/index.md"
    assert entries[0].tag is VersionTag.CURRENT
    assert entries[0].divio_type is DivioType.HOW_TO
    assert entries[0].current_target is True
    assert entries[1].tag is VersionTag.ARCHIVAL
    assert entries[1].current_target is False


def test_load_inventory_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not found"):
        load_inventory(tmp_path / "does-not-exist.yaml")


def test_load_inventory_path_is_directory(tmp_path: Path) -> None:
    target = tmp_path / "as_dir"
    target.mkdir()
    with pytest.raises(LoadError, match="not a file"):
        load_inventory(target)


def test_load_inventory_malformed_yaml(missing_workspace: Path) -> None:
    with pytest.raises(LoadError, match="Malformed YAML"):
        load_inventory(missing_workspace / "inventory.yaml")


def test_load_inventory_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    assert load_inventory(empty) == []


def test_load_inventory_not_a_list(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: value\n", encoding="utf-8")
    with pytest.raises(LoadError, match="must be a list"):
        load_inventory(bad)


def test_load_inventory_row_not_a_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just-a-string\n", encoding="utf-8")
    with pytest.raises(LoadError, match="must be a mapping"):
        load_inventory(bad)


def test_load_inventory_missing_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- path: docs/x.md\n  tag: current\n", encoding="utf-8")
    with pytest.raises(LoadError, match="missing keys"):
        load_inventory(bad)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("path", "", "non-empty string"),
        ("path", 42, "non-empty string"),
        ("tag", "bogus", "invalid tag"),
        ("divio_type", "bogus", "invalid divio_type"),
        ("owning_workstream", "", "owning_workstream"),
        ("owning_workstream", 5, "owning_workstream"),
        ("current_target", "yes", "current_target"),
        ("notes", 42, "notes"),
    ],
)
def test_load_inventory_field_validation(tmp_path: Path, field: str, value: object, match: str) -> None:
    row: dict[str, object] = {
        "path": "docs/x.md",
        "tag": "current",
        "divio_type": "how-to",
        "owning_workstream": "E",
        "current_target": True,
        "citation_refs": [],
        "notes": None,
    }
    row[field] = value
    bad = tmp_path / "bad.yaml"
    import ruamel.yaml

    yaml = ruamel.yaml.YAML(typ="safe")
    with bad.open("w", encoding="utf-8") as handle:
        yaml.dump([row], handle)
    with pytest.raises(LoadError, match=match):
        load_inventory(bad)


def test_load_inventory_archival_must_not_be_current_target(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- path: docs/x.md\n  tag: archival\n  divio_type: none\n  owning_workstream: C\n  current_target: true\n  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )
    with pytest.raises(LoadError, match="archival pages must have current_target=false"):
        load_inventory(bad)


def test_load_inventory_current_must_be_current_target(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- path: docs/x.md\n  tag: current\n  divio_type: how-to\n  owning_workstream: E\n  current_target: false\n  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )
    with pytest.raises(LoadError, match="current pages must have current_target=true"):
        load_inventory(bad)


# --- _render.py ------------------------------------------------------------


def _sample_findings() -> list[FreshnessFinding]:
    return [
        FreshnessFinding(
            rule_id="LEAK-MISSING-BANNER",
            severity="error",
            location="docs/archive/no-banner.md",
            message="archival page missing banner",
            suggested_action="add banner",
        ),
        FreshnessFinding(
            rule_id="LEAK-MISSING-FILE",
            severity="error",
            location="docs/missing.md",
            message="file not on disk",
            suggested_action="create file",
        ),
    ]


def test_render_table_rich_is_deterministic() -> None:
    findings = _sample_findings()
    table_a = render_table_rich(findings)
    table_b = render_table_rich(findings)
    assert table_a.row_count == table_b.row_count == len(findings)
    assert len(table_a.columns) == len(FINDING_COLUMNS)


def test_render_table_plain_is_deterministic() -> None:
    findings = _sample_findings()
    output_a = render_table_plain(findings)
    output_b = render_table_plain(findings)
    assert output_a == output_b
    lines = output_a.splitlines()
    assert lines[0] == "\t".join(FINDING_COLUMNS)
    assert len(lines) == 1 + len(findings)
    assert "LEAK-MISSING-BANNER" in lines[1]


def test_render_table_plain_empty_findings() -> None:
    output = render_table_plain([])
    assert output == "\t".join(FINDING_COLUMNS) + "\n"


# --- version_leakage_check.py CLI -----------------------------------------


def test_build_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert str(args.inventory) == "docs/development/page-inventory.yaml"
    assert str(args.docs_root) == "docs"
    assert args.banner_regex == DEFAULT_BANNER_REGEX
    assert args.report is None
    assert args.ci is False


@pytest.mark.parametrize("ci_flag", [False, True])
def test_main_clean_exits_zero(clean_workspace: Path, capsys: pytest.CaptureFixture[str], ci_flag: bool) -> None:
    argv = [
        "--inventory",
        "inventory.yaml",
        "--docs-root",
        "docs",
    ]
    if ci_flag:
        argv.append("--ci")
    with chdir(clean_workspace):
        exit_code = main(argv)
    assert exit_code == 0
    captured = capsys.readouterr()
    if ci_flag:
        assert captured.out.startswith("rule_id\t")


@pytest.mark.parametrize("ci_flag", [False, True])
def test_main_dirty_exits_one_with_four_findings(
    dirty_workspace: Path,
    capsys: pytest.CaptureFixture[str],
    ci_flag: bool,
) -> None:
    report_path = dirty_workspace / "report.json"
    argv = [
        "--inventory",
        "inventory.yaml",
        "--docs-root",
        "docs",
        "--report",
        str(report_path),
    ]
    if ci_flag:
        argv.append("--ci")
    with chdir(dirty_workspace):
        exit_code = main(argv)
    assert exit_code == 1

    # The JSON report is the deterministic surface; assert exactly 4
    # findings, one per (live) rule_id. LEAK-FRONTMATTER-MISMATCH is retired.
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 1
    assert payload["inventory_rows_count"] == 4
    counts = Counter(f["rule_id"] for f in payload["findings"])
    assert counts == Counter(
        {
            "LEAK-CURRENT-LINKS-ARCHIVAL": 1,
            "LEAK-MISSING-BANNER": 1,
            "LEAK-MISSING-INVENTORY": 1,
            "LEAK-MISSING-FILE": 1,
        }
    )
    # All findings are errors.
    assert all(f["severity"] == "error" for f in payload["findings"])
    capsys.readouterr()


def test_main_missing_inventory_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    with chdir(workspace):
        exit_code = main(
            [
                "--inventory",
                "does-not-exist.yaml",
                "--docs-root",
                "docs",
            ]
        )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()


def test_main_malformed_inventory_exits_two(missing_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with chdir(missing_workspace):
        exit_code = main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "docs",
            ]
        )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "malformed yaml" in captured.err.lower()


def test_main_docs_root_missing_exits_three(clean_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with chdir(clean_workspace):
        exit_code = main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "nonexistent_docs_dir",
            ]
        )
    assert exit_code == 3
    captured = capsys.readouterr()
    assert "does not exist" in captured.err.lower()


def test_main_docs_root_is_file_exits_three(clean_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sentinel = clean_workspace / "not_a_dir.txt"
    sentinel.write_text("hi", encoding="utf-8")
    with chdir(clean_workspace):
        exit_code = main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "not_a_dir.txt",
            ]
        )
    assert exit_code == 3
    captured = capsys.readouterr()
    assert "not a directory" in captured.err.lower()


def test_main_invalid_banner_regex_exits_two(clean_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with chdir(clean_workspace):
        exit_code = main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "docs",
                "--banner-regex",
                "(unterminated",
            ]
        )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "invalid --banner-regex" in captured.err.lower()


def test_main_writes_rich_table_when_not_ci(clean_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Force non-CI path even though pytest's stdout is not a TTY."""
    # _emit_output falls back to plain when stdout is not a TTY. Stub
    # isatty -> True so we exercise the rich branch.
    import scripts.docs.version_leakage_check as module

    original_isatty = sys.stdout.isatty
    sys.stdout.isatty = lambda: True  # type: ignore[method-assign]
    try:
        with chdir(clean_workspace):
            exit_code = module.main(
                [
                    "--inventory",
                    "inventory.yaml",
                    "--docs-root",
                    "docs",
                ]
            )
    finally:
        sys.stdout.isatty = original_isatty  # type: ignore[method-assign]
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Version Leakage Findings" in captured.out


# --- run_checks unit coverage ---------------------------------------------


def test_run_checks_returns_no_findings_on_clean(clean_workspace: Path) -> None:
    with chdir(clean_workspace):
        inventory = load_inventory(Path("inventory.yaml"))
        findings = run_checks(
            inventory=inventory,
            docs_root=Path("docs"),
            banner_regex=re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE),
        )
    assert findings == []


def test_run_checks_detects_all_four_rules(dirty_workspace: Path) -> None:
    with chdir(dirty_workspace):
        inventory = load_inventory(Path("inventory.yaml"))
        findings = run_checks(
            inventory=inventory,
            docs_root=Path("docs"),
            banner_regex=re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE),
        )
    counts = _findings_by_rule(findings)
    assert counts == Counter(
        {
            "LEAK-CURRENT-LINKS-ARCHIVAL": 1,
            "LEAK-MISSING-BANNER": 1,
            "LEAK-MISSING-INVENTORY": 1,
            "LEAK-MISSING-FILE": 1,
        }
    )


def test_run_checks_unreadable_inventory_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An inventory row whose file cannot be read yields LEAK-MISSING-FILE."""
    workspace = tmp_path / "ws"
    (workspace / "docs").mkdir(parents=True)
    page = workspace / "docs" / "page.md"
    page.write_text("# page\n", encoding="utf-8")
    inventory_yaml = workspace / "inventory.yaml"
    inventory_yaml.write_text(
        "- path: docs/page.md\n  tag: current\n  divio_type: how-to\n  owning_workstream: E\n  current_target: true\n  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text

    def boom(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "page.md":
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", boom)
    with chdir(workspace):
        inventory = load_inventory(Path("inventory.yaml"))
        findings = run_checks(
            inventory=inventory,
            docs_root=Path("docs"),
            banner_regex=re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE),
        )
    assert any(f.rule_id == "LEAK-MISSING-FILE" and "permission denied" in f.message for f in findings)


def test_run_checks_skips_external_and_anchor_links(tmp_path: Path) -> None:
    """External links and pure-anchor links must not trigger findings."""
    workspace = tmp_path / "ws"
    (workspace / "docs/current").mkdir(parents=True)
    (workspace / "docs/archive").mkdir(parents=True)
    page = workspace / "docs/current/page.md"
    page.write_text(
        "---\nversion_tag: current\n---\n\n"
        "External: [docs](https://example.com/x.md)\n"
        "Anchor: [here](#section)\n"
        "Mailto: [mail](mailto:x@y.z)\n"
        "Empty: []()\n"
        "Outside-cwd: [out](/etc/passwd)\n",
        encoding="utf-8",
    )
    archive = workspace / "docs/archive/old.md"
    archive.write_text(
        "---\nversion_tag: archival\n---\n\n> Archive notice: legacy\n",
        encoding="utf-8",
    )
    inventory_yaml = workspace / "inventory.yaml"
    inventory_yaml.write_text(
        "- path: docs/current/page.md\n"
        "  tag: current\n"
        "  divio_type: how-to\n"
        "  owning_workstream: E\n"
        "  current_target: true\n"
        "  citation_refs: []\n"
        "  notes: null\n"
        "- path: docs/archive/old.md\n"
        "  tag: archival\n"
        "  divio_type: none\n"
        "  owning_workstream: C\n"
        "  current_target: false\n"
        "  citation_refs: []\n"
        "  notes: null\n",
        encoding="utf-8",
    )
    with chdir(workspace):
        inventory = load_inventory(Path("inventory.yaml"))
        findings = run_checks(
            inventory=inventory,
            docs_root=Path("docs"),
            banner_regex=re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE),
        )
    assert findings == []


# --- private helper unit tests --------------------------------------------


def test_has_banner_caps_at_twenty_nonempty_lines() -> None:
    pattern = re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE)
    # 25 filler non-empty lines, then a banner — should NOT be found.
    body = "\n".join(f"line {i}" for i in range(25))
    body += "\n> Archive notice: too late\n"
    assert _has_banner(body, pattern) is False


def test_has_banner_finds_within_first_twenty() -> None:
    pattern = re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE)
    body = "\n\n> Archive notice: hello\n\nbody\n"
    assert _has_banner(body, pattern) is True


def test_resolve_link_target_empty_input(tmp_path: Path) -> None:
    assert _resolve_link_target("", tmp_path / "p.md") is None


def test_resolve_link_target_pure_anchor(tmp_path: Path) -> None:
    assert _resolve_link_target("#section", tmp_path / "p.md") is None


def test_resolve_link_target_absolute_repo_path(tmp_path: Path) -> None:
    assert _resolve_link_target("/docs/x.md", tmp_path / "p.md") == "docs/x.md"


def test_resolve_link_target_outside_cwd(tmp_path: Path) -> None:
    # Put the source file outside cwd entirely so that any relative
    # resolution lands outside the cwd tree, forcing _resolve_link_target
    # to return None.
    sibling_root = tmp_path / "sibling"
    sibling_root.mkdir()
    source = sibling_root / "p.md"
    source.write_text("# x\n", encoding="utf-8")
    inside_root = tmp_path / "inside"
    inside_root.mkdir()
    with chdir(inside_root):
        assert _resolve_link_target("target.md", source) is None


def test_to_repo_relative_outside_cwd(tmp_path: Path) -> None:
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    inside = tmp_path / "inside"
    inside.mkdir()
    target = sibling / "p.md"
    target.write_text("x", encoding="utf-8")
    with chdir(inside):
        # ``target`` is outside cwd, so relative_to() raises ValueError and
        # we fall through to the absolute-path branch.
        result = _to_repo_relative(target)
    assert result.endswith("/p.md")
    assert "sibling" in result


def test_run_checks_frontmatter_drift_is_not_a_leak_rule(tmp_path: Path) -> None:
    """LEAK-FRONTMATTER-MISMATCH is retired (Mission B): a page whose
    frontmatter disagrees with the inventory tag yields no LEAK finding here —
    that drift is now caught by the blocking INVENTORY-LOCKFILE-DRIFT gate."""
    workspace = tmp_path / "ws"
    (workspace / "docs").mkdir(parents=True)
    page = workspace / "docs/p.md"
    # Frontmatter version_tag deliberately disagrees with the inventory row.
    page.write_text("---\nversion_tag: archival\n---\n# body\n", encoding="utf-8")
    inventory_yaml = workspace / "inventory.yaml"
    inventory_yaml.write_text(
        "- path: docs/p.md\n  tag: current\n  divio_type: how-to\n  owning_workstream: E\n  current_target: true\n  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )
    with chdir(workspace):
        inventory = load_inventory(Path("inventory.yaml"))
        findings = run_checks(
            inventory=inventory,
            docs_root=Path("docs"),
            banner_regex=re.compile(DEFAULT_BANNER_REGEX, re.MULTILINE),
        )
    assert not any(f.rule_id == "LEAK-FRONTMATTER-MISMATCH" for f in findings)
    assert findings == []
