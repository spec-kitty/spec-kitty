---
title: 'Review-artifact integrity (#3044): the topology-seam connection is historical, the open gap is a missing writer'
description: 'Pre-spec research testing whether #3044''s review-artifact-integrity cluster (#2275, #2996, #990) is a topology-seam defect; code-verified answer plus a scoped remediation seed.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/archive/plans/investigations/write-path-topology-root-cause.md
- docs/development/reference/read-side-seam-classification.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/changelog/3.2.x.md
---

# Review-artifact integrity (#3044): the topology-seam connection is historical, the open gap is a missing writer

> **Historical (writer shipped).** The missing approved-verdict writer this note identified shipped with the verdict-seam rebuild (PR #3211, hardened in #3267). The wider verdict-integrity epic #3044 stays open on the *CLI 4.x stable* milestone and tracks its remaining children there. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

**Scope:** pre-spec research. Corroborate or disprove the hypothesis that GH issue
[#3044](https://github.com/Priivacy-ai/spec-kitty/issues/3044)'s review-artifact-integrity cluster
is a live member of this repo's read/write topology-seam defect class (the #3129 investigation and
the `PlacementSeam` read-side migration), before any mission is opened against it. READ-ONLY
analysis; no product code changed by this document.

**Method:** four independent lenses (architecture-verifier, governance-verifier, skeptic, advocate)
investigated the claim from primary sources — code at the current checkout, GitHub issue bodies, and
the two existing topology-seam docs — rather than accepting the epic's own framing at face value.
Each lens fetched sources itself; none traded summaries with the others before reporting. Every
architecture claim below was additionally re-verified by direct `grep`/`Read` after the squad
reported, because the squad's central finding revises the premise this research started from. Full
lens outputs are preserved in [§3](#3-the-four-lenses).

> **Superseded, in part (2026-08-05, mission `review-cycle-verdict-seam-rebuild-01KZ2W7W`,
> ADR [`2026-08-03-1`](/docs/adr/3.x/2026-08-03-1-review-cycle-artifacts-are-coord-partition.md)).**
> This document's diagnosis stands as an accurate record of what was true when it was written; two
> of its own claims are now falsified by that mission, which this note marks without rewriting the
> analysis below.
>
> 1. **"`create_rejected_review_cycle` is the only review-cycle artifact writer in the codebase"**
>    (§2) is no longer true. This document's own **Option A** ("add a writer... through the
>    existing, already-fixed `_review_cycle_wp_dir` seam") was adopted almost verbatim as this
>    mission's FR-001/FR-005 scope, and **Option B** (provenance-validated feedback source) as its
>    content-identity guard (WP10). An approved-verdict writer now exists and durably persists,
>    closing the exact gap §0–§2 identify.
> 2. **"The location split is already closed"** (§0, §2's `_review_cycle_wp_dir` citation) needs a
>    qualifier this document could not have anticipated: this mission's own ADR introduces a
>    **different**, new location-consistency risk — a coord-topology mission's first review cycle
>    for a WP lands PRIMARY (no coordination worktree exists yet at commit time) while every
>    subsequent cycle for the same WP lands COORD, once the worktree materialises. That
>    create-window split is documented in
>    `tests/architectural/census/verdict_seam_IC04.yaml` (WP04) and is the reason
>    `_review_cycle_wp_dir` itself is now a `status: retire` row (FR-003, WP10) in the canonical
>    census below — not because this document's original "already closed" read-side claim was
>    wrong for what it analyzed, but because the ground it stood on changed underneath it.
>
> **Current source of truth for writer/resolver/reader enumeration:**
> `tests/architectural/verdict_seam_census.yaml` (checked against the live AST by
> `tests/architectural/test_verdict_seam_census.py` on every run) — not this document's line-pinned
> counts, which were accurate on 2026-08-02 and are not maintained here going forward.

**Origin:** the operator asked for pre-spec research connecting #3044 to "the recent read/write
topology seam investigation" (`docs/archive/plans/investigations/write-path-topology-root-cause.md` and
`docs/development/read-side-seam-classification.md`) ahead of opening a mission.

---

## 0. The one-paragraph answer

**The connection is real but dated, and the premise needs revising before a mission is scoped.**
The original defect in #2275 — the per-WP approve guard reading the **lane** worktree while the merge
gate read the **coord** worktree, so a stale `rejected` artifact stayed authoritative — was a
genuine instance of the topology-seam program's "which partition is authoritative" disease class,
and the codebase's own comments say so by issue number: `_review_cycle_wp_dir()`
(`src/specify_cli/review/cycle.py:29-49`) documents retiring "the kind-blind
`candidate_feature_dir_for_mission` fold that resolved the coord worktree for a coord-topology
mission — **#2646/#2697/#2275**." Both the approve-guard's path and the merge-gate's path now
resolve through the same `placement_seam(...).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)` call
(confirmed at `post_merge/review_artifact_consistency.py:100-102` and via `_review_cycle_wp_dir`'s
callers) — the location split is **already closed**, by prior work, using exactly the seam mechanism
the topology-seam program recommends.

**What is still open is not a topology bug.** No function exists anywhere in `src/` that persists an
*approved*-verdict `review-cycle-N.md` (`grep -rn "create_approved_review_cycle" src/` → zero hits).
`move-task --to approved`'s `_mt_plan_review_result()`
(`src/specify_cli/cli/commands/agent/tasks_move_task.py:1747-1778`) builds an in-memory
`ReviewResult(verdict="approved", ...)` that feeds only the status-event FSM
(`build_transition_plan`) — it is never written to a file. The only artifact writer that exists,
`create_rejected_review_cycle` (`review/cycle.py:276-330`), hardcodes `verdict="rejected"` and
already routes through the shared, already-fixed seam. This is a **missing write capability**, not
an ambient-location write going to the *wrong* place — the defining shape of the #3129 class (a
write landing on an unintended partition). Nothing here lands anywhere; nothing is written at all.

**#2996(b) (fabrication) and #990 (contamination) are confirmed unrelated to topology.**
`create_rejected_review_cycle` validates `feedback_source` only for existence and non-emptiness
(`review/cycle.py:287-294`) and never inspects *what* the file is — handing it a WP's own prior
`review-cycle-N.md` gets that file's body read verbatim and re-wrapped with fresh (often synthetic
`reviewer_agent: unknown`) frontmatter. That is a content-provenance validation gap in one function,
with no directory/partition decision anywhere in the path. #990's wrapping/embedding mechanism was
not independently code-traced this pass (see [§5](#5-open-questions-for-the-operator) item 2) but
its own issue text describes the same class of problem: what gets written, not where it's read from.
Neither issue is mentioned anywhere in `write-path-topology-root-cause.md`'s 14-issue table or in
`read-side-seam-classification.md`.

---

## 1. What #3044 actually is, corrected against current code

| Child | Original framing (epic body, 2026-07-28) | Live code state (this investigation, 2026-08-02) |
|---|---|---|
| **#2275** | "authority split": approve guard reads lane, merge gate reads coord | **Read-side split already closed.** Both sides now resolve via `placement_seam(...).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`. Remaining gap: no writer persists an approved artifact — a different defect than the one the issue describes. |
| **#2996(a)** | approving review at cycle N+1 writes no artifact | **Confirmed, still open.** Same missing-writer gap as #2275's residual — same root, arguably the same bug reported independently. |
| **#2996(b)** | cycle N+1 artifact is a fabricated duplicate of cycle N with synthetic frontmatter | **Confirmed, still open, code-traced.** `create_rejected_review_cycle` never validates `feedback_source`'s provenance (`review/cycle.py:287-294`) — content-validation gap, zero topology involvement. |
| **#990** | cycle-generation wraps/embeds a prior cycle's frontmatter/body | **Plausible, not independently code-traced this pass.** Consistent in shape with #2996(b) (a content-generation/templating defect), but no lens located the specific wrapping code path with file:line evidence — treat as unverified until a follow-up trace. |

This table is the reason the research changes the mission's likely shape: a mission opened on the
premise "#3044 is a topology-seam extension" would be scoping against a gap that prior work already
closed, and would need to be re-scoped mid-flight once the missing-writer/content-validation shape
surfaced. Scoping from this table instead should avoid that churn.

---

## 2. The mechanism, verified

- `_review_cycle_wp_dir(repo_root, mission_slug, wp_slug)` (`src/specify_cli/review/cycle.py:29-52`)
  is "the ONE resolver the READ seam... and the WRITE seam... share" (its own docstring), routing
  through `placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`.
  Both `create_rejected_review_cycle` (the writer) and the merge-gate's conflict scan
  (`post_merge/review_artifact_consistency.py`) resolve through it. This is the topology-seam
  program's own recommended cure, already applied here — verified directly by reading the module,
  not inferred from the docstring's claim alone.
- `create_rejected_review_cycle` (`review/cycle.py:276-330`) is the **only** review-cycle artifact
  writer in the codebase. It:
  - validates `feedback_source` exists, is a file, and is non-empty (lines 287-294) — **and nothing
    else**, so a caller can feed it any file, including a prior cycle's own artifact;
  - hardcodes `verdict="rejected"` on the constructed `ReviewCycleArtifact` (no verdict parameter
    exists);
  - is called from exactly one call site, `_mt_finalize_plan`
    (`tasks_move_task.py:1704-1716`), gated on `decision.planned_rollback` — i.e. only on the
    rejection path.
- `_mt_plan_review_result` (`tasks_move_task.py:1747-1778`) is the **only** place `verdict="approved"`
  is constructed on the approval path, and it produces an in-memory `ReviewResult` dataclass consumed
  by `build_transition_plan` (the status-event FSM) — never written to a `review-cycle-*.md` file.
  `grep -rn "create_approved_review_cycle" src/` returns zero hits; the two other `verdict="approved"`
  writers in the repo (`merge/done_bookkeeping.py:119,332`) construct unrelated post-merge
  `DoneEvidence`/`ReviewApproval` bookkeeping objects, not review-cycle artifact files.
- `validate_review_artifact` (`review/cycle.py:184-188`, cited by the architecture-verifier lens)
  hard-rejects any `verdict` other than `"rejected"` — a structural reminder that the "approved"
  path was never built out, not merely under-tested.

---

## 3. The four lenses

Full independent lens reports, condensed for length; verdicts as reported, confidence as stated.

### Architecture-verifier — PARTIALLY_CORROBORATED (high confidence)

Found that #2275's read-side split is already closed by the same seam mechanism the topology-seam
program recommends (`review/cycle.py:29-49`'s explicit #2646/#2697/#2275 citation), and that the live
gap — no writer for an approved verdict — is structurally unlike ambient-location writes: "nothing
writes to the *wrong* place; nothing writes at all." Confirmed #2996(a) is the same missing-writer
bug as #2275's residual, and traced #2996(b)'s fabrication to `create_rejected_review_cycle`'s
provenance-blind `feedback_source` handling via a repo regression test
(`tests/review/test_cycle.py:146-230`, a red-pinning test documented as "expected to fail... before
the guard exists"). Disclosed counter-evidence: no test asserts the read-side fix specifically by
issue number, so confidence in "closed" rests on code structure and comments, not a named regression.

### Governance-verifier — PARTIALLY_CORROBORATED

Found #3044 is a legitimately narrow epic (2 re-homed issues + 1 native, one confirmed mechanism),
not the batch-reparent anti-pattern the #3129 investigation's own governance-verifier rejected —
matching this repo's own successful `#2392` narrow-consolidation precedent rather than the rejected
`#3129`-style mega-epic. Found #3044's own "No relitigating the coord/primary partition" non-goal
already forecloses tension with `#1878`'s "No topology redesign" non-goal — the two operate on
different axes (#2275 is a within-partition write-target miss, not a request to change the partition
scheme). Found P0 justified on #2996's audit-integrity argument, unlike #3129's self-disqualifying
"not urgent relative to MVP." Disclosed counter-evidence: "extend the PlacementSeam program" as a
mission's stated mechanism is this research's own inference, not something #3044 itself commits to —
the epic frames the fix as write-correctness, full stop.

### Skeptic — PARTIALLY_REFUTED (medium-high confidence — i.e., the topology-seam framing survives

only for #2275, not the whole epic)

Argued, and confirmed by code, that #2996(b) and #990 have zero worktree/partition content — both
fire regardless of which partition is read, so bundling the whole epic under a "topology seam"
banner overreaches. Found neither issue is mentioned in either canonical topology-seam document.
Found #2275's *own* mechanism (before this research's deeper trace) looked like two hand-rolled path
joins rather than a kind-blind-resolver misuse — a narrower reading than "topology," later refined by
the advocate and architecture-verifier's deeper trace into: already-fixed read split, open write gap.
Steelmanned its own refutation honestly: closing the write gap still requires deciding *which*
worktree to write to (an irreducibly topological choice, even if narrow), and the seam ledger's
own #2646/#2697/#2275 citation proves maintainers do treat review-cycle placement as seam-adjacent.

### Advocate — CORROBORATED (high confidence, for #2275 specifically)

Found the strongest evidence in the set: `review/cycle.py`'s own docstring names #2275 as a member
of the kind-blind-fold disease class the seam program already cured, and both the approve-guard's and
merge-gate's paths now converge on the identical `MissionArtifactKind.WORK_PACKAGE_TASK` seam call.
Argued the remaining fix is naturally an extension of the *existing* writer (`create_rejected_review_cycle`
already routes through the shared seam) rather than a bespoke patch — generalize it to accept a verdict,
or add a sibling `create_approved_review_cycle` that reuses `_review_cycle_wp_dir`. Cited `#1878`'s
own deferred item 4 ("is-a-worktree type invariant... instead of ad-hoc path checks") as a direction
`MissionArtifactKind` classification is a partial, real step toward. Disclosed counter-evidence
honestly: #2996(b) and #990 are correctly excluded from this framing — #3044's own "Scope note"
already draws that line ("clustering here records the shared thesis, it does not merge the work").

### Synthesis (this document)

All four lenses converge, after code verification, on the corrected picture in [§0](#0-the-one-paragraph-answer)
and [§1](#1-what-3044-actually-is-corrected-against-current-code): the topology-seam connection is
real and historically documented in the code itself for #2275, already resolved for its read side,
and the epic's genuinely open work — a missing approved-verdict writer, plus two unrelated
content-validation defects — does not need further topology-seam program investment to close. This
reframes the mission scope away from "extend PlacementSeam to review artifacts" (already done) and
toward "build the approved-verdict writer symmetric to the existing rejected-verdict one, plus harden
`create_rejected_review_cycle`'s input validation."

---

## 4. Remediation options (for a future mission to select from)

| Option | Shape | Status |
|---|---|---|
| **A — approved-verdict writer, seam-routed** | Add a writer (new `create_approved_review_cycle`, or generalize `create_rejected_review_cycle` with a `verdict` parameter) that persists `review-cycle-(N+1).md` with `verdict: approved`, a real `reviewer_agent`, through the existing, already-fixed `_review_cycle_wp_dir` seam. Call it from `move-task --to approved`/`--to done` whenever the latest artifact's verdict is `rejected`. | **Recommended as primary mission scope.** Closes #2275's residual gap and #2996(a). No topology-seam extension needed — the seam this would route through already exists and is already correct. |
| **B — provenance-validated feedback source** | Extend `create_rejected_review_cycle`'s `feedback_source` validation to reject (or detect and refuse) a source that is itself a prior `review-cycle-N.md` for the same WP, or require a structured feedback object instead of an arbitrary path. | **Recommended as a second mission scope item.** Closes #2996(b); regression coverage may already exist as a red-pinning test (`tests/review/test_cycle.py:146-230`) to turn green. |
| **C — cycle-generation wrapping fix** | Trace and fix whatever code path allows a new cycle's frontmatter/body to wrap or embed a prior cycle's content (#990). | **Gated — needs its own code trace before scoping.** Not independently verified this pass; a mission should either budget a research spike for #990 first, or explicitly defer it to a follow-up if the trace surfaces a different mechanism than B. |
| **D — extend PlacementSeam/topology-seam program into review artifacts** | Route review-cycle reads/writes through a new `MissionArtifactKind` seam classification. | **Not needed.** Already done — `_review_cycle_wp_dir` already routes through `MissionArtifactKind.WORK_PACKAGE_TASK`. Proposing this as new mission work would duplicate existing, working infrastructure. |

If a mission is opened against #3044, **Options A + B are the concrete, code-grounded scope** — both
are additive, both close a named child issue (#2275's residual + #2996 fully), and neither requires
touching worktree/partition logic. Option C should be a research spike inside the same mission (or a
fast-follow) rather than assumed-included scope, since its mechanism wasn't traced here.

---

## 5. Open questions for the operator

1. **Should #2275 be re-narrowed or annotated?** Its issue text still describes a lane-vs-coord read
   split that appears already closed in code. A mission scoped literally against #2275's current text
   risks re-discovering ground already covered. Recommend either editing #2275 to reflect the
   residual (write-side) gap, or explicitly noting in the mission spec that #2275's read-side
   description is stale and the mission targets the write-side residual only.
2. **Is #990's mechanism worth tracing before mission scoping, or during it?** This research did not
   locate #990's specific wrapping/embedding code path with file:line evidence — only its issue text
   and a structural argument (by analogy to #2996(b)) that it's likely a sibling content-generation
   defect. A dedicated trace (a fifth lens, or a mission research WP) should confirm this before
   committing Option C to a mission's scope.
3. **Should the approved-verdict writer be a new function or a generalized existing one?** Advocate
   and architecture-verifier both floated "generalize `create_rejected_review_cycle` with a verdict
   parameter" vs. "add a sibling `create_approved_review_cycle`" without settling it — a plan-phase
   architecture decision for whichever mission takes this on.
4. **Is `--skip-review-artifact-check`'s false-audit-evidence problem (#2996's "Why P0" motivation)
   in scope for this mission, or deferred?** #3044's own scope note excludes the adjacent override-
   annotation defect (#1817/#1924) as a non-goal; confirm the same boundary applies here, i.e. that
   Options A/B remove the *need* for the override on the normal path without this mission also needing
   to fix the override mechanism itself.
5. **Should #2646/#2697 (the two issues `review/cycle.py`'s own docstring cites alongside #2275 as
   already-fixed instances of the kind-blind fold) be checked for their own residual gaps**, the same
   way #2275 turned out to have one? Neither is a child of #3044 and neither was investigated this
   pass; flagged here only because the docstring groups them together.

---

## Addendum 2026-08-02 — post-spec squad resolved all five open questions

*Mission `review-verdict-write-integrity-01KZ1CGF` opened against this research's Options A + B. A
post-spec dialectic squad (architect-alphonso, reviewer-renata, debugger-debbie, planner-priti)
reviewed the committed spec and resolved every open question above; the operator then decided each
escalation. Recorded here so this doc's own open-questions section isn't left stale the way #2275's
issue text was.*

1. **#2275 annotated** — comment posted: <https://github.com/Priivacy-ai/spec-kitty/issues/2275#issuecomment-5158401081>.
2. **#990's mechanism traced, and it collapsed into Option B, not Option C.** `debugger-debbie`
   confirmed `create_rejected_review_cycle`'s unvalidated `feedback_source` read
   (`src/specify_cli/review/cycle.py:287-295`) is the identical mechanism for both #2996(b) and #990 —
   there was never a separate "cycle-generation wrapping" code path to trace. Two pre-existing tests
   (`tests/review/test_cycle.py::test_self_referential_feedback_source_is_rejected`,
   `::test_new_cycle_body_never_duplicates_a_prior_cycle_file`) already reproduce both as RED on
   `main`. **Option C is retired as a distinct option** — it was Option B all along. The operator
   folded #990 into the mission's FR-002 on this evidence.
3. **Approved-verdict writer shape deferred to `/spec-kitty.plan`**, as this doc originally
   recommended — still unresolved, correctly left for the plan phase.
4. **`--skip-review-artifact-check`'s audit-evidence problem**: the operator chose to verify rather
   than rebuild. The squad found #1817 (the issue naming this exact problem) is a stale,
   never-cross-referenced duplicate of #1924, already fixed and closed 2026-06-14 — confirmed live in
   `src/specify_cli/review/artifacts.py:307-376`. #1817 was closed as duplicate-of-#1924 directly on
   the tracker; no mission scope was needed.
5. **#2646/#2697 checked — and this doc's own §1 defect-class table needs a correction, not just an
   answer.** A squad lens initially concluded (matching this doc's architecture-verifier reasoning)
   that `WORK_PACKAGE_TASK`'s unconditional PRIMARY-partition classification makes the coord-duplication
   shape #2646/#2697 describe "structurally impossible today." A second lens, reading #2646's own
   reproduction directly, found the opposite: `_get_wp_review_verdict`'s `agent tasks status` scan
   (`src/specify_cli/agent_utils/status.py`) does route through the same seam for its PRIMARY read, but
   #2646's actual reported defect is that a coord-topology mission's *canonical write* lands on the
   coordination authority while that scan only ever reads PRIMARY — the two lenses disagreed on a
   consequential point. Adjudicating from #2646/#2697's own issue text directly (not either lens's
   summary) confirmed the second reading: both are live, reproducible, independent of #2275/#2996/#990,
   and **not** closed by the same fix. The operator chose to fix both for real inside the mission
   (`FR-003`) rather than split them into a fast-follow — meaning this doc's own framing in §1/§4 ("no
   topology-seam extension needed") held for #2275/#2996/#990 but not for #2646/#2697, which turn out to
   be a genuine, still-open member of the read/write topology-seam defect class this doc set out to
   investigate in the first place.

**Net effect**: every #3044 native child (#2275, #2996, #990) is closed by this mission's scope; #1817
is closed independently. #2646/#2697 — genuine topology-seam-class members, not #3044 children —
are fixed as bundled, efficiency-motivated scope, not epic scope. Full detail:
`kitty-specs/review-verdict-write-integrity-01KZ1CGF/spec.md`.

---

## See also

- [Write-path topology: ambient-location root cause and remediation options](write-path-topology-root-cause.md) — the sibling #3129 investigation this research was asked to connect #3044 to; the write-side member of the same seam-classification style of pre-spec research.
- [Read-side placement-seam classification ledger](../../../development/reference/read-side-seam-classification.md) — the `PlacementSeam.read_dir(kind)` migration ledger; `MissionArtifactKind.WORK_PACKAGE_TASK` (the kind `_review_cycle_wp_dir` already routes through) is downstream of this program's infrastructure.
- [Investigations index](../../../plans/investigations/index.md)
