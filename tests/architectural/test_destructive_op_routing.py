"""Unification routing gate (missions ``merge-destructive-op-safety-01M2XQF8`` and
``destructive-residue-context-01M4KBPS``, NFR-006/FR-007/FR-006,
``contracts/routing-invariant.md``).

A non-vacuous architectural gate (DIRECTIVE_043) proving the defect class
#4752/#4753/#5965/#5966 describe (a destructive git command, or a recursive
checkout deletion, run against state that holds the only copy of a file) is
closed BY CONSTRUCTION, not by reviewer goodwill. There is **no allowlist**
(ADR ``2026-09-30-1-allowlist-ratchets-are-priced-debt``): a destructive site is
either routed through the one guard (``git/destructive_guard.py``) or it fails.

1. **Routing gate.** Every command LITERAL below under ``src/specify_cli/``,
   ``src/runtime/``, ``src/charter/`` and ``src/kernel/`` is a failure, except
   inside the guard's own implementation (``git/destructive_guard.py`` and
   ``git/ref_advance.py``, the named :data:`_GUARD_INTERNAL_MODULES`):

   ``git reset --hard``, ``git worktree remove --force``, ``git worktree prune``,
   ``git merge --abort``, ``git stash push``, ``git stash drop``,
   ``git branch -D``, ``git clean -f`` (``-fd``, ``-fdx``, ``--force``) and
   ``git checkout --force`` / ``-f``.

   The census is LIVE (AST-driven, re-run every test run against the actual
   tree), not a hand-copied snapshot.
2. **Recursive-deletion gate.** No reference to ``shutil.rmtree`` (a call, an
   ``atexit.register(shutil.rmtree, ...)``, a ``from shutil import rmtree``
   alias) outside the four modules that PROVE ownership at run time
   (:data:`_RMTREE_PERMITTED`). Telling a checkout path from a temp tree
   statically is not decidable; forbidding the bare call and routing through
   helpers that prove ownership at run time is (research D7).
3. **Tool-owned confinement.** ``CheckoutRole.TOOL_OWNED`` (under which every
   path is disposable) may be named only in the modules that create scratch,
   cache or just-created checkouts (:data:`_TOOL_OWNED_PERMITTED`).
4. **Named-intent pin.** ``guarded_branch_delete(..., operator_intent=...)``,
   which skips the unique-commit check, is passed only by
   ``missions/_create.py::_delete_branch`` (``--force-recreate``).
5. **Non-vacuity.** Every needle detects a planted literal through the SAME
   scanner; the guard modules, scanned without their exclusion, do contain
   literals; and planting a literal in a copy of the live tree turns the gate red.

Detection strategy
-------------------
A bare text ``grep`` for ``"reset", "--hard"`` would miss the one real
indirection this codebase has (``coordination/workspace.py``'s
``_GIT_WORKTREE = "worktree"`` module constant). This gate instead walks every
``ast.List``/``ast.Tuple`` literal, resolves each element that is either a
string constant or a `Name` bound to a module-level string constant, and
matches an ORDERED (not necessarily contiguous) subsequence of the target
command's tokens -- so ``[..., _GIT_WORKTREE, "remove", "--force", ...]`` is
caught exactly like the literal spelling.
"""

from __future__ import annotations

import ast as _ast
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SRC_ROOT,
    CensusKey,
    argv_tokens,
    census_keys,
    census_keys_for_sources,
    census_partition,
    composite_key,
    describe_unexpected,
    from_import_map,
    import_alias_map,
    iter_py_files,
    module_string_constants,
    ordered_subsequence,
    parse,
    read_sources,
    render_census_key,
    scan_planted_source,
)

pytestmark = pytest.mark.architectural

# The AST plumbing (file iteration, parsing, module-constant resolution, argv
# tokenisation, ordered-subsequence matching, qualname resolution and the
# self-mutation harness) is the single shared authority in
# ``_destructive_op_census`` (DIRECTIVE_044); this file keeps only the
# git-argv classifier and the named module constants below. There is no
# allowlist and no ``CensusKey`` row (ADR 2026-09-30-1).

