# Research: Consolidation window provenance and reconciliation split

**Mission**: `consolidation-window-provenance-01M6Y84D` · **Phase**: 0 · **Date**: 2026-11-08
**Inputs**: `spec.md`; the operator-confirmed intent and Engineering Alignment (2026-11-08); the pre-spec brownfield squad: architect-alphonso (design options and scope), paula-patterns (code shape and split risk), researcher-robbie (prior art and current truth), plus a symbol inventory of `reconciliation.py`. These squad reports are the evidence base. Their file:line anchors were spot-checked on the current branch (`reconciliation.py` 4,096 lines; `transition_pipeline.py:180-219` stamp site; `write_branch_bound.py:55-120`; `wp_attribution.py:665-699`; `git_probes.py:666` `path_state_at`; the three `build_approved_wp_set` call sites `phase_claim.py:521`, `forecast.py:422`, `phase_gate.py:72`; the #5048(b) site `reconciliation.py:3715-3728`).

No `[NEEDS CLARIFICATION]` remains. Every fork the squad raised was settled by a resolved Decision Moment or by the Engineering Alignment.

## R-01 — Where the window is recorded

- **Decision**: On the status transition event, under one namespaced key `policy_metadata.wp_window`, written on each non-migration move of a lane-mapped work package into `claimed` / `in_progress`. Readers bind to the **first** such event (Decision Moments `window_source`, `window_writer`).
- **Rationale**: The event log is already the only authority (`2026-09-29-1-closed-world-refuse-on-mixed-lanes` Decision 2; `2026-10-04-5-approval-stamp-bounds-the-approved-claim` Options 4 and 10 reject a second store). `policy_metadata` already carries `lane_head`, so the extension ships from core alone; the spec-kitty-events payload types it as `dict[str, Any]`. A typed gap value distinguishes "capture failed" from "never recorded", which the best-effort `lane_head` stamp cannot do (`status/lane_head.py` C-1).
- **Writing on every opening move, reading the window opener**: the pure pipeline cannot know whether a move is a work package's first entry without reading its history, and it must stay history-free and git-free. Writing on every entry into `claimed` / `in_progress` costs nothing (the reading is already taken for `lane_head`). The reader picks the window opener (R-16, FR-021); it superseded the original "first entry, later entries never consulted" rule after the post-plan squad.
- **Alternatives considered**:
  - (a) Derive windows only from existing `lane_head` stamps, with no new key (robbie Q1-a, alphonso "Layer 1"). Rejected by the operator: it cannot express a typed gap, and the lane path must not re-derive the opening from older stamps.
  - (b) A separate provenance file or sidecar. Rejected: a second authority and a second read door (ADR `2026-11-06-2-one-status-read-contract`), already rejected twice.
  - (c) A new canonical event type `WorkWindowRecorded`. Rejected for now: it duplicates the transition, adds an atomicity obligation, and is blocked on a spec-kitty-events release (ADR `2026-10-14-1-event-native-core-one-canonical-event-writer` D-4).
  - (d) Write only on the first opening move, with the shell reading history. Rejected: it adds a history read on every move and moves window logic into the shell.

## R-02 — One window model, with named variants (inventory of today's notions)

- **Decision**: The ADR defines **one** work-package window, `(window-open SHA, newest approval stamp]`, and maps every existing notion to it or to a **named window variant**. No variant's verdict changes in this Mission except FR-007 on the lane path.
- **As-is inventory** (alphonso §0, robbie F-05), which the ADR table reproduces:

  | # | Notion | Home | Disposition in the window model |
  |---|---|---|---|
  | 1 | `coord_base_ref` (lane-tip range base) | `phase_claim.py:515` | `ClaimInputs.coord_base` |
  | 2 | `excluded_window_base` (target pre-mutation tip) | `phase_claim.py:518` | `ClaimInputs.target_base` (claim base input) |
  | 3 | `_bound_claim_base` | `reconciliation.py:2191` | derived from 1 and 2, unchanged; the degraded window's opening edge |
  | 4 | presence `lane_bases` = `first_governed_open_stamp` | `wp_attribution.py:665` | **variant "lane anchor"**: `blocked` opens; unchanged |
  | 5 | `WorkWindow` implementation / review windows | `wp_attribution.py:317-356` | **variant "canceled-content windows"**: class-change windows of mixed lanes; unchanged |
  | 6 | approval stamp (newest non-migration approval `lane_head`) | `approved_bound.py` | the window's closing edge, and the fallback bound |
  | 7 | evidence window `planning_commit_sha..tip` | `wp_evidence.py:166` | **variant "owned-file evidence"**: not stamp-based; unchanged |
  | 8 | `single_branch` authorship window `merge-base(target, mission)..mission` | `lanes/single_branch_landing.py:223` | unchanged; `single_branch` approval windows read the recorded opening when present (FR-011) |
  | 9 | closed-world anchors (dependency-lane tips + target base) | `reconciliation.py:2455` | anchor SHAs from `ClaimInputs`; frozen on resume (FR-015) |

- **Rationale**: Unifying the `blocked` opener asymmetry (rows 4 and 6/approval opener) would change closed-world verdicts, which is outside NFR-002.
- **Alternatives considered**: (a) unify all notions behind a single `WindowLedger` substrate now (alphonso §1, Design A). Deferred: it is the right end state, but it would turn the split into a redesign. (b) remove the `blocked` asymmetry. Rejected: an unscoped verdict change.

## R-03 — Missing window: fallback plus gap report, never a refusal on its own

- **Decision**: A work package whose first opening event lacks the key ("not recorded"), records a capture failure ("capture failed"), or records a SHA that is not on the lane ("not on lane") is judged with a degraded window `(claim base, approval stamp]`. That is exactly today's approval-stamp coverage for that work package. It is listed in the gap report. It is never refused for the gap alone, and no refusal code is added (Decision Moment `missing_window_rule`; spec C-010).
- **Rationale**: Missions in flight at upgrade, including those mid-consolidation, must reach their pre-upgrade verdict (US3). On a lane where every work package has a gap, the union of degraded windows equals today's approval-stamp bound, so US3-1 and US3-2 hold by construction. The gap is not silent (robbie F-14): it is reported, and `APPROVAL_STAMP_MISSING` (a missing *approval* stamp) still refuses as today.
- **Alternatives considered**: refuse plus attest, as S8 did for `single_branch` (robbie Q6-a). Rejected: it would strand in-flight Missions. A warn-first period with no fallback is equivalent to the fallback, but without a defined verdict.

## R-04 — Typed gap reasons and recorded causes

- **Decision** (amended after the post-plan squad, R-16): four reader-level reasons: `not_recorded`, `capture_failed`, `lane_branch_missing`, `not_on_lane`. Two are written to an event: `capture_failed`, with a closed `cause` set (`git_error`, `probe_error`) and a free-text `detail`, and `lane_branch_missing` (no `cause`), its own reason because a missing lane branch is the normal state before `implement`. `not_on_lane` also covers a SHA that does not resolve in this clone (FR-022). A not-applicable reading (planning lane, work package not in `lanes.json`, no `lanes.json`) writes no key.
- **Rationale**: The writer can only know what it observed. "Not recorded" and "not on lane" are facts about the log and the lane at read time. A closed cause set keeps the contract checkable by the Java writer.
- **Alternatives considered**: writing a gap for not-applicable readings. Rejected: it would add noise on planning lanes, which are never windowed.

## R-05 — `ClaimInputs`: one value, one constructor, three sources

- **Decision**: A frozen `ClaimInputs` with these fields: target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins (refs plus SHAs), excluded canceled work packages, strategy, the status directory read, and its `source` ∈ {`LIVE`, `LIVE_THEN_SAVED`, `SAVED`}. One constructor builds it. `forecast.py`, `phase_claim.py` and `phase_gate.py` adopt it in Phase 2, **preserving every per-mode quirk**. Phase 4 aligns the forecast's excluded set (FR-013) and makes the closed world on resume read the frozen anchors (FR-015).
- **Rationale**: The three call sites already call the same builder; parity is lost in the **inputs** (alphonso, paula P-07). Doing the extraction behaviour-preserving first lets the corpus witness it. Each alignment is then a small red-first change.
- **Frozen dependency anchors**: derived from `ConsolidationState.pre_interrupt_lane_tips`, because dependency lanes are Mission lanes, so no new state field is expected. IC-08 confirms coverage. A pre-upgrade record without a frozen tip for a dependency lane keeps today's live read, and the ADR names this a degraded anchor.
- **Alternatives considered**: (a) correct the inputs inside the extraction. Rejected: it mixes a behaviour change into a refactor (C-004). (b) Route claim reads through `resolve_status_read` now (alphonso, ADR `2026-11-06-2-one-status-read-contract`). Deferred: that ADR is Proposed and parity does not require it. `ClaimInputs` records the status directory each mode reads today.

## R-06 — Split unit and shape

- **Decision**: The split covers both halves of the module, claim side and verify side. The units are: a shared kernel; claim types (whole `ApprovedWpCommitSet`); rendering; closed world (with external dependency refs); approved bound (with write-branch and the lane-tip re-check); the canceled pair (mixed lane + canceled dependency, one slice); authorship + presence (one slice, one spine walk); the verifier (`Divergence` / `VerifyResult` whole); claim orchestration (`build_approved_wp_set`, refusal order whole). The modules are **flat siblings** named `reconciliation_<unit>.py`, behind `reconciliation.py` as a re-exporting facade.
- **Rationale**: The verifier alone is about 13% of the file (robbie F-06). The kernel is small, about eight symbols (paula P-06). Authorship and presence share one walk (paula P-03), and the canceled pair shares a refusal stack (paula R-2). A flat layout avoids a subpackage named like the facade, and avoids a new `__init__.py`, which would bring in the version-bump rule.
- **Alternatives considered**: (a) verifier-only split. Rejected: it leaves the hotspot `_collect_authored` untouched. (b) Per-check claim records composing `ApprovedWpCommitSet` (alphonso `collect`/`judge`). Deferred: it multiplies construction-site risk across about 33 test files (C-006). (c) Rewrite caller imports now. Rejected (C-005); migrating callers is out of scope.

## R-07 — Proving "pure move"

- **Decision**: The proof has four parts: the characterization corpus (verdict status, refusal code, divergence fields, exit code per mode), the refusal-precedence matrix, and the surface pin with identity, all recorded before the move and byte-identical after; plus at least one deterministic seeded mutation per moved check (a monkeypatched verdict that always passes, or a flipped predicate) that must turn a corpus scenario red.
- **Rationale**: Seeded mutations are deterministic and cheap in CI. `mutmut` exists (`pyproject.toml [tool.mutmut]`), but it is slow and sandbox-sensitive, so it stays an optional local cross-check.
- **Diff coverage**: a pure move shows up as added lines to the diff-cover ≥ 90% gate (paula P-13). The corpus executes the moved lines. No coverage exemption is added (NFR-005).
- **Alternatives considered**: an AST check that moved bodies are byte-identical (paula Q7-c). Optional: a reviewer aid, not a gate, because import-line edits make bodies differ legitimately.

## R-08 — Test interception after the move

- **Decision**: Add `tests/consolidation/reconciliation_family.py` (`RECONCILIATION_FAMILY` plus a patch helper), copying the `EXECUTOR_FAMILY` precedent. Add a guard that fails when a string target `specify_cli.consolidation.reconciliation.<name>` names a name that module does not look up itself. After the split the facade looks up nothing, so every stale patch fails until it is retargeted.
- **Rationale**: Without the guard, a patch on the facade succeeds but intercepts nothing, and the tests go vacuously green (alphonso, paula P-04).
- **Alternatives considered**: inject the git probes instead of patching. Rejected: it is not a pure move in shape.

## R-09 — `--dry-run` and the approved bound: docs vs code

- **Decision**: The corpus pins the forecast verdict for a post-approval-commit fixture. If the forecast already reports the bound refusal (`forecast.py:422` calls `build_approved_wp_set`, which runs the bound), the "residual" sentence in CLAUDE.md and in `2026-10-04-5-approval-stamp-bounds-the-approved-claim` is corrected as campsite cleaning, in the ADR concern. Until the test runs, the ADR does not state either claim.
- **Rationale**: robbie F-10 and alphonso both read a contradiction; only execution settles it.

## R-10 — #5048(b): deletion inferred from any probe error

- **Decision**: Replace `blob_id_at` + `except GitProbeError: deletions.add(path)` in `_final_authored_walk` with `git_probes.path_state_at`. `None` means the path is absent, so it is a genuine deletion. `GitProbeError` means the read failed, so the claim refuses through the existing claim-time refusal channel, naming the path and the error. The change is red-first, in Phase 4, after the move (Decision Moment `live_defects`).
- **Rationale**: `path_state_at` already exists for exactly this distinction (`git_probes.py:666`, #5046 WP04). It keeps one git read per path.
- **Alternatives considered**: pin and file separately (robbie F-09). The operator ruled the fix in scope; the pin lands in Phase 1 as a strict `xfail` of the intended verdict.

## R-11 — Resume and live dependency-lane anchors

- **Decision**: `_closed_world_anchors` takes the dependency-lane tips from `ClaimInputs`. On the `SAVED` source these are the tips frozen at claim capture. Every caller of the anchors receives the same values. Red-first, Phase 4.
- **Rationale**: The planning-lane exclusion in the same function already exists for this hazard (`reconciliation.py:2474-2478`). The gate re-check already uses frozen SHAs (`run.bound_anchor_shas`).
- **Alternatives considered**: defer to #7359 (alphonso). The operator ruled it in scope.

## R-12 — Cross-repository writer and durability horizon

- **Decision**: Python writes the key now. A spec-kitty-events issue asks the Java write service to write, preserve and type it (FR-006): filed as spec-kitty/spec-kitty-events#229 (operator ruling 2026-11-08, Decision Moment `01M6YAG2HE6Q2XNQMGK6X3MBEK`). The durability horizon is **one consolidation attempt** (forecast, fresh run, resume, teardown); surviving a rebase landing is not a goal. The key is classified `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS` (ADR `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`).
- **Rationale**: The stamp writer moves to the Java service (`2026-10-22-1-the-java-write-service-is-the-canonical-event-writer` D-4), and the write-service pin is still pending. Plain SHAs from ref reads are what a GitPort can produce.

## R-13 — Residual counts and ADR hygiene

- **Decision**: The corpus counts the strict-`xfail` residuals from the test files (`test_canceled_line_attribution_6309.py`, `test_canceled_content_residuals.py`, `test_approved_bound_residuals.py`, `tests/integration/test_single_branch_approval_windows.py`), not from ADR prose. The ADR cites by full slug, and names #5703 (lane-id rebuild orphans recorded windows) as a limit.

## R-14 — No version bump for the `status/__init__.py` re-export

- **Decision**: Re-exporting `WP_WINDOW_KEY` touches `src/specify_cli/status/__init__.py`. **Operator ruling (2026-11-08): no version bump.** The Mission adds a changelog fragment under `docs/changelog/unreleased/` and does not change the `pyproject.toml` version. This is consistent with charter standing order 7 ("no version numbers in scope"), which wins over the CLAUDE.md `__init__.py` rule.
- **Alternatives considered**: bumping `pyproject.toml` in the Mission PR. Rejected by the operator.

## R-15 — Exemption anchors on the window path (post-plan ruling)

- **Decision** (operator, Decision Moment `01M6YAFYHT0RMVZB03THW1WWSE`): on the lane window path, a lane's **own** approval stamps no longer exempt its commits; the windows decide. The approval stamps of **other** lanes stay exemption anchors, beside the closed-world anchors, because a commit another lane's approval stamp reaches is content inside a reviewed tip. FR-007 and SC-001 state that exception; a dependency-chain fixture pins it (US2-6), and the own-lane variant refuses (US2-7).
- **Rationale**: today `_approved_bound_verdict` passes `stamp_anchors` of every bounded lane, the lane's own included (`reconciliation.py:2188-2192, 2254-2268`), and `write_branch_bound._outside` skips the exempt set, so the US2 stray commit (reachable from WP02's own stamp) would never be "outside" and FR-007 could not go green (debbie D-1). Dropping every cross-lane exemption would refuse dependency chains in every multi-lane Mission.
- **Consequence**: a lane on which every work package has a gap keeps today's anchors, own stamps included, by running today's check unchanged (FR-023).

## R-16 — The window opener (post-plan ruling)

- **Decision** (operator, Decision Moment `01M6YAG16WDVMM37HCJCHAC5YW`): the window opens at the first non-migration move into `claimed` / `in_progress` after the work package last returned to `planned`, skipping leading openers that recorded "lane branch missing" (written as its own gap reason, not `capture_failed`), with the cycle's openers ordered by lane topology and by event-log order when their SHAs are unrelated (FR-021).
- **Interpretation recorded for review**: review rejections move a work package `in_review → planned` (`review/arbiter.py:270`, `tasks_transition_core.py:583`), and the transition matrix allows `approved → planned`. Reading every move to `planned` as a reset would put a reworked work package's own earlier commits outside its window, refused with no attestation route, and would contradict US2-4. A move to `planned` out of `for_review`, `in_review`, `approved` or `done` is therefore rework (no reset); any other move to `planned` (today `in_progress → planned`, or a forced move) is a rewind (reset). The operator can overturn this in review; the spec Assumptions and the ADR state it.
- **Rationale**: a "first claim forever" rule makes `move-task --to claimed` before `implement` a permanent gap (debbie D-2, renata F-12), lets a skewed-clock rework narrow the window into an un-attestable over-refusal (D-3, `event_log_merge.py:178-184` re-sorts by `at`), and over-widens the window of a rewound work package (D-5). The skip is sound because a "lane branch missing" reading proves no lane commit existed at that instant; a deleted-and-recreated lane is guarded at `implement` by `DESTROYED_LANE` / `LANE_WORK_TIP_UNKNOWN`.
- **Residuals named in the ADR**: parallel claims on one lane and a claim parked without returning to `planned` (over-wide; strict `xfail`); the rewind boundary is located in event-log order, not topology.
- **One selector**: `window_opener_events(events, wp_id, *, cycle)` serves the recorded-window reader (`cycle=True`) and `approval_window_open_stamp`'s `single_branch` derivation (`cycle=False`, today's rule, FR-011), so the rule lives once (debbie D-7).

