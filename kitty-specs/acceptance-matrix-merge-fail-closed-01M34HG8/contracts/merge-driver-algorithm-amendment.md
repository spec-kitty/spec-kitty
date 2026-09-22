# Contract amendment: matrix merge-driver field-conflict behavior

**Supersedes** (as a living record — the originals are immutable archived snapshots and are
NOT edited): `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md`
rule 4 / Verification, and the FR-004 negative control of completed mission
`gate-artifact-merge-driver-unit-gate-01KZPG7V` (which treated the embedded-marker/no-abort
outcome as correct). **Recorded via** ADR `docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md`
(the amendment section) and this file.

## Before (current, corrupting)

> If the same field diverges on both sides, emit a structured conflict result
> (fail-closed, no consolidation abort per `2026-07-23-2`) — i.e. embed a
> git-style conflict-marker string as the field value; the merge does not abort.

This is unsafe for **gate/verdict** artifacts: an embedded marker in `pass_fail`
recomputes `overall_verdict` to `fail`, silently corrupting an accepted mission.

## After (this mission)

Scope is a **verdict-authority field** of a gate/verdict artifact — `pass_fail`
and negative-invariant `result` on the acceptance matrix, `verdict` on the issue
matrix — reconciled so #4880 (no silent verdict corruption) and #2804 (a scaffold
row must yield to the filled side, never abort a normal consolidation) both hold:

> On a both-sides divergence from base:
> - **Verdict-authority field, one side is the unset sentinel** (`pending` /
>   `unknown`): yield to the authored side (the lane that recorded a verdict wins;
>   no abort).
> - **Verdict-authority field, both sides genuinely authored and different**
>   (e.g. `pass` vs `fail`, `fixed` vs `wontfix`): **fail closed** — the driver
>   raises `RowMatrixMergeError` → `typer.Exit(1)`; git leaves the conflict for a
>   human and the integration path does not advance the target ref.
> - **Any non-verdict field** (`evidence`, `evidence_ref`, `description`, `notes`,
>   `proof_type`, …): prefer the target side (`ours`), per the #2804 / #1732
>   target-authoritative convention. Never aborts, never embeds a conflict marker.
>
> **Non-authoritative prose** artifacts (the review-cycle `.md`) are entirely out
> of scope and keep their existing best-effort embed behavior.

A git-style conflict marker is NEVER embedded as a field value in a gate/verdict
matrix by this driver.

## Verification

- Two genuinely-authored, differing verdicts (`pass_fail` pass/fail or `verdict`
  fixed/wontfix) ⇒ driver exits non-zero, no matrix committed (IC-2 red-first).
- An authored verdict vs the unset sentinel (`pending`/`unknown`) ⇒ resolves to the
  authored value, merge succeeds (the common lane-consolidation case; #2804 preserved).
- A filled row vs a scaffold on a non-verdict field ⇒ resolves to the target's
  filled value; no marker embedded (NFR-001).
- Review-cycle driver behavior unchanged (NFR-002).
