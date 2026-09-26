"""Guardrail: stale *path-literal* references to a moved charter module (#3818).

The M2b split (mission ``charter-activation-split-01M16ZSE``, #3807) relocated
the activation-side ``charter`` modules from ``src/charter/<mod>.py`` into
``src/charter/activation/<mod>.py``. Import statements are re-pointed and
guarded by the sibling C-004 boundary gate
(``test_charter_offering_does_not_import_activation.py``). It is also distinct
from ``test_charter_path_literal_authority.py`` (which owns *which* current
charter path literals are canonical/allowlisted -- the SSOT authority); this
module instead closes
the class of straggler an import-rewrite pass does not touch at all: a *string
literal* that spells out the old dotted path or the old file path, never
executed as an import and therefore invisible to any import-based scanner.

The #3807 landing's own census (see
``kitty-specs/charter-activation-split-01M16ZSE/contracts/activation-topology-map.md``,
"Census refresh" addendum) found exactly two live shapes of this straggler and
fixed every occurrence before merge:

1. ``unittest.mock.patch("charter.<old>...")`` mock-target strings — a typo'd
   or unmigrated patch target does not raise ``ImportError`` like a real
   import would; it silently patches nothing, and the test that "passes"
   is exercising the REAL (unpatched) code path.
2. Path-literal entries inside an arch-gate allowlist tuple/list/set (e.g. an
   ``_ALLOWED_*_FILES`` census) naming ``src/charter/<old>.py`` — the gate
   that owns the allowlist keeps matching the file by its old path and
   silently stops covering it once the file moves.

Plus one doc-facing shape named in the WP body: a *relative* markdown link
(``[..](../../src/charter/<old>.py)``) — a broken cross-reference in shipped
documentation.

Scope decisions (read before "why doesn't this catch X")
----------------------------------------------------------
This gate is deliberately narrower than "every string in the tree that
contains the substring 'charter.<old>'". A naive substring/line scan over
docstrings, comments, and assertion messages was tried first during this
gate's authoring and produced dozens of hits that are prose — narrative text
*describing* the move (rename-mapping examples such as
``"``src/charter/mission_type_profiles.py`` -> ``charter.activation.mission_type_profiles``"``
in ``test_no_dead_modules.py``, or an RST cross-reference in a module
docstring) rather than a functioning path reference. None of that prose was
part of the #3807 census and fixing it is not this gate's job (nor
achievable without a real content-editorial pass). So this gate only reaches:

* **Python**: the argument of a call whose callee resolves to a bare
  ``patch`` name or ``<anything>.patch`` attribute (``patch(...)``,
  ``mock.patch(...)``, ``unittest.mock.patch(...)``) — matched on the dotted
  ``charter.<moved>`` form; and any string element of a ``list``/``tuple``/
  ``set`` *display* (an allowlist-census shape) — matched on the
  ``src/charter/<moved>.py`` file-path form. Docstrings, comments, and plain
  assertion-message prose are never inspected.
* **Markdown**: the target of a markdown link (``](...)``) whose target is
  NOT an absolute URL (no ``http://``/``https://`` scheme) — matched on the
  ``src/charter/<moved>.py`` file-path form. Inline code spans, fenced code
  samples, and prose are never inspected.

Both patterns require the "moved" token to sit at a name/path boundary (a
negative lookbehind excluding a preceding identifier or path character), so
``charter.context`` never false-matches on ``charter.context_state`` (they
are distinct moved modules; text ending in ``...text_state`` never trips the
shorter alternative because the walk backtracks to the longer one — see
:func:`test_word_boundary_context_does_not_match_context_state`), and a
same-named *different* package is never flagged: ``specify_cli.cli.commands.
charter.context`` names a real, unrelated ``context.py`` living under
``src/specify_cli/cli/commands/charter/`` (the CLI's own charter command
group), not the top-level ``charter`` package this gate polices — the
lookbehind sees the ``.`` before ``charter`` (from ``commands.charter``) and
declines to start a match there.

Historical archives (``kitty-specs/**``, ``docs/adr/**``, ``docs/plans/**``)
are immutable snapshots and are excluded — see
:data:`ARCHIVE_PATH_PREFIXES`.

Performance: files are pre-filtered on the substring ``"charter"`` before
paying for an ``ast.parse`` (any match requires that literal substring
somewhere in the file), which keeps this comfortably under the suite's 5s
NFR-002 budget on the real tree (~1.8s locally against ~1.3k charter-
mentioning files out of ~4.3k total under ``src/`` + ``tests/``).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_source, read_source

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_TESTS_ROOT = _REPO_ROOT / "tests"
_DOCS_ROOT = _REPO_ROOT / "docs"
_ACTIVATION_ROOT = _SRC_ROOT / "charter" / "activation"

#: Immutable historical snapshots -- never scanned. Prefixes are relative to
#: the repo root and posix-separated (matches ``relative_to(...).as_posix()``).
ARCHIVE_PATH_PREFIXES: tuple[str, ...] = ("kitty-specs/", "docs/adr/", "docs/plans/")

_URL_SCHEME_RE = re.compile(r"^https?://")


@dataclass(frozen=True)
class StaleReference:
    """One flagged occurrence: *relpath* line *lineno* names old *token*."""

    relpath: str
    lineno: int
    token: str


# ---------------------------------------------------------------------------
# The moved-module census (derived, not hand-maintained).
# ---------------------------------------------------------------------------


def moved_module_names(activation_root: Path = _ACTIVATION_ROOT) -> frozenset[str]:
    """Names physically relocated under ``src/charter/activation/``.

    Top-level ``.py`` modules (minus ``__init__``) plus subpackage directory
    names (a directory counts only if it is a real Python package, i.e. it
    has an ``__init__.py`` -- a stray non-package directory, or a bare data
    file such as ``ERROR_CODES.md``, contributes nothing). Absent-directory
    is not an error: it returns the empty set rather than raising, matching
    the non-vacuity idiom this repo's other pre-move-authored gates use
    (see ``test_charter_offering_does_not_import_activation.py``).
    """
    if not activation_root.exists():
        return frozenset()
    names: set[str] = set()
    for entry in sorted(activation_root.iterdir()):
        if entry.is_dir():
            if (entry / "__init__.py").exists():
                names.add(entry.name)
        elif entry.suffix == ".py" and entry.stem != "__init__":
            names.add(entry.stem)
    return frozenset(names)


def _alternation(moved: frozenset[str]) -> str:
    """Longest-first alternation so backtracking still finds the correct
    (longer) alternative when a shorter one is a prefix of it -- belt and
    braces alongside the trailing ``\\b`` that already forces this (see the
    module docstring's word-boundary note).
    """
    return "|".join(re.escape(name) for name in sorted(moved, key=len, reverse=True))


def dotted_pattern(moved: frozenset[str]) -> re.Pattern[str]:
    """``charter.<moved>`` as a fresh dotted-path start, not nested deeper.

    The negative lookbehind excludes both plain identifier continuation
    (``foocharter.x``) and, critically, a preceding dotted segment
    (``commands.charter.x``) -- the exact shape that lets
    ``specify_cli.cli.commands.charter.context`` (a real, different,
    same-named module) pass through unflagged.
    """
    return re.compile(rf"(?<![\w.])charter\.({_alternation(moved)})\b")


def path_pattern(moved: frozenset[str]) -> re.Pattern[str]:
    """``src/charter/<moved>.py`` as a path, tolerant of a ``/`` or ``.``
    immediately before ``src`` (so ``../../src/charter/<moved>.py`` inside a
    relative markdown link still matches) but not a preceding identifier
    character (so ``othersrc/charter/<moved>.py`` does not).
    """
    return re.compile(rf"(?<!\w)src/charter/({_alternation(moved)})\.py\b")


# ---------------------------------------------------------------------------
# Python-side scan: patch() mock targets + allowlist-tuple path literals.
# ---------------------------------------------------------------------------


def _is_patch_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "patch"
    if isinstance(func, ast.Attribute):
        return func.attr == "patch"
    return False


def _patch_target_string(node: ast.Call) -> str | None:
    """The literal string ``patch``/``mock.patch`` is called with, whether
    passed positionally or as the ``target=`` keyword.
    """
    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return None
    for kw in node.keywords:
        if kw.arg == "target" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _string_constant(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_python_source(
    source: str,
    *,
    relpath: str,
    dotted_re: re.Pattern[str],
    path_re: re.Pattern[str],
) -> list[StaleReference]:
    """Every stale reference in one Python source string.

    Two independent shapes, both AST-driven (never a raw substring scan over
    the whole file, which would also light up docstrings/comments): a
    ``patch(...)`` call's target string (dotted form), and a string element
    of any ``list``/``tuple``/``set`` display (path form -- the allowlist
    census shape). A syntactically invalid source fails closed
    (:class:`~tests.architectural._ast_scan.UnparseableSourceError`, #5139):
    a file the gate cannot parse is a file it never checked.
    """
    tree = parse_source(source, display=relpath)
    found: list[StaleReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_patch_call(node):
            target = _patch_target_string(node)
            if target is not None:
                match = dotted_re.search(target)
                if match:
                    found.append(StaleReference(relpath, node.lineno, match.group(0)))
        elif isinstance(node, ast.List | ast.Tuple | ast.Set):
            for elt in node.elts:
                value = _string_constant(elt)
                if value is None:
                    continue
                match = path_re.search(value)
                if match:
                    found.append(StaleReference(relpath, elt.lineno, match.group(0)))
    return found


def _iter_python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts]


def _relpath(path: Path, *, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _is_archived(relpath: str) -> bool:
    return any(relpath.startswith(prefix) for prefix in ARCHIVE_PATH_PREFIXES)


def collect_python_stale_references(
    roots: tuple[Path, ...],
    *,
    moved: frozenset[str],
    repo_root: Path = _REPO_ROOT,
) -> list[StaleReference]:
    """Scan every ``*.py`` file under *roots* (excluding archives)."""
    dotted_re = dotted_pattern(moved)
    path_re = path_pattern(moved)
    found: list[StaleReference] = []
    for root in roots:
        for path in _iter_python_files(root):
            relpath = _relpath(path, repo_root=repo_root)
            if _is_archived(relpath):
                continue
            text = read_source(path, display=relpath)
            # Cheap pre-filter: any match requires this literal substring
            # somewhere in the file, so files without it never pay for an
            # ast.parse (NFR-002 -- keeps this gate comfortably sub-5s).
            if "charter" not in text:
                continue
            found.extend(scan_python_source(text, relpath=relpath, dotted_re=dotted_re, path_re=path_re))
    return found


# ---------------------------------------------------------------------------
# Markdown-side scan: relative-link targets only.
# ---------------------------------------------------------------------------

# ``](target)`` where target does not start with a URL scheme. Non-greedy
# and character-class-excluded on ``)`` so the match stops at the link's own
# closing paren rather than swallowing trailing prose on the same line.
_MD_LINK_RE = re.compile(r"\]\(([^)]*)\)")


def scan_markdown_source(
    source: str,
    *,
    relpath: str,
    path_re: re.Pattern[str],
) -> list[StaleReference]:
    """Every stale *relative* markdown link target in one markdown source.

    Deliberately narrower than "the substring appears anywhere in the file"
    -- see the module docstring's Scope decisions section. An absolute
    ``http(s)://`` link target is never flagged even if it happens to embed
    an old path (e.g. a GitHub blob URL); that is a different, rarer shape
    this gate does not claim to cover.
    """
    found: list[StaleReference] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for link_match in _MD_LINK_RE.finditer(line):
            target = link_match.group(1)
            if _URL_SCHEME_RE.match(target):
                continue
            path_match = path_re.search(target)
            if path_match:
                found.append(StaleReference(relpath, lineno, path_match.group(0)))
    return found


def collect_markdown_stale_references(
    root: Path,
    *,
    moved: frozenset[str],
    repo_root: Path = _REPO_ROOT,
) -> list[StaleReference]:
    """Scan every ``*.md`` file under *root* (excluding archives)."""
    if not root.exists():
        return []
    path_re = path_pattern(moved)
    found: list[StaleReference] = []
    for path in sorted(root.rglob("*.md")):
        relpath = _relpath(path, repo_root=repo_root)
        if _is_archived(relpath):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "charter" not in text:
            continue
        found.extend(scan_markdown_source(text, relpath=relpath, path_re=path_re))
    return found


def collect_all_stale_references(
    *,
    moved: frozenset[str],
    src_root: Path = _SRC_ROOT,
    tests_root: Path = _TESTS_ROOT,
    docs_root: Path = _DOCS_ROOT,
    repo_root: Path = _REPO_ROOT,
) -> list[StaleReference]:
    """The full gate: Python (``src/`` + ``tests/``) + Markdown (``docs/``)."""
    return [
        *collect_python_stale_references((src_root, tests_root), moved=moved, repo_root=repo_root),
        *collect_markdown_stale_references(docs_root, moved=moved, repo_root=repo_root),
    ]


def _format_findings(findings: list[StaleReference]) -> str:
    return "\n".join(f"  {ref.relpath}:{ref.lineno} names stale token {ref.token!r}" for ref in findings)


# ---------------------------------------------------------------------------
# The real gate.
# ---------------------------------------------------------------------------


def test_no_stale_charter_path_literals_on_real_tree() -> None:
    """SC-001: zero stale-path-literal stragglers on the merged tree.

    The #3807 landing's own census (module docstring) confirmed zero
    deep-path/mock-target/doc-link stragglers to a moved module before
    merge; this is the standing regression guard for that invariant.
    """
    moved = moved_module_names()
    assert moved, (
        "moved_module_names() returned empty against the real "
        f"{_ACTIVATION_ROOT} -- either the M2b split was reverted or this "
        "gate's discovery logic is broken; either way it would be silently "
        "vacuous below"
    )
    findings = collect_all_stale_references(moved=moved)
    assert not findings, (
        "stale charter path literal(s) found -- these name a moved module "
        "by its pre-M2b top-level path (should be "
        "charter.activation.<module> / src/charter/activation/<module>.py):\n"
        f"{_format_findings(findings)}"
    )


def test_moved_module_names_derives_a_non_trivial_real_set() -> None:
    """Non-vacuity for the census itself: the real activation/ tree yields a
    plausible module set, not an accidental empty/degenerate one.
    """
    moved = moved_module_names()
    assert len(moved) >= 10, moved
    assert "__init__" not in moved
    # A subpackage (has its own __init__.py) is included by name...
    assert "corpus" in moved
    # ...but a bare non-Python asset sibling (ERROR_CODES.md) contributes
    # nothing: it is neither a .py module nor a package directory.
    assert "ERROR_CODES" not in moved
    assert "ERROR_CODES.md" not in moved


# ---------------------------------------------------------------------------
# Non-vacuity: synthetic trees proving each shape IS caught (T002).
# ---------------------------------------------------------------------------

_MOVED = frozenset({"context", "context_state", "_drg_helpers"})


def test_flags_stale_patch_target_dotted_form(tmp_path: Path) -> None:
    """The exact shape #3807 named: ``patch("charter.<old>...")``."""
    module = tmp_path / "test_example.py"
    module.write_text(
        "from unittest.mock import patch\n\ndef test_thing():\n    with patch('charter._drg_helpers.load_validated_graph'):\n        pass\n",
        encoding="utf-8",
    )

    findings = collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path)

    assert findings == [StaleReference("test_example.py", 4, "charter._drg_helpers")]


def test_flags_stale_mock_dot_patch_and_keyword_target_form(tmp_path: Path) -> None:
    """Both ``mock.patch(...)`` (attribute form) and the ``target=`` keyword."""
    module = tmp_path / "test_example.py"
    module.write_text(
        "import unittest.mock\n\ndef test_thing():\n    unittest.mock.patch(target='charter.context.build_charter_context')\n",
        encoding="utf-8",
    )

    findings = collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path)

    assert findings == [StaleReference("test_example.py", 4, "charter.context")]


