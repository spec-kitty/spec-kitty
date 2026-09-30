"""Non-vacuous FS-op ownership-routing gate (mission
``ownership-boundary-preservation-01M32KEN``, WP09/T025, FR-010/NFR-002/
NFR-004/NFR-006, ``contracts/ownership-guard-contract.md`` C3).

A non-vacuous architectural gate (DIRECTIVE_043) proving the data-loss class
this mission closes — ``init`` and the upgrade migrations deleting user-visible
command/skill/template/governance assets *by name* without proof of package
ownership — is closed BY CONSTRUCTION.

Because the ``asset_preservation`` guard **performs the removal itself** (contract
C1 invariant 0; mirrors ``git/destructive_guard.py::guarded_worktree_remove``),
a routed fix-site carries **no raw destructive literal at all**. The census
therefore has exactly two legitimate buckets:

* the guard's own implementation (``src/specify_cli/asset_preservation/`` — NOT
  in the scanned mutating-flow module set, so guard-internal ``rmtree``/
  ``unlink``/``rmdir`` never appear here); and
* the frozen, individually-rationalized, **shrink-only** ``_ALLOWLIST`` of
  genuinely-safe ops (ephemeral scratch, ``.worktrees/*`` teardown of
  package-generated dirs/symlinks, broken-symlink/package-state markers,
  overwrite-guarded relocations, backup-guarded discards, empty-only ``rmdir``,
  already-content-guarded exemplars, non-user machine surfaces).

A NEW raw destructive literal at any ``init``/migration site is neither ⇒ it
FAILS the gate by construction (contract C3.3). The gate refuses to absorb a
still-raw user-content site into the allowlist (a leftover un-routed op is a
regression, not an allowlist candidate — WP09 binding correction #3).

The five C3 invariants, each an assertion below:

1. **Census (live, AST).** ``test_every_destructive_literal_is_allowlisted``.
2. **Op-vocabulary exhaustiveness.** ``test_op_vocabulary_is_exhaustive`` — a
   destructive-shaped call the classifier does not recognise (e.g. a future
   ``os.removedirs``) FAILS, so it cannot silently evade the census.
3. **Routed sites are literal-free.** enforced jointly by the census (no raw
   literal outside the allowlist) and the per-module positive-routing check.
4. **Positive routing — pinned + completeness-checked.**
   ``test_pinned_routed_module_set_is_complete`` +
   ``test_each_routed_module_routes_and_is_allowlist_clean``: the required
   routed-module set is pinned to the WP02–WP08 authoritative surface and
   completeness-checked against the live set, so dropping a module fails.
5. **Self-mutation, both directions.**
   ``test_scanner_detects_a_planted_unrouted_op`` (planted op detected) and
   ``test_removing_an_allowlist_entry_reproduces_a_gate_failure`` (drop one real
   entry ⇒ reproduces the failure). Shrink-only: a vanished site only WARNS.

MODULE-COARSE caveat (contract C3.4 — do not over-trust this gate)
------------------------------------------------------------------
Positive routing is proven at MODULE granularity: a routed module both calls
into ``asset_preservation`` and carries no un-allowlisted raw literal. It does
NOT prove per-PATH preservation — e.g. that ``init`` preserves
``.kittify/command-templates`` while still deleting the package-managed
``templates``/``.scratch`` at the single ``guard_destructive_removal`` call in
its 3-name cleanup loop. Those per-path guarantees ride on the C4 behavioural
WP tests (the preserve/owned-delete pairs), not on this architectural gate.
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SPECIFY_CLI_ROOT,
    CensusKey,
    assert_changed_argument_is_unexpected,
    assert_partition_survives_drift,
    assert_second_identical_op_is_unexpected,
    census_keys,
    census_keys_for_sources,
    census_partition,
    describe_unexpected,
    diff_against_allowlist,
    drop_one_entry,
    enclosing_qualname,
    from_import_map,
    import_alias_map,
    iter_py_files,
    parse,
    read_sources,
    render_census_key,
    scan_planted_source,
    with_leading_argument,
)

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Scanned module set: init.py + agent/config.py + research.py + every upgrade
# migration. The guard's OWN implementation lives in
# src/specify_cli/asset_preservation/ and
# is deliberately NOT in this set, so its chokepoint rmtree/unlink/rmdir never
# reach the census (contract C3.1 / data-model.md).
#
# research.py (WP02/#4926/FR-004) routes its destructive OVERWRITE through
# ``guard_destructive_overwrite`` — a distinct primitive from
# ``guard_destructive_removal`` that ``_calls_guard_destructive_removal``
# below does not recognise — so research.py is scanned for raw literals but
# deliberately NEVER joins ``_ROUTED_MODULES`` below. See
# ``test_research_py_removal_literals_are_never_allowlisted`` for the
# explicit fail-closed guard this asymmetry requires.
#
# runtime/migrate.py (mission asset-preservation-migrate-fetch, #4961) routes
# its per-project asset removal through ``guard_destructive_removal`` (the
# guard performs the delete on a proven byte-identical counterpart, preserving
# any differing/unprovable file), so it JOINS ``_ROUTED_MODULES`` — its one raw
# literal is an empty-only ``Path.rmdir`` (allowlisted below).
#
# doctrine/sources/git_source.py (#4960/#4989) preserves hand-authored packs
# via a temp-clone + move-aside pattern and a dirty/ahead-guarded reset — NOT
# the removal guard — so it is scanned for raw literals but deliberately NEVER
# joins ``_ROUTED_MODULES``. Its only raw removals are ephemeral-temp cleanups
# (allowlisted below); see ``test_git_source_removal_literals_only_target_ephemeral_temps``
# for the explicit fail-closed guard that a user-content removal can never be
# allowlisted for it.
# ---------------------------------------------------------------------------
_INIT_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "init.py"
_AGENT_CONFIG_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "agent" / "config.py"
_RESEARCH_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "research.py"
_MIGRATE_PY = SPECIFY_CLI_ROOT / "runtime" / "migrate.py"
_GIT_SOURCE_PY = SPECIFY_CLI_ROOT / "doctrine" / "sources" / "git_source.py"
_MIGRATIONS_DIR = SPECIFY_CLI_ROOT / "upgrade" / "migrations"

_GUARD_CALL = "guard_destructive_removal("
_RESEARCH_PY_REL = "src/specify_cli/cli/commands/research.py"
_GIT_SOURCE_REL = "src/specify_cli/doctrine/sources/git_source.py"

#: The ONLY first-argument variable names a git_source.py raw removal may
#: target: the ephemeral ``.tmp-<uuid>`` clone and the ``.old-<uuid>``
#: move-aside backup THIS fetch created — never ``target_dir`` (the operator's
#: hand-authored pack). See ``test_git_source_removal_literals_only_target_ephemeral_temps``.
_GIT_SOURCE_EPHEMERAL_TARGETS: frozenset[str] = frozenset({"tmp_dir", "old_dir"})


def _module_set() -> list[Path]:
    return [
        _INIT_PY,
        _AGENT_CONFIG_PY,
        _RESEARCH_PY,
        _MIGRATE_PY,
        _GIT_SOURCE_PY,
        *iter_py_files(_MIGRATIONS_DIR),
    ]


# ---------------------------------------------------------------------------
# Op classifier. ``_CLASSIFIER_ATTRS`` are the destructive attribute names the
# census recognises and routes/allowlists; ``_REFERENCE_ATTRS`` is the broader
# exhaustiveness reference (adds ``removedirs``) so a destructive-shaped call
# the classifier does NOT map is caught by the exhaustiveness self-test rather
# than silently evading the census (contract C3.2).
#
# SCOPE: both vocabularies cover the *removal* family only (rmtree/unlink/
# remove/rmdir/removedirs/shutil.move). The *overwrite* family — ``os.replace``/
# ``os.rename``/``os.renames``/``Path.replace`` — is deliberately NOT in either
# set: those spellings are also the safe write-then-replace atomic-write
# primitive (``kernel.atomic``), indistinguishable from a destination-clobber by
# call syntax alone, so flagging them here would red the gate on the correct
# idiom. Covering destination-clobbering renames needs its own contract —
# tracked by #4901 (the overwrite half of the asset-loss class this gate closes
# for the removal half). Do not add them to ``_REFERENCE_ATTRS`` without it.
# ---------------------------------------------------------------------------
_CLASSIFIER_ATTRS: frozenset[str] = frozenset({"rmtree", "move", "unlink", "remove", "rmdir"})
_REFERENCE_ATTRS: frozenset[str] = frozenset({"rmtree", "move", "unlink", "remove", "rmdir", "removedirs"})
_PATH_DELETE_METHODS: frozenset[str] = frozenset({"unlink", "rmdir"})
_MODULE_RECEIVERS: frozenset[str] = frozenset({"os", "shutil"})
#: Wrapper primitives that stand in for a raw removal at their call site
#: (``_safe_rmtree``/``_safe_unlink``). None exist in the tree today (the
#: former m_3_2_0rc45 wrappers were routed through the guard), but the
#: classifier keeps detecting them so a reintroduction is censused, not missed.
_WRAPPER_NAMES: frozenset[str] = frozenset({"_safe_rmtree", "_safe_unlink"})


def _attr_op(call: ast.Call, attrs: frozenset[str], module_aliases: Mapping[str, str]) -> str | None:
    """Canonical op label (``shutil.rmtree`` / ``os.unlink`` / ``Path.rmdir`` …)
    for a destructive *attribute* call restricted to *attrs*; ``None`` otherwise.

    ``remove``/``move``/``rmtree``/``removedirs`` count only when qualified by an
    ``os``/``shutil`` receiver (so ``list.remove(x)`` / ``str.replace`` never
    match); ``unlink``/``rmdir`` are Path deletion methods on any receiver.
    *module_aliases* resolves an aliased receiver (``import shutil as sh`` ->
    ``sh.rmtree(...)``) back to its canonical module name before the
    ``_MODULE_RECEIVERS`` check, so an alias is not invisible to the census.
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    attr = func.attr
    if attr not in attrs:
        return None
    recv = func.value
    recv_name = recv.id if isinstance(recv, ast.Name) else None
    canonical_recv = module_aliases.get(recv_name, recv_name) if recv_name is not None else None
    if canonical_recv in _MODULE_RECEIVERS:
        return f"{canonical_recv}.{attr}"
    if attr in _PATH_DELETE_METHODS:
        return f"Path.{attr}"
    return None


