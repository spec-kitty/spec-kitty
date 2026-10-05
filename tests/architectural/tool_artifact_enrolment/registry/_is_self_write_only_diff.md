# Exemption mechanism -- `_is_self_write_only_diff`

<!-- Machine-readable exemption-registry row (R-014). Parsed by
     tests/architectural/test_exemption_registry_ratchet.py. ONE mechanism per
     file, so a retirement WP deletes ONLY its own row and never collides with a
     sibling retirement editing a shared file (squad-mandated design; the plan's
     stated reason for rejecting golden-count mode). The registry only SHRINKS:
     when a mechanism is retired onto the owner, its literal(s)/symbol vanish from
     src/ and the overcount / symbol-presence arm goes RED until this row file is
     deleted (red -> green per retirement). -->


- mechanism: `_is_self_write_only_diff`
- module: `src/specify_cli/cli/commands/implement_cores.py`
- literals: `_WP_SELF_WRITE_FILENAME_RE`
- symbol: `_is_self_write_only_diff`
- retirement-wp: `WP14`
- retirement-ref: `IC-07d`
- owner-route: `is_toolchain_generated_churn`
- status: `justified-survivor`

**WP14 (IC-07d) genuine must-keep, not a silent survivor.** The plan's IC-07d
retirement double-listed `_drop_vcs_lock_only_meta` and
`_drop_runtime_frontmatter_only_wp` as owner-routable (like their sibling
`_exclude_coord_owned`, which DOES route fully onto the owner-exposed
`is_status_state_path` leg -- its row was deleted, not replaced). Implementation
found the vcs-lock/frontmatter pair cannot make that same move: they are
structural twins of EACH OTHER (same "keep unless the predicate flags a
runtime self-write" shape, now merged into one `_drop_if`-consumed predicate),
but their filename gate is a `meta.json`/`WP##.md` DIFF comparison, not a
`MissionArtifactKind` classification -- `is_toolchain_generated_churn` answers
"is this file's *kind* toolchain-generated" (a whole-file verdict; `meta.json`
is unconditionally self-bookkeeping there, `WP##.md` is unconditionally
PRIMARY/never churn), while this predicate must answer "is THIS DIFF only the
runtime's own claim-time self-write", which requires reading both the working
tree and the committed baseline and comparing the changed keys/body. Forcing
the owner's kind-based verdict in here would either (a) always-drop `meta.json`
regardless of content -- silently swallowing a genuine non-lock operator edit,
regressing `test_non_lock_dirty_meta_still_blocks_auto_commit_false_claim` -- or
(b) never drop `WP##.md` at all (it is never toolchain-generated churn by
kind), regressing every runtime-frontmatter-only-diff test. Both are C6
violations. Registered here -- with real justification prose, `status:
justified-survivor`, and a live `_is_self_write_only_diff` symbol -- rather
than silently retained, per plan.md's "if implementation finds a genuine
must-keep, it becomes an explicit, justified registry row, never a silent
survivor" (WP15 precedent).

**#3471 status-log and snapshot legs (still diff-scoped, no new kind
derivation).** Under `--no-auto-commit` the predicate also exempts a claim's
own status writes on a topology without a coordination branch: the event log
when it is exactly the committed log plus appended claim transitions
(`planned -> claimed`, `claimed -> in_progress`) and nothing else, and the
snapshot when that log qualifies and the snapshot's working bytes are exactly
what the status store materializes from it. Which files take these legs is
decided by the owner's `is_status_state_path` (the `STATUS_STATE` kind), not
by a local filename list, so no kind is re-derived here; what the predicate
adds is again a DIFF verdict the owner's whole-file kind answer cannot give
(a hand-edited snapshot, a rewritten log prefix, a non-JSON or non-claim
appended line, or a log the store cannot read all keep the file, so the
claim is still refused). The allocator's `created_at` stamp likewise counts
as runtime frontmatter on the `WP##.md` leg only together with a
`base_commit` change.