def test_flags_stale_allowlist_tuple_path_entry(tmp_path: Path) -> None:
    """The arch-gate path-literal allowlist shape: a plain census tuple."""
    module = tmp_path / "src" / "specify_cli" / "some_gate.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "_ALLOWED_FILES = (\n    'src/charter/context_state.py',\n    'src/specify_cli/unrelated.py',\n)\n",
        encoding="utf-8",
    )

    findings = collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path)

    assert findings == [StaleReference("src/specify_cli/some_gate.py", 2, "src/charter/context_state.py")]


def test_flags_stale_markdown_relative_link(tmp_path: Path) -> None:
    """The exact shape #3818 names: ``[..](../../src/charter/<old>.py)``."""
    doc = tmp_path / "guide.md"
    doc.write_text(
        "See the [context resolver](../../src/charter/context.py) for detail.\n",
        encoding="utf-8",
    )

    findings = collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path)

    assert findings == [StaleReference("guide.md", 1, "src/charter/context.py")]


# ---------------------------------------------------------------------------
# Non-vacuity: shapes that must NOT be flagged (false-positive guards).
# ---------------------------------------------------------------------------


def test_does_not_flag_the_correct_activation_form(tmp_path: Path) -> None:
    """The re-pointed, correct form must never itself be flagged."""
    module = tmp_path / "test_example.py"
    module.write_text(
        "from unittest.mock import patch\n\n"
        "def test_thing():\n"
        "    with patch('charter.activation.context.build_charter_context'):\n"
        "        pass\n"
        "\n"
        "_ALLOWED_FILES = ('src/charter/activation/context.py',)\n",
        encoding="utf-8",
    )

    assert collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path) == []