def _resolved_op(
    call: ast.Call,
    attrs: frozenset[str],
    module_aliases: Mapping[str, str],
    from_imports: Mapping[str, tuple[str, str]],
) -> str | None:
    """*attrs*-restricted op label for *call*, resolving BOTH an aliased
    attribute receiver (``import shutil as sh``) and a bare name bound by a
    ``from``-import (``from shutil import rmtree``) to the canonical
    ``module.attr`` label. A bare-``Name`` call not bound by a tracked
    ``from``-import is not a receiver-qualified op at all (a plain function
    call has no receiver to canonicalize) and returns ``None``.
    """
    func = call.func
    if isinstance(func, ast.Name):
        bound = from_imports.get(func.id)
        if bound is None:
            return None
        module, attr = bound
        if attr in attrs and module in _MODULE_RECEIVERS:
            return f"{module}.{attr}"
        return None
    return _attr_op(call, attrs, module_aliases)


def _classify_op(
    call: ast.Call,
    module_aliases: Mapping[str, str],
    from_imports: Mapping[str, tuple[str, str]],
) -> str | None:
    """The op label the census routes/allowlists, or ``None`` for a non-op call."""
    func = call.func
    if isinstance(func, ast.Name) and func.id in _WRAPPER_NAMES:
        return func.id
    return _resolved_op(call, _CLASSIFIER_ATTRS, module_aliases, from_imports)


def _find_destructive_ops(path: Path) -> list[tuple[int, str]]:
    """``(lineno, op)`` for every raw destructive literal the classifier maps in *path*."""
    tree = parse(path)
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            op = _classify_op(node, module_aliases, from_imports)
            if op is not None:
                hits.append((node.lineno, op))
    return hits


def _live_sources() -> dict[str, str]:
    """``{repo-rel path: source}`` for every file the census scans."""
    return read_sources(_module_set())


def _census_keys(sources: Mapping[str, str]) -> dict[CensusKey, int]:
    """Content-keyed live census: ``{CensusKey: lineno}`` (the line is diagnostic only)."""
    return census_keys_for_sources(sources, _find_destructive_ops)