# ---------------------------------------------------------------------------
# Routing gate -- destructive-command literals
# ---------------------------------------------------------------------------

_RESET_HARD = "reset_hard"
_WORKTREE_REMOVE_FORCE = "worktree_remove_force"
_WORKTREE_PRUNE = "worktree_prune"
_MERGE_ABORT = "merge_abort"
_STASH_PUSH = "stash_push"
_STASH_DROP = "stash_drop"
_BRANCH_DELETE_FORCE = "branch_delete_force"
_CLEAN_FORCE = "clean_force"
_CHECKOUT_FORCE = "checkout_force"

_PATTERN_NEEDLES: dict[str, tuple[tuple[str, ...], ...]] = {
    _RESET_HARD: (("reset", "--hard"),),
    _WORKTREE_REMOVE_FORCE: (("worktree", "remove", "--force"),),
    _WORKTREE_PRUNE: (("worktree", "prune"),),
    _MERGE_ABORT: (("merge", "--abort"),),
    _STASH_PUSH: (("stash", "push"),),
    _STASH_DROP: (("stash", "drop"),),
    _BRANCH_DELETE_FORCE: (("branch", "-D"),),
    _CHECKOUT_FORCE: (("checkout", "--force"), ("checkout", "-f")),
}

#: ``git clean`` is forced by ``-f`` in any short-option cluster (``-fd``, ``-fdx``, ``-xdf``) or ``--force``.
_CLEAN_FORCE_LONG = "--force"

#: The guard's own implementation: the one place a destructive command literal belongs.
_GUARD_INTERNAL_MODULES: dict[str, str] = {
    "src/specify_cli/git/destructive_guard.py": "the guard: every destroy runs here, after the only-copy scan",
    "src/specify_cli/git/ref_advance.py": "the ref-advance resync: dirty-checks every checkout before its reset",
}

#: Roots the census scans (the destructive set can live in any layer that shells out to git).
_SCAN_ROOTS: tuple[Path, ...] = tuple(SRC_ROOT / name for name in ("specify_cli", "runtime", "charter", "kernel"))

#: Files-scanned floor (NFR-002): the widened scan covered 1395 files when the allowlist was emptied.
#: A scan that silently shrinks below it is vacuous.
_FILES_SCANNED_FLOOR = 1390


def _is_forced_clean(tokens: list[str | None]) -> bool:
    """True for ``clean`` followed by ``--force`` or a short-option cluster holding ``f``."""
    resolved = [token for token in tokens if token is not None]
    if "clean" not in resolved:
        return False
    after = resolved[resolved.index("clean") + 1 :]
    return any(token == _CLEAN_FORCE_LONG or (token.startswith("-") and not token.startswith("--") and "f" in token[1:]) for token in after)


def _classify_argv(tokens: list[str | None]) -> str | None:
    for pattern, alternatives in _PATTERN_NEEDLES.items():
        if any(ordered_subsequence(tokens, *needles) for needles in alternatives):
            return pattern
    return _CLEAN_FORCE if _is_forced_clean(tokens) else None


def _is_guard_internal(path: Path) -> bool:
    posix = path.as_posix()
    return any(posix.endswith(rel) for rel in _GUARD_INTERNAL_MODULES)


def _find_destructive_literals(path: Path) -> list[tuple[int, str]]:
    """``(lineno, pattern)`` for every destructive-command argv literal in *path* (the guard's own modules excluded)."""
    if _is_guard_internal(path):
        return []
    return _find_destructive_literals_unfiltered(path)


def _find_destructive_literals_unfiltered(path: Path) -> list[tuple[int, str]]:
    tree = parse(path)
    consts = module_string_constants(tree)
    hits: list[tuple[int, str]] = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.List, _ast.Tuple)):
            pattern = _classify_argv(argv_tokens(node, consts))
            if pattern is not None:
                hits.append((node.lineno, pattern))
    return hits