## R-17 — One frozen anchor set on resume (post-plan ruling)

- **Decision** (operator, Decision Moment `01M6YAFZVZAYR4G20Q2X4PN0FT`): on `--resume` one frozen claim-time anchor set feeds every consumer of `_closed_world_anchors`: the mixed-lane resolver (`reconciliation.py:2116`), the approved bound (`:2268`), the fully-canceled lane's own commits (`:2529`) and the approved-reviewed attestation (`approved_attestation.py:198`; `SAVED` on a resume, live on a fresh run, where live equals what the claim freezes). That is four callers, not the "five" the plan first said (renata F-01). FR-015 is widened; NFR-002 names each flip, (e) closed world, (f) approved bound, (g) fully-canceled lane, each with its own red-first test through `consolidate --resume` on the SIGKILL harness (renata F-07, NFR-010).
- **Coverage of `pre_interrupt_lane_tips`** (renata, IC-15 question): whenever a resume passes H5 (`_refuse_unanchored_resume`), every dependency lane the closed world anchors on has a frozen tip. Holes, each named in the ADR: (H1) no capture when the status surface does not resolve (degraded anchor, live read kept); (H2) a full-restore rollback re-baselines the record and drops the tips on LANES/`single_branch` (#6770), so the next resume is a fresh capture by design; (H3) the attestation caller, now covered by CI-5; (H4) a canceled set that changes between capture and resume only refuses or drops anchors, both safe.

## R-18 — Proving the corpus can fail, and what it records (post-plan)

- **Decision**: the corpus runner computes verdicts **in process** (Typer `CliRunner` or the direct `consolidate` entry), so seeded mutations applied through `RECONCILIATION_FAMILY` reach it; resume cells reach their interrupted state with the SIGKILL harness, then resume in process. The mutation test (IC-17) lands in Phase 1 with a mutation table (check → mutated function → mutation → expected red cell), against the unsplit module, and is re-run after the split (renata F-02, F-09). The golden file records today's actual verdict for every cell; intended verdicts are separate strict `xfail(raises=AssertionError)` tests; a window-state axis is set explicitly per cell (renata F-03, F-04).
- **Supersedes** R-07's "monkeypatched verdict" mechanism wording, which a subprocess corpus could not honour.

## Findings disposition (pre-spec squad, every finding)

Dispositions: **accepted** (taken as stated), **changed** (taken in altered form, or overruled by an operator ruling), **deferred_with_rationale**.

### architect-alphonso

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| A-01 | "Durable at transition time" conflicts with the best-effort `lane_head` contract; record the gap as a typed fact | accepted | R-04, FR-003, IC-06 |
| A-02 | Forecast and real run call the same builder with different inputs; name one `ClaimInputs` | accepted | R-05, IC-08 |
| A-03 | Closed-world anchors read live dependency-lane names on resume; fix in a follow-up | changed | Fixed here, red-first, in Phase 4 (IC-15), per Decision Moment `live_defects` |
| A-04 | String-target monkeypatches go vacuous after a move | accepted | R-08, IC-05, IC-12 |
| A-05 | The probe moves into the Java GitPort; record plain SHAs; keep the probe a port | accepted | R-12; `LaneHeadReading` stays an injected port |
| A-06 | `policy_metadata` is untyped; one namespaced key plus a spec-kitty-events issue | accepted | R-01, IC-09 |
| A-07 | Per-check `collect`/`judge` with a composite claim | deferred_with_rationale | C-006 keeps `ApprovedWpCommitSet` whole; composition after this Mission (R-06) |
| A-08 | Promote `wp_attribution` to a `WindowLedger` substrate for all notions | changed | One reader in `wp_attribution` for the window opening (IC-07); full ledger deferred; ADR table maps all notions (R-02) |
| A-09 | `--dry-run` / approved-bound docs drift | accepted | R-09, IC-02 pins by test |
| A-10 | Claim reads bypass the status read door; carry `StatusReadSurface` | changed | `ClaimInputs` records the status directory each mode reads today; routing through `resolve_status_read` deferred (R-05) |
| A-11 | Design A in two layers: derive from stamps first, record later | changed | The operator chose the recorded key now and no lane-path re-derivation (R-01, R-03) |
| A-12 | Keep the Mission behaviour-preserving; behaviour changes go to follow-ups | changed | The operator included four bounded red-first changes in Phase 4, after the split (NFR-002) |
| A-13 | Land the move as one short-lived PR; keep the facade for in-flight PRs | accepted | One PR; Phase 3 is one contiguous series behind a facade (C-005) |

### paula-patterns

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| P-01 | `ApprovedWpCommitSet` is a god-claim with "empty means off" fields; keep it whole | accepted | C-006, IC-10 (moved unchanged, field order kept) |
| P-02 | `build_approved_wp_set` order is the refusal-precedence contract | accepted | IC-03 matrix; orchestration stays one function (IC-11) |
| P-03 | Authorship + presence share one spine walk; one slice | accepted | C-007, IC-11 (moves last) |
| P-04 | Module-bound patches go vacuous; `RECONCILIATION_FAMILY` helper | accepted | IC-05, IC-12 |
| P-05 | Private names consumed outside; surface pin; facade; promote kernel to public names | changed | Surface pin plus facade accepted (IC-04, C-005); promotion to public names deferred (caller migration out of scope) |
| P-06 | The kernel is small, about eight symbols; extract first | accepted | IC-10 |
| P-07 | Three call sites feed different inputs; the split must not fix that silently | changed | Unified behaviour-preserving in Phase 2 (IC-08); alignment red-first in Phase 4 (IC-15, IC-16) per operator scope |
| P-08 | Forecast shares only the content check | deferred_with_rationale | Spec Assumption "forecast scope of parity"; follow-up #7362 |
| P-09 | Dead-symbol allowlist keys and reducer census literal path name the module | accepted | IC-12 (net-0 re-key or keep in place) |
| P-10 | `CHURN_SURFACE_MODULES` does not list the bookkeeping classifier's future home | accepted | IC-10 check |
| P-11 | Keep `Divergence` / `VerifyResult` whole | accepted | C-006, IC-11 |
| P-12 | No gate keys on path, size or `__all__` | accepted | No work-package time on other gates; converse rollback caution kept (C-009) |
| P-13 | Diff-cover counts moved lines | accepted | R-07: the corpus executes moved lines; no exemption |
| P-14 | Function-local imports avoid cycles | accepted | IC-10/IC-12: move with functions; fresh-interpreter import smoke test |

### researcher-robbie

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| F-01 | The window model exists for `single_branch` (S8, #7283); generalise tier 2 to lanes; the ADR un-defers Option 6 | accepted | IC-13 reuses `write_branch_bound` machinery; IC-01 frames the ADR as amending Option 6; rollout = fallback for gaps (R-03) |
| F-02 | A separate provenance record is already rejected twice | accepted | R-01, C-001 |
| F-03 | Stamp writer moves to Java; a new key is a cross-repo change; default "no new fields" | changed | The operator ruled a new namespaced key now, Python-written (C-003); Java via the FR-006 issue |
| F-04 | Durable ≠ survives landing; classify in `DOSSIER_SHA_FIELDS` | accepted | R-12, FR-005, IC-07 |
| F-05 | Five or six window definitions with a deliberate `blocked` asymmetry | accepted | R-02 named variants; asymmetry kept |
| F-06 | A verifier-only split covers about 13% of the file | accepted | R-06 |
| F-07 | Import surface needs a facade | accepted | C-005, IC-04 |
| F-08 | No cross-check verdict matrix | accepted | FR-016, IC-02 |
| F-09 | #5048(b) live; pin, do not fold into the move | changed | Pinned in Phase 1 (strict `xfail`), fixed red-first in Phase 4 after the move (IC-14), per `live_defects` |
| F-10 | `--dry-run` docs drift; verify by execution | accepted | R-09 |
| F-11 | Two recording tiers (event log vs `state.json`); leave rollback alone | accepted | ADR states both tiers (IC-01); C-009 |
| F-12 | ADR cross-reference hazards; #5703 as a limit | accepted | C-011, R-13 |
| F-13 | Residual counts drift between ADR text and test pins | changed | The corpus counts from test files and the ADR text is synced (R-13); issue-body edits deferred to Mission closeout (operator GitHub writes) |
| F-14 | `lane_head` is best-effort; no silent fallback | changed | The fallback is reported (gap report) and distinct from `APPROVAL_STAMP_MISSING`, which still refuses (R-03); operator `missing_window_rule` |

No contested finding was dropped. The squad's open questions are all closed by the six Decision Moments and the Engineering Alignment.

## Findings disposition (post-plan squad, 2026-11-08, every finding)

Inputs: debugger-debbie (failure modes, 9 findings), reviewer-renata (verifiability and soundness, 14 findings plus 4 IC-15 coverage holes), and the mechanical coverage check (glm-5.3; 3 unmapped constraints). Dispositions as above. Rulings: Decision Moments `01M6YAFYHT0RMVZB03THW1WWSE` (anchors), `01M6YAFZVZAYR4G20Q2X4PN0FT` (resume anchors), `01M6YAG16WDVMM37HCJCHAC5YW` (window opener), `01M6YAG2HE6Q2XNQMGK6X3MBEK` (events issue, filed as spec-kitty/spec-kitty-events#229).

### debugger-debbie

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| D-1 | [HIGH] Lane anchors include the lane's own approval stamps, which exempt the very commit FR-007 must refuse; dependency chains exempt via another lane's stamp | changed | Ruling `01M6YAFYHT0RMVZB03THW1WWSE`: own stamps dropped on the window path, other lanes' stamps kept as the named exception; FR-007/SC-001 reworded; US2-6/US2-7; dependency-chain fixture (IC-02, IC-13); R-15, data-model WW-2a |
| D-2 | [MEDIUM] A first opener before the lane branch exists becomes a permanent `capture_failed` gap | changed | Ruling `01M6YAG16WDVMM37HCJCHAC5YW`: written as its own gap reason `lane_branch_missing` and skipped when leading (FR-003, FR-021, US1-5, contract W-3/R-1); test in `test_wp_window_capture.py` |
| D-3 | [MEDIUM] "First opener" is order-ambiguous; wall-clock re-sort makes skewed rework an un-attestable over-refusal | changed | Ruling: topology order with log-order fallback (FR-021, contract R-1); skewed-clock fixture (IC-07, IC-02); the rewind boundary itself stays log-ordered, named residual (R-16) |
| D-4 | [MEDIUM] Unresolvable `open_sha` undefined; the `on_lane` tip has no source on two paths | accepted | FR-022: unresolvable = `not on lane`; the one tip the bound resolves is passed to the classifier on every path incl. `approved_bound_refusal`, with a parity case (IC-07, IC-13, data-model §3, contract R-4) |
| D-5 | [MEDIUM] First-opener window is over-wide for claimed-early, parked, rewound and parallel-claim WPs | changed | Ruling: rewinds start a new cycle (FR-021, US1-6). Review rejections do not reset (interpretation, R-16). Parallel claims and parked-without-rewind stay a named residual, strict `xfail` (IC-02, data-model WW-6, ADR) |
| D-6 | [LOW] Mixed gap/recorded lanes argued only for the all-degraded case | accepted | US3-3 reworded ("every work package predates the upgrade"); US3-4 pins the pass and gap line; gap-then-recorded with a stray is NFR-002 (a); data-model WW-7 |
| D-7 | [LOW] Two (three) implementations of the opener rule | changed | One selector `window_opener_events(..., cycle)` for the reader and `approval_window_open_stamp` (legacy rule kept for `single_branch`, FR-011); `first_governed_open_stamp` stays the named variant (IC-07, R-16) |
| D-8 | [LOW] NFR-007 "≤ 2 queries per WP" is not what the reused machinery does | accepted | NFR-007 reworded: O(WPs + anchors) plus a constant per refused commit, exempt set computed once per lane and shared by tier 1 and tier 2; counted seam named |
| D-9 | [LOW] Java writer dropping the key is a silent downgrade, invisible on `orchestrator-api` | deferred_with_rationale | The envelope stays unchanged (spec Assumption, no contract bump); a stderr log is no contract and invisible to orchestrators; named as an ADR residual (contract "Not affected"); the gap report joins the envelope with the next contract version |

### reviewer-renata

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| F-01 | [HIGH] `_closed_world_anchors` also feeds the approved bound; caller count wrong; IC-15 leaves the bound's verdict open | changed | Ruling `01M6YAFZVZAYR4G20Q2X4PN0FT`: one frozen anchor set for all four callers; FR-015 widened; NFR-002 (e)/(f)/(g); US4-3, US4-5; caller count corrected (R-17, IC-15) |
| F-02 | [HIGH] Seeded mutations cannot reach a subprocess corpus | accepted | In-process corpus runner; env-gated child shim only if a cell needs a subprocess; mutation table (NFR-008, IC-02, IC-17, R-18) |
| F-03 | [HIGH] No window-state axis; "0 other changes" can pass vacuously | accepted | Window-state axis set explicitly per cell (FR-016, IC-02) |
| F-04 | [HIGH] Strict-`xfail` cells cannot be compared byte-for-byte; xfail without `raises` | accepted | Golden records actual verdicts for every cell; intended verdicts in strict `xfail(raises=AssertionError)` tests; NFR-001 = golden unchanged, NFR-002 = golden diff ⊆ named cells (FR-016, NFR-001, NFR-002, IC-02) |
| F-05 | [HIGH] Fallback gives today's refused set but not today's output | accepted | FR-023: all-gap lane runs today's `check_lane` unchanged; WW-2 restates `stamp_refusal` first and `content_commits` filtering; corpus cell pins the refusal text (US3-5, IC-13) |
| F-06 | [MEDIUM] IC-16 alone does not make forecast and fresh inputs equal | accepted | FR-013 defines equality (resolved SHAs, status dir by path + digest); IC-16 also resolves the forecast's coordination base and status directory; one strict `xfail` per divergence (US5-1, data-model CI-2) |
| F-07 | [MEDIUM] Resume fixtures unspecified; easy routes reach a fresh run | accepted | SIGKILL harness, kill after anchor `save_state` and before `_phase_merge_lanes`, `state.json` precondition, no hand-written records (NFR-010, IC-15) |
| F-08 | [MEDIUM] Red-first through the entry point not required | accepted | NFR-010; IC-13 (`consolidate`, `--dry-run`), IC-14 (in-process `consolidate`, probe patched at its lookup home), IC-15 (`--resume`), IC-16 (`--dry-run --json`); red SHAs in the PR |
| F-09 | [MEDIUM] Mutations land only after the move | accepted | IC-17 in Phase 1 against the unsplit module, re-run after the split (NFR-008) |
| F-10 | [MEDIUM] Swapped-order control does not show the pair co-occurs | accepted | IC-03 asserts both markers before order; non-co-occurring pairs listed with their short-circuit site |
| F-11 | [MEDIUM] Query-count requirement names no counting seam | accepted | NFR-007 names the seam (`git_probes` / `kernel.git` history helpers; `rev-list` / `merge-base` count, `rev-parse` does not) |
| F-12 | [LOW] A gap on the first event hides a later recorded SHA | changed | Resolved by the opener ruling (skip leading `lane_branch_missing`), pinned in `test_wp_window_capture.py`; quickstart demonstrates `implement` and the `move-task` case |
| F-13 | [LOW] Surface pin's scan may miss string patch targets | accepted | IC-04 generator also collects string-literal dotted targets |
| F-14 | [LOW] A mixed lane weakens the check without saying so | accepted | US3-4 pins the pass and the gap-report line; data-model WW-7 |
| H-1 | IC-15 hole: no capture when the status surface does not resolve | accepted | Named degraded anchor (FR-015, data-model CI-3, ADR); live read kept |
| H-2 | IC-15 hole: full-restore re-baseline drops the tips on LANES/`single_branch` | accepted | By design (#6770): the next resume is a fresh capture; FR-015 fixtures use SIGKILL so they cannot be vacuous (NFR-010, ADR) |
| H-3 | IC-15 hole: the attestation caller is outside the claim | changed | Covered by the ruling: on a resume it reads the `SAVED` anchor set; on a fresh run live tips (equal to the frozen ones on an unmutated state) (data-model CI-5, IC-15) |
| H-4 | IC-15 hole: frozen set judged against the live canceled set | accepted | Harmless (H5 refuses or anchors drop); stated in the ADR |

### Mechanical coverage check (glm-5.3)

| ID | Finding (short) | Disposition | Where / rationale |
|---|---|---|---|
| G-01 | C-009 (rollback authority untouched) maps to no IC | accepted | Cross-cutting, every IC (plan note above Phase 1; coverage table) |
| G-02 | C-013 (targeted test runs only) maps to no IC | accepted | Cross-cutting, every IC |
| G-03 | C-014 (code quality gates) cited nowhere in plan.md | accepted | Cross-cutting, every IC |

**Counts**: 30 findings — accepted 21, changed 8, deferred_with_rationale 1. No finding was dropped.
