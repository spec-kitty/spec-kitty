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
    diff_against_allowlist,
    drop_one_entry,
    enclosing_qualname,
    from_import_map,
    import_alias_map,
    iter_py_files,
    parse,
    scan_planted_source,
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
# ---------------------------------------------------------------------------
_INIT_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "init.py"
_AGENT_CONFIG_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "agent" / "config.py"
_RESEARCH_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "research.py"
_MIGRATIONS_DIR = SPECIFY_CLI_ROOT / "upgrade" / "migrations"

_GUARD_CALL = "guard_destructive_removal("
_RESEARCH_PY_ALLOWLIST_PREFIX = "src/specify_cli/cli/commands/research.py:"


def _module_set() -> list[Path]:
    return [_INIT_PY, _AGENT_CONFIG_PY, _RESEARCH_PY, *iter_py_files(_MIGRATIONS_DIR)]


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
    if tree is None:
        return []
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            op = _classify_op(node, module_aliases, from_imports)
            if op is not None:
                hits.append((node.lineno, op))
    return hits


def _scan_module_set() -> dict[str, list[tuple[int, str]]]:
    live: dict[str, list[tuple[int, str]]] = {}
    for py_file in _module_set():
        hits = _find_destructive_ops(py_file)
        if hits:
            live[py_file.relative_to(REPO_ROOT).as_posix()] = hits
    return live


def _flatten(live: dict[str, list[tuple[int, str]]]) -> set[str]:
    return {f"{rel}:{lineno}:{op}" for rel, hits in live.items() for lineno, op in hits}


