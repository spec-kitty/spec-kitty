"""T011-T014 (#5078 WP03): every printed ``git commit`` recipe in
``src/specify_cli`` uses ``spec-kitty safe-commit`` (the shared
``_commit_recipes.safe_commit_recipe`` renderer), never raw ``git add`` /
``git commit`` instructions.

Operator decision (#5078): safe-commit is consumer doctrine. This module is
an AST scan over ALL of ``src/specify_cli`` that finds every string constant
or f-string containing the substring ``"git commit"`` (excluding docstrings,
which are explanatory prose, and subprocess argv list elements, which are
code that actually runs git -- out of scope per the operator decision: "Only
change strings printed as instructions for an agent or user. Leave code that
actually runs git.").

Every hit must be either:

* the rendered safe-commit recipe text (``safe_commit_recipe`` renders
  ``spec-kitty safe-commit ...``, which does not contain the substring
  ``"git commit"`` at all, so a converted print site drops out of the scan
  entirely), or
* named in ``_ALLOWED_GIT_COMMIT_HITS`` below with a one-line rationale --
  reserved for text that is NOT a copy/paste commit recipe: a log/error
  message reporting an ALREADY-ATTEMPTED commit's outcome, an internal
  prefix-matching constant, banner/prose text, or a bootstrap recipe for a
  scenario safe-commit structurally cannot serve (no destination ref yet, or
  an empty/allow-empty commit with no file paths).

Base count (pinned at the WP03 planning base, verified 2026-09-28 against
research.md R-8): scanning the pre-fix tree found 24 unique "git commit"
string hits across src/specify_cli. 11 of those were genuine printed
recipes (workflow_executor.py x3, implement.py x1, tasks_parsing_validation.py
x5, charter/_synthesis.py x1, mission_setup_plan.py x1) and were converted to
``safe_commit_recipe`` calls by this WP; the remaining 13 are the allowlist
below, unchanged by this WP's fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from specify_cli.cli.commands._commit_recipes import PROTECTED_PRIMARY_HINT, safe_commit_recipe

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SRC_ROOT = Path(__file__).resolve().parents[4] / "src" / "specify_cli"
_NEEDLE = "git commit"

# (relative-path-from-src/specify_cli, lineno): one-line rationale.
# Every entry here is text this WP judged NOT to be a printed copy/paste
# commit recipe (see module docstring). Reviewers: a new entry needs its own
# rationale, not a rubber stamp of this list -- and a converted recipe site
# is REMOVED from this list, never added to it (the rendered
# ``spec-kitty safe-commit ...`` text never contains "git commit").
_ALLOWED_GIT_COMMIT_HITS: dict[tuple[str, int], str] = {
    (
        "cli/commands/agent/workflow_cores.py",
        116,
    ): "Banner prose telling the agent to ignore OTHER agents' commits -- not a recipe to run.",
    (
        "cli/commands/implement.py",
        664,
    ): (
        "_DEMOTION_REFUSAL_MSG: prose describing a manual meta.json-flatten "
        "conflict repair (`git add` + `git commit`, no concrete files/message/"
        "branch spelled out) -- not a copy/paste recipe, and the scenario "
        "(reconciling a demoted coordination_branch) isn't one safe-commit's "
        "single-target model covers."
    ),
    (
        "consolidation/ordering.py",
        482,
    ): "Error-reason string reporting an ALREADY-ATTEMPTED subprocess git commit's failure, not a recipe.",
    (
        "coordination/write_seam.py",
        189,
    ): "_EMPTY_CHANGESET_PREFIX: an internal prefix-matching constant shared with commit_router, not printed as a recipe.",
    (
        "core/mission_creation.py",
        869,
    ): (
        "Bootstrap recipe for an unborn HEAD (`git commit --allow-empty -m "
        "'Initial commit'`): no destination ref exists yet and there are no "
        "file paths to pass, so safe-commit's file-set/branch model cannot "
        "express it -- structurally out of scope, not an oversight."
    ),
    (
        "git/commit_helpers.py",
        1169,
    ): "logger.warning template reporting an ALREADY-RUN `git commit`'s stderr, not a recipe.",
    (
        "git/commit_helpers.py",
        1183,
    ): "logger.warning template reporting an ALREADY-RUN `git commit`'s warnings, not a recipe.",
    (
        "git/commit_helpers.py",
        1209,
    ): "RuntimeError detail reporting an ALREADY-ATTEMPTED `git commit`'s failure, not a recipe.",
    (
        "migration/runner.py",
        373,
    ): "logger.warning reporting an ALREADY-ATTEMPTED migration git commit's failure (attempt 1), not a recipe.",
    (
        "migration/runner.py",
        375,
    ): "logger.warning reporting an ALREADY-ATTEMPTED migration git commit's exception (attempt 1), not a recipe.",
    (
        "migration/runner.py",
        389,
    ): "logger.error reporting an ALREADY-ATTEMPTED migration git commit's failure (attempt 2), not a recipe.",
    (
        "migration/runner.py",
        391,
    ): "logger.error reporting an ALREADY-ATTEMPTED migration git commit's exception (attempt 2), not a recipe.",
    (
        "migration/runner.py",
        579,
    ): "_fail() detail string reporting an ALREADY-ATTEMPTED migration git commit's failure, not a recipe.",
}


class _DocstringCollector(ast.NodeVisitor):
    """Collects the ``id()`` of every module/function/class docstring Constant."""

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
    """Maps ``id(child) -> parent`` for every AST node, single pass."""

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
    """True if *node* sits in a list/tuple literal whose first element is the
    string literal ``"git"`` -- the real subprocess argv shape
    (``subprocess.run(["git", "commit", ...])``), code that actually runs
    git and is out of scope per the operator decision.

    Narrowed (WP03 review cycle 1, #3) from "any element of any list/tuple
    literal passed to any Call": that broader shape also exempted a git-
    commit string joined into a printed GUIDANCE list, e.g.
    ``"\\n".join(["Commit first:", "  git commit -m ..."])`` -- code that
    prints a copy/paste recipe, squarely in scope. The ``elts[0] == "git"``
    check is real argv's own signature and does not match that shape (its
    first element is prose, not ``"git"``).
    """
    parent = parent_map.get(id(node))
    if not isinstance(parent, ast.List | ast.Tuple):
        return False
    elts = parent.elts
    return bool(elts) and isinstance(elts[0], ast.Constant) and elts[0].value == "git"


def find_git_commit_recipe_hits(*, source: str, filename: str = "<test>") -> list[tuple[int, str]]:
    """Return ``(lineno, snippet)`` for every non-docstring, non-argv string
    constant or f-string in *source* containing the substring ``"git commit"``.
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
                # Counted once via the enclosing JoinedStr below.
                continue
            if _NEEDLE not in node.value:
                continue
            if _is_subprocess_argv_element(node, parents.parent):
                continue
            hits.append((node.lineno, node.value[:80]))
        elif isinstance(node, ast.JoinedStr):
            text = "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
            if _NEEDLE in text:
                hits.append((node.lineno, text[:80]))
    return hits


