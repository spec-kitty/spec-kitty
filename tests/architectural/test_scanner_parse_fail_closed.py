"""Architectural scanners must fail closed on source they cannot parse (#5139).

A scanner that swallows a ``SyntaxError`` (``except SyntaxError: continue`` /
``return []`` / ``pass``) silently drops the file from its scan, so the gate it
feeds passes over code it never read. #4362 closed that in the meta-read census
scanners; this gate closes the class: no ``except`` clause under
``tests/`` may catch a parse failure without re-raising, outside
the rationale-bearing :data:`_ALLOWED_SWALLOWS` ledger. Scanners route through
:mod:`tests.architectural._ast_scan` instead.

The ledger is checked for exact equality against the live scan: a new swallow
fails, and so does a stale row (its handler was removed but the row was not).
"""

from __future__ import annotations

import ast
import builtins
from collections import Counter
from pathlib import Path

import pytest

from tests.architectural._ast_scan import UnparseableSourceError, parse_file, qualname_by_line, read_and_parse

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TESTS_ROOT = _REPO_ROOT / "tests"

#: The live tree has well over this many scanner/test modules; a scan that
#: visits fewer is broken (non-vacuity floor).
_MIN_SCANNED_FILES = 2500

#: ``(repo-relative path, enclosing qualname) -> (handler count, rationale)``.
#: Only handlers that deliberately tolerate an unparseable input belong here --
#: never a scanner walking ``src/`` or ``tests/`` for a census.
_ALLOWED_SWALLOWS: dict[tuple[str, str], tuple[int, str]] = {}


#: SyntaxError and its subclasses.
_SYNTAX_FAMILY = frozenset({"SyntaxError", "IndentationError", "TabError"})
#: Handlers this broad also catch a SyntaxError.
_BROAD = frozenset({"Exception", "BaseException"})
#: Builtin exception classes -- any other name caught around a parse (an alias
#: such as ``E = SyntaxError``, or ``UnparseableSourceError``) is presumed to
#: cover the parse failure.
_BUILTIN_EXCEPTIONS = frozenset(name for name, obj in vars(builtins).items() if isinstance(obj, type) and issubclass(obj, BaseException))
#: Scanner helpers that parse source (any receiver).
_PARSE_HELPERS = frozenset({"literal_eval", "parse_file", "parse_source", "read_and_parse", "parse_module"})
#: Generic names that only mean "parse Python" as a bare call (``from ast import
#: parse``, builtin ``compile``) or on the ``ast`` module -- ``re.compile`` /
#: ``json.parse``-style receivers are not source parsing.
_AST_PARSE_NAMES = frozenset({"parse", "compile"})
#: Exceptions a failing ``_ast_scan`` helper raises (``UnparseableSourceError``
#: is an ``AssertionError``), so catching them around a parse is a swallow too.
_HELPER_FAILURES = frozenset({"AssertionError"})


def _exception_names(node: ast.expr) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Tuple):
        return {name for element in node.elts for name in _exception_names(element)}
    return set()