# ---------------------------------------------------------------------------
# The frozen allowlist. Built from a LIVE AST census of the integrated lane
# tree (post WP01-WP08) reproduced by this file's own scanner. Every entry is a
# genuinely-safe op with a one-line rationale (NFR-006). Each entry is keyed by
# CONTENT, never by line (FR-006): ``CensusKey`` = (repo-relative path,
# enclosing qualname, normalized token line, op, op_ordinal among identical
# live sites in that function), so an unrelated line shift never re-pins it.
# Shrink-only: a site that disappears only WARNS; a NEW un-rationalized
# literal, a second identical op or a changed argument FAILS. Routed
# fix-sites are ABSENT here on purpose — they carry no raw literal. Rationale
# prose that cites an old line ("Re-pinned from :1596") is history, not a key.
# ---------------------------------------------------------------------------
_ALLOWLIST: dict[CensusKey, str] = {
    # --- runtime/migrate.py (1): empty-only rmdir after routed removal -----
    CensusKey(
        rel="src/specify_cli/runtime/migrate.py",
        qualname="_cleanup_empty_dirs",
        token_line="dirpath . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): (
        "empty-only rmdir (raises OSError on non-empty): _cleanup_empty_dirs prunes a "
        "now-empty SHARED_ASSET_DIRS directory ONLY inside an `if not any(dirpath.iterdir())` "
        "emptiness check, after execute_migration's routed guard_destructive_removal already "
        "removed the proven byte-identical files and preserved every differing one (#4961) — "
        "cannot lose content."
    ),
    # --- doctrine/sources/git_source.py (4): ephemeral temp-clone teardown -
    CensusKey(
        rel="src/specify_cli/doctrine/sources/git_source.py",
        qualname="GitSource._first_install",
        token_line="shutil . rmtree ( tmp_dir , ignore_errors = True )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): (
        "ephemeral temp cleanup (#4960): removes ONLY the `.tmp-<uuid>` clone dir this "
        "fetch created when `git clone` fails — target_dir is left exactly as found, never "
        "touched (scanned-not-routed: git_source.py preserves via temp-clone + move-aside, "
        "not the removal guard)."
    ),
    CensusKey(
        rel="src/specify_cli/doctrine/sources/git_source.py",
        qualname="GitSource._first_install",
        token_line="shutil . rmtree ( tmp_dir , ignore_errors = True )",
        op="shutil.rmtree",
        op_ordinal=1,
    ): (
        "ephemeral temp cleanup (#4960): removes ONLY the `.tmp-<uuid>` clone dir this fetch created when `git checkout <ref>` fails — target_dir is never touched."
    ),
    CensusKey(
        rel="src/specify_cli/doctrine/sources/git_source.py",
        qualname="GitSource._promote",
        token_line="shutil . rmtree ( tmp_dir , ignore_errors = True )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): (
        "ephemeral temp cleanup (#4960): _promote removes ONLY the `.tmp-<uuid>` clone dir on "
        "an OSError during the move-aside promote; a moved-aside target is restored from its "
        "`.old-<uuid>` backup, never rmtree'd."
    ),
    CensusKey(
        rel="src/specify_cli/doctrine/sources/git_source.py",
        qualname="GitSource._promote",
        token_line="shutil . rmtree ( old_dir , ignore_errors = True )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): (
        "ephemeral backup cleanup (#4960): _promote's finally-block removes the `.old-<uuid>` "
        "move-aside backup ONLY after `promoted` is True (a successful promote) — the previous "
        "content is already safely in place at target_dir."
    ),
    # --- cli/commands/agent/config.py (1): empty-only rmdir after guard ----
    CensusKey(
        rel="src/specify_cli/cli/commands/agent/config.py", qualname="_remove_project_agent_surface", token_line="root . rmdir ( )", op="Path.rmdir", op_ordinal=0
    ): (
        "empty-only rmdir: prunes the now-possibly-empty parent `root` only on the "
        "guard's owned branch (verdict.owned), after guard_destructive_removal already "
        "removed `surface` itself — raises OSError (caught) on a non-empty preserved dir."
    ),
    # --- init.py (4): ephemeral scratch, backup-guarded discard, marker ----
    CensusKey(
        rel="src/specify_cli/cli/commands/init.py",
        qualname="_finish_command_delivery",
        token_line="( project / _PENDING_COMMAND_SKILLS ) . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): (
        "package-state marker: unlinks the .kittify pending-command-skills record only after a "
        "changed-check raises — a machine-written pointer, never user content."
    ),
    CensusKey(
        rel="src/specify_cli/cli/commands/init.py",
        qualname="_discard_failed_project_scaffold",
        token_line="shutil . rmtree ( project_path )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): (
        "backup-guarded: _discard_failed_project_scaffold runs back_up_operator_subtrees(...) to "
        "project_path.parent FIRST, so operator subtrees are archived before the scaffold rmtree."
    ),
    CensusKey(rel="src/specify_cli/cli/commands/init.py", qualname="init", token_line="shutil . rmtree ( scratch )", op="shutil.rmtree", op_ordinal=0): (
        "ephemeral scratch: best-effort sweep of .kittify/.resolved-* / .merged-* resolver scratch "
        "dirs (name-prefixed, package-generated this run); the #4861 command-templates cleanup just "
        "above is routed through the guard (literal-free). Re-pinned from :1596 (WP02, mission "
        "ownership-boundary-overwrite-hardening-01M35ER3): WP03's cleanup edits shifted this single "
        "line down by 20 — verified LINE-SHIFT-ONLY (same op-kinds, same count of 4 literals in "
        "init.py as base; 136/453/677 sit above the edit region and are unaffected). Re-pinned again "
        "from :1616 (pre-PR squad BLOCKER, #4931 re-arm fix): the `copy_specify_base_from_local`/"
        "`copy_specify_base_from_package` call sites now capture a `TemplateCopyResult` and set "
        "`templates_dir_created_this_run` from its `templates_created` field instead of "
        "unconditionally, shifting this single line down by 6 — verified LINE-SHIFT-ONLY (same "
        "op-kinds, same count of 4 literals in init.py as base; 136/453/677 unaffected)."
    ),
    # --- m_0_10_0 (3): empty-only rmdir after preserve-all -----------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py",
        qualname="PythonOnlyMigration._remove_bash_scripts",
        token_line="kittify_bash . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): (
        "empty-only rmdir (raises on non-empty): removes .kittify/scripts/bash only when it is empty "
        "after the routed guard preserved every unprovable script — cannot lose content."
    ),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py",
        qualname="PythonOnlyMigration._remove_bash_scripts",
        token_line="kittify_ps . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes .kittify/scripts/powershell only when empty after preserve-all."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py",
        qualname="PythonOnlyMigration._cleanup_worktree_bash_scripts",
        token_line="wt_bash . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes a worktree .kittify/scripts/bash dir only when empty after the routed worktree-script preserve sweep."),
    # --- m_0_10_2 (1): empty-only rmdir after routed toml sweep ------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py",
        qualname="_sweep_legacy_command_tomls",
        token_line="commands_dir . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes .kittify/commands only when empty after the routed guard swept the legacy command tomls."),
    # --- m_0_10_8 (7): broken-symlink teardown + one relocation ------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="kittify_memory . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("broken-symlink teardown: removes a broken .kittify/memory symlink (is_symlink()-gated) before recreating it — never a real file."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="shutil . move ( str ( root_memory ) , str ( kittify_memory ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: moves root memory/ -> .kittify/memory only when the destination is absent (overwrite-guarded rename, not a delete)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="kittify_agents . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("broken-symlink teardown: removes a broken .kittify/AGENTS.md symlink (is_symlink()-gated)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="wt_memory . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("broken-symlink teardown: removes a broken worktree memory symlink (resolve()-checked broken)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="wt_memory . unlink ( )",
        op="Path.unlink",
        op_ordinal=1,
    ): ("broken-symlink teardown: removes a broken worktree memory symlink (OSError/RuntimeError resolve fallback — still symlink-only)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="wt_agents . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("broken-symlink teardown: removes a broken worktree AGENTS.md symlink (resolve()-checked)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        qualname="FixMemoryStructureMigration.apply",
        token_line="wt_agents . unlink ( )",
        op="Path.unlink",
        op_ordinal=1,
    ): ("broken-symlink teardown: removes a broken worktree AGENTS.md symlink (resolve fallback — symlink-only)."),
    # --- m_0_2_0 (2): overwrite-guarded relocation -------------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_2_0_specify_to_kittify.py",
        qualname="SpecifyToKittifyMigration.apply",
        token_line="shutil . move ( str ( specify_dir ) , str ( kittify_dir ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames the legacy .specify tree into .kittify (move, not delete)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_2_0_specify_to_kittify.py",
        qualname="SpecifyToKittifyMigration.apply",
        token_line="shutil . move ( str ( specs_dir ) , str ( kitty_specs_dir ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames a legacy .specify child into .kittify (move, not delete)."),
    # --- m_0_6_5 (2): relocation + worktree teardown -----------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_6_5_commands_rename.py",
        qualname="CommandsRenameMigration.apply.rename_dir",
        token_line="shutil . move ( str ( old ) , str ( new ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: rename_dir moves a package-generated commands dir to its new name (move)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_6_5_commands_rename.py",
        qualname="CommandsRenameMigration.apply",
        token_line="shutil . rmtree ( wt_templates_commands )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree's package-generated .kittify/templates/commands dir (regenerated from main), never operator content."),
    # --- m_0_7_2 (1): worktree teardown ------------------------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_7_2_worktree_commands_dedup.py",
        qualname="WorktreeCommandsDedupMigration.apply",
        token_line="shutil . rmtree ( wt_commands )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: dedups a worktree's package-generated commands dir that inherits from main."),
    # --- m_0_8_0_remove_active_mission (1): package-state marker -----------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_8_0_remove_active_mission.py",
        qualname="RemoveActiveMissionMigration.apply",
        token_line="active_mission . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("package-state marker: removes the retired machine-written active-mission pointer file."),
    # --- m_0_8_0_worktree_agents_symlink (1): worktree symlink teardown ----
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_8_0_worktree_agents_symlink.py",
        qualname="WorktreeAgentsSymlinkMigration.apply",
        token_line="wt_agents . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree AGENTS symlink before recreating the package-managed link."),
    # --- m_0_9_0 (2): source-after-move + emptiness-checked lane teardown --
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py",
        qualname="FrontmatterOnlyLanesMigration._migrate_feature",
        token_line="md_file . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("source-after-move: removes the original task md only after its content was written to the new tasks/ location (relocation, not loss)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py",
        qualname="FrontmatterOnlyLanesMigration._migrate_feature",
        token_line="shutil . rmtree ( lane_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("lane teardown, emptiness-checked: removes a legacy lane dir only after _get_real_contents confirms no real files remain (only .DS_Store/.gitkeep)."),
    # --- m_0_9_1 (7): source-after-move, lane + worktree teardown ----------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._migrate_remaining_files",
        token_line="item . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("source-after-move: removes the original file only after it was relocated to its new path."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._migrate_remaining_files",
        token_line="shutil . rmtree ( lane_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("lane teardown, emptiness-checked: removes a legacy lane dir once its real contents are gone."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._cleanup_worktrees",
        token_line="commands_dir . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree commands symlink that inherits from main."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._cleanup_worktrees",
        token_line="shutil . rmtree ( commands_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree's package-generated commands dir (inherits from main)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._cleanup_worktrees",
        token_line="parent . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes the now-empty parent dir after the worktree commands teardown."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._cleanup_worktrees",
        token_line="scripts_dir . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree .kittify/scripts symlink that inherits from main."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py",
        qualname="CompleteLaneMigration._cleanup_worktrees",
        token_line="shutil . rmtree ( scripts_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree's package-generated .kittify/scripts dir."),
    # --- m_2_0_0 (1): already-content-guarded exemplar ---------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_0_retire_git_hooks.py",
        qualname="RetireGitHooksMigration.apply",
        token_line="hook_path . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("already-content-guarded exemplar (data-model do-not-change): retires a package-installed git hook only after content identity is confirmed."),
    # --- m_2_0_6 (5): worktree teardown + empty-only rmdir -----------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py",
        qualname="_cleanup_legacy_worktree_assets",
        token_line="commands_dir . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree commands symlink that inherits from main."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py",
        qualname="_cleanup_legacy_worktree_assets",
        token_line="shutil . rmtree ( commands_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree's package-generated commands dir."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py",
        qualname="_cleanup_legacy_worktree_assets",
        token_line="parent . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes the now-empty parent dir after the worktree commands teardown."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py",
        qualname="_cleanup_legacy_worktree_assets",
        token_line="scripts_dir . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree .kittify/scripts symlink that inherits from main."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py",
        qualname="_cleanup_legacy_worktree_assets",
        token_line="shutil . rmtree ( scripts_dir )",
        op="shutil.rmtree",
        op_ordinal=0,
    ): ("worktree teardown: removes a worktree's package-generated .kittify/scripts dir."),
    # --- m_2_0_7 (3): already-guarded exemplar + empty-only rmdir ----------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py",
        qualname="FixStaleOverridesMigration.apply",
        token_line="override_file . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("already-content-guarded exemplar (data-model do-not-change): removes a stale override only when it matches the package default."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py",
        qualname="_cleanup_empty_override_dirs",
        token_line="dirpath . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: prunes an empty override dir after stale-override cleanup."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py",
        qualname="_cleanup_empty_override_dirs",
        token_line="overrides_dir . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: prunes a second empty override dir after stale-override cleanup."),
    # --- m_2_1_3 (1): already-guarded exemplar -----------------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py",
        qualname="RestorePromptCommandsMigration.apply",
        token_line="thin_shim_file . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("already-content-guarded exemplar (data-model do-not-change): removes a stale prompt command under a content check while restoring the package prompts."),
    # --- m_3_1_1 (7): overwrite-guarded renames + empty-only rmdir ---------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._normalize_layouts",
        token_line="shutil . move ( str ( memory_constitution ) , str ( charter_dir / ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames memory/constitution.md -> charter/charter.md into a freshly-mkdir'd charter dir (move)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._normalize_layouts",
        token_line="shutil . move ( str ( item ) , str ( dest ) )",
        op="shutil.move",
        op_ordinal=0,
    ): (
        "relocation, overwrite-guarded: merges a constitution/ item into charter/ only when the "
        "destination does not exist; a collision is archived by the routed guard, never clobbered (#4862)."
    ),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._normalize_layouts",
        token_line="constitution_dir . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: removes the residual constitution/ dir after colliding items were archived/removed and merged items moved out — empty by construction."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._normalize_layouts",
        token_line="shutil . move ( str ( constitution_dir ) , str ( charter_dir ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames .kittify/constitution/ -> .kittify/charter/ (move)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._normalize_layouts",
        token_line="shutil . move ( str ( old_md ) , str ( new_md ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames charter/constitution.md -> charter/charter.md (move)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._rename_agent_artifacts",
        token_line="shutil . move ( str ( old_cmd ) , str ( new_cmd ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames a per-agent spec-kitty.constitution.md command to spec-kitty.charter.md (move)."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py",
        qualname="CharterRenameMigration._rename_agent_artifacts",
        token_line="shutil . move ( str ( old_skill ) , str ( new_skill ) )",
        op="shutil.move",
        op_ordinal=0,
    ): ("relocation: renames a per-agent constitution-doctrine skill dir to charter-doctrine (move)."),
    # --- m_3_1_2 (2): already-guarded exemplar + empty-only rmdir ----------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py",
        qualname="_SafeGlobalizeCommandsBase.apply",
        token_line="target . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("already-content-guarded exemplar (data-model do-not-change): removes a per-project command under a content/ownership check while globalizing."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py",
        qualname="_SafeGlobalizeCommandsBase.apply",
        token_line="agent_dir . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: prunes the now-empty per-project commands dir after globalization."),
    # --- m_3_2_0rc35 (2): already-guarded exemplar + empty-only rmdir ------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_2_0rc35_codex_to_skills.py",
        qualname="_move_owned_prompts",
        token_line="p . path . unlink ( )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("already-content-guarded exemplar (data-model do-not-change): _move_owned_prompts removes a prompt only after confirming package ownership."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_2_0rc35_codex_to_skills.py",
        qualname="_try_remove_empty_prompts_dir",
        token_line="prompts_dir . rmdir ( )",
        op="Path.rmdir",
        op_ordinal=0,
    ): ("empty-only rmdir: _try_remove_empty_prompts_dir removes the prompts dir only when empty."),
    # --- m_3_2_8 (1): atomic-write temp cleanup ----------------------------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_2_8_provision_kitty_env.py",
        qualname="_atomic_write_claudeignore",
        token_line="os . unlink ( tmp_path )",
        op="os.unlink",
        op_ordinal=0,
    ): ("ephemeral atomic-write temp: removes the just-written tmp file on an os.replace failure — a machine temp this function created, never user content."),
    # --- m_3_3_0 (2): atomic-write temp + non-user machine surface ---------
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_3_0_op_record_schema_v2.py",
        qualname="_atomic_rewrite",
        token_line="tmp_path . unlink ( missing_ok = True )",
        op="Path.unlink",
        op_ordinal=0,
    ): ("ephemeral atomic-write temp: finally-block cleanup (missing_ok) of the tmp file _atomic_rewrite created."),
    CensusKey(
        rel="src/specify_cli/upgrade/migrations/m_3_3_0_op_record_schema_v2.py",
        qualname="OpRecordSchemaV2Migration.apply",
        token_line="path . unlink ( missing_ok = True )",
        op="Path.unlink",
        op_ordinal=0,
    ): (
        "non-user machine surface: deletes an unsalvageable machine-written kitty-ops Op record "
        "(missing_ok), per the migration's own salvage plan — not a user asset."
    ),
}


