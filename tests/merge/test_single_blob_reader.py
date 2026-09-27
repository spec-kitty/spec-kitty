"""Single-raw-git-blob-reader guard (SC-002).

The merge domain used to carry two byte-identical raw ``git show
<ref>:<path>`` blob readers -- ``merge/bookkeeping_projection.py::
_git_show_blob_bytes`` and ``merge/git_probes.py::_read_git_blob_bytes``.
These were collapsed to the single canonical ``git_probes`` copy. This
module makes "exactly one raw blob reader in ``src/specify_cli/merge/``" a
checked, non-vacuous invariant rather than a one-off cleanup: a bare AST scan
(no subprocess, no git) finds every function shaped like a raw
``["git", "show", f"{ref}:{path}"]`` reader and asserts the found set is
exactly the canonical one.

Three test groups, each carrying its own honest markers:

* the scanner itself, run over the real tree -- pure AST, ``fast``/``unit``;
* self-mutation (a planted second reader must be caught) plus negative
  controls (``git show --stat`` / a non-``show`` git call must NOT be
  caught) -- same ``fast``/``unit`` scanner, planted ``tmp_path`` sources;
* a behavior check of the canonical reader's two outcomes against a real
  temp git repo -- ``integration``/``git_repo`` (NOT ``fast``/``unit``: it
  shells out to real ``git``).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from specify_cli.merge.git_probes import _read_git_blob_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
MERGE_ROOT = REPO_ROOT / "src" / "specify_cli" / "merge"

# The single, canonical raw blob reader this gate protects (SC-002).
_CANONICAL_READER = ("specify_cli/merge/git_probes.py", "_read_git_blob_bytes")


def _is_ref_path_join(node: ast.expr) -> bool:
    """True if *node* is an f-string shaped exactly like ``f"{ref}:{path}"``.

    Requires an adjacent triple ``FormattedValue, Constant(':'), FormattedValue``
    inside the ``JoinedStr`` -- i.e. two interpolations sandwiching a bare ``:``
    literal. Deliberately tighter than "any colon anywhere in the f-string" so a
    differently-shaped colon-bearing f-string (e.g. a single interpolation with a
    literal ``":2:"`` prefix, as used by the merge-conflict stage-index reader)
    does NOT match.
    """
    if not isinstance(node, ast.JoinedStr):
        return False
    values = node.values
    for i in range(len(values) - 2):
        a, b, c = values[i], values[i + 1], values[i + 2]
        if isinstance(a, ast.FormattedValue) and isinstance(b, ast.Constant) and b.value == ":" and isinstance(c, ast.FormattedValue):
            return True
    return False


def _is_git_show_blob_literal(node: ast.expr) -> bool:
    """True if *node* is a ``["git", "show", f"{ref}:{path}"]``-shaped literal.

    Requires the first two elements to be the literals ``"git"``/``"show"``
    AND at least one remaining element to be a ref:path join (see
    :func:`_is_ref_path_join`) -- deliberately excludes ``git show --stat``
    (no colon-joining f-string element) and any non-``show`` git subcommand
    (second element mismatch).
    """
    if not isinstance(node, ast.List | ast.Tuple):
        return False
    elts = node.elts
    if len(elts) < 3:
        return False
    first, second = elts[0], elts[1]
    if not (isinstance(first, ast.Constant) and first.value == "git"):
        return False
    if not (isinstance(second, ast.Constant) and second.value == "show"):
        return False
    return any(_is_ref_path_join(elt) for elt in elts[2:])


def _is_subprocess_git_show_call(node: ast.AST) -> bool:
    """True if *node* is a ``subprocess.run``/``subprocess.check_output`` git-show-blob call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name not in {"run", "check_output"}:
        return False
    if not node.args:
        return False
    return _is_git_show_blob_literal(node.args[0])


def _qualnames_with_bodies(
    node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    prefix: str = "",
) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Every function/method in *node*, paired with its dotted qualname."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for child in node.body:
        if isinstance(child, ast.ClassDef):
            found.extend(_qualnames_with_bodies(child, prefix=f"{prefix}{child.name}."))
        elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            qualname = f"{prefix}{child.name}"
            found.append((qualname, child))
            found.extend(_qualnames_with_bodies(child, prefix=f"{qualname}."))
    return found


