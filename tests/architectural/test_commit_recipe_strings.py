"""Every printed ``git commit`` recipe in
``src/specify_cli`` uses ``spec-kitty safe-commit`` (the shared
``_commit_recipes.safe_commit_recipe`` renderer), never raw ``git add`` /
``git commit`` instructions.

Operator decision (#5078): safe-commit is consumer doctrine. This module is
an AST scan over ALL of ``src/specify_cli`` that finds every string constant
or f-string with the SHAPE of a copy-paste ``git commit`` recipe (see
``is_recipe_shaped``; excluding docstrings,
which are explanatory prose, and subprocess argv list elements, which are
code that actually runs git -- out of scope per the operator decision: "Only
change strings printed as instructions for an agent or user. Leave code that
actually runs git.").

Every hit must be either:

* the rendered safe-commit recipe text (``safe_commit_recipe`` renders
  ``spec-kitty safe-commit ...``, which does not contain the substring
  ``git commit`` at all, so a converted print site drops out of the scan
  entirely), or
* named in ``_ALLOWED_GIT_COMMIT_HITS`` below with a one-line rationale --
  reserved for text that is NOT a copy/paste commit recipe: a log/error
  message reporting an ALREADY-ATTEMPTED commit's outcome, an internal
  prefix-matching constant, banner/prose text, or a bootstrap recipe for a
  scenario safe-commit structurally cannot serve (no destination ref yet, or
  an empty/allow-empty commit with no file paths).

The allowlist is keyed on stable content -- the file plus a distinctive
substring of the flagged text -- never on line numbers, so an unrelated edit
above an allowlisted site cannot turn the scan red, and a real content change
at a site does.

Known limits of the shape classifier (``is_recipe_shaped``), by design:

* not seen: a command assembled from several literals (``"git " + "commit"``,
  ``" ".join(...)``, ``%``/``.format`` over separate pieces); only a single
  string constant or one f-string is classified;
* not seen: a command whose first word is not literally ``git`` (an alias,
  ``$GIT``, ``command git``); other committing subcommands (``git merge``,
  ``git cherry-pick``);
* not seen: a follower that is a plain word or sentence punctuation other than a
  final ``.`` (``,`` ``:`` ``)``) when the string has no ``git add``. That is how
  prose and log lines read; a recipe in that shape would be missed;
* fail-safe over-flags, pinned in ``_KNOWN_OVER_FLAGS``: prose ending in
  ``git commit`` (a final ``.`` included), a quoted ``'git commit'``, and a
  ``word/word`` follower that reads as a path (``git commit and/or ...``).

Shapes that used to be on this list and are now flagged, each with a fixture:
interpolations inside an f-string (shown as ``{}``, also between ``git`` and
``commit`` and attached to ``commit``), an ellipsis (spaced or attached), a
trailing ``.``, a ``%s`` or ``[options]`` follower, a redirect, Rich markup
closing the command, a capitalised ``Git``, and a quoted ``-C "dir with spaces"``.

This is the scanner half. It lives under ``tests/architectural/`` so that the
architectural battery, which pull-request CI selects for every change under
``src/specify_cli/``, runs it. The renderer unit tests stay in
``tests/specify_cli/cli/commands/test_commit_recipes.py``.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
_MIN_DISTINCTIVE_LEN = 16

# (relative-path-from-src/specify_cli, distinctive substring of the flagged
# text): one-line rationale. Keyed on content, not line numbers (DIRECTIVE_041).
# Every entry here is text judged NOT to be a printed copy/paste commit recipe
# (see module docstring). Reviewers: a new entry needs its own rationale, not a
# rubber stamp of this list -- and a converted recipe site is REMOVED from this
# list, never added to it (the rendered ``spec-kitty safe-commit ...`` text
# never contains "git commit").
_ALLOWED_GIT_COMMIT_HITS: dict[tuple[str, str], str] = {
    (
        "coordination/planning_commit.py",
        "silently demotes",
    ): (
        "DEMOTION_REFUSAL_MSG: prose describing a manual meta.json-flatten "
        "conflict repair (`git add` + `git commit`, no concrete files/message/"
        "branch spelled out) -- not a copy/paste recipe, and the scenario "
        "(reconciling a demoted coordination_branch) isn't one safe-commit's "
        "single-target model covers."
    ),
    (
        "core/mission_creation_roots.py",
        "has no commits yet",
    ): (
        "Bootstrap recipe for an unborn HEAD (`git commit --allow-empty -m "
        "'Initial commit'`): no destination ref exists yet and there are no "
        "file paths to pass, so safe-commit's file-set/branch model cannot "
        "express it -- structurally out of scope, not an oversight."
    ),
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

    Deliberately narrow (not "any element of any list/tuple literal passed to
    any Call": that broader shape also exempted a git-commit string joined
    into a printed GUIDANCE list, e.g.
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


# --- Recipe-shape classifier (FR-013) ---------------------------------------
#
# A string is a recipe when it names a ``git ... commit`` command AND either
# the command is followed by something a reader would copy and run, or the
# same string also tells the reader to ``git add``. Only the text is
# inspected: where the string ends up (``help=``, ``print``, a list) never
# changes the verdict.

# ``git`` plus any global options: ``-C <dir>``, ``-c <key>=<value>``, ``--<long>``.
_OPTION_ARGUMENT = r"""(?:"[^"]*"|'[^']*'|\S+)"""
_GIT_PREFIX = rf"(?<![\w-])[Gg]it(?:[ \t]+(?:-[Cc][ \t]+{_OPTION_ARGUMENT}|--[A-Za-z][\w-]*(?:=\S+)?|\{{\}}))*"
# ``commit`` / ``add`` as whole words: ``commit-tree``, ``commit-graph`` and ``commits`` do not match.
_GIT_COMMIT = re.compile(_GIT_PREFIX + r"[ \t]+commit(?![\w-])")
_GIT_ADD = re.compile(_GIT_PREFIX + r"[ \t]+add(?![\w-])")