def test_word_boundary_context_does_not_match_context_state(tmp_path: Path) -> None:
    """``context`` (a moved module) never false-matches inside
    ``context_state`` (a distinct moved module) -- both python and markdown
    sides.
    """
    module = tmp_path / "test_example.py"
    module.write_text(
        "from unittest.mock import patch\n\ndef test_thing():\n    with patch('charter.context_state._MIN_EFFECTIVE_DEPTH'):\n        pass\n",
        encoding="utf-8",
    )
    py_findings = collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path)
    assert py_findings == [StaleReference("test_example.py", 4, "charter.context_state")]
    assert py_findings[0].token != "charter.context"

    doc = tmp_path / "guide.md"
    doc.write_text(
        "[state](../../src/charter/context_state.py)\n",
        encoding="utf-8",
    )
    md_findings = collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path)
    assert md_findings == [StaleReference("guide.md", 1, "src/charter/context_state.py")]
    assert md_findings[0].token != "src/charter/context.py"


def test_does_not_flag_same_name_different_package(tmp_path: Path) -> None:
    """``specify_cli.cli.commands.charter.context`` is a real, different
    module (the CLI's own charter command group ships its own
    ``context.py``) -- not the top-level ``charter`` package this gate
    polices. Must never be flagged (WP01 explicit non-goal).
    """
    module = tmp_path / "test_example.py"
    module.write_text(
        "from unittest.mock import patch\n\ndef test_thing():\n    with patch('specify_cli.cli.commands.charter.context.build_charter_context'):\n        pass\n",
        encoding="utf-8",
    )

    assert collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path) == []