def find_git_show_blob_readers(root: Path) -> set[tuple[str, str]]:
    """Scan every ``*.py`` file directly under *root* for a raw git-show blob reader.

    Returns ``{(rel_path, qualname)}`` for every function whose body contains a
    call matching :func:`_is_subprocess_git_show_call` (SC-002). Pure AST
    walk -- never executes ``git`` or the scanned code.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(root.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            raise ValueError(f"{path}: cannot parse as Python source -- fix the file or exclude it explicitly") from exc
        rel = f"specify_cli/merge/{path.name}"
        for qualname, func in _qualnames_with_bodies(tree):
            if any(_is_subprocess_git_show_call(call) for call in ast.walk(func)):
                found.add((rel, qualname))
    return found


# ---------------------------------------------------------------------------
# Scanner over the real tree
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.unit
def test_exactly_one_git_show_blob_reader_in_merge_domain() -> None:
    found = find_git_show_blob_readers(MERGE_ROOT)
    assert found == {_CANONICAL_READER}, (
        "Exactly one raw git-show blob reader is allowed in "
        "src/specify_cli/merge/ (SC-002) -- import "
        "specify_cli.merge.git_probes._read_git_blob_bytes instead of adding "
        f"a new one. Found: {sorted(found)}"
    )


# ---------------------------------------------------------------------------
# Non-vacuity: self-mutation + negative controls
# ---------------------------------------------------------------------------

_PLANTED_SECOND_READER = """
import subprocess
from pathlib import Path


def _second_blob_reader(repo: Path, ref: str, rel_path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout
"""

_PLANTED_NEGATIVE_CONTROLS = '''
import subprocess


def _show_stat_is_not_a_blob_read(repo, ref):
    """``git show --stat`` has no colon-joining f-string element -- not a match."""
    subprocess.run(["git", "show", "--stat", ref], cwd=repo, check=False)


def _status_is_not_show(repo):
    """A non-``show`` git subcommand -- not a match."""
    subprocess.run(["git", "status"], cwd=repo, check=False)


def _stage_index_read_is_not_a_ref_path_join(repo, file_path):
    """A single interpolation with a literal ':2:' prefix -- not a ref:path join."""
    subprocess.run(["git", "show", f":2:{file_path}"], cwd=repo, capture_output=True, check=False)
'''


@pytest.mark.fast
@pytest.mark.unit
def test_scanner_detects_a_planted_second_reader(tmp_path: Path) -> None:
    (tmp_path / "planted.py").write_text(_PLANTED_SECOND_READER, encoding="utf-8")
    found = find_git_show_blob_readers(tmp_path)
    assert found == {("specify_cli/merge/planted.py", "_second_blob_reader")}


@pytest.mark.fast
@pytest.mark.unit
def test_scanner_negative_controls_git_show_stat_and_non_show(tmp_path: Path) -> None:
    (tmp_path / "planted_negative.py").write_text(_PLANTED_NEGATIVE_CONTROLS, encoding="utf-8")
    assert find_git_show_blob_readers(tmp_path) == set()


@pytest.mark.fast
@pytest.mark.unit
def test_scanner_fails_loud_on_an_unparsable_file(tmp_path: Path) -> None:
    """An unparsable ``*.py`` file must fail the scan, not be silently skipped
    (a silent skip could hide a real second reader living in a broken file)."""
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot parse as Python source"):
        find_git_show_blob_readers(tmp_path)


# ---------------------------------------------------------------------------
# Behavior of the canonical reader (real temp git repo -- NOT fast/unit)
# ---------------------------------------------------------------------------


def _init_committed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.co"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Blob Reader Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / "a.txt").write_bytes(b"hello\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)


@pytest.mark.integration
@pytest.mark.git_repo
def test_read_git_blob_bytes_committed_file_returns_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_committed_repo(repo)

    assert _read_git_blob_bytes(repo, "HEAD", "a.txt") == b"hello\n"


@pytest.mark.integration
@pytest.mark.git_repo
def test_read_git_blob_bytes_missing_path_returns_none(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_committed_repo(repo)

    assert _read_git_blob_bytes(repo, "HEAD", "missing.txt") is None
