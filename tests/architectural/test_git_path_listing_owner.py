"""Class gate: ``src/kernel/git/`` is the only reader of paths from git (#5392, #5400).

Mission ``git-paths-are-data-01M3SSXR``. A caller that builds a path-listing git
argv (``status --porcelain``, ``ls-files``, ``diff --name-only``, ...) or splits
git's output on NUL or ``" -> "`` re-implements the path parsing that
``kernel.git`` owns. That is the defect class behind the quoted-path bugs
(#5392/#5400): paths are data, and only the owner decodes them.

The rule is the census in ``_git_path_listing_census.py`` (the single
authority; this gate does not restate it). The gate runs it over every
``src/**/*.py`` file except ``src/kernel/git/`` and requires **zero** hits.

**The allowlist is empty and stays empty.** There is no allowlist, no
``_baselines.yaml`` entry and no count to ratchet (ADR
``2026-09-30-1-allowlist-ratchets-are-priced-debt``). A new hit is fixed by
asking ``kernel.git`` (``status_entries``, ``tree_paths``, ``changed_paths``,
...) instead; see ``kitty-specs/git-paths-are-data-01M3SSXR/quickstart.md``.
This gate also owns what T019 of ``test_destructive_op_routing.py`` used to
guard (no parallel ``status --porcelain`` dirty predicate): a porcelain argv can
no longer exist outside the owner.

Baseline: over the planning base ``b99f6f41`` the census reported **119 hits in
51 files** (1336 source files scanned). The mission closes at **0**.

Non-vacuity (standing order 5): a scanned-file floor, one planted-hit test per
census form, the ``worktree list --porcelain`` negative control, and a positive
control proving the census does find hits inside the owner when the owner
exclusion is bypassed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import iter_py_files, parse
from tests.architectural._git_path_listing_census import OWNER_ROOT, Hit, census, census_source, classify_argv, src_files

pytestmark = pytest.mark.architectural

_SCANNED_FILE_FLOOR = 1200

_FIX_HINT = (
    "Ask kernel.git (status_entries / tree_paths / changed_paths / ...) instead of building a path-listing "
    "argv or splitting git output; see kitty-specs/git-paths-are-data-01M3SSXR/quickstart.md"
)


def _plant(tmp_path: Path, body: str) -> list[Hit]:
    planted = tmp_path / "planted.py"
    planted.write_text(body, encoding="utf-8")
    return census([planted])


def _kinds(hits: list[Hit]) -> set[str]:
    return {hit.kind for hit in hits}


def test_no_path_listing_or_git_output_parsing_outside_kernel_git() -> None:
    hits = census(src_files())
    assert not hits, (
        "Path-listing git argv or git-output parsing outside src/kernel/git/ (allowlist is empty):\n"
        + "\n".join(f"  {hit.rel}:{hit.lineno}: {hit.kind}" for hit in hits)
        + f"\n{_FIX_HINT}"
    )


def test_gate_scans_a_non_trivial_number_of_files() -> None:
    scanned = [p for p in src_files() if OWNER_ROOT not in p.resolve().parents]
    assert len(scanned) >= _SCANNED_FILE_FLOOR, f"only {len(scanned)} source files scanned; the gate is vacuous below {_SCANNED_FILE_FLOOR}"


def test_positive_control_census_finds_hits_inside_the_owner_when_exclusion_is_off() -> None:
    owner_hits = [hit for path in iter_py_files(OWNER_ROOT) for hit in census_source(path.name, parse(path))]
    assert owner_hits, "the census found nothing in src/kernel/git/ even with the owner exclusion bypassed; the rule has gone blind"
    assert census(iter_py_files(OWNER_ROOT)) == [], "the owner exclusion in census() stopped working"


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("status", 'def f():\n    return ["git", "status", "--porcelain"]\n'),
        ("status", 'def f(root):\n    return _git(root, "status", "--porcelain")\n'),
        ("diff", 'def f(root):\n    return _run_git_diff(root, "base", "--name-only")\n'),
        ("diff", 'def f(root):\n    return _run_git_diff(root, "base", "--name-status")\n'),
        ("diff", 'def f(root):\n    return _run_git_diff(root, "base", "--numstat")\n'),
        ("ls", 'def f():\n    return ("git", "ls-files")\n'),
        ("split", "def f(out):\n    return out.split('\\0')\n"),
        ("arrow", 'def f(line):\n    return " -> " in line\n'),
        ("split", 'def f(line):\n    return line.split(" -> ")\n'),
        ("slice", "def f(porcelain_lines):\n    return [line[3:] for line in porcelain_lines]\n"),
        ("check-ignore", 'def f():\n    return ["git", "check-ignore", "-z", "--stdin"]\n'),
        ("status", 'def f():\n    return ["git", "status", "--short"]\n'),
        ("status", 'def f():\n    return ["git", "status", "-z"]\n'),
        ("diff", 'def f():\n    return ["git", "diff-tree", "-r", "HEAD"]\n'),
        ("diff", 'def f():\n    return ["git", "diff-index", "HEAD"]\n'),
        ("split", "def f(out):\n    return out.rsplit('\\0', 1)\n"),
        ("split", "def f(out):\n    return out.partition(b'\\0')\n"),
        ("status", 'def f():\n    return ["git", "status", "-s"]\n'),
        ("ls", 'def f():\n    return ["git", "ls-tree", "-r", "HEAD"]\n'),
        ("diff", 'def f():\n    return ["git", "diff", "--stat", "HEAD"]\n'),
        ("diff", 'def f():\n    return ["git", "log", "--raw"]\n'),
        ("diff", 'def f(extra):\n    return ["git", "show", *extra, "--name-status"]\n'),
        ("split", 'def f(out):\n    return out.rsplit(" -> ")\n'),
    ],
    ids=[
        "list-argv-status",
        "positional-constant-status",
        "name-only-alone",
        "name-status-alone",
        "numstat-alone",
        "ls-files-tuple",
        "nul-split",
        "arrow-membership",
        "arrow-split",
        "porcelain-prefix-slice",
        "check-ignore",
        "status-short",
        "status-z",
        "bare-diff-tree",
        "bare-diff-index",
        "nul-rsplit",
        "bytes-nul-partition",
        "status-s",
        "ls-tree",
        "diff-stat",
        "log-raw",
        "show-name-status-after-splat",
        "arrow-rsplit",
    ],
)
def test_planted_hit_is_reported(tmp_path: Path, kind: str, body: str) -> None:
    assert kind in _kinds(_plant(tmp_path, body))


def test_planted_slice_outside_a_porcelain_function_is_not_reported(tmp_path: Path) -> None:
    assert _plant(tmp_path, "def f(items):\n    return items[3:]\n") == []


def test_worktree_list_porcelain_is_not_reported(tmp_path: Path) -> None:
    assert _plant(tmp_path, 'def f():\n    return ["git", "worktree", "list", "--porcelain"]\n') == []


@pytest.mark.parametrize(
    "body",
    [
        '_STATUS = "status"\n\n\ndef f(root):\n    return _git(root, _STATUS, "--porcelain")\n',
        'STATUS = "status"\nPORCELAIN = "--porcelain"\nrun(["git", STATUS, PORCELAIN])\n',
    ],
    ids=["positional-constant", "constant-list-argv"],
)
def test_module_constant_indirection_does_not_hide_a_hit(tmp_path: Path, body: str) -> None:
    assert _kinds(_plant(tmp_path, body)) == {"status"}


@pytest.mark.parametrize(
    "source",
    [
        'run(["git", "check-ignore", "-q", "path"])',
        'run(["git", "diff-index", "--quiet", "HEAD"])',
        'run(["git", "rev-parse", "HEAD"])',
        'run(["git", "diff", "--quiet"])',
        "status_entries(root, untracked='all')",
        'text.split(",")',
        'print("status")',
        'run(["gh", "pr", "diff", "--name-only"])',
    ],
)
def test_clean_code_is_not_flagged(tmp_path: Path, source: str) -> None:
    assert _plant(tmp_path, source + "\n") == []


def test_classify_argv_ignores_unresolved_tokens() -> None:
    assert classify_argv([None, "status", None]) is None
    assert classify_argv(["status", None, "--porcelain"]) == "status"


def test_owner_package_is_skipped(tmp_path: Path) -> None:
    stray = tmp_path / "stray.py"
    stray.write_text('run(["git", "ls-files"])\n', encoding="utf-8")
    assert _kinds(census([stray])) == {"ls"}
    owner_files = sorted(OWNER_ROOT.glob("*.py"))
    assert owner_files
    assert census(owner_files) == []