# ---------------------------------------------------------------------------
# Pinned routed-module set (WP02-WP08 authoritative_surface). Paths relative to
# src/specify_cli. Completeness-checked against the live set below.
# ---------------------------------------------------------------------------
_ROUTED_MODULES: frozenset[str] = frozenset(
    {
        "cli/commands/init.py",
        "cli/commands/agent/config.py",
        "runtime/migrate.py",
        "upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py",
        "upgrade/migrations/m_3_1_1_charter_rename.py",
        "upgrade/migrations/m_0_10_0_python_only.py",
        "upgrade/migrations/m_0_10_2_update_slash_commands.py",
        "upgrade/migrations/m_2_0_11_remove_clarify_command.py",
        "upgrade/migrations/m_2_1_2_remove_release_skill.py",
        "upgrade/migrations/m_2_2_0_profile_context_deployment.py",
        "upgrade/migrations/m_3_2_0rc43_retire_profile_context_command.py",
        "upgrade/migrations/m_0_6_7_ensure_missions.py",
        "upgrade/migrations/m_unify_charter_activation_finalize.py",
    }
)


def _calls_guard_destructive_removal(tree: ast.Module) -> bool:
    """True when *tree* contains an actual ``ast.Call`` to
    ``guard_destructive_removal`` — either a bare-name call (the standard
    ``from specify_cli.asset_preservation import guard_destructive_removal``
    call-site shape) or a qualified attribute call (``module.
    guard_destructive_removal(...)``). AST-verified, not a text/substring
    match, so a mere comment mentioning the guard or the package name does
    not count as routed."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "guard_destructive_removal":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "guard_destructive_removal":
            return True
    return False


def _live_routed_modules() -> set[str]:
    """Modules in the scanned set that call into ``asset_preservation`` —
    proven by an actual AST ``Call`` to ``guard_destructive_removal``, not a
    substring match (a module that merely mentions it in a comment or
    docstring must not count as routed)."""
    routed: set[str] = set()
    for py_file in _module_set():
        tree = parse(py_file)
        if _calls_guard_destructive_removal(tree):
            routed.add(py_file.relative_to(SPECIFY_CLI_ROOT).as_posix())
    return routed


# ---------------------------------------------------------------------------
# C3.1 + C3.3 -- live census: every raw literal is allowlisted (routed sites
# are literal-free; the guard's own impl is out of the scanned set).
# ---------------------------------------------------------------------------


def _census_partition(sources: Mapping[str, str]) -> tuple[set[CensusKey], set[CensusKey]]:
    """This gate's binding of :func:`census_partition` (finder + ``_ALLOWLIST``)."""
    return census_partition(_census_keys(sources), _ALLOWLIST)


