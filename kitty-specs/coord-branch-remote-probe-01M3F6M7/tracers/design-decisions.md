# Tracer: Design Decisions

Seeded at planning; appended during implementation.

- **D-01 — Extend the one canonical probe, do not fork it.** The remote check is added to
  `_coord_branch_exists` (surface_resolver.py), the ONE authority both readers and the doctor
  consume. No second parallel branch-existence probe (C-001). `_coord_branch_is_local_head`
  (the WRITE self-materialization gate, #4970) stays STRICTER — a remote-only branch remains
  "not a local head" so the write gate keeps refusing self-materialization (C-002).
- **D-02 — Remote probe is `git ls-remote --heads <remote> <coord>`, gated behind the local
  fast paths.** Runs only after local-head miss AND `refs/remotes/` scan miss, with a bounded
  timeout. A non-empty match ⇒ present. Any error / non-zero / timeout / unreachable ⇒
  fail-closed "present" (NFR-002). Zero round-trips on the common full-clone/local-head path
  (NFR-001).
- **D-03 — "Exists on ANY remote", not only origin.** The guard enumerates configured remotes
  (`git remote`) so a branch on a non-`origin` remote still counts as present. Avoids a
  false-deleted verdict on multi-remote setups.
- **D-04 — Doctor flatten re-verifies independently (WP02).** Even reaching a
  NEVER_CREATED finding, `_fix_never_created_branches` re-checks the remote before the
  destructive `flatten_coordination_metadata`; present-on-remote ⇒ skip + actionable message.
  Independent of the probe so a future probe regression cannot reach the destructive mutation.
- **D-05 — Implement auto-commit demotion guard (WP03) is a SEMANTIC check, not a blanket
  meta.json exclusion.** meta.json legitimately belongs in planning artifacts; the guard fires
  only when the uncommitted diff DROPS `coordination_branch` or DEMOTES `topology`. Ordinary
  meta.json edits (e.g. `source_description`) commit unchanged (US3 scenario 2).
- **D-06 — Guidance rewrite (FR-006).** `CoordinationBranchDeleted.next_step` and the doctor
  hint must not steer a remote-present situation toward flatten; they name "the branch exists
  on the remote — fetch it / materialize the worktree". Scoped to the remote-present case so
  the genuine-deletion guidance is preserved.

## Post-spec adversarial squad fold-in (2026-09-26, 2 opus lenses)

- **D-07 — Tri-state, not binary (both lenses, HIGH).** `git ls-remote` distinguishes
  MATCH (present) / reachable-CLEAN-MISS exit0-empty (that remote votes absent) /
  ERROR|TIMEOUT (fail-closed present). CRUCIAL: **zero remotes configured ⇒ keep today's
  local-authority "absent"** — a literal "no remote ⇒ present" would red the origin-less
  DELETED tests (`test_coord_never_created.py`, `test_backfill_topology` T007). The real
  trigger always has origin configured.
- **D-08 — C-001: a SECOND remote probe already ships.** `_branch_resolvable`
  (`mission_type.py:1292`) does local-head-OR-ls-remote-across-all-remotes but fails toward
  FALSE (reopen-eligibility). Cannot literally unify (opposite fail-direction). Resolution:
  extract ONE shared tri-state primitive `{HIT, CLEAN_MISS, ERROR}` in a canonical git-probe
  home; both consumers apply their own fail-direction. Also fixes `_branch_resolvable`'s
  missing-timeout hang. WP02/WP03 consume it too.
- **D-09 — Third probe consumer.** `backfill_topology.py:220` also reads `_coord_branch_exists`
  (skip-flatten decision) — correct direction, but WP01 blast radius must add
  `tests/specify_cli/migration/test_backfill_topology*.py`.
- **D-10 — C-002 safe by construction.** `_coord_branch_is_local_head` (write gate) and
  `coord_branch_has_committed_artifact` stay LOCAL-strict; WP01 must NOT add remote-awareness
  to them. Remote-only ⇒ still "not a local head" ⇒ write keeps refusing self-materialization.
  Prove via `tests/mission_runtime/test_write_target_degrade_selfmat.py`.
- **D-11 — Memoization (F3).** Single-branch/CI checkouts never materialize coord, so
  `probe_coord_state`'s git arm fires the network on EVERY coord read. Memoize the remote
  lookup per-process keyed `(repo_root, coord_branch)`.
- **D-12 — Guidance dead-end (F4).** The existing `git worktree add <coord>` recovery hint
  FAILS on a single-branch clone (ref not fetched). FR-006 branches the message: remote-only ⇒
  "`git fetch origin <coord_branch>` first". Delivered on the emit-refusal path (the read path
  degrades silently), not the read fallback.
- **D-13 — Read path fails closed (F5, tiered rigour on #4959/#4970 seam).** Verify
  `_resolve_status_surface_dir` (resolution.py:~1285) raises `CoordinationWorktreeUnmaterialized`
  for the remote-only site, never returns an empty coord_dir a reader treats as "nothing
  written". (Cf. coord-worktree-unmaterialized memory gotcha.)
- **D-14 — WP03 deterministic REFUSE (F6).** Not "refuse OR withhold". Predicate: HEAD
  `coordination_branch` non-null → working absent/null, corroborated by
  `routes_through_coordination(HEAD) AND NOT routes_through_coordination(working)`. Baseline
  `git show HEAD:kitty-specs/<slug>/meta.json`; exit 128 (untracked) ⇒ ALLOW; corrupt ⇒ REFUSE.
  Hook the staging DECISION seam (`detect_structural_planning_changes` /
  `resolve_planning_artifact_staging`), not a parallel gate.
- **D-15 — Dependency edges: WP02→WP01, WP03→WP01.** Files non-overlapping
  (surface_resolver+shared-primitive+mission_type / _coordination_doctor / implement).

## WP01 implementation deviation (2026-09-26)

- **D-16 — FR-006's guidance branch lands on `CoordinationWorktreeUnmaterialized`, not
  `CoordinationBranchDeleted` (deviation from D-06/D-12's literal wording).** Traced every
  `CoordinationBranchDeleted.for_mission(...)` call site
  (`surface_resolver.py`, both `_read_path_resolver.py` sites, both `mission_runtime/
  resolution.py` sites): all five gate on `CoordState.DELETED`, which `probe_coord_state`
  can only return when `_coord_branch_exists` answers `False`. After WP01's own fix, a
  remote-only branch makes `_coord_branch_exists` return `True` (HIT/ERROR), so
  `CoordState.DELETED` — and therefore `CoordinationBranchDeleted` — is now STRUCTURALLY
  UNREACHABLE for a remote-only branch; only `CoordState.UNMATERIALIZED` (→
  `CoordinationWorktreeUnmaterialized`) is reached. Branching `CoordinationBranchDeleted
  .next_step` on local-head-vs-remote-only would be dead code with no non-vacuous test
  (violates the charter's architectural-gate-non-vacuity standing order — "a gate cannot
  self-validate"). Implemented the FR-006 fetch-first branch on
  `CoordinationWorktreeUnmaterialized.next_step` instead — the site actually reached — proven
  live by the two T001 regressions (post-fix assertion: `next_step` contains
  `git fetch origin <coord_branch>`). `CoordinationBranchDeleted.next_step` is untouched;
  its genuine-deletion wording is unaffected and still correct for the case that DOES reach
  it (both remotes clean-miss, or zero remotes + no local head).
- **D-17 — Doctor-hint branching (mission_type.py "where applicable" in the WP prompt) is
  WP02 territory, not WP01's.** `_coordination_doctor.py` is not in WP01's `owned_files`; WP01
  only fixes the shared probe + the `CoordinationWorktreeUnmaterialized` read-path guidance it
  now reaches. WP02 (`_fix_never_created_branches` re-verification, per D-04) owns the
  doctor-surface half of FR-006.
## WP02 implementation (2026-09-26)

- **D-18 — `repo_root` is an optional parameter, not a signature break.** `_fix_never_created_
  branches(findings, repo_root=None)`: every pre-existing unit test (4 in
  `test_coordination_doctor.py`, 2 in `test_doctor_coordination.py`) calls it with the
  single-arg legacy signature and asserts unconditional flatten — changing the guard's
  activation to "opt-in via a keyword the real dispatch path always supplies" instead of
  "always-on" avoided touching any file outside WP02's `owned_files` while keeping those
  pre-existing tests' contract (and, per D-04, still closing the real `--fix` end-to-end path,
  since `_apply_never_created_fix` — the only real caller — now always passes `repo_root`).
- **D-19 — Skip reason is a lookup, not a hand-rolled second remote check (C-001).**
  `_coord_branch_remote_skip_reason(repo_root, coord_branch)` is a thin one-branch-per-outcome
  wrapper over WP01's `remote_branch_lookup`; it owns zero git subprocess calls itself. HIT and
  ERROR both return an actionable skip-reason string (fail-closed, NFR-002); CLEAN_MISS and
  NO_REMOTE both return `None` (proceed) — mirroring D-07's tri-state-plus-no-remote shape from
  WP01's design, reused rather than re-derived.
- **D-20 — No remote-name in the skip message.** `remote_branch_lookup` returns only the
  tri-state outcome, not which remote matched — the WP prompt's example phrasing ("exists on
  `<remote>`") named a specific remote, but surfacing one would require a second query or
  threading remote names back out of the shared primitive (scope creep on a WP01-owned surface,
  locality-of-change). The skip message instead says "still exists on a remote" — actionable
  (`git fetch` is remote-agnostic) without inventing a return shape WP01 does not provide.

## WP03 implementation (2026-09-26)

- **D-21 (WP03) — the demotion guard lives entirely in `implement.py`, not
  `implement_cores.py`, even though `detect_structural_planning_changes` /
  `resolve_planning_artifact_staging` (the "staging DECISION seam" the WP prompt names) are
  physically defined in `implement_cores.py` and only re-exported into `implement.py`.**
  WP03's `owned_files` lists only `implement.py`; the WP prompt's line-number pointers
  (`:678`/`:724`) actually resolve to the CALL sites of those two functions inside
  `_ensure_planning_artifacts_committed_git` in `implement.py`, not their definitions. Read
  literally as "extend `detect_structural_planning_changes`" this would require editing
  `implement_cores.py` (out of scope / ownership violation) — resolved by hooking a new
  sibling guard (`_refuse_if_meta_json_demotion`) at the same call-site position
  (immediately after `files_to_commit = plan.files_to_commit; if not files_to_commit: return`,
  mirroring the existing `_print_structural_planning_refusal` fail-closed pattern one seam
  earlier) rather than touching the core functions themselves. This satisfies "hook the
  staging DECISION seam, not a parallel commit gate" without crossing the ownership boundary.
- **D-22 (WP03) — baseline read uses a fresh `git show HEAD:<path>` + `json.loads`, not the
  `mission_metadata` loader.** The predicate needs to distinguish THREE outcomes (no baseline
  / baseline-but-corrupt / baseline-and-parseable), and `mission_metadata.load_meta` family
  helpers collapse "missing" and "corrupt" (legacy-tolerated `except (OSError,
  MissionMetaReadError): continue`, per `implement.py:479`) into one outcome — exactly the
  distinction FR-005's contract needs (untracked→ALLOW vs corrupt→REFUSE are different
  verdicts). A small dedicated `_read_json_at_ref` (returns `(has_baseline, parsed_or_None)`)
  keeps the three-way split explicit instead of forcing it back through a loader designed to
  blur it.
