---
title: Charter Synthesizer — Atomicity via Stage + Ordered Promote + 
  Manifest-Last Commit
description: 'Synthesis writes into a staging tree, validates, then promotes files in a fixed order with the manifest last, so a crash cannot leave a half-promoted doctrine tree.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-17'
---

## Context and Problem Statement

Phase 3 writes two separate directory trees during synthesis:

- **Content** under `.kittify/doctrine/` — directives, tactics, styleguides, project DRG graph. Consumed by `DoctrineService`, `_drg_helpers`, and `DirectiveRepository` / `TacticRepository` / `StyleguideRepository`.
- **Bookkeeping** under `.kittify/charter/` — per-artifact provenance sidecars, the synthesis manifest (commit-marker), and ephemeral staging.

A partial write state — content without provenance, or provenance without the manifest — is worse than no synthesis at all: consumers see partial data and behave unpredictably. Crucially, any process that is interrupted (SIGKILL, disk full, machine crash) between the first file write and the final manifest write must leave the system in a recoverable state, not an inconsistent one.

A naive sequential-write approach ("write content files, then write provenance, then write manifest") cannot guarantee this. We need an atomicity model that:
1. Validates everything before touching the live tree.
2. Promotes with minimal window for partial live-tree state.
3. Provides a canonical "this bundle is committed and valid" marker.
4. Preserves diagnostic state for operator recovery after any failure.

---

## Decision Drivers

- Zero partial writes under `.kittify/doctrine/` or `.kittify/charter/` — any failure must leave the live tree either as-before or fully promoted (C-002, FR-005, NFR-008).
- Fail-closed: validation failures (schema, DRG, path-guard) produce no live-tree mutations (FR-008, NFR-004).
- Interrupted-run recovery: operator should be able to diagnose what went wrong without re-running from scratch (EC-5).
- Idempotent re-run: running synthesis again on unchanged inputs produces byte-identical output (FR-014, NFR-006).
- Performance: fail-closed from detection to return < 5s (NFR-004). This is a correctness problem at kilobyte scale, not a throughput problem.
- Cross-platform: `os.replace` is atomic-on-POSIX, atomic-rename-on-Windows (per Python docs) — acceptable for our scale.

---

## Considered Options

### Option A — Pure in-memory staging, then sequential write (rejected)

Stage all artifacts in memory. Validate. Then write sequentially: content files, provenance sidecars, manifest.

**Rejected**: No recovery story for SIGKILL or disk-full mid-write. A partially written set of content files under `.kittify/doctrine/` that lacks a manifest is a silently broken bundle that consumers may partly load.

### Option B — Journal + replay (rejected)

Write a WAL (write-ahead log) recording intended operations. On failure, replay journal on next run to reach committed state. On success, delete journal.

**Rejected**: Correct but over-engineered for kilobyte-scale writes. Dragged significant complexity into Phase 3 (journal schema, replay logic, journal GC) without buying meaningful recovery benefit over Option C. Flagged as a future path if write scale grows by orders of magnitude.

### Option C — Stage + ordered promote + manifest-last (chosen)

Every synthesis run stages **all** writes inside a single staging root at `.kittify/charter/.staging/<runid>/`. The staging dir mirrors the final layout with internal `doctrine/` and `charter/` subtrees. Full validation (schema, DRG, path-guard) runs against the staged tree. Only on pass does the promote step begin.

Promote uses ordered `os.replace` calls:
1. Content files to `.kittify/doctrine/`.
2. Provenance sidecars to `.kittify/charter/provenance/`.
3. Synthesis manifest to `.kittify/charter/synthesis-manifest.yaml` — **last**.

The manifest is the authoritative commit marker. A reader that encounters a missing or internally inconsistent manifest treats the synthesized content as partial-and-rerunable, not authoritative.

On success: staging dir wiped.
On failure at any stage: staging dir preserved as `.staging/<runid>.failed/` with a `cause.yaml` diagnostic. Operator runs `charter synthesize` again to produce a fresh staging dir and promote.

---

## Decision Outcome

**Chosen option: C — Stage + ordered promote + manifest-last.**

### Run lifecycle

```
CREATED  ──▶  STAGING  ──▶  VALIDATING  ──▶  PROMOTING  ──▶  COMMITTED
   │              │               │               │
   │              ▼               ▼               ▼
   │           FAILED          FAILED          FAILED
   │         (adapter/       (schema/         (os.replace
   │          schema)         DRG/path-        or manifest
   │                          guard)           error)
   ▼
ABORTED
```