#: Files-scanned floor (NFR-002): the finder scanned 120 files on the planning
#: base (3717c7ea). A scan that silently shrinks below it is vacuous.
_FILES_SCANNED_FLOOR = 120

#: Every file carrying an allowlisted site; the line-drift test runs per file.
_DRIFT_FILES: tuple[str, ...] = tuple(sorted({key.rel for key in _ALLOWLIST}))

_NON_WIDENING_REL = "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py"
_NON_WIDENING_OP = "shutil.move"


def test_every_destructive_literal_is_allowlisted() -> None:
    sources = _live_sources()
    assert len(sources) >= _FILES_SCANNED_FLOOR, f"census scanned {len(sources)} files, below the pinned floor {_FILES_SCANNED_FLOOR}"
    unexpected, suppressed = _census_partition(sources)
    stale = set(_ALLOWLIST) - suppressed

    assert not unexpected, (
        "New raw destructive filesystem literal(s) found in the init/migration "
        "mutating-flow module set outside the frozen allowlist (FR-010/NFR-006). "
        "Route the removal through asset_preservation.guard_destructive_removal "
        "(the guard performs the delete, leaving no raw literal), or — only for a "
        "genuinely-safe op — add a one-line rationale entry to _ALLOWLIST. Do NOT "
        "absorb a still-raw user-content site into the allowlist: "
        f"{describe_unexpected(unexpected, sources, _find_destructive_ops)}"
    )
    assert suppressed, "Non-vacuity: the census suppressed no allowlisted site at all"
    if stale:
        warnings.warn(
            f"Shrink-only allowlist: the following site(s) no longer carry a raw destructive literal — safe to delete from _ALLOWLIST: {sorted(stale)}",
            UserWarning,
            stacklevel=1,
        )