def _live_sources() -> dict[str, str]:
    """``{repo-rel path: source}`` for every file the census scans."""
    return read_sources(path for root in _SCAN_ROOTS for path in iter_py_files(root))


def _census_keys(sources: Mapping[str, str]) -> dict[CensusKey, int]:
    """Content-keyed live census: ``{CensusKey: lineno}`` (the line is diagnostic only)."""
    return census_keys_for_sources(sources, _find_destructive_literals)


def _unexpected(sources: Mapping[str, str]) -> set[CensusKey]:
    """Every live site: with no allowlist, every site the census finds is unexpected."""
    return census_partition(_census_keys(sources), {})[0]


def test_the_gate_has_no_allowlist() -> None:
    """ADR 2026-09-30-1: a registry of exempted sites is priced debt; this gate carries none."""
    assert "_ALLOWLIST" not in globals()


def test_no_destructive_command_literal_outside_the_guard() -> None:
    """NFR-006/FR-007/INV-3: every destructive-command literal is routed through the guard (none is exempt)."""
    sources = _live_sources()
    assert len(sources) >= _FILES_SCANNED_FLOOR, f"census scanned {len(sources)} files, below the pinned floor {_FILES_SCANNED_FLOOR}"
    unexpected = _unexpected(sources)

    assert not unexpected, (
        "Destructive git command literal(s) found outside the guard (git/destructive_guard.py). "
        "Route the site through guarded_worktree_remove / guarded_reset_hard / guarded_merge_abort / "
        "guarded_worktree_prune / guarded_branch_delete (or, for a tool-owned scratch tree, "
        f"consolidation.workspace.remove_scratch_worktree): {describe_unexpected(unexpected, sources, _find_destructive_literals)}"
    )


def test_guard_internal_modules_exist() -> None:
    """A renamed guard module must not silently drop out of the exclusion (and make the scan vacuous)."""
    missing = sorted(rel for rel in _GUARD_INTERNAL_MODULES if not (REPO_ROOT / rel).is_file())
    assert not missing, f"Guard module(s) no longer exist: {missing}"


# ---------------------------------------------------------------------------
# Positive routing proof (C-003): the LIVE user-facing force-removal call
# sites actually reach the shared chokepoint. The scan above proves no
# UNROUTED raw literal exists anywhere; this proves the specific known routed
# sites are not merely "absent because the file doesn't exist".
# ---------------------------------------------------------------------------
_ROUTED_WORKTREE_REMOVE_SITES: tuple[str, ...] = (
    "specify_cli/consolidation/phase_teardown.py",
    "specify_cli/coordination/workspace.py",
    "specify_cli/orchestrator_api/consolidation.py",
)


def test_live_worktree_removal_sites_route_through_the_guard() -> None:
    """C-003: merge lane cleanup, coordination teardown+stale-prune, and
    orchestrator cleanup each call ``guarded_worktree_remove`` -- not a raw
    ``git worktree remove --force``."""
    missing = [rel for rel in _ROUTED_WORKTREE_REMOVE_SITES if "guarded_worktree_remove(" not in (SRC_ROOT / rel).read_text(encoding="utf-8")]
    assert not missing, f"Expected routed site(s) no longer call guarded_worktree_remove(...): {missing}"


# ---------------------------------------------------------------------------
# Self-mutation (non-vacuity) proof for the literal gate.
# ---------------------------------------------------------------------------

_PLANTED_ARGV: dict[str, str] = {
    _RESET_HARD: '["git", "reset", "--hard", "HEAD"]',
    _WORKTREE_REMOVE_FORCE: '["git", "worktree", "remove", str(worktree), "--force"]',
    _WORKTREE_PRUNE: '["git", "worktree", "prune"]',
    _MERGE_ABORT: '["git", "merge", "--abort"]',
    _STASH_PUSH: '["git", "stash", "push"]',
    _STASH_DROP: '["git", "stash", "drop"]',
    _BRANCH_DELETE_FORCE: '["git", "branch", "-D", name]',
    _CLEAN_FORCE: '["git", "clean", "-fdx"]',
    _CHECKOUT_FORCE: '["git", "checkout", "--force", ref]',
}