# ---------------------------------------------------------------------------
# The frozen allowlist. Built from a LIVE AST census of the integrated lane
# tree (post WP01-WP08) reproduced by this file's own scanner. Every entry is a
# genuinely-safe op with a one-line rationale (NFR-006). Shrink-only: a site
# that disappears only WARNS; a NEW un-rationalized literal FAILS. Routed
# fix-sites are ABSENT here on purpose — they carry no raw literal.
# ---------------------------------------------------------------------------
_ALLOWLIST: dict[str, str] = {
    # --- cli/commands/agent/config.py (1): empty-only rmdir after guard ----
    "src/specify_cli/cli/commands/agent/config.py:168:Path.rmdir": (
        "empty-only rmdir: prunes the now-possibly-empty parent `root` only on the "
        "guard's owned branch (verdict.owned), after guard_destructive_removal already "
        "removed `surface` itself — raises OSError (caught) on a non-empty preserved dir."
    ),
    # --- init.py (4): ephemeral scratch, backup-guarded discard, marker ----
    "src/specify_cli/cli/commands/init.py:136:Path.unlink": (
        "package-state marker: unlinks the .kittify pending-command-skills record only after a "
        "changed-check raises — a machine-written pointer, never user content."
    ),
    "src/specify_cli/cli/commands/init.py:453:shutil.rmtree": (
        "backup-guarded: _discard_failed_project_scaffold runs back_up_operator_subtrees(...) to "
        "project_path.parent FIRST, so operator subtrees are archived before the scaffold rmtree."
    ),
    "src/specify_cli/cli/commands/init.py:677:shutil.rmtree": (
        "ephemeral scratch: removes the .resolved-command-templates-<mission> resolver scratch dir "
        "this run creates immediately below — package-generated, never user-authored."
    ),
    "src/specify_cli/cli/commands/init.py:1622:shutil.rmtree": (
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
    "src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py:221:Path.rmdir": (
        "empty-only rmdir (raises on non-empty): removes .kittify/scripts/bash only when it is empty "
        "after the routed guard preserved every unprovable script — cannot lose content."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py:224:Path.rmdir": (
        "empty-only rmdir: removes .kittify/scripts/powershell only when empty after preserve-all."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py:266:Path.rmdir": (
        "empty-only rmdir: removes a worktree .kittify/scripts/bash dir only when empty after the routed worktree-script preserve sweep."
    ),
    # --- m_0_10_2 (1): empty-only rmdir after routed toml sweep ------------
    "src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py:67:Path.rmdir": (
        "empty-only rmdir: removes .kittify/commands only when empty after the routed guard swept the legacy command tomls."
    ),
    # --- m_0_10_8 (7): broken-symlink teardown + one relocation ------------
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:106:Path.unlink": (
        "broken-symlink teardown: removes a broken .kittify/memory symlink (is_symlink()-gated) before recreating it — never a real file."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:117:shutil.move": (
        "relocation: moves root memory/ -> .kittify/memory only when the destination is absent (overwrite-guarded rename, not a delete)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:165:Path.unlink": (
        "broken-symlink teardown: removes a broken .kittify/AGENTS.md symlink (is_symlink()-gated)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:201:Path.unlink": (
        "broken-symlink teardown: removes a broken worktree memory symlink (resolve()-checked broken)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:205:Path.unlink": (
        "broken-symlink teardown: removes a broken worktree memory symlink (OSError/RuntimeError resolve fallback — still symlink-only)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:227:Path.unlink": (
        "broken-symlink teardown: removes a broken worktree AGENTS.md symlink (resolve()-checked)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py:230:Path.unlink": (
        "broken-symlink teardown: removes a broken worktree AGENTS.md symlink (resolve fallback — symlink-only)."
    ),
    # --- m_0_2_0 (2): overwrite-guarded relocation -------------------------
    "src/specify_cli/upgrade/migrations/m_0_2_0_specify_to_kittify.py:63:shutil.move": (
        "relocation: renames the legacy .specify tree into .kittify (move, not delete)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_2_0_specify_to_kittify.py:74:shutil.move": (
        "relocation: renames a legacy .specify child into .kittify (move, not delete)."
    ),
    # --- m_0_6_5 (2): relocation + worktree teardown -----------------------
    "src/specify_cli/upgrade/migrations/m_0_6_5_commands_rename.py:103:shutil.move": (
        "relocation: rename_dir moves a package-generated commands dir to its new name (move)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_6_5_commands_rename.py:141:shutil.rmtree": (
        "worktree teardown: removes a worktree's package-generated .kittify/templates/commands dir (regenerated from main), never operator content."
    ),
    # --- m_0_7_2 (1): worktree teardown ------------------------------------
    "src/specify_cli/upgrade/migrations/m_0_7_2_worktree_commands_dedup.py:69:shutil.rmtree": (
        "worktree teardown: dedups a worktree's package-generated commands dir that inherits from main."
    ),
    # --- m_0_8_0_remove_active_mission (1): package-state marker -----------
    "src/specify_cli/upgrade/migrations/m_0_8_0_remove_active_mission.py:53:Path.unlink": (
        "package-state marker: removes the retired machine-written active-mission pointer file."
    ),
    # --- m_0_8_0_worktree_agents_symlink (1): worktree symlink teardown ----
    "src/specify_cli/upgrade/migrations/m_0_8_0_worktree_agents_symlink.py:106:Path.unlink": (
        "worktree teardown: removes a worktree AGENTS symlink before recreating the package-managed link."
    ),
    # --- m_0_9_0 (2): source-after-move + emptiness-checked lane teardown --
    "src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py:251:Path.unlink": (
        "source-after-move: removes the original task md only after its content was written to the new tasks/ location (relocation, not loss)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py:272:shutil.rmtree": (
        "lane teardown, emptiness-checked: removes a legacy lane dir only after _get_real_contents confirms no real files remain (only .DS_Store/.gitkeep)."
    ),
    # --- m_0_9_1 (7): source-after-move, lane + worktree teardown ----------
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:301:Path.unlink": (
        "source-after-move: removes the original file only after it was relocated to its new path."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:324:shutil.rmtree": (
        "lane teardown, emptiness-checked: removes a legacy lane dir once its real contents are gone."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:422:Path.unlink": (
        "worktree teardown: removes a worktree commands symlink that inherits from main."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:425:shutil.rmtree": (
        "worktree teardown: removes a worktree's package-generated commands dir (inherits from main)."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:431:Path.rmdir": (
        "empty-only rmdir: removes the now-empty parent dir after the worktree commands teardown."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:450:Path.unlink": (
        "worktree teardown: removes a worktree .kittify/scripts symlink that inherits from main."
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py:453:shutil.rmtree": (
        "worktree teardown: removes a worktree's package-generated .kittify/scripts dir."
    ),
    # --- m_2_0_0 (1): already-content-guarded exemplar ---------------------
    "src/specify_cli/upgrade/migrations/m_2_0_0_retire_git_hooks.py:127:Path.unlink": (
        "already-content-guarded exemplar (data-model do-not-change): retires a package-installed git hook only after content identity is confirmed."
    ),
    # --- m_2_0_6 (5): worktree teardown + empty-only rmdir -----------------
    "src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:416:Path.unlink": (
        "worktree teardown: removes a worktree commands symlink that inherits from main."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:418:shutil.rmtree": (
        "worktree teardown: removes a worktree's package-generated commands dir."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:421:Path.rmdir": (
        "empty-only rmdir: removes the now-empty parent dir after the worktree commands teardown."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:433:Path.unlink": (
        "worktree teardown: removes a worktree .kittify/scripts symlink that inherits from main."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py:435:shutil.rmtree": (
        "worktree teardown: removes a worktree's package-generated .kittify/scripts dir."
    ),
    # --- m_2_0_7 (3): already-guarded exemplar + empty-only rmdir ----------
    "src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py:93:Path.unlink": (
        "already-content-guarded exemplar (data-model do-not-change): removes a stale override only when it matches the package default."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py:135:Path.rmdir": (
        "empty-only rmdir: prunes an empty override dir after stale-override cleanup."
    ),
    "src/specify_cli/upgrade/migrations/m_2_0_7_fix_stale_overrides.py:139:Path.rmdir": (
        "empty-only rmdir: prunes a second empty override dir after stale-override cleanup."
    ),
    # --- m_2_1_3 (1): already-guarded exemplar -----------------------------
    "src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py:350:Path.unlink": (
        "already-content-guarded exemplar (data-model do-not-change): removes a stale prompt command under a content check while restoring the package prompts."
    ),
    # --- m_3_1_1 (7): overwrite-guarded renames + empty-only rmdir ---------
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:224:shutil.move": (
        "relocation: renames memory/constitution.md -> charter/charter.md into a freshly-mkdir'd charter dir (move)."
    ),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:240:shutil.move": (
        "relocation, overwrite-guarded: merges a constitution/ item into charter/ only when the "
        "destination does not exist; a collision is archived by the routed guard, never clobbered (#4862)."
    ),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:269:Path.rmdir": (
        "empty-only rmdir: removes the residual constitution/ dir after colliding items were archived/removed and merged items moved out — empty by construction."
    ),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:279:shutil.move": ("relocation: renames .kittify/constitution/ -> .kittify/charter/ (move)."),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:293:shutil.move": ("relocation: renames charter/constitution.md -> charter/charter.md (move)."),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:394:shutil.move": (
        "relocation: renames a per-agent spec-kitty.constitution.md command to spec-kitty.charter.md (move)."
    ),
    "src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:419:shutil.move": (
        "relocation: renames a per-agent constitution-doctrine skill dir to charter-doctrine (move)."
    ),
    # --- m_3_1_2 (2): already-guarded exemplar + empty-only rmdir ----------
    "src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py:158:Path.unlink": (
        "already-content-guarded exemplar (data-model do-not-change): removes a per-project command under a content/ownership check while globalizing."
    ),
    "src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py:171:Path.rmdir": (
        "empty-only rmdir: prunes the now-empty per-project commands dir after globalization."
    ),
    # --- m_3_2_0rc35 (2): already-guarded exemplar + empty-only rmdir ------
    "src/specify_cli/upgrade/migrations/m_3_2_0rc35_codex_to_skills.py:208:Path.unlink": (
        "already-content-guarded exemplar (data-model do-not-change): _move_owned_prompts removes a prompt only after confirming package ownership."
    ),
    "src/specify_cli/upgrade/migrations/m_3_2_0rc35_codex_to_skills.py:234:Path.rmdir": (
        "empty-only rmdir: _try_remove_empty_prompts_dir removes the prompts dir only when empty."
    ),
    # --- m_3_2_8 (1): atomic-write temp cleanup ----------------------------
    "src/specify_cli/upgrade/migrations/m_3_2_8_provision_kitty_env.py:452:os.unlink": (
        "ephemeral atomic-write temp: removes the just-written tmp file on an os.replace failure — a machine temp this function created, never user content."
    ),
    # --- m_3_3_0 (2): atomic-write temp + non-user machine surface ---------
    "src/specify_cli/upgrade/migrations/m_3_3_0_op_record_schema_v2.py:230:Path.unlink": (
        "ephemeral atomic-write temp: finally-block cleanup (missing_ok) of the tmp file _atomic_rewrite created."
    ),
    "src/specify_cli/upgrade/migrations/m_3_3_0_op_record_schema_v2.py:266:Path.unlink": (
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
        if tree is not None and _calls_guard_destructive_removal(tree):
            routed.add(py_file.relative_to(SPECIFY_CLI_ROOT).as_posix())
    return routed


# ---------------------------------------------------------------------------
# C3.1 + C3.3 -- live census: every raw literal is allowlisted (routed sites
# are literal-free; the guard's own impl is out of the scanned set).
# ---------------------------------------------------------------------------


def test_every_destructive_literal_is_allowlisted() -> None:
    live_flat = _flatten(_scan_module_set())
    unexpected, stale = diff_against_allowlist(live_flat, _ALLOWLIST)

    assert not unexpected, (
        "New raw destructive filesystem literal(s) found in the init/migration "
        "mutating-flow module set outside the frozen allowlist (FR-010/NFR-006). "
        "Route the removal through asset_preservation.guard_destructive_removal "
        "(the guard performs the delete, leaving no raw literal), or — only for a "
        "genuinely-safe op — add a one-line rationale entry to _ALLOWLIST. Do NOT "
        "absorb a still-raw user-content site into the allowlist: "
        f"{sorted(unexpected)}"
    )
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
    ``src/specify_cli/cli/commands/research.py:*`` key may EVER appear in
    ``_ALLOWLIST``. Makes FR-004/SC-005's "the census refuses to allowlist a
    raw user-content op" claim actually backed for the one module WP02 adds."""
    research_keys = sorted(key for key in _ALLOWLIST if key.startswith(_RESEARCH_PY_ALLOWLIST_PREFIX))
    assert not research_keys, (
        "research.py literal(s) present in _ALLOWLIST — its destructive-overwrite "
        "fabrication must be routed through guard_destructive_overwrite (T021), "
        f"never allowlisted: {research_keys}"
    )


def test_allowlisted_files_exist() -> None:
    """A renamed/deleted allowlisted file must not silently drop out of the scan
    (an absent file reads as zero live hits — a false 'shrink' masking a rename
    the allowlist should track)."""
    rel_paths = {key.rsplit(":", 2)[0] for key in _ALLOWLIST}
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
    if tree is None:
        return []
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
        literals = {f"{repo_rel}:{lineno}:{op}" for lineno, op in _find_destructive_ops(path)}
        unexpected = literals - _ALLOWLIST.keys()
        if unexpected:
            unrouted_literals[rel] = sorted(unexpected)

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
    live_flat = _flatten(_scan_module_set())
    victim, shrunk_allowlist = drop_one_entry(_ALLOWLIST)

    unexpected, _stale = diff_against_allowlist(live_flat, shrunk_allowlist)

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the allowlist did "
        "not reproduce a gate failure against the live tree. The census gate is "
        "vacuous — investigate diff_against_allowlist / _scan_module_set before "
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
    tree = parse(_INIT_PY)
    assert tree is not None
    hits = _find_destructive_ops(_INIT_PY)
    assert hits, "init.py should carry at least one allowlisted destructive literal"
    lineno = hits[0][0]
    assert enclosing_qualname(tree, lineno) != ""
