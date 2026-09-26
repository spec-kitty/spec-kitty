# Contract: destructive-op preservation invariant

Every destructive filesystem operation on operator-visible content in the two covered flows MUST
honour this contract. It is the single behavioural spec the fixed sites and their tests are held to.

## Invariant (applies to both flows)

Given a candidate operation `destroy(target)` where `target` may hold operator-authored bytes:

1. **Prove or preserve.** The operation proceeds ONLY when ownership is proven (content-hash /
   managed-path / canonical-marker for `.kittify/` assets; "is a clone of the configured `url`" for a
   git pack). When ownership is NOT proven, the content is **preserved in place or backed up** — never
   deleted, never reset away.
2. **Never widen the blast radius.** An operation scoped to `target` never mutates unrelated content
   (no sweeping other staged/dirty index entries; no deleting a directory the operation did not create).
3. **Honest outcome.** Success exits 0 with a truthful message; a preservation/refusal is reported
   (backup path named when one was written); the tool NEVER prints "removed"/"reset"/"normalized" for
   content it preserved. A refusal that cannot proceed safely exits non-zero with a message that names
   the preserved path — never a bare underlying error that hides the (non-)deletion.
4. **Fail-closed on ambiguity.** Any unreadable state, probe error, or "differs but unprovable" case
   resolves toward preservation, not destruction.

> Corrected by the post-plan adversarial pass (research.md F5–F10). This is the authoritative contract.

## Site A — `runtime/migrate.py` (FR-001, FR-002; #4961)

- `execute_migration` routes BOTH the IDENTICAL and SUPERSEDED removal through
  `guard_destructive_removal(path, project_dir, prover=CanonicalContentProver(canonical=<package-counterpart bytes>), backup_parent=None, dry_run=dry_run)` (F5).
  - Byte-identical to the shipped counterpart → `canonical_content` proof → removed (unchanged behaviour
    for genuine duplicates, NFR-004).
  - Differs from the counterpart (customised OR outdated default alike) → unproven → **preserved in
    place** (`backup_parent=None`), reported via the verdict diagnostic. Do NOT archive-then-remove
    (that would move the file out of place, contradicting "survives in place").
  - The marker-only `CanonicalContentProver()` (default) and `ManifestProver` are WRONG here (F5):
    the marker one would delete a customised marker-bearing command file; the manifest one is inert.
- Thread the package-counterpart bytes into the removal site via `_find_package_counterpart` (migrate.py
  :50-66) or by having `classify_asset` return them; `execute_migration` currently discards them.
- `--dry-run` performs no mutation and labels a differing customised file honestly (never "superseded").
- Out of scope (deferred, but ALSO closed by the fail-closed guard): the `.kittify/missions/**`
  counterpart-lookup miss — a misclassified file is unprovable → preserved, so no deletion (F10).

## Site B — `doctrine/sources/git_source.py` (FR-003, FR-004; #4960, #4989)

- `_first_install` (F8): clone into a fresh `.tmp-<uuid>` sibling; promote via the `snapshot.py:196-228`
  move-aside(`.old-<uuid>`)/promote/restore pattern (NOT a bare `Path.replace` — it raises on a
  non-empty and, on Windows, an existing-empty target). On any failure remove ONLY the temp. Refuse up
  front (non-destructive) when `local_path` exists AND is non-empty (a `.git`-bearing valid clone never
  reaches `_first_install`, so "is a clone of url" is unobservable here — do not build that helper).
  MUST permit a pre-existing EMPTY `local_path` (the `doctrine/template_render/resolve.py::_resolve_git`
  caller passes an empty `mkdtemp`). No manifest exists for a fetched pack (C-003) → backup primitives +
  move-aside, not the prover guard.
- `_update` (F6/F7): resolve the reset target BY REF TYPE — `origin/<ref>` only when
  `git rev-parse --verify --quiet refs/remotes/origin/<ref>` succeeds (branch), else bare `<ref>`
  (tag/SHA) — a blanket `origin/<ref>` regresses tag/SHA-pinned packs. Before any `git reset --hard`,
  run the ahead check (`git rev-list --count origin/<ref>..HEAD` > 0) AND `git/ref_advance._dirty_entries`
  (wired with the resolved target SHA + `_target_tree_paths`, kw-only). For a dirty OR ahead/divergent
  pack, preserve git-natively (create a backup branch/ref, or preserve the whole dir incl. `.git`) OR
  fail-closed refuse — a worktree-bytes archive is INSUFFICIENT to preserve committed local history.

## Site C — architectural gate (FR-005)

- Two distinct gates (F9):
  - git-argv gate `test_destructive_op_routing.py` already scans all of `src/specify_cli` → the ONLY
    change is to re-pin/trim the `git_source.py:98:reset_hard` allowlist entry (:160-164) and fix its
    now-false "throwaway clone" rationale.
  - FS-op gate `test_mutation_ownership_routing.py` / `_destructive_op_census.py` scan a fixed
    `_module_set()` — extend it to `runtime/migrate.py` and `doctrine/sources/git_source.py`. Then:
    add `migrate.py` to `_ROUTED_MODULES` (it routes through the guard; else
    `test_pinned_routed_module_set_is_complete` fails); keep `git_source.py` scanned-but-NOT-routed
    (it uses backup/temp-swap, mirror the `research.py` never-allowlist guard); add allowlist entries
    for `migrate.py:239` empty-only `Path.rmdir` and the `git_source.py` temp `shutil.rmtree` (+ a
    `shutil.move` swap if used).
  - Note: `Path.rename`/`os.replace` (e.g. `migrate.py:202`, or a rename-based swap) are NOT caught by
    the FS classifier (rename/replace deliberately excluded, #4901) — do not rely on the gate for those.
- The gate is proven fail-able (adding a raw un-rationalised literal reds it; removing it greens it).
