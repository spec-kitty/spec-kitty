# Research: Consolidation window provenance and reconciliation split

**Mission**: `consolidation-window-provenance-01M6Y84D` · **Phase**: 0 · **Date**: 2026-11-08
**Inputs**: `spec.md`; the operator-confirmed intent and Engineering Alignment (2026-11-08); the pre-spec brownfield squad: architect-alphonso (design options and scope), paula-patterns (code shape and split risk), researcher-robbie (prior art and current truth), plus a symbol inventory of `reconciliation.py`. These squad reports are the evidence base. Their file:line anchors were spot-checked on the current branch (`reconciliation.py` 4,096 lines; `transition_pipeline.py:180-219` stamp site; `write_branch_bound.py:55-120`; `wp_attribution.py:665-699`; `git_probes.py:666` `path_state_at`; the three `build_approved_wp_set` call sites `phase_claim.py:521`, `forecast.py:422`, `phase_gate.py:72`; the #5048(b) site `reconciliation.py:3715-3728`).

No `[NEEDS CLARIFICATION]` remains. Every fork the squad raised was settled by a resolved Decision Moment or by the Engineering Alignment.

## R-01 — Where the window is recorded

- **Decision**: On the status transition event, under one namespaced key `policy_metadata.wp_window`, written on each non-migration move of a lane-mapped work package into `claimed` / `in_progress`. Readers bind to the **first** such event (Decision Moments `window_source`, `window_writer`).
- **Rationale**: The event log is already the only authority (`2026-09-29-1-closed-world-refuse-on-mixed-lanes` Decision 2; `2026-10-04-5-approval-stamp-bounds-the-approved-claim` Options 4 and 10 reject a second store). `policy_metadata` already carries `lane_head`, so the extension ships from core alone; the spec-kitty-events payload types it as `dict[str, Any]`. A typed gap value distinguishes "capture failed" from "never recorded", which the best-effort `lane_head` stamp cannot do (`status/lane_head.py` C-1).
- **Writing on every opening move, reading the first**: the pure pipeline cannot know whether a move is a work package's first entry without reading its history, and it must stay history-free and git-free. Writing on every entry into `claimed` / `in_progress` costs nothing (the reading is already taken for `lane_head`). The reader rule then matches `approval_window_open_stamp`: later entries are never consulted.
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

- **Decision**: Three reader-level reasons: `not_recorded`, `capture_failed`, `not_on_lane`. Only `capture_failed` is ever written to an event, with a closed `cause` set (`lane_branch_missing`, `git_error`, `probe_error`) and a free-text `detail`. A not-applicable reading (planning lane, work package not in `lanes.json`, no `lanes.json`) writes no key.
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

- **Decision**: Python writes the key now. A spec-kitty-events issue asks the Java write service to write, preserve and type it (FR-006). The durability horizon is **one consolidation attempt** (forecast, fresh run, resume, teardown); surviving a rebase landing is not a goal. The key is classified `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS` (ADR `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`).
- **Rationale**: The stamp writer moves to the Java service (`2026-10-22-1-the-java-write-service-is-the-canonical-event-writer` D-4), and the write-service pin is still pending. Plain SHAs from ref reads are what a GitPort can produce.

## R-13 — Residual counts and ADR hygiene

- **Decision**: The corpus counts the strict-`xfail` residuals from the test files (`test_canceled_line_attribution_6309.py`, `test_canceled_content_residuals.py`, `test_approved_bound_residuals.py`, `tests/integration/test_single_branch_approval_windows.py`), not from ADR prose. The ADR cites by full slug, and names #5703 (lane-id rebuild orphans recorded windows) as a limit.

## R-14 — Version-bump rule vs charter

- **Decision**: Re-exporting `WP_WINDOW_KEY` touches `src/specify_cli/status/__init__.py`. Add a changelog fragment under `docs/changelog/unreleased/`. The `pyproject.toml` version bump is left to the release owner (charter standing order 7: "no version numbers in scope"; the charter wins over CLAUDE.md on conflict). Flagged for the operator on the PR.

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