# What may directly follow ``commit`` in a copy-paste recipe. Anything else
# (a plain word, ``,``, ``.``, ``)``) is prose or a log line.
_RECIPE_FOLLOWER = re.compile(
    r"""
      [`'"]                                         # a quote or the end of a backtick span
    | [ \t]*(?:\r?\n|\Z)                            # the end of a line or of the string
    | [ \t]*(?:&&|\|\|?|;|\\)                        # a shell operator or a line continuation
    | [ \t]+(?:-{1,2}[A-Za-z]|--(?:[ \t]|\Z))         # a flag, or the ``--`` separator
    | [ \t]+[<{$%"'\[]                               # a placeholder, an expansion, a synopsis bracket, an opening quote
    | \{\}                                          # an f-string interpolation attached to the command
    | \[/                                            # a Rich markup tag closing right after the command
    | [ \t]*(?:\.{3}|\u2026)                          # an ellipsis
    | [ \t]+\.(?!\w)                                 # a ``.`` path
    | \.[ \t]*(?:\r?\n|\Z)                           # a final period: the sentence ends in the command
    | [ \t]*\d?>                                    # a redirect
    | [ \t]+(?:\S*/\S*|[\w-]+\.[A-Za-z0-9]{1,6}(?!\w))  # a path or a file name
    """,
    re.VERBOSE,
)


def _commit_commands(text: str) -> list[re.Match[str]]:
    return list(_GIT_COMMIT.finditer(text))


def _has_recipe_follower(text: str, commands: list[re.Match[str]]) -> bool:
    return any(_RECIPE_FOLLOWER.match(text, command.end()) for command in commands)


def is_recipe_shaped(text: str) -> bool:
    """Whether *text* has the shape of a copy-paste ``git commit`` recipe.

    True when *text* names a ``git commit`` command (``git -C <dir> commit`` and
    ``git -c <key>=<value> commit`` included) and either that command is followed
    by a flag, a quote, a placeholder, a ``$`` expansion, a path, a shell
    operator, or the end of the string, line or backtick span, or the same
    string also contains ``git add``. Any other mention is prose or a log line.
    """
    commands = _commit_commands(text)
    if not commands:
        return False
    return _GIT_ADD.search(text) is not None or _has_recipe_follower(text, commands)


def _fstring_text(node: ast.JoinedStr) -> str:
    """The literal text of an f-string, each interpolation shown as ``{}``.

    Dropping interpolations would let ``f"git -C {d} commit"`` collapse to
    ``git -C  commit``, hiding the ``commit`` behind the option argument.
    """
    return "".join(part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}" for part in node.values)


