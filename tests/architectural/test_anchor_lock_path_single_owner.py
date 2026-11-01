"""One owner for the anchor-keyed lock path (#6727, DIRECTIVE_044).

``kernel.locks.anchored_lock_path`` is the single implementation of "resolve the anchor,
case-normalise it, digest it, and place the result under
``<git-common-dir>/spec-kitty-locks/``". Before #6727 the rule was written out three
times, and the charter synthesis copy was taken from the event-log copy on purpose
(#6453), so the next family would have made a fourth.

This gate closes that defect class: a module under ``src/`` that is **not**
``src/kernel/locks.py`` may not both name the lock directory and build a *lock file name
from a case-normalised path* (the anchor rule's identity step is
``os.path.normcase(<resolved path>)``). Files that place a fixed-name or caller-keyed lock
under the lock directory are allowed and are asserted here as the positive control: the
Mission status lock is keyed by a directory name, the project-level one by a fixed
sentinel, the verdict-save queue by a constant, the design authoring lock by a digest of a
Mission slug (an identifier, not a path), and the lock shim only re-exports the name.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

#: The one module allowed to derive an anchor digest for a lock file name.
OWNER_RELPATH = "src/kernel/locks.py"

#: The directory name, as the modules that name it spell it.
LOCK_DIRECTORY_NAME = "spec-kitty-locks"

#: Files that legitimately place a lock under the lock directory *without* a digest.
FIXED_NAME_PLACEMENTS = (
    "src/specify_cli/core/checkout_file_lock.py",  # re-exports LOCK_DIRECTORY
    "src/specify_cli/status/locking.py",  # Mission-keyed and fixed-sentinel status locks
    "src/specify_cli/review/verdict_commit_queue.py",  # one fixed file name
    "src/specify_cli/design/receipts.py",  # digest of a Mission slug, not of a path
)


def _relpath(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _names_lock_directory(tree: ast.AST) -> int | None:
    """Line of the first reference to ``LOCK_DIRECTORY`` (name, import, or literal), if any."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "LOCK_DIRECTORY":
            return node.lineno
        if isinstance(node, ast.Attribute) and node.attr == "LOCK_DIRECTORY":
            return node.lineno
        if isinstance(node, ast.ImportFrom) and any(alias.name == "LOCK_DIRECTORY" for alias in node.names):
            return node.lineno
        if isinstance(node, ast.Constant) and node.value in {LOCK_DIRECTORY_NAME, "LOCK_DIRECTORY"}:
            return node.lineno
    return None


def _case_normalises_a_path(tree: ast.AST) -> int | None:
    """Line of the first ``normcase`` call, if any -- the anchor rule's identity step."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "normcase":
                return node.lineno
            if isinstance(func, ast.Name) and func.id == "normcase":
                return node.lineno
    return None


def _derives_a_digest(tree: ast.AST) -> int | None:
    """Line of the first digest derivation, if any."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "kernel.content_digest":
            return node.lineno
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "hashlib":
            return node.lineno
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "hashlib":
                return node.lineno
            if isinstance(func, ast.Name) and "digest" in func.id.lower():
                return node.lineno
    return None


def find_anchor_digest_copies(relpath: str, source: str) -> list[int]:
    """Lines of *source* that name the lock directory and derive a lock name from a path.

    Empty unless all three halves of the anchor rule are present -- the lock directory, a
    digest, and the case-normalisation of the path being digested -- so a fixed-name lock
    file and a digest of a non-path identifier are not findings.
    """
    tree = ast.parse(source, filename=relpath)
    lock_line = _names_lock_directory(tree)
    digest_line = _derives_a_digest(tree)
    normcase_line = _case_normalises_a_path(tree)
    if lock_line is None or digest_line is None or normcase_line is None:
        return []
    return sorted({lock_line, digest_line, normcase_line})


def _scanned_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_the_scan_reaches_the_whole_src_tree() -> None:
    """A detector that scans nothing must go red, not green."""
    scanned = [_relpath(path) for path in _scanned_files()]

    assert len(scanned) > 100, f"only {len(scanned)} modules scanned under {SRC_ROOT}"
    assert OWNER_RELPATH in scanned
    for relpath in FIXED_NAME_PLACEMENTS:
        assert relpath in scanned, f"{relpath} is no longer scanned -- update FIXED_NAME_PLACEMENTS with its new home"


def test_only_kernel_locks_may_derive_an_anchor_digest_for_a_lock_path() -> None:
    """FR-006: a second copy of the rule fails here instead of passing review by eye."""
    copies = {
        relpath: lines
        for path in _scanned_files()
        if (relpath := _relpath(path)) != OWNER_RELPATH
        for lines in [find_anchor_digest_copies(relpath, path.read_text(encoding="utf-8"))]
        if lines
    }

    assert not copies, "anchor-keyed lock paths must come from kernel.locks.anchored_lock_path; found a hand-rolled copy at " + ", ".join(
        f"{relpath}:{','.join(str(line) for line in lines)}" for relpath, lines in sorted(copies.items())
    )


def test_fixed_name_lock_placements_still_name_the_lock_directory() -> None:
    """Positive control: the allowed files really are in the gate's sample.

    Without this, a rename of ``LOCK_DIRECTORY`` (or a move of these modules) would make
    the gate above pass because it no longer recognises anything.
    """
    for relpath in FIXED_NAME_PLACEMENTS:
        source = (REPO_ROOT / relpath).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relpath)
        assert _names_lock_directory(tree) is not None, f"{relpath} no longer names LOCK_DIRECTORY -- update the gate"
        assert find_anchor_digest_copies(relpath, source) == [], f"{relpath} now builds a lock name from a case-normalised path -- use the helper"


def test_a_hand_rolled_copy_is_flagged() -> None:
    """Negative control: the pre-#6727 shape is a finding."""
    copy = (
        "import hashlib\n"
        "import os\n"
        "from kernel.locks import LOCK_DIRECTORY\n"
        "\n"
        "def lock_path(anchor):\n"
        "    digest = hashlib.sha256(os.path.normcase(str(anchor)).encode('utf-8')).hexdigest()[:32]\n"
        "    return anchor / LOCK_DIRECTORY / f'{digest}.lock'\n"
    )

    found = find_anchor_digest_copies("src/example/copy.py", copy)

    assert found, "the pre-#6727 shape must be a finding"
    assert 6 in found  # the line that digests the normcased path


def test_the_digest_rule_without_the_lock_directory_is_not_flagged() -> None:
    """Negative control: a digest for a non-lock purpose (the write-service protocol id)."""
    unrelated = "import hashlib\n\n\ndef repository_id(path):\n    return hashlib.sha256(str(path).encode('utf-8')).hexdigest()\n"

    assert find_anchor_digest_copies("src/example/unrelated.py", unrelated) == []


def test_the_lock_directory_without_a_digest_is_not_flagged() -> None:
    """Negative control: a fixed file name under the lock directory."""
    fixed_name = "from kernel.locks import LOCK_DIRECTORY\n\n\ndef lock_path(root):\n    return root / LOCK_DIRECTORY / '__checkout__.status.lock'\n"

    assert find_anchor_digest_copies("src/example/fixed.py", fixed_name) == []


def test_the_owner_itself_is_the_only_module_with_the_rule() -> None:
    """The owner keeps the rule (so deleting it can never make the gate vacuously green)."""
    source = (REPO_ROOT / OWNER_RELPATH).read_text(encoding="utf-8")

    assert find_anchor_digest_copies(OWNER_RELPATH, source), "kernel/locks.py no longer contains the anchor digest rule"