- `CREATED` → new staging dir opened, no writes yet.
- `STAGING` → writes inside staging only (never in live tree; path guard enforces this).
- `VALIDATING` → schema + DRG + path-guard + cross-checks on staged tree. Any failure → `FAILED`.
- `PROMOTING` → ordered `os.replace` of artifact + provenance files; finally manifest.
- `COMMITTED` → manifest written; staging dir wiped.
- `FAILED` → staging dir preserved as `.staging/<runid>.failed/` + `cause.yaml` for operator diagnosis.

### Resynthesis lifecycle

Identical to run lifecycle above, but `STAGING` stages only the targeted artifacts. `PROMOTING` replaces only those files. Manifest is **rewritten** (not appended) with the new `run_id` and updated entries for regenerated artifacts; untouched artifacts retain prior `content_hash` in the manifest.

### Manifest authority rule

The live tree is authoritative IFF:
1. `.kittify/charter/synthesis-manifest.yaml` exists, AND
2. Every `content_hash` listed in the manifest matches the SHA-256 of the file at `path`.

Readers that do not verify condition (2) before trusting the live tree are violating this contract.

### Path-guard integration

All staging writes go through `PathGuard`. The staging dir (`.kittify/charter/.staging/<runid>/`) is under `.kittify/charter/` — already in the default allowlist. Promote writes go through `PathGuard.replace()` which verifies both src and dst before calling `os.replace`. No live-tree write can bypass the guard.

### .failed directory preservation

On any FAILED transition, the staging dir is renamed to `.staging/<runid>.failed/` (not deleted). A `cause.yaml` diagnostic is written into the failed dir recording the exception class, message, and traceback. Operators can inspect, repair, and rerun. The `.staging/` subtree is in `.gitignore` so failed dirs are never accidentally committed.

---

## Consequences

### Positive

- Manifest-last provides a single, checkable "committed" signal that consumers and `bundle validate` can rely on without walking the content tree.
- Staging under `.kittify/charter/.staging/` means content files under `.kittify/doctrine/` are never touched during failed runs. Legacy projects and consuming tools are never exposed to partial content.
- `os.replace` is atomic at the OS level on POSIX and Windows — the promote window is O(file_count) individual atomic renames, not a database transaction. At kilobyte scale and tens of files, this is acceptable.
- Preserved `.failed/` dirs give operators diagnostic information without requiring a re-run to reproduce the failure.

### Negative

- A SIGKILL during the PROMOTING phase after some `os.replace` calls have succeeded but before the manifest is written leaves the live tree in a partial state. The manifest is absent → readers treat the bundle as partial-and-rerunable. Operator must re-run synthesis. This is acceptable given the write scale.
- `.failed/` dirs accumulate if synthesis fails repeatedly without manual cleanup. Mitigated by a `charter doctor` extension (flagged as follow-up, out of scope for this mission) and a staging-dir size warning in `bundle validate`.

### Neutral

- `StagingPromoteError` is raised when an `os.replace` or manifest write fails during promote; orchestration preserves the failed dir before raising. The CLI surfaces this error with the failed-dir path for diagnosis.

---

## Path Guard Implementation Note

`src/charter/synthesizer/path_guard.py` wraps every filesystem write method used by the synthesizer (`write_text`, `write_bytes`, `replace`, `mkdir`, `rmtree`, `rename`). A lint-style test (`test_path_guard.py`) greps `src/charter/synthesizer/` for direct write primitives (`open(..., 'w')`, `Path.write_text`, `Path.write_bytes`, `shutil.move`, `os.replace`, `os.rename`) outside `path_guard.py` and fails if any are found. This makes path-guard bypass a CI regression (R-10).

---

## Related Decisions

- **ADR-2026-04-17-1** — Adapter seam and fixture keying.
- **KD-5** — Fail-closed path guard integrated at write seam.
- **KD-2** — Atomicity model (this ADR documents the implementation of KD-2).
- **DIRECTIVE_003** — Decision documentation policy.

## More Information

- Plan: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/plan.md` §KD-2, §Risks & Premortem R-7
- Data model: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/data-model.md` §E-6, §E-9
- Spec: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/spec.md` §FR-005, §FR-008, §FR-014, §FR-016, §NFR-006, §NFR-008, §US-5, §EC-5