def find_git_commit_recipe_hits(*, source: str, filename: str = "<test>") -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every non-docstring, non-argv string
    constant or f-string in *source* that ``is_recipe_shaped``.
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
            if not is_recipe_shaped(node.value):
                continue
            if _is_subprocess_argv_element(node, parents.parent):
                continue
            hits.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            text = _fstring_text(node)
            if is_recipe_shaped(text):
                hits.append((node.lineno, text))
    return hits


def _scan_src_specify_cli() -> list[tuple[str, str]]:
    """Return ``(relative_path, flagged_text)`` for every hit under src/specify_cli."""
    found: list[tuple[str, str]] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_SRC_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        found.extend((rel, text) for _lineno, text in find_git_commit_recipe_hits(source=source, filename=str(path)))
    return found


def _allowlist_covers(entry: tuple[str, str], hit: tuple[str, str]) -> bool:
    (allowed_path, allowed_substring), (hit_path, hit_text) = entry, hit
    return allowed_path == hit_path and allowed_substring in hit_text


def test_no_unallowed_git_commit_recipe_strings_in_src() -> None:
    """Every printed ``git commit`` recipe is safe-commit-shaped.

    Any hit not covered by an entry in ``_ALLOWED_GIT_COMMIT_HITS`` (with a
    rationale) is a regression -- either a new raw ``git commit`` recipe was
    printed, or a known one was reverted from ``safe_commit_recipe``.
    """
    unexplained = [hit for hit in _scan_src_specify_cli() if not any(_allowlist_covers(entry, hit) for entry in _ALLOWED_GIT_COMMIT_HITS)]
    assert not unexplained, (
        "Printed git-commit recipe(s) found outside the reviewed allowlist "
        "-- convert to _commit_recipes.safe_commit_recipe() or add a "
        f"rationale to _ALLOWED_GIT_COMMIT_HITS: {[(path, text[:80]) for path, text in unexplained]}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    """Every allowlist entry must still match a live hit.

    A stale entry (its site was converted, reworded or deleted) is dead
    bookkeeping that would silently mask a future regression at that spot, so
    it must be removed -- the allowlist only ever shrinks.
    """
    found = _scan_src_specify_cli()
    stale = sorted(entry for entry in _ALLOWED_GIT_COMMIT_HITS if not any(_allowlist_covers(entry, hit) for hit in found))
    assert not stale, f"Allowlist entries with no matching source hit (stale, remove them): {stale}"


def test_allowlist_entries_are_specific_enough_to_be_stable_keys() -> None:
    """A substring that is too short would silently cover unrelated future hits."""
    too_short = sorted(entry for entry in _ALLOWED_GIT_COMMIT_HITS if len(entry[1]) < _MIN_DISTINCTIVE_LEN)
    assert not too_short, f"Allowlist substrings must be distinctive (>= {_MIN_DISTINCTIVE_LEN} chars): {too_short}"


def test_allowlist_matching_ignores_line_numbers() -> None:
    """Positive control for the content key: shifting a site down the file does not change coverage."""
    entry = ("a.py", "git commit --allow-empty")
    before = find_git_commit_recipe_hits(source="RECIPE = 'git commit --allow-empty -m x'\n")
    after = find_git_commit_recipe_hits(source="\n\n\nimport os\nRECIPE = 'git commit --allow-empty -m x'\n")
    assert before[0][0] != after[0][0]
    assert _allowlist_covers(entry, ("a.py", before[0][1]))
    assert _allowlist_covers(entry, ("a.py", after[0][1]))
    assert not _allowlist_covers(entry, ("b.py", after[0][1]))


def test_scanner_positive_control_flags_a_recipe_fixture() -> None:
    """Sanity check on the scanner itself: a fixture string shaped exactly
    like the recipes the safe-commit conversion targets is still flagged when NOT allowlisted.
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
    """Positive control: a printed recipe joined
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
# Classifier contract (FR-013, FR-014): data first.
# ---------------------------------------------------------------------------

# The 11 recipes the tree held before commit 3e09226fb4 converted them to
# ``safe_commit_recipe(...)`` (#5078). Each ``source`` is the VERBATIM source
# line from ``git show '3e09226fb4^:src/specify_cli/<path>'`` (3e09226fb4^ is
# 0d4466a39ebc56c3633ccce032ac3e60b60d235a), indentation included, so the
# f-string handling of the scanner is exercised too. Do not paraphrase.
_HISTORICAL_RECIPES: list[tuple[str, int, str]] = [
    (
        "cli/commands/agent/mission_setup_plan.py",
        137,
        '        console.print(f"[yellow]You may need to commit manually:[/yellow] git add {file_path} && git commit")',
    ),
    (
        "cli/commands/agent/tasks_parsing_validation.py",
        388,
        "        guidance.append(f'  git commit -m \"research({wp_id}): <describe your research outputs>\"')",
    ),
    (
        "cli/commands/agent/tasks_parsing_validation.py",
        390,
        "        guidance.append(f'  git commit -m \"docs({wp_id}): <describe your changes>\"')",
    ),
    (
        "cli/commands/agent/tasks_parsing_validation.py",
        588,
        "    guidance.append(f'  git commit -m \"feat({wp_id}): <describe implementation>\"')",
    ),
    (
        "cli/commands/agent/tasks_parsing_validation.py",
        618,
        "    guidance.append(f'  git commit -m \"feat({wp_id}): <describe implementation>\"')",
    ),
    (
        "cli/commands/agent/tasks_parsing_validation.py",
        712,
        "    guidance.append('  git commit -m \"chore: remove planning artifacts from lane branch\"')",
    ),
    (
        "cli/commands/agent/workflow_executor.py",
        1378,
        "    lines.append(f'     git commit -m \"feat({normalized_wp_id}): <brief description>\"')",
    ),
    (
        "cli/commands/agent/workflow_executor.py",
        1455,
        "    lines.append(f'      git commit -m \"feat({normalized_wp_id}): <brief description>\"')",
    ),
    (
        "cli/commands/agent/workflow_executor.py",
        1514,
        "    print(f'  1. git status && git add <your-files> && git commit -m \"feat({normalized_wp_id}): <description>\"')",
    ),
    (
        "cli/commands/charter/_synthesis.py",
        749,
        "    console.print(\"  git commit -m 'chore: charter synthesis artifacts'\")",
    ),
    (
        "cli/commands/implement.py",
        424,
        "    console.print(f'  git commit -m \"chore: planning artifacts for {mission_slug}\"')",
    ),
]

# One positive per shape of FR-013. Keyed by a short shape name.
_RECIPE_SHAPES: dict[str, str] = {
    "flag-short": 'git commit -m "feat(WP01): x"',
    "flag-long": "git commit --amend",
    "quote-double": 'git commit "feat(WP01): x"',
    "quote-single": "git commit 'feat(WP01): x'",
    "placeholder-angle": "git commit <message>",
    "placeholder-brace": "git commit {msg}",
    "dollar-variable": "git commit $MESSAGE",
    "dollar-substitution": "git commit $(cat message.txt)",
    "path-with-slash": "git commit kitty-specs/demo/spec.md",
    "path-with-extension": "git commit meta.json",
    "operator-and": "git commit && git push",
    "operator-semicolon": "git commit; echo done",
    "operator-pipe": "git commit | tee commit.log",
    "operator-backslash-continuation": 'git commit \\\n    -m "x"',
    "end-of-string": "Then run git commit",
    "end-of-line": "Stage the files:\n  git commit\nthen push",
    "end-of-backtick-span": "Then run `git commit` yourself.",
    "global-dir-option": 'git -C {repo} commit -m "x"',
    "global-dir-option-absolute": "git -C /work/repo commit -m x",
    "global-config-option": "git -c user.name=Bot commit -m x",
    "global-config-option-hookspath": "git -c core.hooksPath=/dev/null commit",
    "co-occurring-git-add-ellipsis": "git add ... && git commit ...",
    "co-occurring-git-add-flagless-imperative": "Stage the files with git add, then git commit the change.",
    "flag-with-file-argument": "git commit -F message.txt",
    "global-long-option": "git --no-pager commit -m x",
    "indented-multi-line-guidance": "Run:\n  git commit -a\nand push.",
    "ellipsis-follower": "Commit with git commit ... when done",
    "unicode-ellipsis-follower": "Commit with git commit \u2026 when done",
    "dot-path-follower": "git commit . and push",
    "percent-template-follower": "Commit with git commit %s when done",
    "rich-markup-closes-the-command": "run [bold]git commit[/bold] now",
    "capitalised-git": "Git commit -m x",
    "quoted-dir-option-with-spaces": 'git -C "my repo" commit -m x',
    "ellipsis-attached": "Commit with git commit... when done",
    "sentence-final-period": "Before you push, run git commit.",
    "usage-synopsis-brackets": "Usage: git commit [options]",
    "redirect-stdout": "git commit > commit.log",
    "redirect-stderr-merge": "git commit 2>&1",
    "interpolated-options-before-the-subcommand": "git {} commit",
    "interpolation-attached-to-the-subcommand": "git commit{}",
}

# Mentions that are NOT a recipe: the help text that caused #5708 (the wording
# commit 22994ca25 shipped; it was reworded on the mainline since, and this
# copy stays as the historical false positive), log lines reporting an
# already-attempted commit, and prose.
_HELP_TEXT_5708 = "Commit message. Repeat -m to add paragraphs (joined by a blank line, as git commit does)."
_NOT_RECIPES: dict[str, str] = {
    "help-text-5708": _HELP_TEXT_5708,
    "other-subcommand-commit-tree": "git commit-tree failed",
    "other-subcommand-commit-graph": "git commit-graph write failed for the object store",
    "prose-comma-after": "After git commit, run the checks again.",
    "prose-in-passing": "The reviewer wants the git commit history to stay linear.",
    "prose-plural": "Ignore git commits and status changes from other agents",
    "log-primary-checkout": "git commit failed on the primary checkout: ",
    "log-prefix-constant": "safe_commit: git commit failed",
    "log-stderr-template": "git commit in %s: %s",
    "log-warnings-template": "git commit in %s produced warnings on a successful commit: %s",
    "log-attempt-one": "git commit failed (attempt 1): %s",
    "log-exception-attempt-two": "git commit exception (attempt 2): %s",
    "log-after-retry": "git commit failed after retry",
    "log-colon-after": "git commit: nothing to commit, working tree clean",
    "prose-parenthetical": "(see the git commit documentation for details)",
}

# Documented fail-safe over-flags: prose the classifier flags on purpose because
# it cannot tell it from a recipe by shape. Pinned so the behaviour is a decision.
_KNOWN_OVER_FLAGS: dict[str, str] = {
    "prose-slash-word-reads-as-a-path": "Use git commit and/or git push as your workflow needs",
    "prose-ending-in-the-command": "Before you push, run git commit",
    "quoted-command-name": "Never type 'git commit' by hand here",
    "sentence-final-period-in-prose": "Nothing is staged until you git commit.",
}


@pytest.mark.parametrize(("path", "line", "source"), _HISTORICAL_RECIPES, ids=[f"{p.rsplit('/', 1)[-1]}:{n}" for p, n, _ in _HISTORICAL_RECIPES])
def test_each_historical_recipe_is_flagged(path: str, line: int, source: str) -> None:
    """FR-014: every recipe the tree held before 3e09226fb4 is still flagged."""
    hits = find_git_commit_recipe_hits(source=textwrap.dedent(source), filename=f"{path}:{line}")
    assert len(hits) == 1, f"{path}:{line} is no longer flagged: {source!r}"
    assert is_recipe_shaped(hits[0][1])


def test_historical_recipe_set_has_the_eleven_known_members() -> None:
    assert len(_HISTORICAL_RECIPES) == 11
    assert len({(path, line) for path, line, _ in _HISTORICAL_RECIPES}) == 11


@pytest.mark.parametrize("text", list(_RECIPE_SHAPES.values()), ids=list(_RECIPE_SHAPES))
def test_every_recipe_shape_is_flagged(text: str) -> None:
    """FR-013: one positive per shape."""
    assert is_recipe_shaped(text)


@pytest.mark.parametrize("text", list(_NOT_RECIPES.values()), ids=list(_NOT_RECIPES))
def test_non_recipe_mentions_are_not_flagged(text: str) -> None:
    """FR-013: prose, help text and log lines that mention ``git commit`` stay clean."""
    assert not is_recipe_shaped(text)


@pytest.mark.parametrize("text", list(_KNOWN_OVER_FLAGS.values()), ids=list(_KNOWN_OVER_FLAGS))
def test_known_over_flags_stay_flagged(text: str) -> None:
    """Fail-safe: an ambiguous mention is flagged rather than missed (see the module docstring)."""
    assert is_recipe_shaped(text)


def test_shipped_message_option_help_is_not_flagged() -> None:
    """The help text ``safe-commit`` and ``spec-commit`` ship today is prose to the scanner (read as text, never imported)."""
    path = _SRC_ROOT / "cli" / "commands" / "_commit_message.py"
    source = path.read_text(encoding="utf-8")
    assert "MESSAGE_OPTION_HELP" in source
    assert find_git_commit_recipe_hits(source=source, filename=str(path)) == []


def test_scanner_flags_a_global_option_recipe_in_source() -> None:
    """``git -C <dir> commit`` never contained the bare substring; the shape rule sees it."""
    hits = find_git_commit_recipe_hits(source='MSG = "Commit it: git -C /repo commit -m x"\n')
    assert [text for _lineno, text in hits] == ["Commit it: git -C /repo commit -m x"]


def test_scanner_verdict_does_not_depend_on_where_the_string_is_used() -> None:
    """A recipe passed as ``help=`` is flagged; the help prose is not. Only the text decides."""
    prose = f"typer.Option(help={_HELP_TEXT_5708!r})\n"
    recipe = 'typer.Option(help="Run git commit -m x")\n'
    assert find_git_commit_recipe_hits(source=prose) == []
    assert [text for _lineno, text in find_git_commit_recipe_hits(source=recipe)] == ["Run git commit -m x"]


def test_planted_recipe_in_a_real_source_file_turns_the_scan_red() -> None:
    """Non-vacuity (FR-016): the real file is clean; the same text plus a planted recipe is flagged.

    The planted string exists only in memory; nothing under ``src/`` is touched.
    """
    real = (_SRC_ROOT / "cli" / "commands" / "_commit_message.py").read_text(encoding="utf-8")
    assert find_git_commit_recipe_hits(source=real) == []
    planted = real + "\nPLANTED = \"git commit -m 'x'\"\n"
    assert [text for _lineno, text in find_git_commit_recipe_hits(source=planted)] == ["git commit -m 'x'"]


# F-strings are scanned as their literal parts with each interpolation replaced
# by ``{}``, so ``git -C {d} commit`` cannot collapse to ``git -C  commit``.
# Each case is source text run through the AST scanner, not a plain string.
_FSTRING_RECIPE_SOURCES: dict[str, str] = {
    "global-dir-option": 'line = f"git -C {d} commit -m x"\n',
    "global-dir-option-with-add": "line = f\"git -C {d} add {p} && git -C {d} commit -m 'chore: x'\"\n",
    # Verbatim from cli/commands/mission_type.py (_commit_flattened_meta): three
    # implicitly concatenated f-strings, so one JoinedStr.
    "implicit-concatenation-witness": (
        "console.print(\n"
        '    f"[yellow]Warning:[/yellow] discard of {mission_slug} flattened "\n'
        '    f"meta.json but could not commit it ({exc}). Commit it manually: "\n'
        '    f"git -C {repo_root} add {meta_path} && git -C {repo_root} commit "\n'
        "    f\"-m 'chore({mission_slug}): flatten discarded mission metadata'\"\n"
        ")\n"
    ),
    "interpolation-as-the-only-follower": 'line = f"git commit {args}"\n',
    "interpolated-options-before-the-subcommand": 'line = f"git {opts} commit"\n',
    "interpolation-attached-to-the-subcommand": 'line = f"git commit{args}"\n',
}


@pytest.mark.parametrize("source", list(_FSTRING_RECIPE_SOURCES.values()), ids=list(_FSTRING_RECIPE_SOURCES))
def test_scanner_flags_fstring_recipes_with_interpolated_parts(source: str) -> None:
    assert len(find_git_commit_recipe_hits(source=source)) == 1


def test_scanner_keeps_fstring_log_lines_clean() -> None:
    source = 'line = f"git commit failed in {path}: {err}"\n'
    assert find_git_commit_recipe_hits(source=source) == []


def test_scan_root_anchor_resolves_to_the_source_tree() -> None:
    """A wrong ``parents[...]`` index must fail loudly, not pass as "no hits"."""
    assert _SRC_ROOT.is_dir(), f"scan root does not exist: {_SRC_ROOT}"
    assert _SRC_ROOT.name == "specify_cli"
    assert any(_SRC_ROOT.rglob("*.py")), f"scan root holds no Python files: {_SRC_ROOT}"
