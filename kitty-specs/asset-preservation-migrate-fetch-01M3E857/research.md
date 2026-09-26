# Research & Findings Ledger — asset-preservation migrate+fetch

Mission: `asset-preservation-migrate-fetch-01M3E857`. Base: `skupstream/main` @ `e8054f4994`.
Scope (operator-confirmed): fold #4961 + #4960 + #4989. Grounded by a read-only 3-lens squad
(mechanism/debugger ×2 + planner scope lens). Every finding carries file:line evidence; contested
points are dispositioned, none silently dropped.

## Decision log
- **D1** — Fold #4989 with #4960 (same module `git_source.py`, same class). Operator-confirmed
  2026-09-26. Rationale: fixing `_first_install` while `_update` still hard-resets committed
  directives ships a visible half-fix; shared fix surface, tests, and arch-gate entry.
- **D2** — Base the mission on live `skupstream/main`, not the stale local branch (lesson from the
  #5036 supersession finding). All three seeds re-checked LIVE on base; none superseded.
- **D3** — git-source uses backup + clone-to-temp-swap (no manifest → not the full prover guard);
  migrate uses `guard_destructive_removal` + content provers. One invariant, two adapters.

## Supersession check (#5036-style) — all three LIVE on base, none superseded
- #4961 — `runtime/migrate.py`: SUPERSEDED→`path.unlink()` present, no backup. LIVE.
- #4960 — `git_source.py` `_first_install`: unconditional `shutil.rmtree(target_dir)` on clone &
  checkout failure. LIVE.
- #4989 — `git_source.py` `_update`: `reset --hard` (target = local `self.ref`, not `origin/<ref>`),
  no dirty check. LIVE. (No open PRs for any of the three.)

## F1 — #4961: migrate deletes customised shipped template (debugger lens)
- `src/specify_cli/runtime/migrate.py` `classify_asset` (:69): a package counterpart that DIFFERS →
  `SUPERSEDED` (:112); NO branch yields `CUSTOMIZED` for a differing copy of a shipped template
  (:114 only when no counterpart exists). `execute_migration` (:145) unlinks SUPERSEDED at
  :189-195 — the only remaining raw destructive literal in any SK mutating flow.
- Crux: no content-only signal distinguishes "old default" from "customised shipped template";
  charter forbids name/content identity as ownership proof. `SUPERSEDED` exists for a real reason
  (#285 version-skew). Correct move: fail-closed toward preservation — never unlink on unproven
  ownership.
- Fix: route the :194-195 removal through `guard_destructive_removal(path, project_dir,
  prover=AnyProver([ManifestProver(), CanonicalContentProver()]), backup_parent=…)`
  (`asset_preservation/guard.py:148`). Mirror the CLOSED sibling init fix #4931/#4861 at
  `src/specify_cli/cli/commands/init.py:1604`. Keep `classify_asset` honest for reporting.
- Tests to re-pin (`tests/upgrade/test_migrate_integration.py`):
  `test_superseded_when_differs_from_package` (:824-838, the exact pin),
  `test_outdated_agents_md_superseded` (:686), `test_mix_of_identical_customized_and_superseded`
  (:709), `test_superseded_files_removed_not_moved_to_overrides` (:891),
  `test_version_skew_scenario_end_to_end` (:957, #285 rationale — redefine removed→preserved/archived),
  `test_superseded_count_in_report` (:1005). Add red-first: a customised template survives
  `execute_migration(dry_run=False)`, exit 0.

## F2 — #4960: git_source `_first_install` rmtree (debugger lens)
- `src/specify_cli/doctrine/sources/git_source.py` `_first_install` (:58-84): unconditional
  `shutil.rmtree(target_dir)` at :64-65 (clone fail — dir existed BEFORE clone, which is WHY the
  clone failed → deletes user pack) and :76 (checkout fail). `fetch()` dispatch on
  `(target_dir/".git").exists()` (:51-53). Live-confirmed: pre-existing pack destroyed on bad url.
- Reference pattern to copy: `src/specify_cli/doctrine/snapshot.py::write_snapshot` :196-228
  (move-aside `.old-<uuid>` → promote `.tmp-<uuid>` → restore-on-failure → delete backup only after
  success), staging :122-137. GitSource deliberately bypasses `write_snapshot` today
  (`snapshot.py:704-709`).
- Fix: clone into a `.tmp-<uuid>` sibling; swap on success; on failure rmtree only the TEMP; refuse
  up front when `local_path` exists and is not a clone of `url`.

## F3 — #4989: git_source `_update` hard-reset (debugger lens)
- `_update` (:86-107): fetch-failure branch SAFE (:88-95, "existing clone remains untouched"). On
  success: `reset_target = self.ref if self.ref else "origin/HEAD"` then `git reset --hard
  reset_target` (:97-98). Sub-bug A: discards committed+uncommitted local directives every fetch,
  exit 0, no dirty-check/backup. Sub-bug B: `ref="main"` → resets to LOCAL `main` (fetch only moved
  `origin/main`) → pack never advances; correct target is `origin/<ref>`.
- Fix: dirty-check via `src/specify_cli/git/ref_advance.py::_dirty_entries` (arch-gate T019 mandates
  reuse) + backup via `asset_preservation/backup.py` before any reset; resolve `origin/<ref>`.

## F4 — arch-gate blast radius (both lenses)
- `tests/architectural/test_destructive_op_routing.py:160-164` LINE-PINS the `_update` reset
  allowlist entry (`git_source.py:98:reset_hard`) with a now-FALSE rationale ("throwaway
  doctrine-pack clone"). Any `_update` edit shifts :98 → breaks the census → must re-pin (guarded
  reset) or delete (temp-swap).
- `tests/architectural/test_mutation_ownership_routing.py` + `_destructive_op_census.py` today scan
  only `init.py`/`agent/config.py`/`research.py`/upgrade migrations. Extend to scan
  `runtime/migrate.py` + `doctrine/sources/git_source.py` (FR-005). Prove gate fail-able both ways.
- Both seed modules are UNROUTED today (neither imports `asset_preservation`).

## Reusable primitives (do not open-code)
- `asset_preservation/guard.py:148` `guard_destructive_removal(path, project_path, *, prover,
  is_tree, backup_parent, dry_run) -> OwnershipVerdict` — removes when proven; preserves-in-place
  (backup_parent=None) or archives-then-removes (backup_parent set) when unproven; always exits ok.
- `asset_preservation/provers.py`: `ManifestProver`(:73), `CanonicalContentProver`(:174 marker
  `<!-- spec-kitty-command-version:`), `ManagedPathProver`(:146), `AnyProver`(:212).
- `asset_preservation/backup.py`: `backup_before_overwrite(path)->Path`(:68, O_EXCL sidecar,
  symlink-safe, never removes source); `archive_into(path, project_path, backup_parent)->Path`(:89).
- `git/ref_advance.py::_dirty_entries` — canonical residue-aware dirty predicate (arch-gate T019).
- Reference atomic install: `snapshot.py:196-228` / `:122-137`.

## Established fix pattern (scope lens) — docs/changelog/CHANGELOG.md:39-58
Content-based ownership proof (never name); unprovable → preserve/archive (reported), never delete;
verdict-driven honest messaging, always exit success with diagnostic; arch gate closes the class;
ATDD red-first; NO CLI version bump. git-source nuance: no manifest → backup + clone-to-temp-swap.

## Deferred (recorded, not dropped)
- #4961 P2 `.kittify/missions/**` counterpart-lookup miss (`_find_package_counterpart` :50-66
  double-probe blind spot; same in `m_2_0_7_fix_stale_overrides._matches_package_default` :119-126).
  Recoverable move-to-overrides → own ticket.
- Encoding cluster #4968/#4962/#4946 (different root: charset re-decode). Skills-CRLF #4998
  (Windows, corrupting prepend). Merge-integrity #4933 → epic #5001.

---

# Post-plan adversarial pass (3 lenses: fit / correctness / scope) — dispositions

All three lenses ran read-only against base `e8054f4994` and converged. Every contested finding is
dispositioned `accepted` (folded into plan/contract) or `deferred_with_rationale`. None dropped.

## F5 — Prover design must be byte-match-to-counterpart, not marker/manifest (ACCEPTED; fit+scope lenses)
The planned `AnyProver([ManifestProver(), CanonicalContentProver()])` is WRONG:
- `ManifestProver` (`provers.py:86-143`) is inert for `.kittify/{templates,missions,...}` (proves only
  skills/command manifests) → always `None`.
- `CanonicalContentProver()` with default args proves only via the marker
  `<!-- spec-kitty-command-version:`; shipped templates carry NO such marker
  (`grep -rl spec-kitty-command-version packs/` = 0). ⇒ a byte-IDENTICAL markerless default would be
  UNPROVEN → preserved, flipping removed→preserved, violating NFR-004 and redding the IDENTICAL tests.
- Worse, a customised-but-marker-bearing command file (user edits body, keeps the version marker) would
  be PROVEN by the default marker → REMOVED — a NEW data-loss hole, contra init.py #4861 which uses
  `ManagedPathProver` and preserves `.kittify/command-templates`.
**Fix (A1):** route BOTH IDENTICAL and SUPERSEDED removal through
`guard_destructive_removal(path, project_dir, prover=CanonicalContentProver(canonical=<package
counterpart bytes>), backup_parent=None, dry_run=dry_run)`. Byte-match to the shipped counterpart is a
first-class `canonical_content` proof (`provers.py:207-208`): identical→proven→removed (NFR-004);
differing (customised OR old default)→unproven→preserved-in-place (fixes #4961; closes the marker
false-positive). Drop the inert `ManifestProver`. Requires threading the counterpart bytes into
`execute_migration` (re-derive via `_find_package_counterpart(rel, package_root, mission)`
migrate.py:50-66, or have `classify_asset` return them). `backup_parent=None` = preserve in place
(matches the "survives in place, exit 0" regression); do NOT archive-then-remove.

## F6 — `_update` ref-type resolution; blanket origin/<ref> regresses tags/SHAs (ACCEPTED; correctness lens GAP-A)
`GitSource.ref` may be a branch, tag, or SHA (git_source.py:34). After `git fetch --tags origin`:
`git reset --hard origin/main` advances (fix for #4989 sub-bug B) BUT `origin/<tag>` / `origin/<sha>`
do NOT resolve → a blanket `origin/<ref>` REGRESSES tag-pinned and SHA-pinned packs (which work today
via bare ref). **Fix (A4a):** resolve by ref type — use `origin/<ref>` only when
`git rev-parse --verify --quiet refs/remotes/origin/<ref>` succeeds (branch), else bare `<ref>`.

## F7 — committed-ahead local commits need git-native backup, not a worktree archive (ACCEPTED; correctness lens GAP-B)
`_dirty_entries` is status-only → returns `[]` for a clean worktree that has local commits ahead of
upstream, so the planned "dirty-check → back up before reset" NEVER FIRES for committed-ahead packs.
And `archive_into`/`backup_before_overwrite` copy worktree bytes only — they CANNOT preserve `.git`
history (a local commit chain, or a commit that deleted a tracked file). `reset --hard origin/<ref>`
then silently orphans committed history (`git branch --contains` = none). **Fix (A4b):** add an
explicit ahead check (`git rev-list --count origin/<ref>..HEAD` > 0) AND the dirty check; for dirty OR
ahead/divergent, preserve git-natively (create `git branch backup/<ts> HEAD` / a backup ref, or
preserve the whole dir incl. `.git`) OR fail-closed refuse. A worktree archive alone does NOT satisfy
the preservation contract for committed-ahead packs. `_dirty_entries` wiring (A4c): resolve
`origin/<ref>`→SHA, compute `_target_tree_paths(worktree, new_sha, env)`, then
`_dirty_entries(worktree, env, new_sha=…, target_paths=…)` (kw-only required; a parallel
`git status` predicate is forbidden by arch gate T019).

## F8 — `_first_install` refusal is exists-&-non-empty; must use move-aside; permit empty dir (ACCEPTED; all lenses)
`fetch()` routes to `_update` when `(target_dir/.git).exists()` (git_source.py:51-53), so a valid clone
NEVER reaches `_first_install` — the "is a clone of url" check is unobservable there (no such helper
exists anyway). **Fix (A3):** reframe the `_first_install` refusal as "local_path exists AND is
non-empty (no .git) → refuse"; it is MANDATORY before the swap because `Path.replace(tmp→local_path)`
onto a non-empty dir raises ENOTEMPTY (and on Windows even onto an existing empty dir). Use the
`snapshot.py:196-228` move-aside(`.old-<uuid>`)/promote/restore pattern, NOT a bare `Path.replace`.
MUST permit a pre-existing EMPTY `target_dir`: real caller `doctrine/template_render/resolve.py::
_resolve_git` (:239-243) passes an empty `mkdtemp` dir to `fetch()` — refusing on empty would break
git template-resolve. (Other caller `snapshot.py:704-712` passes the persistent pack dir.) Correct the
contract wording: `_first_install` refuses on exists-&-non-empty, not "is a clone of url".

## F9 — arch-gate FR-005 is under-scoped (ACCEPTED; scope+fit lenses)
Two distinct gates:
- **git-argv gate** `test_destructive_op_routing.py` already scans all of `src/specify_cli`; the
  `git_source.py:98:reset_hard` allowlist entry (:160-164, false "throwaway clone" rationale) is the
  ONLY change — re-pin the line + fix rationale (or trim if the reset is removed).
- **FS-op gate** `test_mutation_ownership_routing.py` scans a fixed `_module_set()` (:106-107). Extend to
  add `runtime/migrate.py` + `doctrine/sources/git_source.py`. Consequences the plan omitted:
  - `migrate.py` routes through the guard → it MUST also be added to `_ROUTED_MODULES` (:449) or
    `test_pinned_routed_module_set_is_complete` (:616) fails.
  - `git_source.py` uses backup/temp-swap, NOT the removal guard → scanned but MUST NOT join
    `_ROUTED_MODULES` (mirror the `research.py` asymmetry + its never-allowlist guard, test :526-545).
  - New allowlist entries needed: `migrate.py:239` empty-only `Path.rmdir` (guarded by `iterdir()`
    check); `git_source.py` temp `shutil.rmtree` cleanup (ephemeral-temp rationale); a `shutil.move`
    swap if used (relocation rationale). `migrate.py:202 Path.rename` and an `os.replace`/`Path.rename`
    swap are NOT caught by the FS classifier (rename/replace deliberately excluded, #4901) — so correct
    contract Site C which wrongly lists "rename" as a scanned literal.

## F10 — deferred scope safe (ACCEPTED)
Routing migrate removal through the fail-closed guard ALSO closes the deferred #4961-P2 `.kittify/
missions/**` counterpart-miss data loss: a misclassified missions/** file is unprovable → preserved,
so no deletion even with the classifier bug present. Deferral of the classifier fix (own ticket) does
not make the 3 folded fixes incoherent. Encoding/#4998/#4933 remain separable (different roots).

## Net effect on WP write-scopes (updated)
- WP01 (#4961): + `tests/runtime/test_e2e_runtime_integration.py` and run
  `tests/runtime/test_global_runtime_convergence_unit.py`; thread counterpart bytes in `execute_migration`.
- WP02 (#4960+#4989): re-pin `tests/specify_cli/doctrine/test_sources.py:188-191` call-order (+ verify
  :214/:264); ref-type resolution + git-native ahead/dirty backup-or-refuse + move-aside pattern.
- WP03 (FR-005): both gates as F9; still depends on WP01+WP02; owns CHANGELOG.md.