def _is_parse_call(node: ast.AST, local_parsers: frozenset[str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _PARSE_HELPERS or func.id in _AST_PARSE_NAMES or func.id in local_parsers
    if isinstance(func, ast.Attribute):
        if func.attr in _PARSE_HELPERS:
            return True
        return func.attr in _AST_PARSE_NAMES and isinstance(func.value, ast.Name) and func.value.id == "ast"
    return False


def _body_parses(body: list[ast.stmt], local_parsers: frozenset[str]) -> bool:
    return any(_is_parse_call(node, local_parsers) for stmt in body for node in ast.walk(stmt))


def _local_parsers(tree: ast.Module) -> frozenset[str]:
    """Names of functions in this module that parse source themselves (one hop of indirection)."""
    return frozenset(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _body_parses(node.body, frozenset()))


def _covers_syntax_error(names: set[str], *, parses: bool) -> bool:
    if names & _SYNTAX_FAMILY:
        return True
    return parses and bool(names & (_BROAD | _HELPER_FAILURES) or names - _BUILTIN_EXCEPTIONS)


def _walk_same_scope(stmts: list[ast.stmt]) -> list[ast.AST]:
    """Every node under ``stmts`` except those inside nested function/class bodies."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        out.append(node)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))
    return out


def _always_reraises(handler: ast.ExceptHandler) -> bool:
    """True only when the handler ends in an unconditional ``raise`` and never escapes early."""
    if not handler.body or not isinstance(handler.body[-1], ast.Raise):
        return False
    return not _escapes(handler.body)


def _escapes(stmts: list[ast.stmt]) -> bool:
    return any(isinstance(node, (ast.Continue, ast.Break, ast.Return)) for node in _walk_same_scope(stmts))


def _swallowing_handler_lines(tree: ast.Module) -> list[int]:
    """Line numbers of every construct that can swallow a parse failure."""
    local_parsers = _local_parsers(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, ast.TryStar)):
            parses = _body_parses(node.body, local_parsers)
            for handler in node.handlers:
                names = _exception_names(handler.type) if handler.type is not None else set()
                covers = parses if handler.type is None else _covers_syntax_error(names, parses=parses)
                if covers and not _always_reraises(handler):
                    lines.append(handler.lineno)
            if parses and node.finalbody and _escapes(node.finalbody):  # ``finally: return`` eats the error
                lines.append(node.finalbody[0].lineno)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            parses = _body_parses(node.body, local_parsers)
            for item in node.items:
                call = item.context_expr
                if not (isinstance(call, ast.Call) and _suppress_call(call)):
                    continue
                names = {name for arg in call.args for name in _exception_names(arg)}
                if any(isinstance(arg, ast.Starred) for arg in call.args):
                    names.add("*")  # ``suppress(*ERRS)``: unknown exception set
                if _covers_syntax_error(names, parses=parses):
                    lines.append(node.lineno)
    return lines


def _suppress_call(call: ast.Call) -> bool:
    func = call.func
    return (isinstance(func, ast.Name) and func.id == "suppress") or (isinstance(func, ast.Attribute) and func.attr == "suppress")


def scan_syntax_error_swallows(root: Path, repo_root: Path) -> tuple[Counter[tuple[str, str]], int]:
    """Return ``(swallowing handlers keyed by (path, qualname), files scanned)``."""
    found: Counter[tuple[str, str]] = Counter()
    scanned = 0
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(repo_root).as_posix()
        tree = parse_file(path, display=rel)
        scanned += 1
        quals = qualname_by_line(tree)
        for lineno in _swallowing_handler_lines(tree):
            found[(rel, quals.get(lineno, "<module>"))] += 1
    return found, scanned


def test_no_scanner_swallows_syntax_errors() -> None:
    live, scanned = scan_syntax_error_swallows(_TESTS_ROOT, _REPO_ROOT)

    assert scanned >= _MIN_SCANNED_FILES, f"scanned only {scanned} files under tests/"
    unaccounted = {key: n for key, n in live.items() if n > _ALLOWED_SWALLOWS.get(key, (0, ""))[0]}
    assert not unaccounted, (
        "handler(s) catch SyntaxError without re-raising, so the scanner drops unparseable files "
        "from its census:\n"
        + "\n".join(f"    {path}::{qual}  x{n}" for (path, qual), n in sorted(unaccounted.items()))
        + "\n\nParse through tests.architectural._ast_scan (read_and_parse / parse_file), or -- if "
        "the input is deliberately allowed to be unparseable -- add a rationale row to _ALLOWED_SWALLOWS."
    )
    stale = {key: count for key, (count, _why) in _ALLOWED_SWALLOWS.items() if live.get(key, 0) != count}
    assert not stale, f"stale _ALLOWED_SWALLOWS row(s) (count no longer matches the live scan): {sorted(stale)}"


def test_every_allowed_swallow_carries_a_rationale() -> None:
    blank = [key for key, (_count, why) in _ALLOWED_SWALLOWS.items() if not why.strip()]
    assert not blank, f"_ALLOWED_SWALLOWS rows without a rationale: {blank}"


_SWALLOWING = {
    "continue": "for p in ps:\n    try:\n        f(p)\n    except SyntaxError:\n        continue\n",
    "return-empty": "def g(s):\n    try:\n        return f(s)\n    except SyntaxError:\n        return []\n",
    "pass": "try:\n    f()\nexcept SyntaxError:\n    pass\n",
    "tuple": "try:\n    f()\nexcept (OSError, SyntaxError):\n    x = None\n",
    "attribute": "import builtins\ntry:\n    f()\nexcept builtins.SyntaxError:\n    pass\n",
    # Evasions found by the #5139 research squad (debugger-debbie):
    "subclass": "try:\n    f()\nexcept IndentationError:\n    pass\n",
    "broad-exception": "import ast\nfor p in ps:\n    try:\n        ast.parse(p)\n    except Exception:\n        continue\n",
    "base-exception": "import ast\ntry:\n    ast.parse(s)\nexcept BaseException:\n    pass\n",
    "bare": "import ast\ntry:\n    ast.parse(s)\nexcept:\n    pass\n",
    "alias": "import ast\nE = SyntaxError\ntry:\n    ast.parse(s)\nexcept E:\n    pass\n",
    "alias-tuple": "import ast\nERRS = (OSError, SyntaxError)\ntry:\n    ast.parse(s)\nexcept ERRS:\n    pass\n",
    "helper-error": "try:\n    parse_file(p)\nexcept UnparseableSourceError:\n    pass\n",
    "conditional-raise": "for p in ps:\n    try:\n        f(p)\n    except SyntaxError:\n        if strict:\n            raise\n        continue\n",
    "nested-def-raise": "try:\n    f()\nexcept SyntaxError:\n    def never():\n        raise\n",
    "suppress": "import ast, contextlib\nwith contextlib.suppress(SyntaxError):\n    ast.parse(s)\n",
    "suppress-broad": "import ast\nfrom contextlib import suppress\nwith suppress(Exception):\n    ast.parse(s)\n",
    # Pre-PR squad evasions:
    "assertion-error": "for p in ps:\n    try:\n        parse_file(p)\n    except AssertionError:\n        continue\n",
    "suppress-starred": "import ast, contextlib\nwith contextlib.suppress(*ERRS):\n    ast.parse(s)\n",
    "finally-return": "import ast\ndef g(s):\n    try:\n        return ast.parse(s)\n    finally:\n        return None\n",
    "helper-indirection": (
        "import ast\ndef load(p):\n    return ast.parse(p.read_text())\nfor p in ps:\n    try:\n        load(p)\n    except Exception:\n        continue\n"
    ),
}


@pytest.mark.parametrize("source", list(_SWALLOWING.values()), ids=list(_SWALLOWING))
def test_detector_flags_a_planted_swallow(tmp_path: Path, source: str) -> None:
    (tmp_path / "planted.py").write_text(source, encoding="utf-8")

    found, scanned = scan_syntax_error_swallows(tmp_path, tmp_path)

    assert scanned == 1
    assert sum(found.values()) == 1


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    f()\nexcept SyntaxError as exc:\n    raise AssertionError('x') from exc\n",
        "try:\n    f()\nexcept SyntaxError:\n    log()\n    raise\n",
        "try:\n    f()\nexcept ValueError:\n    pass\n",
        "try:\n    f()\nexcept Exception:\n    pass\n",
        "import ast\ntry:\n    ast.parse(s)\nexcept ValueError:\n    pass\n",
        "import contextlib\nwith contextlib.suppress(KeyError):\n    d.pop(k)\n",
        "import re\ntry:\n    re.compile(x)\nexcept Exception:\n    pass\n",
        "import json\ntry:\n    json.loads(x)\nexcept Exception:\n    pass\n",
    ],
    ids=[
        "translate",
        "reraise",
        "other-exception",
        "broad-without-parse",
        "unrelated-builtin",
        "unrelated-suppress",
        "regex-compile",
        "json-loads",
    ],
)
def test_detector_ignores_a_raising_or_unrelated_handler(tmp_path: Path, source: str) -> None:
    (tmp_path / "ok.py").write_text(source, encoding="utf-8")

    found, _scanned = scan_syntax_error_swallows(tmp_path, tmp_path)

    assert not found


@pytest.mark.parametrize(
    ("payload", "match"),
    [(b"def broken(:\n", r"cannot parse pkg/broken\.py"), (b"\xff\xfe x = 1\n", r"cannot read pkg/broken\.py")],
    ids=["syntax-error", "undecodable"],
)
def test_helpers_fail_closed_naming_the_file(tmp_path: Path, payload: bytes, match: str) -> None:
    broken = tmp_path / "pkg" / "broken.py"
    broken.parent.mkdir()
    broken.write_bytes(payload)

    with pytest.raises(UnparseableSourceError, match=match):
        read_and_parse(broken, display="pkg/broken.py")
    with pytest.raises(AssertionError, match=match):
        parse_file(broken, display="pkg/broken.py")


def test_helpers_fail_closed_on_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UnparseableSourceError, match=r"cannot read gone\.py"):
        parse_file(tmp_path / "gone.py", display="gone.py")


def test_helpers_return_source_and_tree(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")

    source, tree = read_and_parse(good)

    assert source == "x = 1\n"
    assert isinstance(tree.body[0], ast.Assign)