def test_does_not_flag_non_patch_calls_or_plain_strings(tmp_path: Path) -> None:
    """Only ``patch(...)``-shaped calls are inspected on the dotted side --
    a bare module-level string constant (a docstring, a log message, an
    unrelated helper call) is not a mock target and is out of scope.
    """
    module = tmp_path / "test_example.py"
    module.write_text(
        '"""Docstring mentioning charter.context_state, not an import."""\n'
        "MESSAGE = 'see charter.context for detail'\n"
        "\n"
        "def log(msg: str) -> None:\n"
        "    pass\n"
        "\n"
        "log('charter.context failed to load')\n",
        encoding="utf-8",
    )

    assert collect_python_stale_references((tmp_path,), moved=_MOVED, repo_root=tmp_path) == []


def test_does_not_flag_absolute_url_markdown_links(tmp_path: Path) -> None:
    """A relative link is in scope; an absolute ``https://`` link (e.g. a
    GitHub blob URL) is a different, rarer shape this gate does not claim
    -- must never be flagged.
    """
    doc = tmp_path / "guide.md"
    doc.write_text(
        "See [source](https://github.com/example/repo/blob/main/src/charter/context.py).\n",
        encoding="utf-8",
    )

    assert collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path) == []


def test_does_not_flag_bare_inline_code_span_outside_a_link(tmp_path: Path) -> None:
    """A backtick-quoted path mentioned in running prose (not inside
    ``](...)`` link syntax) is not a link target -- must never be flagged.
    """
    doc = tmp_path / "guide.md"
    doc.write_text(
        "The resolver lives at `src/charter/context.py` before the move.\n",
        encoding="utf-8",
    )

    assert collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path) == []