def test_research_py_removal_literals_are_never_allowlisted() -> None:
    """research.py (WP02/#4926/FR-004) routes its destructive OVERWRITE through
    ``guard_destructive_overwrite`` — a primitive ``_calls_guard_destructive_removal``
    does not recognise — so research.py can never join ``_ROUTED_MODULES`` and
    the positive-routing check (``test_each_routed_module_routes_and_is_allowlist_clean``)
    cannot prove its fabrication was routed away. Without this explicit,
    static guard, an implementer could satisfy the live census by adding a
    research.py raw removal literal to ``_ALLOWLIST`` with a rationale instead
    of actually deleting the unlink()+touch() fabrication (T021) — the census
    would go green while the #4926 destroyer silently returned. Fail closed,
    independent of the live scan: no
    ``CensusKey`` with ``rel == "src/specify_cli/cli/commands/research.py"`` may EVER appear in
    ``_ALLOWLIST``. Makes FR-004/SC-005's "the census refuses to allowlist a
    raw user-content op" claim actually backed for the one module WP02 adds."""
    research_keys = sorted(render_census_key(key) for key in _ALLOWLIST if key.rel == _RESEARCH_PY_REL)
    assert not research_keys, (
        "research.py literal(s) present in _ALLOWLIST — its destructive-overwrite "
        "fabrication must be routed through guard_destructive_overwrite (T021), "
        f"never allowlisted: {research_keys}"
    )


