"""Shrink-only ratchet over the flake8-pytest-style (PT) weak-oracle baseline.

Issue #5351: `pytest.raises(ValueError)` without ``match=``, a ``raises`` block
where any of several statements can satisfy it, and an assertion inside an
``except`` that never runs when nothing raises all let a test pass on a broken
product (DIRECTIVE_041 integrity rule 1). Ruff can reject those shapes before a
single test runs, so the PT weak-oracle rules are selected in
``pyproject.toml`` and the legacy hits are frozen per file in ``ruff.toml``'s
``[lint.extend-per-file-ignores]`` baseline.

This guard keeps that baseline honest in both directions, the same way
``test_ruff_format_exclude_ratchet.py`` guards the formatter-debt list:

* it cannot grow without a visible bump of ``_BASELINE_PT_PAIRS``;
* an entry whose file no longer trips the listed code must be removed;
* an inline ``# noqa: PT0xx`` (or a file-level ``# ruff: noqa: PT0xx``) is the
  same exemption written somewhere else, so those are counted against their
  own shrink-only high-water mark; and
* the rules are really live: a planted weak oracle in a fresh test file is
  flagged under the repository's own ruff config.
"""

from __future__ import annotations

import json
import subprocess
import sys
import io
import re
import tokenize
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUFF_TOML = _REPO_ROOT / "ruff.toml"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# The PT rules selected in pyproject.toml as weak-oracle gates.
_WEAK_ORACLE_RULES = ("PT010", "PT011", "PT012", "PT015", "PT016", "PT017", "PT030", "PT031")

# Shrink-only high-water mark of (file, PT code) baseline pairs, as of the
# 2026-09-29 enablement (123 files). Lower it when you clean a file; raising it
# needs a reviewed reason the new test cannot simply name its expected failure.
_BASELINE_PT_PAIRS = 125


# Shrink-only high-water mark of inline PT suppressions ((file, line, code)
# triples from line-level or file-level ruff suppression comments) under the
# scanned roots, as of 2026-09-30: nine PT011, each with an inline rationale.
# Lower it when you remove one; raising it needs the same reviewed reason as
# the ruff.toml baseline.
_INLINE_PT_NOQA_HIGH_WATER = 9
_INLINE_SCAN_ROOTS = ("src", "tests")
_NOQA_PT_CODE = re.compile(r"\bPT0\d\d\b")


def _inline_pt_noqa_codes(source: str) -> list[tuple[int, str]]:
    """(line, code) for each PT code named in a ``noqa`` comment of ``source``.

    Reads real comment tokens, so a ``# noqa: PT011`` inside a string literal
    (a planted snippet, a docstring example) is not counted.
    """
    found: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT or "noqa" not in token.string:
            continue
        directive = token.string[token.string.index("noqa") :]
        found.extend((token.start[0], code) for code in _NOQA_PT_CODE.findall(directive))
    return found