def _planted_source(argv: str) -> str:
    return f"import subprocess\n\n\ndef _sneaky(worktree, name, ref):\n    subprocess.run({argv})\n"


@pytest.mark.parametrize("pattern", sorted(_PLANTED_ARGV))
def test_scanner_detects_a_planted_literal_for_every_needle(tmp_path: Path, pattern: str) -> None:
    """Each destructive command is caught by the exact scanner the gate runs."""
    hits = scan_planted_source(tmp_path, "planted.py", _planted_source(_PLANTED_ARGV[pattern]), _find_destructive_literals)
    assert hits == [(5, pattern)], f"Non-vacuity failure: the scanner did not detect a planted {pattern!r} literal. Got: {hits!r}."


def test_every_needle_has_a_planted_proof() -> None:
    """A new needle must come with its non-vacuity proof."""
    assert set(_PLANTED_ARGV) == set(_PATTERN_NEEDLES) | {_CLEAN_FORCE}


@pytest.mark.parametrize("argv", ['["git", "checkout", "-f", ref]', '["git", "clean", "--force", "-d"]', '["git", "clean", "-xdf"]'])
def test_scanner_detects_the_alternate_spellings(tmp_path: Path, argv: str) -> None:
    hits = scan_planted_source(tmp_path, "planted_alt.py", _planted_source(argv), _find_destructive_literals)
    assert [pattern for _, pattern in hits] in ([_CHECKOUT_FORCE], [_CLEAN_FORCE])


def test_scanner_resolves_module_constant_indirection(tmp_path: Path) -> None:
    """The real ``_GIT_WORKTREE = "worktree"`` indirection
    (``coordination/workspace.py``) must not evade detection -- a
    name-only-literal scanner would be structurally blind to it, a live
    false-negative vacuity risk."""
    hits = scan_planted_source(
        tmp_path,
        "planted_indirection.py",
        "import subprocess\n\n"
        '_GIT_WORKTREE = "worktree"\n\n\n'
        "def _remove(repo_root, path):\n"
        '    subprocess.run(["git", "-C", str(repo_root), _GIT_WORKTREE, "remove", "--force", str(path)])\n',
        _find_destructive_literals,
    )
    assert hits == [(7, _WORKTREE_REMOVE_FORCE)], (
        f"Non-vacuity failure: the scanner did not resolve a module-level string-constant indirection for the destructive-command literal. Got: {hits!r}."
    )


def test_scanner_does_not_flag_unrelated_calls(tmp_path: Path) -> None:
    """Control: benign git argv (``worktree add/list``, ``branch -d``, ``checkout main``,
    ``clean -n``, ``stash list``) must not be flagged -- proves the scanner isn't
    simply matching on the command word (vacuous in the OTHER direction)."""
    hits = scan_planted_source(
        tmp_path,
        "planted_benign.py",
        "import subprocess\n\n\n"
        "def _benign(repo_root, path, branch):\n"
        '    subprocess.run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"])\n'
        '    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", str(path), branch])\n'
        '    subprocess.run(["git", "branch", "-d", branch])\n'
        '    subprocess.run(["git", "checkout", branch])\n'
        '    subprocess.run(["git", "clean", "-n"])\n'
        '    subprocess.run(["git", "stash", "list"])\n',
        _find_destructive_literals,
    )
    assert hits == []


def test_the_guard_modules_do_hold_literals_when_not_excluded() -> None:
    """Non-vacuity of the exclusion: scanned WITHOUT it, the guard modules carry real literals,
    so the finder demonstrably sees them and the module-level exclusion is what keeps them out."""
    unfiltered = {rel: _find_destructive_literals_unfiltered(REPO_ROOT / rel) for rel in _GUARD_INTERNAL_MODULES}
    assert all(unfiltered.values()), unfiltered
    patterns = {pattern for hits in unfiltered.values() for _, pattern in hits}
    assert {_RESET_HARD, _WORKTREE_REMOVE_FORCE, _MERGE_ABORT, _WORKTREE_PRUNE, _BRANCH_DELETE_FORCE} <= patterns


