"""Class gate: no sweeping, pathspec-less or hook-bypassing commit route in ``src/`` (#5443, FR-013, SC-005).

Mission ``upgrade-migration-commit-scope-01M4AKVE``. An automatic commit
records exactly the paths the operation wrote. Written paths are committed
through ``safe_commit`` with an explicit list; a merge, revert or squash
conclusion, where git refuses a pathspec, goes through the one
merge-conclusion owner, ``specify_cli.git.merge_conclusion``.

The rule is the census in ``_commit_scope_census.py`` (the single authority;
this gate does not restate it). The gate runs it over every ``src/**/*.py``
file and requires **zero** hits.

**The allowlist is empty and stays empty.** There is no allowlist, no
``_baselines.yaml`` entry and no count to ratchet (ADR
``2026-09-30-1-allowlist-ratchets-are-priced-debt``; Decision
``01M4B2XJQ0JAHVXGVDNQBMF6XF``). The only exemptions are the two canonical
owners, by symbol (Decision ``01M4B6FZNNSTP6DPN2AAEDEQHZ``): ``safe_commit``
(including the temporary-index commit of its private helper
``_commit_with_index_deletions``) and ``run_committing_op`` /
``conclude_in_progress_op``. The two path-scoped commits C-005 records as
unable to use ``safe_commit`` (the mission-number ``commit --only -- <rel_meta>``
in ``consolidation/mission_number/bake.py`` and the consolidation
``commit --amend --only -- <restored>``) carry a pathspec, so the rule accepts
them without any exemption.

Baseline: at the planning base of this WP (``7a022c203``, WP01+WP04+WP06+WP07
merged) the census scanned **1397** source files and reported **11 hits in 5
files** -- ``lanes/auto_rebase.py`` x2, ``lanes/consolidation.py`` x4,
``lanes/worktree_allocator.py`` x3, ``coordination/coherence.py`` x1,
``cli/commands/agent/workflow.py`` x1 -- every one a merge/revert conclusion or
the consolidation amend. The WP closes at **0**.

Non-vacuity (standing order 5): a scanned-file floor, one planted case per
form with its exact ``kind``, negative controls for the non-committing forms,
and positive controls proving both owners really contain what the gate would
otherwise report and that the exemption is keyed by symbol, not by file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._commit_scope_census import (
    CANONICAL_OWNERS,
    KINDS,
    Hit,
    census,
    census_source,
    census_text,
    classify_argv,
    exempt_helper_leaks,
    exempt_helper_leaks_text,
    exempt_hit_holders,
    src_files,
)
from tests.architectural._destructive_op_census import REPO_ROOT

pytestmark = pytest.mark.architectural

#: 90% of the 1397 ``src/**/*.py`` files measured at the planning base.
_SCANNED_FILE_FLOOR = 1257

_FIX_HINT = "route merge/revert/squash conclusions through specify_cli.git.merge_conclusion; commit written paths through safe_commit"

_OWNERS = {owner.rel: owner for owner in CANONICAL_OWNERS}
_COMMIT_HELPERS = "src/specify_cli/git/commit_helpers.py"
_MERGE_CONCLUSION = "src/specify_cli/git/merge_conclusion.py"


def _plant(tmp_path: Path, body: str) -> list[Hit]:
    planted = tmp_path / "planted.py"
    planted.write_text(body, encoding="utf-8")
    return census([planted])


def _kinds(hits: list[Hit]) -> list[str]:
    return sorted(hit.kind for hit in hits)


def _owner_text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_no_sweeping_or_hook_bypassing_commit_outside_the_owner() -> None:
    hits = census(src_files())
    assert hits == [], (
        "Sweeping, pathspec-less or hook-bypassing commit route outside the canonical owners (allowlist is empty):\n"
        + "\n".join(f"  {hit.path}:{hit.lineno} {hit.kind} {hit.argv_repr}" for hit in hits)
        + f"\n{_FIX_HINT}"
    )


def test_gate_scans_a_non_trivial_number_of_files() -> None:
    scanned = src_files()
    assert len(scanned) >= _SCANNED_FILE_FLOOR, f"only {len(scanned)} source files scanned; the gate is vacuous below {_SCANNED_FILE_FLOOR}"


_PLANTED: list[tuple[str, str, list[str]]] = [
    ("add-A", 'run(["git", "add", "-A"])', ["add-sweep"]),
    ("add-dot", 'run(["git", "add", "."])', ["add-sweep"]),
    ("add-all", 'run(["git", "add", "--all"])', ["add-sweep"]),
    ("add-u", 'run(["git", "add", "-u"])', ["add-sweep"]),
    ("add-top", 'run(["git", "add", ":/"])', ["add-sweep"]),
    ("commit-m", 'run(["git", "commit", "-m", msg])', ["commit-no-pathspec"]),
    ("amend", 'run(["git", "commit", "--amend", "--no-edit"])', ["amend-no-pathspec"]),
    ("commit-a", 'run(["git", "commit", "-a", "-m", "x"])', ["commit-all"]),
    ("no-verify", 'run(["git", "commit", "--no-verify", "-m", "x", "--", "p"])', ["hook-bypass"]),
    ("commit-n", 'run(["git", "commit", "-n", "-m", "x", "--", "p"])', ["hook-bypass"]),
    ("hooks-path", 'run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "x", "--", "p"])', ["hook-bypass"]),
    ("merge", 'run(["git", "merge", "--no-edit", b])', ["committing-merge"]),
    ("revert", 'run(["git", "revert", "--no-edit", sha])', ["committing-revert"]),
    ("cherry-pick", 'run(["git", "cherry-pick", sha])', ["committing-cherry-pick"]),
    ("merge-continue", 'run(["git", "merge", "--continue"])', ["committing-merge"]),
    ("git-in-runner", '_git_in(wt, ["commit", "--no-edit"], env)', ["commit-no-pathspec"]),
    ("constant-indirection", '_ADD = "add"\nrun(["git", _ADD, "-A"])', ["add-sweep"]),
    ("varargs-add", 'run_git(cwd, "add", "-A")', ["add-sweep"]),
    ("varargs-commit", 'run_git(cwd, "commit", "-m", msg)', ["commit-no-pathspec"]),
    ("tuple-argv", 'run(("git", "add", "--update"))', ["add-sweep"]),
    ("message-is-not-a-flag", 'run(["git", "commit", "-m", "-a"])', ["commit-no-pathspec"]),
    ("separator-without-path", 'run(["git", "commit", "-m", "x", "--"])', ["commit-no-pathspec"]),
    ("amend-separator-without-path", 'run(["git", "commit", "--amend", "--no-edit", "--"])', ["amend-no-pathspec"]),
    ("merge-no-verify", 'run(["git", "merge", "--no-verify", b])', ["committing-merge", "hook-bypass"]),
    ("shell-string-add", 'subprocess.run("git add -A && git status", shell=True)', ["add-sweep"]),
    ("shell-string-no-verify", 'os.system("git commit -m x --no-verify")', ["hook-bypass"]),
    ("gitpython-index-add", 'repo.index.add(["p"])', ["library-git-call"]),
    ("gitpython-git-commit", 'repo.git.commit("-m", "x")', ["library-git-call"]),
    ("renamed-runner-list", 'my_runner(wt, ["commit", "--no-edit"])', ["unknown-runner"]),
    ("renamed-runner-varargs", 'my_runner(cwd, "add", "-A")', ["unknown-runner"]),
]


@pytest.mark.parametrize(("body", "expected"), [(body, kinds) for _, body, kinds in _PLANTED], ids=[case for case, _, _ in _PLANTED])
def test_planted_hit_is_reported(tmp_path: Path, body: str, expected: list[str]) -> None:
    assert _kinds(_plant(tmp_path, body + "\n")) == expected


def test_planted_forms_cover_every_kind() -> None:
    covered = {kind for _, _, kinds in _PLANTED for kind in kinds}
    assert covered == KINDS


_NEGATIVE: list[tuple[str, str]] = [
    ("merge-squash", 'run(["git", "merge", "--squash", src])'),
    ("merge-no-commit", 'run(["git", "merge", "--no-edit", "--no-ff", "--no-commit", b])'),
    ("merge-ff-only", 'run(["git", "merge", "--ff-only", b])'),
    ("merge-abort", 'run(["git", "merge", "--abort"])'),
    ("revert-abort", 'run(["git", "revert", "--abort"])'),
    ("commit-only-pathspec", 'run(["git", "commit", "--only", "-m", "x", "--", "p"])'),
    ("commit-pathspec", 'run(["git", "commit", "-m", "x", "--", "p"])'),
    ("amend-only-pathspec", 'run(["git", "commit", "--amend", "--only", "--no-edit", "--allow-empty", "--", *restored])'),
    ("add-separator-path", 'run(["git", "add", "--", "p"])'),
    ("add-path", 'run(["git", "add", "p"])'),
    ("worktree-add", 'run(["git", "worktree", "add", "--detach", tmp, b])'),
    ("revert-n", 'run(["git", "revert", "-n", sha])'),
    ("rebase", 'run(["git", "rebase", "main"])'),
    ("varargs-add-force", 'run_git(cwd, "add", "--force", "--", *paths)'),
    ("plumbing-commit-tree", 'run(["git", "commit-tree", tree, "-p", parent, "-m", m])'),
    ("not-git", 'run(["gh", "pr", "merge", "--squash"])'),
    ("no-git-prefix-outside-runner", 'args = ["commit", "--no-edit"]'),
    ("ui-step-named-commit", 'tracker.complete("commit", "commit created")'),
    ("docstring-mentions-a-sweep", 'def f():\n    """Never run git add -A here."""'),
    ("shell-string-with-pathspec", 'subprocess.run("git add -- p", shell=True)'),
]


@pytest.mark.parametrize("body", [body for _, body in _NEGATIVE], ids=[case for case, _ in _NEGATIVE])
def test_non_committing_forms_are_not_reported(tmp_path: Path, body: str) -> None:
    assert _plant(tmp_path, body + "\n") == []


@pytest.mark.parametrize("rel", [_COMMIT_HELPERS, _MERGE_CONCLUSION])
def test_owner_really_contains_what_the_gate_would_report(rel: str) -> None:
    """(a) positive control: with the exemption bypassed, each owner reports at least one hit."""
    hits = census_source(_owner_text(rel), rel)
    assert hits, f"{rel}: no hit with the exemption bypassed; the owner's commit argv is no longer statically visible"
    assert census_text(_owner_text(rel), rel) == [], f"{rel}: the owner exemption stopped working"


def test_census_over_both_owner_files_is_empty() -> None:
    """(b) the real files, through the same entry point as the gate."""
    assert census([REPO_ROOT / _COMMIT_HELPERS, REPO_ROOT / _MERGE_CONCLUSION]) == []


@pytest.mark.parametrize("rel", [_COMMIT_HELPERS, _MERGE_CONCLUSION])
def test_owner_source_elsewhere_is_reported(tmp_path: Path, rel: str) -> None:
    """(c) the exemption needs the owner file: the same source at another path is scanned."""
    copy = tmp_path / "other.py"
    copy.write_text(_owner_text(rel), encoding="utf-8")
    assert census([copy]) != []


_ROGUE_ARGV = '["git", "-c", "commit.gpgsign=false", "commit", "-m", message]'


def _with_helper_called_from_safe_commit(text: str, helper: str) -> str:
    """Insert a direct call to *helper* as the first statement of ``safe_commit``."""
    tree = ast.parse(text)
    safe_commit = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "safe_commit")
    first = safe_commit.body[0]
    lines = text.splitlines(keepends=True)
    lines.insert(first.lineno - 1, " " * first.col_offset + f"{helper}()\n")
    return "".join(lines)


def _rogue_function(name: str) -> str:
    return f"\n\ndef {name}():\n    message = 'x'\n    return subprocess.run({_ROGUE_ARGV})\n"


def test_exemption_is_keyed_by_symbol_not_by_file() -> None:
    """(d) inside ``commit_helpers.py``: a function ``safe_commit`` does not call is scanned like any other."""
    text = _owner_text(_COMMIT_HELPERS)

    uncalled = text + _rogue_function("_not_called_by_safe_commit")
    assert _kinds(census_text(uncalled, _COMMIT_HELPERS)) == ["commit-no-pathspec"]

    called = _with_helper_called_from_safe_commit(text + _rogue_function("_called_by_safe_commit"), "_called_by_safe_commit")
    assert census_text(called, _COMMIT_HELPERS) == []

    public = _with_helper_called_from_safe_commit(text + _rogue_function("public_helper"), "public_helper")
    assert _kinds(census_text(public, _COMMIT_HELPERS)) == ["commit-no-pathspec"], "only module-private callees share the exemption"


def test_exemption_does_not_follow_a_second_call_level() -> None:
    """A private helper reached only through another private helper is not exempt (one level only)."""
    text = _owner_text(_COMMIT_HELPERS) + _rogue_function("_two_levels_down") + "\n\ndef _one_level_down():\n    return _two_levels_down()\n"
    text = _with_helper_called_from_safe_commit(text, "_one_level_down")
    assert _kinds(census_text(text, _COMMIT_HELPERS)) == ["commit-no-pathspec"]


def test_canonical_owners_are_exactly_two_keyed_by_symbol() -> None:
    """(e) no third owner, no file-wide exemption."""
    assert len(CANONICAL_OWNERS) == 2
    assert _OWNERS[_COMMIT_HELPERS].symbols == ("safe_commit",)
    assert set(_OWNERS[_MERGE_CONCLUSION].symbols) == {"run_committing_op", "conclude_in_progress_op"}


def test_classify_argv_ignores_unresolved_tokens() -> None:
    assert classify_argv(["git", None, "-A"]) == []
    assert classify_argv(["git", "commit", "-m", None, "--", None]) == []
    assert classify_argv(["git", "add", None]) == []
    assert classify_argv(["git", "commit", None, "-m", "x"]) == ["commit-no-pathspec"], "an unresolved token is never read as '--'"


def test_exempt_hit_holding_helpers_are_reached_only_from_owner_symbols() -> None:
    """The exemption cannot leak: a private helper holding a hit is referenced only from an owner symbol."""
    holders = exempt_hit_holders(_owner_text(_COMMIT_HELPERS), _COMMIT_HELPERS)
    assert "_commit_with_index_deletions" in holders, "non-vacuity: the temp-index commit helper holds a hit"
    leaks = exempt_helper_leaks(src_files())
    assert leaks == [], "exempt helper reached outside its owner symbol:\n" + "\n".join(
        f"  {leak.path}:{leak.lineno} {leak.helper} from {leak.referrer}" for leak in leaks
    )


def test_a_non_owner_caller_of_an_exempt_helper_is_a_leak() -> None:
    """Planted: a public function in the owner file calls the hit-holding helper."""
    text = _owner_text(_COMMIT_HELPERS) + "\n\ndef sneaky_commit(root, ref, msg):\n    return _commit_with_index_deletions(root, ref, msg, [], [])\n"
    leaks = exempt_helper_leaks_text(text, _COMMIT_HELPERS)
    assert [(leak.helper, leak.referrer) for leak in leaks] == [("_commit_with_index_deletions", "sneaky_commit")]


def test_a_foreign_import_of_an_exempt_helper_is_a_leak() -> None:
    """Planted: another module imports or reaches the hit-holding helper through its module."""
    text = (
        "from specify_cli.git.commit_helpers import _commit_with_index_deletions\n"
        "from specify_cli.git import commit_helpers\n\n"
        "def elsewhere(root):\n"
        "    return commit_helpers._commit_with_index_deletions(root, 'main', 'm', [], [])\n"
    )
    leaks = exempt_helper_leaks_text(text, "src/specify_cli/other.py", {"_commit_with_index_deletions"})
    assert sorted((leak.lineno, leak.referrer) for leak in leaks) == [(1, None), (5, "elsewhere")]