def _inline_pt_noqa() -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for root in _INLINE_SCAN_ROOTS:
        for path in sorted((_REPO_ROOT / root).rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "noqa" not in text or "PT0" not in text:
                continue
            rel = str(path.relative_to(_REPO_ROOT))
            hits.extend((rel, line, code) for line, code in _inline_pt_noqa_codes(text))
    return hits


def _pt_baseline() -> dict[str, list[str]]:
    config = tomllib.loads(_RUFF_TOML.read_text(encoding="utf-8"))
    ignores = config["lint"]["extend-per-file-ignores"]
    return {path: sorted(code for code in codes if code.startswith("PT")) for path, codes in ignores.items() if any(code.startswith("PT") for code in codes)}


def _ruff_hits(paths: list[str], rules: tuple[str, ...]) -> set[tuple[str, str]]:
    """(path, code) pairs ruff reports for ``rules`` on ``paths``, ignoring the baseline."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--select", ",".join(rules), "--output-format", "json", *paths],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), f"ruff failed before reporting findings (rc={proc.returncode}):\n{proc.stderr}"
    return {(str(Path(item["filename"]).resolve().relative_to(_REPO_ROOT)), item["code"]) for item in json.loads(proc.stdout or "[]")}


def test_weak_oracle_rules_are_selected() -> None:
    """Every weak-oracle PT rule stays in the enforced ``select`` list."""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    selected = set(config["tool"]["ruff"]["lint"]["select"])
    missing = [rule for rule in _WEAK_ORACLE_RULES if rule not in selected]
    assert not missing, f"PT weak-oracle rules dropped from [tool.ruff.lint].select: {missing}"


def test_pt_baseline_does_not_exceed_high_water_mark() -> None:
    """Growth requires an explicit, reviewed bump of ``_BASELINE_PT_PAIRS``."""
    pairs = sum(len(codes) for codes in _pt_baseline().values())
    assert pairs <= _BASELINE_PT_PAIRS, (
        f"The ruff.toml PT baseline grew to {pairs} (file, code) pairs, above {_BASELINE_PT_PAIRS}. "
        "Give the new pytest.raises/warns a match= or a single statement instead of baselining it."
    )


def test_inline_pt_noqa_does_not_exceed_high_water_mark() -> None:
    """An inline PT suppression bypasses the ruff.toml baseline, so it is counted too."""
    hits = _inline_pt_noqa()
    assert len(hits) <= _INLINE_PT_NOQA_HIGH_WATER, (
        f"{len(hits)} inline PT noqa suppressions, above {_INLINE_PT_NOQA_HIGH_WATER}. "
        "Give the pytest.raises/warns a match= instead of suppressing it: " + ", ".join(f"{path}:{line} {code}" for path, line, code in hits)
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1  # noqa: PT011 - reason\n", [(1, "PT011")]),
        ("x = 1  # noqa: B017, PT011, PT012\n", [(1, "PT011"), (1, "PT012")]),
        ("# ruff: noqa: PT017\nx = 1\n", [(1, "PT017")]),
        ("x = 1  # noqa: E501\n", []),
        ('x = "# noqa: PT011"\n', []),
        ("x = 1  # see PT011 docs, noqa: E501\n", []),
    ],
    ids=["single", "mixed-list", "file-level", "other-code", "in-string", "pt-before-noqa"],
)
def test_inline_pt_noqa_counter_reads_comment_directives(source: str, expected: list[tuple[int, str]]) -> None:
    """Non-vacuity for the counter: it sees each PT code a noqa directive names, and nothing else."""
    assert _inline_pt_noqa_codes(source) == expected


def test_pt_baseline_has_no_glob_entries() -> None:
    """A glob would silently exempt every present and future file under it."""
    globs = [path for path in _pt_baseline() if "*" in path]
    assert not globs, f"PT baseline entries must be exact paths, not globs: {globs}"


def test_every_pt_baseline_entry_still_fires() -> None:
    """A cleaned file's PT codes must leave the baseline in the same commit."""
    baseline = _pt_baseline()
    missing_files = [path for path in baseline if not (_REPO_ROOT / path).exists()]
    assert not missing_files, f"PT baseline names files that no longer exist: {missing_files}"

    live = _ruff_hits(sorted(baseline), _WEAK_ORACLE_RULES)
    stale = sorted((path, code) for path, codes in baseline.items() for code in codes if (path, code) not in live)
    assert not stale, f"{len(stale)} PT baseline entries no longer fire; drop them from ruff.toml: {stale[:20]}"


# (planted snippet, the weak-oracle rule it must trip under the repo config).
# Spans more than one rule so a single rule silently moved to [lint].ignore
# (still "selected", so test_weak_oracle_rules_are_selected stays green) is
# caught here by its planted oracle no longer firing.
_PLANTED_WEAK_ORACLES = (
    ("PT011", "import pytest\n\n\ndef test_planted() -> None:\n    with pytest.raises(ValueError):\n        int('x')\n"),
    (
        "PT030",
        "import warnings\n\nimport pytest\n\n\ndef test_planted() -> None:\n    with pytest.warns(Warning):\n        warnings.warn('x', stacklevel=2)\n",
    ),
    (
        "PT017",
        "def test_planted() -> None:\n    try:\n        int('x')\n    except ValueError as exc:\n        assert str(exc)\n",
    ),
)


@pytest.mark.parametrize(("rule", "planted"), _PLANTED_WEAK_ORACLES, ids=[rule for rule, _ in _PLANTED_WEAK_ORACLES])
def test_planted_weak_oracle_is_flagged_under_repo_config(rule: str, planted: str) -> None:
    """Non-vacuity: the live config rejects a fresh weak oracle for each guarded rule."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "json", "--stdin-filename", "tests/unit/test_planted_weak_oracle.py", "-"],
        cwd=_REPO_ROOT,
        input=planted,
        capture_output=True,
        text=True,
        check=False,
    )
    codes = {item["code"] for item in json.loads(proc.stdout or "[]")}
    assert rule in codes, f"{rule} did not fire on its planted weak oracle; got {sorted(codes)}\n{proc.stderr}"