def test_a_literal_planted_in_the_live_tree_turns_the_gate_red() -> None:
    """Self-mutation: add one raw literal to a copy of a real module and the very check the gate runs reports it (only that file is rescanned)."""
    victim = "src/specify_cli/consolidation/workspace.py"
    sources = {victim: (REPO_ROOT / victim).read_text(encoding="utf-8") + '\n\ndef _planted_sneaky(root):\n    return ["git", "reset", "--hard", "HEAD"]\n'}

    unexpected = _unexpected(sources)

    assert [(key.rel, key.qualname, key.op) for key in unexpected] == [(victim, "_planted_sneaky", _RESET_HARD)]


def test_the_exclusion_is_by_module_not_by_name(tmp_path: Path) -> None:
    """A copy of the literal in a differently named module is NOT excluded."""
    hits = scan_planted_source(tmp_path, "not_the_guard.py", _planted_source(_PLANTED_ARGV[_RESET_HARD]), _find_destructive_literals)
    assert hits


# ---------------------------------------------------------------------------
# Recursive-deletion gate (research D7): no bare shutil.rmtree.
# ---------------------------------------------------------------------------

#: The modules that PROVE ownership at run time before a recursive delete. Named constants with a
#: reason each, not ``CensusKey`` rows: adding one is a reviewed edit of this mapping.
_RMTREE_PERMITTED: dict[str, str] = {
    "src/kernel/tree_removal.py": "remove_tool_owned_tree proves the path lies inside the owned root and holds no .git",
    "src/specify_cli/git/destructive_guard.py": "guarded_tree_delete deletes a checkout only after the only-copy scan",
    "src/specify_cli/asset_preservation/guard.py": "the asset-preservation guard removes only a path the manifest prover owns",
    "src/charter/activation/synthesizer/path_guard.py": "PathGuard.rmtree confines the delete to the synthesizer's allowed write surface",
}


def _is_shutil_rmtree_reference(node: _ast.AST, modules: Mapping[str, str], imported: Mapping[str, tuple[str, str]]) -> bool:
    """``shutil.rmtree`` (any import spelling), a bare name bound by ``from shutil import rmtree [as x]``, or that import itself."""
    if isinstance(node, _ast.Attribute):
        return node.attr == "rmtree" and isinstance(node.value, _ast.Name) and modules.get(node.value.id) == "shutil"
    if isinstance(node, _ast.Name):
        return isinstance(node.ctx, _ast.Load) and imported.get(node.id) == ("shutil", "rmtree")
    if isinstance(node, _ast.ImportFrom):
        return node.module == "shutil" and any(alias.name == "rmtree" for alias in node.names)
    return False


def _find_rmtree_references(path: Path) -> list[int]:
    """Line numbers of every reference to ``shutil.rmtree`` in *path*: a call, an ``atexit.register(shutil.rmtree, ...)``,
    a ``functools.partial`` or a ``from shutil import rmtree [as x]`` alias, however ``shutil`` was imported."""
    tree = parse(path)
    modules = import_alias_map(tree)
    imported = from_import_map(tree)
    return sorted({node.lineno for node in _ast.walk(tree) if _is_shutil_rmtree_reference(node, modules, imported)})


def _rmtree_offenders(sources: Mapping[str, str]) -> dict[str, list[int]]:
    live = scan_sources_for_lines(sources, _find_rmtree_references)
    return {rel: lines for rel, lines in live.items() if rel not in _RMTREE_PERMITTED}


def scan_sources_for_lines(sources: Mapping[str, str], finder: Callable[[Path], list[int]]) -> dict[str, list[int]]:
    """Run a line-number *finder* over in-memory sources (written to a temp tree at the same relative path)."""
    found: dict[str, list[int]] = {}
    with tempfile.TemporaryDirectory(prefix="rmtree-scan-") as tmp:
        for rel, source in sources.items():
            copy = Path(tmp) / rel
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(source, encoding="utf-8")
            lines = finder(copy)
            if lines:
                found[rel] = lines
    return found


