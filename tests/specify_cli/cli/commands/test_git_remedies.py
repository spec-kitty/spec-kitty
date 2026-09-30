"""No module under ``src/specify_cli`` prints a *destructive* git command
line inline: every such recipe is rendered from
``cli.commands._git_remedies`` (#3931, following the #5078 commit-recipe
precedent).

Background (#3931 F-30, P0 after a real data-loss repro in PR #4881): the
move-task lane gate printed ``git restore --source <planning-tip> --staged
--worktree -- kitty-specs/`` as an indented copy/paste command line. Following
it restored the *whole* ``kitty-specs/`` tree from the planning tip, deleting
lane-local files the planning branch did not carry. The fix routes that
remedy through :func:`_git_remedies.restore_recipe` (file-scoped, merge-base
source). This gate stops any equivalent destructive command line from being
re-introduced inline.

Scope (mirrors #5078): the scan flags a destructive git *invocation*
(``git [-C <path>] {restore | reset --hard | rm -r | checkout -- | clean}``)
that appears **at the start of a command line** -- the copy/paste-recipe shape
the defect took, and the shape an operator actually runs. It deliberately does
NOT flag the same verb mentioned mid-sentence in prose or in an
error/status message reporting an already-run command (e.g. "a ``reset
--hard`` was interrupted", "recovery ``git reset --hard HEAD`` failed"): that
text is explanation, not a recipe to run -- the same "only strings printed as
instructions to run; leave prose and code that runs git" boundary #5078 drew.

Subprocess argv lists (``["git", "restore", ...]`` -- code that actually runs
git) and docstrings (prose) are excluded, as in #5078.

**The allowlist is empty and must stay empty** (operator ruling, Stijn,
2026-09-30: allowlist ratchets are expensive CI debt). Every printed
destructive recipe goes through ``_git_remedies``; the one module that legally
holds the rendered text -- ``_git_remedies.py`` itself -- is excluded from the
scan because it is that canonical home. A genuinely un-renderable site is
escalated, not parked here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from specify_cli.cli.commands._git_remedies import GIT_UNDO_ALTERNATIVES, restore_recipe

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SRC_ROOT = Path(__file__).resolve().parents[4] / "src" / "specify_cli"
# The canonical home of destructive-recipe text; it is excluded from the scan
# precisely because it is the single module allowed to build that text.
_RENDERER_MODULE = "cli/commands/_git_remedies.py"

# A destructive git subcommand invoked directly off the ``git`` executable
# (optionally via ``git -C <path>``). ``checkout -- `` targets the pathspec
# form that discards working-tree changes, not branch-switching ``checkout``.
_DESTRUCTIVE_VERB = r"(restore\b|reset\s+--hard\b|rm\s+-r\b|checkout\s+--(\s|$)|clean\b)"
_INVOCATION = re.compile(r"^git(\s+-C\s+\S*)?\s+" + _DESTRUCTIVE_VERB)
# Leading run to strip off a line before testing for a command: whitespace,
# rich-markup tags (``[dim]``/``[red]``...), and a single opening quote/backtick.
_LINE_LEAD = re.compile(r"^(\s|\[[^\]]*\]|[`'\"])+")


def _line_starts_a_destructive_command(line: str) -> bool:
    return bool(_INVOCATION.match(_LINE_LEAD.sub("", line)))


def text_prints_destructive_advice(text: str) -> bool:
    """True if any line of *text* is a destructive git command line."""
    return any(_line_starts_a_destructive_command(line) for line in text.split("\n"))


class _DocstringCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.docstring_ids: set[int] = set()

    def _mark(self, node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            self.docstring_ids.add(id(node.body[0].value))

    def visit_Module(self, node: ast.Module) -> None:
        self._mark(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._mark(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._mark(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark(node)
        self.generic_visit(node)


class _ParentTracker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.parent: dict[int, ast.AST] = {}
        self._stack: list[ast.AST] = []

    def generic_visit(self, node: ast.AST) -> None:
        if self._stack:
            self.parent[id(node)] = self._stack[-1]
        self._stack.append(node)
        super().generic_visit(node)
        self._stack.pop()


def _is_subprocess_argv_element(node: ast.AST, parent_map: dict[int, ast.AST]) -> bool:
    """True if *node* is an element of a ``["git", ...]`` list/tuple literal --
    real subprocess argv, code that runs git, out of scope (as in #5078)."""
    parent = parent_map.get(id(node))
    if not isinstance(parent, ast.List | ast.Tuple):
        return False
    elts = parent.elts
    return bool(elts) and isinstance(elts[0], ast.Constant) and elts[0].value == "git"


def _joinedstr_text(node: ast.JoinedStr) -> str:
    """Reconstruct an f-string's literal text, substituting a non-space
    placeholder for each interpolation so a leading ``git ...`` keeps its
    line-start position."""
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("\x00")
    return "".join(parts)


def find_destructive_advice_hits(*, source: str, filename: str = "<test>") -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every non-docstring, non-argv string
    constant / f-string in *source* that prints a destructive git command line.
    """
    tree = ast.parse(source, filename=filename)
    docstrings = _DocstringCollector()
    docstrings.visit(tree)
    parents = _ParentTracker()
    parents.visit(tree)

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings.docstring_ids:
                continue
            if isinstance(parents.parent.get(id(node)), ast.JoinedStr):
                continue
            if _is_subprocess_argv_element(node, parents.parent):
                continue
            if text_prints_destructive_advice(node.value):
                hits.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            text = _joinedstr_text(node)
            if text_prints_destructive_advice(text):
                hits.append((node.lineno, text))
    return hits


def _scan_src_specify_cli() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_SRC_ROOT).as_posix()
        if rel == _RENDERER_MODULE:
            continue
        source = path.read_text(encoding="utf-8")
        found.extend((rel, text) for _lineno, text in find_destructive_advice_hits(source=source, filename=str(path)))
    return found


def test_no_inline_destructive_git_advice_in_src() -> None:
    """Empty-allowlist gate: no destructive git command line is printed inline.

    Any hit is a regression -- render it from ``_git_remedies`` (or, if a site
    genuinely cannot be rendered, escalate to the operator; do NOT add an
    allowlist here).
    """
    hits = _scan_src_specify_cli()
    assert not hits, (
        "Inline destructive git command line(s) found -- route through "
        "specify_cli.cli.commands._git_remedies instead of printing them "
        f"inline: {[(path, text[:80]) for path, text in hits]}"
    )


# --- scanner controls ------------------------------------------------------


def test_scanner_flags_indented_restore_recipe() -> None:
    fixture = 'guidance.append("  git restore --source main --staged --worktree -- kitty-specs/")\n'
    hits = find_destructive_advice_hits(source=fixture)
    assert len(hits) == 1
    assert "git restore" in hits[0][1]


def test_scanner_flags_reset_hard_recipe_line() -> None:
    fixture = 'console.print("  git reset --hard HEAD~1  (discard)")\n'
    assert len(find_destructive_advice_hits(source=fixture)) == 1


def test_scanner_flags_fstring_recipe_with_interpolated_source() -> None:
    fixture = 'base = "abc"\nline = f"  git restore --source {base} --staged --worktree -- a b"\n'
    hits = find_destructive_advice_hits(source=fixture)
    assert len(hits) == 1
    assert "git restore" in hits[0][1]


def test_scanner_flags_rich_markup_prefixed_recipe() -> None:
    fixture = 'console.print("[dim]git clean -fdx[/dim]")\n'
    assert len(find_destructive_advice_hits(source=fixture)) == 1


def test_scanner_ignores_midsentence_prose_mention() -> None:
    """A verb referenced mid-sentence is explanation, not a recipe."""
    fixture = 'msg = "A git index.lock shows a reset --hard was interrupted mid-transaction."\n'
    assert find_destructive_advice_hits(source=fixture) == []


def test_scanner_ignores_backticked_report_of_an_already_run_command() -> None:
    fixture = 'msg = "behind-own-HEAD recovery `git reset --hard HEAD` failed in the checkout"\n'
    assert find_destructive_advice_hits(source=fixture) == []


def test_scanner_ignores_docstrings() -> None:
    fixture = 'def f():\n    """Consider git reset --hard HEAD~1 to discard."""\n    return 1\n'
    assert find_destructive_advice_hits(source=fixture) == []


def test_scanner_ignores_subprocess_argv() -> None:
    fixture = 'import subprocess\nsubprocess.run(["git", "restore", "--source", "main", "--", "x"])\n'
    assert find_destructive_advice_hits(source=fixture) == []


def test_scanner_does_not_flag_branch_switching_checkout() -> None:
    """``git checkout -b`` / ``git checkout <branch>`` are not destructive."""
    assert find_destructive_advice_hits(source='x = "  git checkout -b feature"\n') == []
    assert find_destructive_advice_hits(source='x = "  git checkout main"\n') == []


# --- restore_recipe renderer ----------------------------------------------


def test_restore_recipe_scopes_to_named_files_from_source() -> None:
    recipe = restore_recipe(["kitty-specs/m/tasks/WP02.md", "kitty-specs/m/issue-matrix.json"], source="deadbeef")
    assert recipe == "git restore --source deadbeef --staged --worktree -- kitty-specs/m/tasks/WP02.md kitty-specs/m/issue-matrix.json"


def test_restore_recipe_refuses_directory_scope() -> None:
    """The exact F-30 defect: a directory-scoped restore must be impossible to render."""
    with pytest.raises(ValueError, match="directory-scoped"):
        restore_recipe(["kitty-specs/"], source="deadbeef")


def test_restore_recipe_refuses_empty_paths() -> None:
    with pytest.raises(ValueError, match="at least one non-empty file path"):
        restore_recipe([], source="deadbeef")
    with pytest.raises(ValueError, match="at least one non-empty file path"):
        restore_recipe(["   "], source="deadbeef")


def test_restore_recipe_never_renders_directory_needle() -> None:
    recipe = restore_recipe(["kitty-specs/m/plan.md"], source="base")
    assert "-- kitty-specs/ " not in recipe + " "
    assert not recipe.rstrip().endswith("/")


def test_undo_alternatives_are_the_expected_git_commands() -> None:
    joined = "\n".join(GIT_UNDO_ALTERNATIVES)
    assert "git reset --soft HEAD~1" in joined
    assert "git reset --hard HEAD~1" in joined
    assert "git revert <commit>" in joined
    assert "git reflog" in joined