def _scan_src_specify_cli() -> dict[tuple[str, int], str]:
    """Return ``{(relative_path, lineno): snippet}`` for every hit under src/specify_cli."""
    found: dict[tuple[str, int], str] = {}
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_SRC_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        for lineno, snippet in find_git_commit_recipe_hits(source=source, filename=str(path)):
            found[(rel, lineno)] = snippet
    return found


def test_no_unallowed_git_commit_recipe_strings_in_src() -> None:
    """FR-018/#5078: every printed ``git commit`` recipe is safe-commit-shaped.

    Any hit not named in ``_ALLOWED_GIT_COMMIT_HITS`` (with a rationale) is a
    regression -- either a new raw ``git commit`` recipe was printed, or a
    known one was reverted from ``safe_commit_recipe``.
    """
    found = _scan_src_specify_cli()
    unexplained = {key: snippet for key, snippet in found.items() if key not in _ALLOWED_GIT_COMMIT_HITS}
    assert not unexplained, (
        "Printed git-commit recipe(s) found outside the reviewed allowlist "
        "-- convert to _commit_recipes.safe_commit_recipe() or add a "
        f"rationale to _ALLOWED_GIT_COMMIT_HITS: {unexplained}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    """The allowlist only ever shrinks (a fixed line moving is a rewrite, not
    growth) -- a stale entry naming a hit that no longer exists is dead
    bookkeeping that would silently mask a future regression at that spot.
    """
    found = _scan_src_specify_cli()
    stale = sorted(key for key in _ALLOWED_GIT_COMMIT_HITS if key not in found)
    assert not stale, f"Allowlist entries with no matching source hit (stale, remove them): {stale}"


def test_allowlist_pinned_to_thirteen_residual_hits() -> None:
    """Ratchet: 24 hits existed at the WP03 planning base; 11 were printed
    recipes (converted to safe_commit_recipe by this WP, so they drop out of
    the scan); 13 residual non-recipe hits remain, all allowlisted. This
    count may only go DOWN (further conversions/cleanups), never up.
    """
    assert len(_ALLOWED_GIT_COMMIT_HITS) == 13


def test_scanner_positive_control_flags_a_recipe_fixture() -> None:
    """Sanity check on the scanner itself: a fixture string shaped exactly
    like the recipes this WP converts is still flagged when NOT allowlisted.
    """
    fixture_source = "RECIPE = 'git commit -m \"feat(WP01): x\"'\n"
    hits = find_git_commit_recipe_hits(source=fixture_source)
    assert hits == [(1, 'git commit -m "feat(WP01): x"')]


def test_scanner_ignores_module_docstrings() -> None:
    fixture_source = '"""Module doc mentioning git commit in prose."""\n'
    assert find_git_commit_recipe_hits(source=fixture_source) == []


def test_scanner_ignores_function_docstrings() -> None:
    fixture_source = 'def f():\n    """Runs git commit under the hood."""\n    return 1\n'
    assert find_git_commit_recipe_hits(source=fixture_source) == []


def test_scanner_ignores_subprocess_argv_list() -> None:
    fixture_source = 'import subprocess\nsubprocess.run(["git", "commit -m", "x"])\n'
    assert find_git_commit_recipe_hits(source=fixture_source) == []


def test_scanner_flags_joined_guidance_list() -> None:
    """WP03 review (cycle 1, #3) positive control: a printed recipe joined
    from a guidance list -- ``"\\n".join([..., "  git commit -m ..."])`` -- is
    NOT real subprocess argv (its first element is prose, not ``"git"``) and
    MUST still be flagged. Pre-fix, ``_is_subprocess_argv_element`` exempted
    ANY string inside ANY list/tuple passed to ANY call, so this join call
    site was silently invisible to the scan.
    """
    fixture_source = "lines = '\\n'.join(['Commit first:', '  git commit -m \"feat(WP01): x\"'])\n"
    hits = find_git_commit_recipe_hits(source=fixture_source)
    assert len(hits) == 1
    assert "git commit" in hits[0][1]


def test_scanner_flags_fstring_recipe() -> None:
    fixture_source = 'wp_id = "WP01"\nline = f\'git commit -m "feat({wp_id}): x"\'\n'
    hits = find_git_commit_recipe_hits(source=fixture_source)
    assert len(hits) == 1
    assert "git commit" in hits[0][1]


# ---------------------------------------------------------------------------
# T012/T013: the shared safe_commit_recipe() renderer.
# ---------------------------------------------------------------------------


def test_safe_commit_recipe_renders_files_message_and_branch() -> None:
    recipe = safe_commit_recipe(["foo.py", "bar.py"], "feat(WP01): x", "kitty/mission-demo-lane-a")
    assert recipe == 'spec-kitty safe-commit foo.py bar.py -m "feat(WP01): x" --to-branch kitty/mission-demo-lane-a'


def test_safe_commit_recipe_omits_to_branch_when_none() -> None:
    recipe = safe_commit_recipe(["foo.py"], "chore: x", None)
    assert recipe == 'spec-kitty safe-commit foo.py -m "chore: x"'
    assert "--to-branch" not in recipe


def test_safe_commit_recipe_never_contains_raw_git_commit() -> None:
    """The rendered recipe text itself must never re-trip the scan above."""
    recipe = safe_commit_recipe(["foo.py"], "feat(WP01): x", "main")
    assert _NEEDLE not in recipe


def test_safe_commit_recipe_protected_primary_hint_appended() -> None:
    recipe = safe_commit_recipe(["kitty-specs/demo"], "chore: planning artifacts for demo", "main", protected_primary=True)
    assert PROTECTED_PRIMARY_HINT in recipe
    assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in recipe


def test_safe_commit_recipe_omits_hint_by_default() -> None:
    recipe = safe_commit_recipe(["foo.py"], "chore: x", "main")
    assert PROTECTED_PRIMARY_HINT not in recipe


def test_protected_primary_hint_never_suggests_env_bypass() -> None:
    """Charter 'Agent Push Authorization': never point at the env-var escape hatch."""
    assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in PROTECTED_PRIMARY_HINT
    assert "protected_branches" in PROTECTED_PRIMARY_HINT.replace(".", "")


# ---------------------------------------------------------------------------
# WP03 review-cycle-2 #1: pin ``_print_planning_artifact_commit_instructions``'s
# printed recipe -- a mutation dropping ``planning_branch`` from the
# ``safe_commit_recipe(...)`` call at implement.py ~L432 survived every other
# test in the suite (reviewer-renata, review-cycle-2.md). Drive the
# auto-commit-disabled path directly and assert on the printed recipe text.
# ---------------------------------------------------------------------------


def test_planning_artifact_recipe_pins_to_branch_on_the_planning_branch(capsys: pytest.CaptureFixture[str]) -> None:
    import typer

    from specify_cli.cli.commands.implement import (
        _print_planning_artifact_commit_instructions,
    )

    planning_branch = "kitty/mission-demo-mission-abcd1234"
    lane_branch = "kitty/mission-demo-mission-lane-a"

    with pytest.raises(typer.Exit):
        _print_planning_artifact_commit_instructions(
            current_branch=planning_branch,
            planning_branch=planning_branch,
            auto_commit=False,
            feature_dir=Path("kitty-specs/demo-mission"),
            mission_slug="demo-mission",
        )

    out = capsys.readouterr().out
    assert "spec-kitty safe-commit" in out
    assert "kitty-specs/demo-mission" in out
    assert f"--to-branch {planning_branch}" in out
    assert lane_branch not in out