def test_no_bare_rmtree_outside_the_ownership_proving_modules() -> None:
    """A recursive delete that cannot prove tool ownership at run time is the #5965/#5966 defect class."""
    offenders = _rmtree_offenders(_live_sources())

    assert not offenders, (
        "shutil.rmtree referenced outside the ownership-proving modules. Use kernel.tree_removal.remove_tool_owned_tree "
        "(a tree the tool owns) or git.destructive_guard.guarded_tree_delete (a git checkout): "
        f"{offenders}"
    )


def test_rmtree_permitted_modules_exist_and_each_still_references_it() -> None:
    """No dead exemption: a permitted module that no longer references ``shutil.rmtree`` is removed from the mapping."""
    stale = sorted(rel for rel in _RMTREE_PERMITTED if not (REPO_ROOT / rel).is_file() or not _find_rmtree_references(REPO_ROOT / rel))
    assert not stale, f"Permitted rmtree module(s) with no rmtree reference left: {stale}"


@pytest.mark.parametrize(
    "source",
    [
        "import shutil\n\n\ndef f(p):\n    shutil.rmtree(p)\n",
        "import shutil as sh\n\n\ndef f(p):\n    sh.rmtree(p)\n",
        "from shutil import rmtree\n\n\ndef f(p):\n    rmtree(p)\n",
        "from shutil import rmtree as rm\n\n\ndef f(p):\n    rm(p)\n",
        "import atexit\nimport shutil\n\n\ndef f(p):\n    atexit.register(shutil.rmtree, p)\n",
        "import shutil\n\n\ndef f():\n    import functools\n    return functools.partial(shutil.rmtree, ignore_errors=True)\n",
    ],
    ids=["call", "module-alias", "from-import", "from-import-alias", "atexit-register", "partial"],
)
def test_rmtree_scanner_detects_every_spelling(tmp_path: Path, source: str) -> None:
    """Self-mutation: a planted ``shutil.rmtree`` in any spelling is caught by the gate's own scanner."""
    assert scan_planted_source(tmp_path, "planted_rmtree.py", source, _find_rmtree_references)


def test_rmtree_scanner_ignores_other_rmtree_methods_and_shutil_functions(tmp_path: Path) -> None:
    """Control: ``PathGuard.rmtree`` (a method) and ``shutil.copytree`` are not a bare ``shutil.rmtree``."""
    source = "import shutil\n\n\ndef f(guard, a, b):\n    guard.rmtree(a)\n    shutil.copytree(a, b)\n"
    assert scan_planted_source(tmp_path, "planted_ok.py", source, _find_rmtree_references) == []


def test_a_rmtree_planted_in_the_live_tree_turns_the_gate_red() -> None:
    victim = "src/specify_cli/consolidation/workspace.py"
    sources = {victim: (REPO_ROOT / victim).read_text(encoding="utf-8") + "\n\ndef _planted(path):\n    import shutil\n\n    shutil.rmtree(path)\n"}

    assert list(_rmtree_offenders(sources)) == [victim]


# ---------------------------------------------------------------------------
# Tool-owned confinement: CheckoutRole.TOOL_OWNED makes EVERY path disposable.
# ---------------------------------------------------------------------------

#: The modules that may name ``CheckoutRole.TOOL_OWNED``: the role's own definition, and the modules that
#: create scratch, cache or just-created checkouts. Anywhere else it would be an escape hatch.
_TOOL_OWNED_PERMITTED: dict[str, str] = {
    "src/specify_cli/coordination/coherence.py": "defines the role and its is_disposable_residue rule",
    "src/specify_cli/consolidation/workspace.py": "the merge/baseline/numbering scratch worktrees and the merge workspace",
    "src/specify_cli/charter_packs/sources/git_source.py": "the pack-source cache clone under the tool's own cache root",
    "src/specify_cli/core/mission_creation_rollback.py": "rollback deletes only the directories this very Mission creation just made",
}


