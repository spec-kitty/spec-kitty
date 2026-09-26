"""Keep tests out of shared, world-writable temporary directories.

The live invariant is negative and baseline-free: test source must use isolated
fixtures instead of hard-coded shared temp roots.  Both scanners run against a
non-empty corpus and through controlled positive/negative examples.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.architectural._ast_scan import read_source

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TESTS_ROOT = _REPO_ROOT / "tests"
_SELF_PATH = Path(__file__).resolve()
_TMP_LITERAL = "/" + "tmp" + "/"
_EVASION_LITERALS: tuple[str, ...] = (
    "/dev/shm/",
    "/scratch/",
    "/var/" + "tmp/",
)


def scan_file_for_tmp_literal(path: Path) -> list[int]:
    """Return 1-based lines containing the forbidden shared-temp literal."""
    if not path.is_file():
        return []
    lines = read_source(path).splitlines()
    return [line for line, text in enumerate(lines, start=1) if _TMP_LITERAL in text]


def _python_test_files(root: Path = _TESTS_ROOT) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.resolve() != _SELF_PATH)


def _collect_violations(
    *,
    tests_root: Path = _TESTS_ROOT,
    repo_root: Path = _REPO_ROOT,
) -> list[tuple[str, list[int]]]:
    violations: list[tuple[str, list[int]]] = []
    for path in _python_test_files(tests_root):
        hits = scan_file_for_tmp_literal(path)
        if hits:
            violations.append((path.relative_to(repo_root).as_posix(), hits))
    return violations


def _line_has_evasion_root_literal(line: str) -> str | None:
    for literal in _EVASION_LITERALS:
        if f'"{literal}' in line or f"'{literal}" in line:
            return literal
    return None


def test_no_shared_tmp_literals_in_live_test_corpus() -> None:
    files = _python_test_files()
    assert files, "test-source scan collected zero Python files"
    assert _collect_violations() == []


def test_shared_tmp_scanner_has_two_sided_fault_bite(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    source = tests_root / "test_probe.py"

    source.write_text("value = 'isolated-path'\n", encoding="utf-8")
    assert _collect_violations(tests_root=tests_root, repo_root=tmp_path) == []

    source.write_text(f"value = '{_TMP_LITERAL}shared'\n", encoding="utf-8")
    assert _collect_violations(tests_root=tests_root, repo_root=tmp_path) == [
        ("tests/test_probe.py", [1])
    ]


def test_no_evasion_roots_in_live_test_corpus() -> None:
    files = _python_test_files()
    assert files, "evasion scan collected zero Python files"
    violations: list[tuple[str, str, int]] = []
    for path in files:
        lines = read_source(path).splitlines()
        for lineno, line in enumerate(lines, start=1):
            literal = _line_has_evasion_root_literal(line)
            if literal is not None:
                violations.append(
                    (path.relative_to(_REPO_ROOT).as_posix(), literal, lineno)
                )
    assert violations == []


def test_evasion_scanner_has_two_sided_fault_bite() -> None:
    for literal in _EVASION_LITERALS:
        assert _line_has_evasion_root_literal(f'x = "{literal}file"') == literal
        assert _line_has_evasion_root_literal(f"x = '{literal}file'") == literal
    assert _line_has_evasion_root_literal('x = ".worktrees/scratch/"') is None
    assert _line_has_evasion_root_literal("# see /dev/shm/ for rationale") is None
