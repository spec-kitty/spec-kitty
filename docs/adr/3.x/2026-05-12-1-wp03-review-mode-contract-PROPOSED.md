---
title: 'PROPOSAL: `spec-kitty review` lightweight vs post-merge mode contract (WP03)'
description: 'Proposes an explicit signal separating lightweight working-tree review from post-integration mission review, hard-blocking when required gate artifacts are absent.'
status: Proposed
date: '2026-05-12'
doc_status: active
kind: ADR
updated: '2026-05-12T00:00:00Z'
---

- rev 1 (2026-05-12 AM): initial proposal, three open sub-questions.
- rev 2 (2026-05-12 PM): HiC resolved Q1 (hard-block with remediation guidance) and Q3 (keep gate logic *near* review.py but pre-emptively refactor the file for god-class risk — see new WP07 in mission spec). Q2 remains open pending the drift-impact analysis below.

**Date:** 2026-05-12

**Deciders:** Architect Alphonso (proposer), HiC (final decision)

**Technical Story:**
- Mission `review-merge-gate-hardening-3-2-x-01KRC57C` WP03
- Source bug: [Priivacy-ai/spec-kitty#985](https://github.com/Priivacy-ai/spec-kitty/issues/985)
- Parent epic: [#822](https://github.com/Priivacy-ai/spec-kitty/issues/822), [#992](https://github.com/Priivacy-ai/spec-kitty/issues/992) (WS-5)

---

## Context and Problem Statement

`spec-kitty review` (implemented at `src/specify_cli/cli/commands/review.py:235`) is documented as a four-step post-merge validation (WP lane check, dead-code scan, BLE001 audit, report writer). In practice the command **can also be invoked before merge** to perform consistency checks against the working tree — and there is no explicit signal in code or surface telling the two intentions apart.

The mission-review doctrine for *post-merge* runs requires:
- `issue-matrix.md` (hand-authored Markdown table, conventional in 7 prior stable/release missions, no generator)
- Gate 1–4 records (currently inline in `review.py:291–446`, not surfaced as report fields)
- `mission-exception.md` when cross-repo E2E has an environmental xfail
- A non-trivial `mission-review-report.md` whose YAML frontmatter (`verdict` / `reviewed_at` / `findings`) accurately reflects the gates that ran

The bug (#985) is that the existing command can emit `verdict: pass / findings: 0` from a *post-merge intent* invocation while none of the required artifacts exist — and operators take that as authoritative release evidence.

The mission spec FR-005 calls for two explicit modes. The architectural question is: **what is the canonical signal that selects the mode, and what is the report contract per mode?**

## Decision Drivers

- **Operator transparency.** A reviewer must never mistake a lightweight check for a release gate. The mode must be visible in stdout, JSON, and the persisted report.
- **Backward compatibility.** Existing operator workflows (`spec-kitty review --mission <slug>` without a flag) should not break; behavior may change but not in a way that turns a currently-passing legitimate invocation into a stderr-only spew.
- **Existing signals.** `meta.json.baseline_merge_commit` is already populated by post-083 mission merge and is the *only* explicit post-merge signal in code today (`review.py:284–285`). Reusing it avoids inventing a new lifecycle concept that #992 WS-1 may want to define centrally.
- **JSON stability.** FR-009 requires diagnostic codes to be JSON-stable for the cross-surface fixture harness (#992 Phase 0). Mode names and failure codes must be machine-parseable strings.
- **Lightweight mode must remain useful.** Pre-merge consistency checks are valuable during mission iteration; the contract must not push operators away from them.

## Considered Options

- **(A) Implicit mode via `baseline_merge_commit` only** — no CLI flag; command auto-selects.
- **(B) Explicit `--mode {lightweight|post-merge}` flag with auto-detect default** — flag overrides; default is auto-detect from `baseline_merge_commit`.
- **(C) Two separate subcommands** — `spec-kitty review consistency` vs `spec-kitty review mission`.
- **(D) New `mission_state` field in `meta.json`** — explicit lifecycle field (`proposed | in_progress | merged | accepted`); command reads it.

## Proposed Decision Outcome

**Recommended option: (B) Explicit `--mode {lightweight|post-merge}` flag with auto-detect default**, because it (i) satisfies FR-005 with the smallest CLI surface change, (ii) preserves backward compatibility via auto-detect from the already-existing `baseline_merge_commit` signal, (iii) gives operators an explicit override for the legitimate edge case of running lightweight checks on an already-merged mission (e.g., from a detached verification worktree), and (iv) does not pre-empt the centralized lifecycle authority work in #992 WS-1.

**Concrete contract proposal (subject to HiC adjustment):**

1. **Mode resolution order:**
   1. `--mode` CLI flag if present.
   2. Else `lightweight` if `meta.json.baseline_merge_commit` is absent.
   3. Else `post-merge`.
2. **Lightweight mode contract.** Stdout/JSON output explicitly states `mode: lightweight (not a release gate)`. The persisted `mission-review-report.md` frontmatter adds `mode: lightweight` and writes "Lightweight consistency check; not a release gate" as the first line of the body. Lightweight mode runs only Step 1 (WP lane consistency) and Step 4 (report writer); skips dead-code scan and BLE001 audit. Verdict can still be `pass` but the report's wording makes the limitation unambiguous.
3. **Post-merge mode contract.** Stdout/JSON output explicitly states `mode: post-merge (release gate)`. The report frontmatter adds `mode: post-merge` and the following keys become **required** for verdict `pass` or `pass_with_notes`:
   - `issue_matrix_present: true` (artifact `issue-matrix.md` exists in the mission dir, or was auto-generated this run — see point 6 below)
   - `gates_recorded: [gate_1, gate_2, gate_3, gate_4]` (each with `command`, `exit_code`, `result`)
   - `mission_exception_present: true | not_applicable` (when `mission-exception.md` is required and validated)
   Absence of any required key → exit non-zero with a diagnostic.
4. **Diagnostic codes (JSON-stable, per FR-009).** Proposed namespace `MISSION_REVIEW_*`:
   - `MISSION_REVIEW_ISSUE_MATRIX_MISSING`
   - `MISSION_REVIEW_GATE_RECORD_MISSING` (with subcode `gate_1`…`gate_4`)
   - `MISSION_REVIEW_MISSION_EXCEPTION_INVALID`
   - `MISSION_REVIEW_MODE_MISMATCH` (e.g., `--mode post-merge` invoked when `baseline_merge_commit` is absent — explicit operator override of the auto-detect signal; warn-or-block per HiC choice in §"Open sub-questions for HiC" below)
5. **`mission-review-report.md` schema becomes explicit.** Today the YAML fields (`verdict`, `reviewed_at`, `findings`) are implicit in writer code. WP03 promotes them to a documented schema in `docs/` (and validates them in tests) so review tooling, dashboards, and the cross-surface harness can rely on a stable contract.
6. **`issue-matrix.md` handling.** Current pattern is hand-authored. WP03 adds (i) a documented Markdown schema (header columns: `Issue | Scope | Verdict | Evidence ref`), (ii) a passive validator (parse the table; fail if header drifts), (iii) **NO auto-generation in this WP** (deferred to a successor mission once tracked-issue ingest is decided). Post-merge mode requires the file to exist; auto-generation is an explicit non-goal here per #822 anti-scope.

### Consequences if approved

#### Positive

- Operator can never mistake a lightweight check for a release gate (mode is in stdout, JSON, and the persisted report).
- The auto-detect default preserves backward compatibility for the canonical happy-path invocation.
- `issue-matrix.md` becomes a typed artifact (schema, validator) without inflating WP03 with auto-generation work.
- Diagnostic codes plug directly into the #992 Phase 0 cross-surface fixture harness with stable names.
- `baseline_merge_commit` becomes a real lifecycle signal — usable by #992 WS-1 later.

#### Negative

- One new CLI flag (`--mode`) on `spec-kitty review`.
- Operator may run `--mode post-merge` on a pre-merge mission expecting a quick sanity check and get a hard fail. Mitigation: the `MISSION_REVIEW_MODE_MISMATCH` diagnostic is explicit. (HiC: choose warn vs block — see open sub-question.)

#### Neutral

- The bare invocation `spec-kitty review --mission <slug>` continues to work; mode is implicit.

### Confirmation

- Regression: synthetic mission with `baseline_merge_commit` set, no `issue-matrix.md` → bare `spec-kitty review` exits non-zero with `MISSION_REVIEW_ISSUE_MATRIX_MISSING`.
- Regression: same mission, `--mode lightweight` override → exit 0, report has `mode: lightweight`, body begins with "Lightweight consistency check; not a release gate".
- Eat-our-own-dogfood (NFR-003): this mission's own final review runs in `--mode post-merge`, produces an `issue-matrix.md`, and records Gate 1–4.

## Pros and Cons of the Options

### (A) Implicit mode via `baseline_merge_commit` only

No CLI flag; command always auto-selects mode from the meta field.

**Pros:**
- Zero new CLI surface.
- Smallest diff.

**Cons:**
- No operator override. Verifying a merged mission from a detached worktree with a quick lightweight check becomes impossible.
- "Magic" behavior: the same command does different things in different contexts with no visible switch.
- Pre-083 missions (no `baseline_merge_commit` field) always run lightweight, even when run post-merge — silently.

### (B) Explicit `--mode` flag with auto-detect default

Recommended above.

**Pros:** see "Consequences if approved" above.

**Cons:** see "Consequences if approved" above. The only real cost is one new flag.

### (C) Two separate subcommands

`spec-kitty review consistency` vs `spec-kitty review mission`.

**Pros:**
- Maximal clarity. Hard to misuse.

**Cons:**
- Breaks every existing invocation of `spec-kitty review`. Hidden in agents, prompts, mission templates, doctrine, docs. Out of proportion for a stabilization mission.
- Violates #822 anti-scope clause on "no new CLI surface beyond what a single bug fix requires."

### (D) New `mission_state` field in `meta.json`

Add `mission_state: proposed | in_progress | merged | accepted` to meta.json; command reads it.

**Pros:**
- Cleanest semantic model.
- Aligns with #992 WS-1 future direction.

**Cons:**
- Cross-cutting: every status-mutating command (next, agent action, move-task, merge) would need to write the field consistently. That is exactly the WorkPackageLifecycle authority work the #992 epic is meant to do. **Doing it inside WP03 pre-empts and inflates a separate workstream.**
- Migration: existing missions need backfill.
- This is a *successor* mission's design, not WP03's.

## Resolved sub-questions (HiC, 2026-05-12)

### Q1 — Mode mismatch behavior → **RESOLVED: hard-block with remediation guidance**

HiC accepted the recommendation: when an operator runs `--mode post-merge` against a mission whose `meta.json.baseline_merge_commit` is absent, the command **blocks** with `MISSION_REVIEW_MODE_MISMATCH`. Implementation detail added by HiC: the diagnostic must contain (i) a clear description of *what is going on* (i.e., "this mission has not been merged; post-merge review requires a baseline commit"), and (ii) a *suggested remediation path* the operator can follow.

**Diagnostic message contract (encoded as part of WP03 acceptance):**

```
ERROR: MISSION_REVIEW_MODE_MISMATCH
  Mission '<slug>' has no baseline_merge_commit recorded in meta.json.
  Post-merge mission review requires the mission to be merged first
  (the merge step records the baseline commit that the review compares against).

  What this means:
    --mode post-merge expects to validate a merged mission against its
    release-gate doctrine. Running it on a pre-merge mission would either
    inspect an arbitrary point in the working tree (false confidence) or
    fail the dead-code scan trivially.

  Remediation options:
    1. If the mission is ready to merge: run 'spec-kitty merge --mission <slug>'
       and re-run this command after the merge completes.
    2. If you want a pre-merge sanity check: re-run with --mode lightweight.
    3. If meta.json baseline_merge_commit is missing because of a pre-083
       legacy mission: see docs/migration/mission-id-canonical-identity.md
       and run 'spec-kitty migrate backfill-identity' first.
```

The diagnostic is JSON-stable: machine-parseable code (`MISSION_REVIEW_MODE_MISMATCH`) plus human-readable body. Stdout writes the code; the body goes to stderr. JSON output includes both as structured fields.

### Q3 — Gate source-of-truth → **RESOLVED: keep gate logic near review.py, but pre-emptively split the file**

HiC accepted the "leave inline for now" recommendation **with a structural caveat**: `src/specify_cli/cli/commands/review.py` is at risk of becoming a god-module (multiple concerns, growing LOC) once WP03's contract enforcement code lands on top of the existing gate logic. To prevent that, a **hygiene refactor of `review.py`** must happen *before* WP03's contract code is added.

**Important scope distinction:** this refactor is a **mechanical file/method split for hygiene**, not a domain-context extraction. The full domain split (e.g., extracting a `ReleaseEvidence` aggregate) belongs to #992 WS-5 ReleaseEvidence in a successor mission. WP03's refactor scope is strictly:

- Split `review.py` into a small package: `src/specify_cli/cli/commands/review/__init__.py` + sibling files for each Gate.
- Extract generic helpers (e.g., report writer, lane-check, dead-code scanner, BLE001 audit) into named functions in dedicated sibling files (`_report.py`, `_lane_gate.py`, `_dead_code.py`, `_ble001_audit.py`).
- The public `review_mission()` entry stays where it is so all existing imports remain valid.
- **No new abstractions, no new public types, no domain modeling.** Anything more sophisticated than "move methods to sibling files and stop the LOC bleed" is out of scope for WP03's refactor and belongs to the WS-5 successor mission.

This refactor is captured as **WP07 in the mission spec** (prerequisite to WP03). See mission spec for FRs.

## Open sub-questions for HiC

### Q2 — `issue-matrix.md` validator strictness → **still open; HiC requested more background**

HiC: "I need more background to make an informed decision here. Explain the issue, and what the issue-matrix drift would mean in practice."

#### What `issue-matrix.md` is, in concrete terms

`issue-matrix.md` is the per-mission audit ledger that records, for each GitHub issue in the mission's scope, the resolution verdict and the evidence supporting that verdict. It is hand-authored today (no generator). The conventional shape — established by the mission `stability-and-hygiene-hardening-2026-04-01KQ4ARB` on 2026-04-26 — is a Markdown table.

#### Observed drift in three recent missions (real examples on `origin/main`)

The shape today is NOT identical across missions. Examined three:

**Shape A** (`stable-320-release-blocker-cleanup-01KQW4DF/issue-matrix.md`):

```markdown
| Issue | Scope | Verdict | Evidence ref |
|-------|-------|----------|--------------|
| #952  | …     | fixed   | WP01; <files>; <tests>; CI <jobs> passed on PR #981 |
```

**Shape B** (`release-3-2-0a5-tranche-1-01KQ7YXH/issue-matrix.md`):

```markdown
| Issue | FR | WP | Verdict | evidence_ref |
|-------|----|----|---------|--------------|
| #705  | FR-002 | WP01 | `fixed` | … |
```

**Shape C** (`charter-golden-path-e2e-tranche-1-01KQ806X/issue-matrix.md`):

No leading table at all — narrative prose first explaining the verdict legend, then the table appears further down with column names `Issue | Verdict | Evidence`.

Three drift dimensions are already in the wild:

1. **Column count and order.** Shape A has 4 columns; Shape B has 5 (`FR` and `WP` columns added).
2. **Column-name capitalization and spacing.** `Evidence ref` vs `evidence_ref` — same intent, different identifiers.
3. **Document structure.** Shape C puts narrative ahead of the table, which a naive Markdown-table parser would either skip or fail on depending on its rules.

#### What "drift" means in practice for the new contract

WP03 introduces tooling that depends on `issue-matrix.md` being machine-readable:

- **Cross-surface fixture harness** (#992 Phase 0): asserts the matrix exists and can be parsed for a synthesized post-merge fixture.
- **Dashboard rendering**: if/when the dashboard ever surfaces issue-matrix verdicts per mission, it needs predictable column semantics.
- **The `gates_recorded` report field** (FR-007): WP03 wants to record the per-issue verdict alongside Gate 1–4 records; the join key is the matrix's `Issue` column.

If WP03 ships with a **strict validator** (hard-fail on header drift):

- *Positive:* breakage is loud and immediate. The first mission that drifts can't pass post-merge review until the matrix conforms. The schema stabilizes for downstream consumers.
- *Negative:* legitimate evolution of the matrix (e.g., a future "Severity" column) requires a coordinated schema bump. Past missions whose matrix shape predates the validator would fail when re-reviewed (though re-review is rare).

If WP03 ships with a **loose validator** (warn-and-parse-what-you-can):

- *Positive:* tolerates the existing shape variation; doesn't break re-review of past missions.
- *Negative:* downstream consumers (harness, dashboard, future tooling) get unpredictable data. The drift problem persists because "warn" is widely ignored. We end up with `feedback://` vs `review-cycle://` all over again (cf. #962 — silent pointer-scheme drift that took a dedicated bug to fix).

#### Architect Alphonso revised recommendation

**Hard-fail (strict) on the *header row only***, with a single forward-compatibility rule: columns may be **added** without breaking validation, but the four canonical columns `Issue | Scope | Verdict | Evidence ref` must be present in that order. Renames, removals, or capitalization changes hard-fail with `MISSION_REVIEW_ISSUE_MATRIX_SCHEMA_DRIFT`. The body rows are parsed loosely (free-form Markdown in cells) to keep authoring practical.

This (i) stabilizes the canonical contract that downstream consumers depend on, (ii) makes legitimate forward evolution (extra columns) possible without a coordinated schema bump, (iii) catches the high-cost drift modes (rename, reorder, remove) loudly. The existing missions whose shape diverges are not currently re-reviewed by tooling, so the constraint only fires forward from WP03 onward; if they ever are re-reviewed, the operator gets a clear diagnostic naming the missing canonical column.

**HiC decision needed:** approve "strict on header, additive-tolerant, loose on body" — or override with a different stance (looser, stricter, or different forward-compat rule).

## More Information

- Source bug body: [#985](https://github.com/Priivacy-ai/spec-kitty/issues/985)
- Code reference: `src/specify_cli/cli/commands/review.py:235` (`review_mission` entry point); `src/specify_cli/cli/commands/review.py:284–285` (`baseline_merge_commit` check); `src/specify_cli/cli/commands/review.py:465–470` (current YAML frontmatter writer).
- Mission spec FR-005 through FR-009 and NFR-001 through NFR-003 in `kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/spec.md`.