def _is_tool_owned_reference(node: _ast.AST, imported: Mapping[str, tuple[str, str]]) -> bool:
    """``CheckoutRole.TOOL_OWNED``, or a bare name bound by ``from ... import TOOL_OWNED [as x]``."""
    if isinstance(node, _ast.Attribute):
        return node.attr == "TOOL_OWNED" and isinstance(node.value, _ast.Name) and node.value.id == "CheckoutRole"
    if isinstance(node, _ast.Name):
        return isinstance(node.ctx, _ast.Load) and imported.get(node.id, ("", ""))[1] == "TOOL_OWNED"
    return False


def _find_tool_owned_references(path: Path) -> list[int]:
    """Line numbers naming ``CheckoutRole.TOOL_OWNED`` (or a bare ``TOOL_OWNED`` imported from ``coherence``)."""
    tree = parse(path)
    imported = from_import_map(tree)
    return sorted({node.lineno for node in _ast.walk(tree) if _is_tool_owned_reference(node, imported)})


def _tool_owned_offenders(sources: Mapping[str, str]) -> dict[str, list[int]]:
    live = scan_sources_for_lines(sources, _find_tool_owned_references)
    return {rel: lines for rel, lines in live.items() if rel not in _TOOL_OWNED_PERMITTED}


def test_tool_owned_role_is_confined_to_the_scratch_and_cache_modules() -> None:
    offenders = _tool_owned_offenders(_live_sources())

    assert not offenders, f"CheckoutRole.TOOL_OWNED named outside the modules that own scratch/cache checkouts: {offenders}"


def test_tool_owned_permitted_modules_each_still_name_the_role() -> None:
    stale = sorted(rel for rel in _TOOL_OWNED_PERMITTED if not (REPO_ROOT / rel).is_file() or not _find_tool_owned_references(REPO_ROOT / rel))
    assert not stale, f"Permitted TOOL_OWNED module(s) that no longer name the role: {stale}"


def test_tool_owned_scanner_detects_a_planted_use(tmp_path: Path) -> None:
    source = "from specify_cli.coordination.coherence import CheckoutRole, ResidueContext\n\nCTX = ResidueContext(role=CheckoutRole.TOOL_OWNED)\n"
    assert scan_planted_source(tmp_path, "planted_owned.py", source, _find_tool_owned_references) == [3]
    bare = "from specify_cli.coordination.coherence import TOOL_OWNED\n\nROLE = TOOL_OWNED\n"
    assert scan_planted_source(tmp_path, "planted_owned_bare.py", bare, _find_tool_owned_references) == [3]


def test_a_tool_owned_use_planted_in_the_live_tree_turns_the_gate_red() -> None:
    victim = "src/specify_cli/status/doctor_husks.py"
    sources = {victim: (REPO_ROOT / victim).read_text(encoding="utf-8") + "\n\n_PLANTED = CheckoutRole.TOOL_OWNED\n"}

    assert list(_tool_owned_offenders(sources)) == [victim]


# ---------------------------------------------------------------------------
# Named-intent pin: only --force-recreate may skip the unique-commit check.
# ---------------------------------------------------------------------------

_OPERATOR_INTENT_CALLERS: frozenset[tuple[str, str]] = frozenset({("src/specify_cli/missions/_create.py", "_delete_branch")})
_GUARDED_BRANCH_DELETE = "guarded_branch_delete"


def _operator_intent_callers(path: Path) -> list[tuple[int, str]]:
    """``(lineno, enclosing qualname)`` of each ``guarded_branch_delete(..., operator_intent=...)`` call in *path*."""
    source = path.read_text(encoding="utf-8")
    callers: list[tuple[int, str]] = []
    for node in _ast.walk(_ast.parse(source)):
        if not isinstance(node, _ast.Call) or not any(keyword.arg == "operator_intent" for keyword in node.keywords):
            continue
        func = node.func
        name = func.attr if isinstance(func, _ast.Attribute) else func.id if isinstance(func, _ast.Name) else ""
        if name == _GUARDED_BRANCH_DELETE:
            callers.append((node.lineno, composite_key(source, node.lineno)[0]))
    return callers