def _git_source_removal_targets() -> dict[int, str | None]:
    """Map each git_source.py destructive-removal literal line -> the name of its
    first positional argument (``None`` when it is not a bare ``Name``).

    Used by the fail-closed never-allowlist guard below to prove that every
    allowlisted git_source.py removal targets an ephemeral temp/backup variable,
    never ``target_dir``.
    """
    tree = parse(_GIT_SOURCE_PY)
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    targets: dict[int, str | None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _classify_op(node, module_aliases, from_imports) is not None:
            first = node.args[0] if node.args else None
            targets[node.lineno] = first.id if isinstance(first, ast.Name) else None
    return targets


def test_git_source_removal_literals_only_target_ephemeral_temps() -> None:
    """git_source.py (#4960/#4989) is scanned-but-NOT-routed: it preserves
    hand-authored packs via a temp-clone + move-aside pattern and a
    dirty/ahead-guarded reset, NOT ``guard_destructive_removal``. Its only
    legitimate raw removals are of the ephemeral ``.tmp-<uuid>`` clone and the
    ``.old-<uuid>`` move-aside backup THIS fetch created — never ``target_dir``
    (the operator's pack).

    Mirrors ``test_research_py_removal_literals_are_never_allowlisted``: without
    this static, fail-closed guard an implementer could satisfy the live census
    by adding a ``shutil.rmtree(target_dir)`` (destroying the operator pack) to
    ``_ALLOWLIST`` behind a benign rationale, and the census would go green while
    the destroyer silently returned. Independent of the live scan: every
    allowlisted ``git_source.py`` removal literal must, in the actual on-disk
    source, pass one of ``_GIT_SOURCE_EPHEMERAL_TARGETS`` as its first positional
    argument. A line with no recognised removal call (``None``) also fails —
    fail-closed against a stale entry whose content key no longer matches a live site."""
    targets = _git_source_removal_targets()
    live_linenos = _census_keys(read_sources([_GIT_SOURCE_PY]))
    offenders: dict[str, str | None] = {}
    for key in _ALLOWLIST:
        if key.rel != _GIT_SOURCE_REL:
            continue
        lineno = live_linenos.get(key)
        target = targets.get(lineno) if lineno is not None else None
        if target not in _GIT_SOURCE_EPHEMERAL_TARGETS:
            offenders[render_census_key(key, lineno)] = target
    assert not offenders, (
        "Allowlisted git_source.py removal literal(s) do not target an ephemeral "
        f"temp/backup ({sorted(_GIT_SOURCE_EPHEMERAL_TARGETS)}) — a user-content "
        "removal (e.g. shutil.rmtree(target_dir)) must NEVER be allowlisted; route "
        "the fix or fix the key. Offending entry -> first-arg name: "
        f"{offenders}"
    )


def test_allowlisted_files_exist() -> None:
    """A renamed/deleted allowlisted file must not silently drop out of the scan
    (an absent file reads as zero live hits — a false 'shrink' masking a rename
    the allowlist should track)."""
    rel_paths = {key.rel for key in _ALLOWLIST}
    missing = sorted(rel for rel in rel_paths if not (REPO_ROOT / rel).is_file())
    assert not missing, f"Allowlisted file(s) no longer exist: {missing}"


# ---------------------------------------------------------------------------
# C3.2 -- op-vocabulary exhaustiveness: no destructive-shaped call in the
# module set is left unclassified.
# ---------------------------------------------------------------------------


def _unhandled_reference_ops(path: Path) -> list[tuple[int, str]]:
    """Destructive-shaped calls (reference vocabulary) the classifier does NOT
    map — i.e. would silently evade the census (e.g. a future ``os.removedirs``)."""
    tree = parse(path)
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    unhandled: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            ref = _resolved_op(node, _REFERENCE_ATTRS, module_aliases, from_imports)
            if ref is not None and _classify_op(node, module_aliases, from_imports) is None:
                unhandled.append((node.lineno, ref))
    return unhandled


def test_op_vocabulary_is_exhaustive() -> None:
    offenders: dict[str, list[tuple[int, str]]] = {}
    for py_file in _module_set():
        hits = _unhandled_reference_ops(py_file)
        if hits:
            offenders[py_file.relative_to(REPO_ROOT).as_posix()] = hits
    assert not offenders, (
        "Destructive-shaped filesystem call(s) present in the module set that the "
        "census classifier does NOT recognise (contract C3.2). A future op like "
        "os.removedirs must be added to _CLASSIFIER_ATTRS (and routed/allowlisted) "
        f"so it cannot silently evade the census: {offenders}"
    )


# ---------------------------------------------------------------------------
# C3.4 -- positive routing, pinned + completeness-checked.
# ---------------------------------------------------------------------------


def test_calls_guard_destructive_removal_requires_an_actual_call() -> None:
    """A module that merely MENTIONS the guard's name or the package name (a
    comment, a docstring, a string constant) must not read as routed — only a
    real ``ast.Call`` counts. Proves ``_live_routed_modules`` is AST-verified,
    not a substring match, before trusting the pinned-set comparison below."""
    mention_only = ast.parse(
        "# conceptually related to asset_preservation.guard_destructive_removal\nGUARD_NAME = 'guard_destructive_removal'\nPACKAGE_NAME = 'asset_preservation'\n"
    )
    assert _calls_guard_destructive_removal(mention_only) is False

    bare_name_call = ast.parse("from specify_cli.asset_preservation import guard_destructive_removal\n\n\ndef f(x):\n    guard_destructive_removal(x)\n")
    assert _calls_guard_destructive_removal(bare_name_call) is True

    qualified_call = ast.parse("from specify_cli import asset_preservation\n\n\ndef f(x):\n    asset_preservation.guard_destructive_removal(x)\n")
    assert _calls_guard_destructive_removal(qualified_call) is True


def test_pinned_routed_module_set_is_complete() -> None:
    """The pinned WP02-WP08 routed set must EQUAL the live set of modules that
    call into asset_preservation. Dropping a module from the pin (while it still
    routes) fails here; a new routing site must be added to the pin."""
    live = _live_routed_modules()
    assert live == _ROUTED_MODULES, (
        "Pinned routed-module set drifted from the live asset_preservation "
        f"callers. Missing from pin (routed but not pinned): {sorted(live - _ROUTED_MODULES)}. "
        f"Pinned but no longer routing: {sorted(_ROUTED_MODULES - live)}."
    )


def test_each_routed_module_routes_and_is_allowlist_clean() -> None:
    """Each pinned module (a) calls asset_preservation.guard_destructive_removal
    and (b) carries no raw destructive literal OUTSIDE the frozen allowlist —
    the fix-site literal is gone (the guard performs the delete). MODULE-COARSE:
    per-path preservation is proven by the C4 behavioural tests, not here."""
    no_guard_call: list[str] = []
    unrouted_literals: dict[str, list[str]] = {}
    for rel in sorted(_ROUTED_MODULES):
        path = SPECIFY_CLI_ROOT / rel
        text = path.read_text(encoding="utf-8")
        if _GUARD_CALL not in text:
            no_guard_call.append(rel)
        repo_rel = path.relative_to(REPO_ROOT).as_posix()
        literals = census_keys(repo_rel, text, _find_destructive_ops(path)).keys()
        unexpected = literals - _ALLOWLIST.keys()
        if unexpected:
            unrouted_literals[rel] = [render_census_key(key) for key in sorted(unexpected)]

    assert not no_guard_call, f"Pinned routed module(s) do not call guard_destructive_removal(...): {no_guard_call}"
    assert not unrouted_literals, (
        "Pinned routed module(s) carry a raw destructive literal outside the "
        "allowlist — a leftover un-routed fix site (route it through the guard, do "
        f"not allowlist a user-content op): {unrouted_literals}"
    )


# ---------------------------------------------------------------------------
# C3.5 -- self-mutation, both directions (+ benign controls).
# ---------------------------------------------------------------------------


def test_scanner_detects_a_planted_unrouted_op(tmp_path: Path) -> None:
    """A planted, un-routed raw ``shutil.rmtree`` is caught by the exact scanner
    the primary census gate runs (non-vacuity, direction 1)."""
    hits = scan_planted_source(
        tmp_path,
        "planted_unrouted.py",
        "import shutil\n\n\ndef _sneaky_cleanup(target):\n    shutil.rmtree(target)\n",
        _find_destructive_ops,
    )
    assert hits == [(5, "shutil.rmtree")], f"Non-vacuity failure: the FS-op scanner did not detect a planted raw shutil.rmtree. Got: {hits!r}."


def test_scanner_detects_a_planted_aliased_import_op(tmp_path: Path) -> None:
    """A planted ``import shutil as sh; sh.rmtree(...)`` is still detected —
    the receiver-name census resolves the alias to its canonical module
    before the ``_MODULE_RECEIVERS`` check (contract C3.2 blind-spot fix).
    Without ``import_alias_map`` resolution, ``sh`` is not ``"shutil"`` and
    the old fixed-``{"os","shutil"}`` receiver check would have silently
    missed this call — the assertion below would have failed on the prior
    classifier."""
    hits = scan_planted_source(
        tmp_path,
        "planted_aliased_import.py",
        "import shutil as sh\n\n\ndef _sneaky_cleanup(target):\n    sh.rmtree(target)\n",
        _find_destructive_ops,
    )
    assert hits == [(5, "shutil.rmtree")], f"Non-vacuity failure: the FS-op scanner did not detect a planted aliased-import shutil.rmtree. Got: {hits!r}."


def test_scanner_detects_a_planted_from_import_op(tmp_path: Path) -> None:
    """A planted ``from shutil import rmtree; rmtree(...)`` is still detected
    — a bare-``Name`` call bound by a tracked ``from``-import resolves to its
    canonical ``module.attr`` label (contract C3.2 blind-spot fix). The old
    classifier matched only ``ast.Attribute`` receivers, so a bare-name call
    from a ``from``-import was invisible to it — the assertion below would
    have failed on the prior classifier."""
    hits = scan_planted_source(
        tmp_path,
        "planted_from_import.py",
        "from shutil import rmtree\n\n\ndef _sneaky_cleanup(target):\n    rmtree(target)\n",
        _find_destructive_ops,
    )
    assert hits == [(5, "shutil.rmtree")], f"Non-vacuity failure: the FS-op scanner did not detect a planted from-import shutil.rmtree. Got: {hits!r}."


def test_exhaustiveness_detects_a_planted_unhandled_op(tmp_path: Path) -> None:
    """A planted destructive-shaped op OUTSIDE the classifier vocabulary
    (``os.removedirs``) is flagged by the exhaustiveness scan — proving C3.2 has
    teeth against a future op the census does not yet classify."""
    unhandled = scan_planted_source(
        tmp_path,
        "planted_unhandled.py",
        "import os\n\n\ndef _sneaky(target):\n    os.removedirs(target)\n",
        _unhandled_reference_ops,
    )
    assert unhandled == [(5, "os.removedirs")], (
        f"Non-vacuity failure: the exhaustiveness scan did not flag a planted unclassified os.removedirs. Got: {unhandled!r}."
    )


def test_scanner_does_not_flag_benign_calls(tmp_path: Path) -> None:
    """Control (other direction): ``list.remove`` / ``str.replace`` / ``dict.pop``
    must NOT be flagged — the classifier keys on os/shutil receivers and Path
    deletion methods, not on the bare method name."""
    hits = scan_planted_source(
        tmp_path,
        "planted_benign.py",
        'def _benign(items, text, mapping):\n    items.remove(1)\n    text = text.replace("a", "b")\n    mapping.pop("k", None)\n    return text\n',
        _find_destructive_ops,
    )
    assert hits == [], f"Benign method calls were misclassified as destructive ops: {hits!r}."


def test_removing_an_allowlist_entry_reproduces_a_gate_failure() -> None:
    """Non-vacuity (direction 2): dropping ONE real allowlist entry and
    re-diffing against the ACTUAL live scan reproduces exactly the failure
    ``test_every_destructive_literal_is_allowlisted`` would raise for a genuine
    un-routed regression — proving the primary gate is not vacuously green."""
    live = _census_keys(_live_sources())
    victim, shrunk_allowlist = drop_one_entry(_ALLOWLIST)

    unexpected, _stale = diff_against_allowlist(live, shrunk_allowlist)

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the allowlist did "
        "not reproduce a gate failure against the live tree. The census gate is "
        "vacuous — investigate diff_against_allowlist / _census_keys before "
        "trusting a green run."
    )