# ---------------------------------------------------------------------------
# Archive exclusion (T003): historical snapshots are never scanned.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("archive_prefix", ARCHIVE_PATH_PREFIXES)
def test_does_not_flag_archived_historical_snapshots(tmp_path: Path, archive_prefix: str) -> None:
    """A stale reference inside ``kitty-specs/**``, ``docs/adr/**``, or
    ``docs/plans/**`` is a frozen historical record, not live drift -- the
    gate must pass it through unflagged even though the identical content
    at a live path would be flagged (see the paired positive cases above).
    """
    archived_dir = tmp_path / archive_prefix
    archived_dir.mkdir(parents=True)
    (archived_dir / "notes.md").write_text(
        "[old link](../../src/charter/context.py)\n",
        encoding="utf-8",
    )

    assert collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path) == []


def test_archive_exclusion_is_not_vacuous(tmp_path: Path) -> None:
    """Companion to the archive-exclusion cases: the same content at a
    live (non-archived) path in the SAME synthetic tree IS flagged, proving
    the exclusion is a real prefix check and not an accidental blanket
    pass.
    """
    for prefix in ARCHIVE_PATH_PREFIXES:
        archived_dir = tmp_path / prefix
        archived_dir.mkdir(parents=True)
        (archived_dir / "notes.md").write_text(
            "[old link](../../src/charter/context.py)\n",
            encoding="utf-8",
        )
    live_dir = tmp_path / "docs" / "architecture"
    live_dir.mkdir(parents=True)
    (live_dir / "notes.md").write_text(
        "[old link](../../src/charter/context.py)\n",
        encoding="utf-8",
    )

    findings = collect_markdown_stale_references(tmp_path, moved=_MOVED, repo_root=tmp_path)

    assert findings == [StaleReference("docs/architecture/notes.md", 1, "src/charter/context.py")]