def test_only_force_recreate_passes_an_operator_intent() -> None:
    live = {
        (rel, qualname)
        for root in _SCAN_ROOTS
        for path in iter_py_files(root)
        for rel in [path.relative_to(REPO_ROOT).as_posix()]
        if not rel.endswith("git/destructive_guard.py")
        for _, qualname in _operator_intent_callers(path)
    }

    assert live == _OPERATOR_INTENT_CALLERS


def test_operator_intent_scanner_detects_a_planted_caller(tmp_path: Path) -> None:
    source = (
        "from specify_cli.git.destructive_guard import guarded_branch_delete\n\n\n"
        "def sneaky(root):\n"
        "    guarded_branch_delete(root, 'b', creation_base=None, operator_intent='force_recreate')\n"
    )
    assert [qualname for _, qualname in scan_planted_source(tmp_path, "planted_intent.py", source, _operator_intent_callers)] == ["sneaky"]


# ---------------------------------------------------------------------------
# CensusKey construction (T018): ordinals, file and op separation, rendering.
# ---------------------------------------------------------------------------

_TWIN_SOURCE = (
    "import subprocess\n\n\n"
    "def rollback(wt):\n"
    '    subprocess.run(["git", "-C", wt, "merge", "--abort"])\n'
    "    wt.touch()\n"
    '    subprocess.run(["git", "-C", wt, "merge", "--abort"])\n'
)


def test_census_keys_assign_ordinals_to_a_same_key_pair() -> None:
    """Two identical ops in one function share ``(qualname, token_line, op)``
    and are told apart only by ``op_ordinal``, in line order."""
    keys = census_keys("pkg/mod.py", _TWIN_SOURCE, [(7, _MERGE_ABORT), (5, _MERGE_ABORT)])
    token_line = "subprocess . run ( [ , , wt , , ] )"
    assert keys == {
        CensusKey("pkg/mod.py", "rollback", token_line, _MERGE_ABORT, 0): 5,
        CensusKey("pkg/mod.py", "rollback", token_line, _MERGE_ABORT, 1): 7,
    }


def test_census_keys_are_distinct_across_files() -> None:
    """The same site in two files yields two keys: ``rel`` is part of the key."""
    first = census_keys("pkg/a.py", _TWIN_SOURCE, [(5, _MERGE_ABORT)])
    second = census_keys("pkg/b.py", _TWIN_SOURCE, [(5, _MERGE_ABORT)])
    assert first.keys().isdisjoint(second.keys())


def test_census_keys_are_distinct_across_ops() -> None:
    """Two op labels on one line never share an ordinal sequence."""
    keys = census_keys("pkg/mod.py", _TWIN_SOURCE, [(5, _MERGE_ABORT), (5, _RESET_HARD)])
    assert {(key.op, key.op_ordinal) for key in keys} == {(_MERGE_ABORT, 0), (_RESET_HARD, 0)}


def test_render_census_key_names_identity_line_and_tokens() -> None:
    """Failure output carries ``rel::qualname::op#ordinal``, the diagnostic line
    and the token line, so an author can write the ``CensusKey(...)`` literal."""
    [(key, lineno)] = census_keys("pkg/mod.py", _TWIN_SOURCE, [(7, _MERGE_ABORT)]).items()
    rendered = render_census_key(key, lineno)
    assert rendered == f"pkg/mod.py::rollback::{_MERGE_ABORT}#0 (line 7) tokens=subprocess . run ( [ , , wt , , ] )"


def test_census_partition_splits_unexpected_from_suppressed() -> None:
    """The shared seam: a live key absent from the allowlist is unexpected, a
    live allowlisted key is suppressed, and a stale allowlist key is neither."""
    live = {"kept": 10, "new": 20}
    allowlist = {"kept": "rationale", "gone": "rationale"}
    assert census_partition(live, allowlist) == ({"new"}, {"kept"})
