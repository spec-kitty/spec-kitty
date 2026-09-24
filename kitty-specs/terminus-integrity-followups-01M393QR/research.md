# Phase 0 Research — Terminus Integrity Follow-ups

Consolidated from three read-only, profile-loaded research lenses re-verified against this base (the #5012 spine on `fix/terminus-merge-integrity`). Full per-lens detail: `work/epic-5001-research/followup-{architect,debbie,paula}.md`.

> **Supply-chain note:** this mission adds/upgrades/removes **no** dependency, so directive `051-supply-chain-install-safety` does not gate it. No adversarial supply-chain evidence is owed. The mandatory adversarial evidence for this mission is the post-plan / post-tasks / pre-merge brownfield squads (recorded in `contracts/adversarial-evidence.md`).

---

## WS1 — #5013 squash-content-soundness (architect lens)

**Decision:** Replace the squash PASS early-return in `MergeOutcomeVerifier.verify` (`merge/reconciliation.py:301-302`) with a **squash-sound closed-world blob-attribution axis** run inside `verify()`, riding the existing verify → FAIL → `_rollback_target_after_failed_reconciliation` → exit-1 boundary.

- **Algorithm:** attribute every non-bookkeeping content path of the aggregate squashed diff `B..T` (B = persisted `pre_mutation_target_sha`, T = post-merge target tip) against the union of approved lanes' **first-parent authored blobs** `(path, blob_sha)`. A target path whose final blob is authored by no approved lane ⇒ unattributable ⇒ FAIL ⇒ rollback.
- **Why squash-sound:** compares **tree/blob content**, never lane-tip SHAs or per-lane patch-ids (both destroyed by squash).

**Rationale:** the default `spec-kitty merge` resolves to squash, which sets `verify_reachability=False` and short-circuits to PASS before `_missing_approved` / `_reachable_excluded` / `_unattributable_content` run. The only squash "content proof" (`_assert_squash_projected_content_landed` → `projected_content_matches_target`, `bookkeeping_projection.py`) checks **bookkeeping paths only**, so a removed-WP's code riding a carrier lane ships at exit 0 on the default path.

**Alternatives considered:**
- *(a) patch-id of the squashed result diff* — REJECTED as primary: a squash yields one opaque aggregate patch-id that cannot be decomposed per-WP.
- *(b, unrefined) tree-replay of approved lane tips* — REJECTED: a carrier lane tip already contains the smuggled content; only first-parent authorship excludes it. Blob-granularity attribution avoids conflict-prone replay.
- *Option B: post-projection check in the executor* — REJECTED: splits content authority across two modules and needs a second rollback path.

**New plumbing:** `git_probes.py::blob_id_at(ref, path)` + `changed_paths_in_range(base, tip)` (raise `GitProbeError` → REFUSE, extending the fail-closed discipline); a new claim field `authored_blobs` populated in `build_approved_wp_set` / `_collect_authored`; a new `_unattributable_content_squash` verifier method; reorder so the `excluded_window_base is None` REFUSE fires for squash too.

**Fail-closed:** `GitProbeError` or a `None` window base ⇒ REFUSE, never vacuous PASS (NFR-001).

**Honest residual (deferred, tracked — NOT green-washed):** 3-way merge-resolution content (a path whose final blob equals neither parent verbatim) is bounded, mitigated by file-disjoint lanes, gated behind `enforce_closed_world`. Stays a follow-up; if uncovered, leave it uncovered or `xfail(strict)` with an honest reason. → C-003.

**Red-first:** remove `xfail` on `test_terminus_reconciliation_property::...no_excluded_commit_reachable[squash]`; **default-squash variants** of #4945/#4977/#4981 must assert via **blob/tree-presence** (removed file absent from target), NOT the patch-id window (which is not squash-sound). Add a NEW clean-squash no-false-fail param + direct unit tests for the three new helpers.

---

## WS2 — resume-strategy + lane-tip SHA (debbie lens)

**Decision (a) — honor persisted strategy:** persist `strategy=resolved_strategy.value` at fresh `MergeState` creation (`merge/resolve.py::_load_or_create_merge_state`) AND read it back on resume with precedence **explicit `--strategy` > persisted > config > SQUASH** (`cli/commands/merge.py`). Mirror the landed C-1 target-authority pattern exactly.

**Rationale:** `MergeState.strategy` is a **fully dead field** today — never written with the operator's choice (always the dataclass default), never read on resume; `--resume` collapses to config-or-SQUASH, silently downgrading a `--strategy merge` operator. Both halves are mandatory: half-2 without half-1 reads the dead default and silently *upgrades* a squash operator.

**Decision (b) — preserve pre-interrupt lane tips:** persist `pre_mutation_coord_sha/_ref` (symmetric to the already-persisted `pre_mutation_target_sha`) AND a per-lane pre-interrupt tip map on `MergeState`; anchor resume consolidation + the absolute-reachability axis to the persisted tips, not the live resume-start coord checkpoint.

**Rationale (proven empirically):** #4991 forced `--strategy merge` on resume → PASS; #4982 forced `--strategy merge` → still FAIL (WP01's approved commit unreachable, no mission content on target). Root: `_capture_reconciliation_claim` calls `_capture_coord_checkpoint` **live** every run; on resume the checkpoint already contains attempt-1's consolidation, so the already-consolidated WP's range (`commits_in_range(coord_base, lane)`) is empty and the gate passes vacuously while the commit is not on target. The target window base is persisted+reread; the coord base is **not** — that asymmetry is the bug.

**Adjudicated open question (WP09 residual):** the `SafeCommitHeadMismatch` on a non-default target **was a real product gap, already CLOSED by #5012's FIX A** (`commit_merge_bookkeeping` threads `destination_ref_override=lanes_manifest.target_branch`). Verified in code + empirically. **Sole residual blocker for #4985/#4991 is Decision (a).**

**Child close-out:** #4985/#4991 close on (a) alone; #4982/#4997 need (a)+(b). Confirmed scope = both (Decision `01M393S7...`).

**New hazards + guards:** H1 strategy-flip across resume ⇒ REFUSE if explicit `--strategy` ≠ persisted; H2 pre-fix dead-default read ⇒ already fenced by the FR-012 legacy-marker refusal before strategy is consumed; H3 per-lane tip resurrecting a superseded tip ⇒ treat the persisted tip as a CAS expectation (current == persisted-or-descendant, else REFUSE); H4 unresolved persisted coord base on resume ⇒ REFUSE, never collapse to live checkpoint.

**Red-first:** `test_repro_{4982,4985,4991,4997}.py` are `xfail(strict)` (verified 4 xfailed, no xpass at HEAD). #4985/#4991 markers off after (a); #4982/#4997 off only after (a)+(b). Fixtures already call `write_post_fix_marker` and set `strategy="merge"` — fixture wiring is done; only the product fix is missing.

---

## WS3 — #4970 surface-write self-materialization (paula lens)

**Decision (a) — refuse stale-local-head self-materialization:** augment the self-materialization arm in `assert_coord_write_materialized` (`mission_runtime/write_target_degrade.py:213-214`) to a 3-part predicate: `UNMATERIALIZED AND local-head AND branch carries NO committed artifact-of-this-kind` → allow; else fall through to the existing REFUSE. Detect committed content via `git cat-file -e <coord_branch>:kitty-specs/<slug>/<matrix filename>` for both `issue-matrix.json` and `issue-matrix.md`. Fail-closed on unreadable git (treat as content-present).

**Rationale:** today the "window" is a filesystem-only proxy (`UNMATERIALIZED` + local-head) that never inspects committed content, so a stale local head already owning committed matrix rows is misclassified as a virgin first-write and clobbered.

**Decision (b) — route issue-verdict through the write resolver:** insert a fail-closed `resolve_for_write(root, slug, ISSUE_MATRIX)` at the top of `do_issue_verdict` (`cli/commands/agent/issue_verdict.py`), translating `ActionContextError` → the command's error type. Today it resolves via the degrading READ resolver (`coord_read_dir_for`) → returns None on unmaterialized coord → degrades to PRIMARY → empty row map → clobber.

**Alternatives considered — which writers get `terminus_write`:** RECOMMEND **no blanket flip**. Only the ISSUE_MATRIX / issue-verdict chain (already gated at the write seam; add the read-side reroute). Explicitly NOT `status_transition` (high-frequency append-only log — a blanket flip false-refuses every lane transition on a pruned-worktree host), `decision_log` (fail-open by design), `bookkeeping_commit` / `retrospective_terminus` (deliberately degrade to PRIMARY at close; their integrity is S-B's job). → C-003.

**Boundary (clean):** the git probe homes inside `specify_cli.coordination.surface_resolver` beside `_coord_branch_is_local_head`, which `assert_coord_write_materialized` already lazy-imports — **no new module edge, no `_baselines.yaml` cap growth** (the `coordination` subpackage is already ledgered). → C-002.

**Red-first:** `test_repro_4970.py` is `xfail(strict)`; its reason already names both defects. Decision (a) alone flips the marker (the ISSUE_MATRIX write already runs the gate); (b) is the coupled ownership-correctness half the reason demands. Land both; remove the marker at integration once (a) lands. No fixture changes.

---

## Cross-workstream synthesis

- **Independence:** WS3 (WP02) is fully isolated. WS1 (WP03) and WS2 (WP04) are file-disjoint from each other, but **both wire into `executor.py`** — consolidated into the single serial WP05 to preserve the "one owner per file" guard (retrospective lesson).
- **The #5012 spine already closed** two premises the original brief listed as open: the vacuous-manifest hoist and the `pre_mutation_target_sha` persistence. Verified. The coord-base persistence (WS2b) is the *remaining* asymmetry.
- **Transaction boundary preserved (C-004):** every new check runs before teardown/push/exit-0; the CAS ref discipline and the verify→FAIL→rollback path are extended, not bypassed.