def test_reverting_a_routed_call_to_a_raw_literal_is_caught(tmp_path: Path) -> None:
    """Demonstrates — not merely infers — that reverting a routed fix-site back
    to a raw destructive literal is caught. Reads a REAL routed module's
    on-disk source, string-substitutes its ``guard_destructive_removal(`` call
    for a raw ``shutil.rmtree(``, and feeds the mutated source through the
    exact same planted-source scan helper the other self-mutation checks use.
    A new unrouted-literal hit must appear at the reverted call site."""
    routed_module = SPECIFY_CLI_ROOT / "upgrade" / "migrations" / "m_2_0_11_remove_clarify_command.py"
    real_source = routed_module.read_text(encoding="utf-8")
    assert real_source.count("guard_destructive_removal(") == 1, "fixture assumption: exactly one guard call site in this routed module"

    reverted_source = real_source.replace("guard_destructive_removal(", "shutil.rmtree(")
    assert reverted_source != real_source

    hits = scan_planted_source(tmp_path, "reverted_m_2_0_11.py", reverted_source, _find_destructive_ops)

    assert any(op == "shutil.rmtree" for _lineno, op in hits), (
        f"Non-vacuity failure: reverting the routed guard call at {routed_module.name} to a raw shutil.rmtree(...) was not caught by the scanner. Got: {hits!r}."
    )


def test_enclosing_qualname_is_available_for_diagnostics() -> None:
    """The shared qualname helper resolves a censused op's enclosing function —
    used when a failure needs to name where an unrouted literal lives."""
    source = _INIT_PY.read_text(encoding="utf-8")
    hits = _find_destructive_ops(_INIT_PY)
    assert hits, "init.py should carry at least one allowlisted destructive literal"
    lineno = hits[0][0]
    assert enclosing_qualname(source, lineno) not in {"", "<module>"}


# ---------------------------------------------------------------------------
# Line-drift tolerance (NFR-001) and non-widening (FR-006) through the seam.
# ---------------------------------------------------------------------------


def _site_linenos(rel: str, op: str | None = None) -> list[int]:
    return sorted(lineno for lineno, hit_op in _find_destructive_ops(REPO_ROOT / rel) if op is None or hit_op == op)


def test_mutation_drift_files_cover_the_allowlist() -> None:
    """Companion floor: the drift test runs over at least the 21 allowlisted files."""
    assert len(_DRIFT_FILES) >= 21, _DRIFT_FILES


@pytest.mark.parametrize("rel", _DRIFT_FILES)
def test_mutation_census_survives_line_drift(rel: str) -> None:
    """NFR-001: an unrelated line shift (blank line at the top; a probe
    statement above every census site) leaves ``(unexpected, suppressed)``
    unchanged. RED on the line-keyed allowlist, GREEN on content keys."""
    source = (REPO_ROOT / rel).read_text(encoding="utf-8")
    file_keys = [key for key in _ALLOWLIST if key.rel == rel]
    assert_partition_survives_drift(rel, source, _census_partition, _site_linenos(rel), file_keys)


def test_second_identical_op_in_exempted_function_fails() -> None:
    """Non-widening guard: duplicating the exempted ``shutil.move`` statement in
    ``m_0_10_8_fix_memory_structure.py`` inside its function is reported as unexpected. GREEN on the
    line-keyed base (a new line already yields a new key) and must stay GREEN
    on content keys (``op_ordinal`` makes the duplicate a new key)."""
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    lineno = _site_linenos(_NON_WIDENING_REL, _NON_WIDENING_OP)[0]
    assert_second_identical_op_is_unexpected(_NON_WIDENING_REL, source, _census_partition, lineno)


def test_changed_argument_on_exempted_op_fails() -> None:
    """Non-widening guard: adding a NAME argument to the exempted ``shutil.move``
    call (same line, so the line count is unchanged) makes the site unexpected
    and its old entry stale. RED on the line-keyed base (the ``path:line:op``
    key silently keeps blessing the changed argument); GREEN on content keys
    (the token line changes). Editing only a string argument would not change
    the tokens: ``composite_key`` strips strings."""
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    lineno = _site_linenos(_NON_WIDENING_REL, _NON_WIDENING_OP)[0]
    mutated = with_leading_argument(source, lineno, (ast.Call,), callee=_NON_WIDENING_OP.rsplit(".", 1)[-1])
    assert_changed_argument_is_unexpected(_NON_WIDENING_REL, source, _census_partition, mutated)
