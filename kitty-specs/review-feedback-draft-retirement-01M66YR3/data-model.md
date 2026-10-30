# Data model — review-feedback-draft-retirement-01M66YR3

Two file-backed entities. Neither is a new type in code; both already exist, and this mission adds one
lifetime rule between them.

## E-1 — Review feedback **draft** (`tasks/<wp-dir>/review-feedback-N.md`)

| Field | Type | Notes |
|---|---|---|
| path | filesystem path | Advertised by `review/cycle.py::review_feedback_source_path`; `N` is the next cycle number from the same `max(parsed) + 1` authority the record allocator uses |
| content | UTF-8 text | Free-form reviewer prose; the only copy until the record is written |
| tracked? | git index membership | A reviewer may have committed it; the mission never removes a tracked draft |

**Invariants**

- I-1: the draft is *input only*. No reader resolves it after the record exists — the record carries
  its text.
- I-2: a draft outside `kitty-specs/<mission_slug>/` is not this mission's to remove.
- I-3: a draft is never committed by this mission (C-001): committing it onto a review lane is what
  #6632's first comment shows being squash-deleted on the target branch.

## E-2 — Review-cycle **record** (`tasks/<wp-dir>/review-cycle-N.md`)

| Field | Type | Notes |
|---|---|---|
| cycle_number | int ≥ 1 | Allocated under the mission write lock |
| body | text | `_resolve_review_body` output: the draft text, optionally prefixed by a caller
`body_header` (the #6652 approval line) — the draft bytes always appear verbatim |
| durability | `VerdictPersistenceOutcome` | `classification`, `verdict_durably_persisted`,
`evidence_ref`, `destination_ref`; durable means the bytes were read back from the destination ref
and compared |

**Invariants**

- I-4: the record's body contains the draft's text verbatim (FR-006). Prefix-only composition is what
  makes removing the draft lossless.
- I-5: `verdict_durably_persisted` is the *only* signal that authorizes removing anything (FR-002);
  `local_only` (`--no-auto-commit`), `persistence_failed` and the protected-target-branch path never
  do.
- I-6: the record's bytes are unchanged by this mission (C-002).

## Transition: the retirement decision

| durable? | inside `kitty-specs/<mission>/`? | tracked? | bytes == recorded? | outcome |
|---|---|---|---|---|
| no | – | – | – | keep, silent (existing behaviour) |
| yes | no | – | – | keep, silent (not this seam's file) |
| yes | yes | yes | – | keep, silent (already committed; tree is clean) |
| yes | yes | no | no | keep, **warn** (edited after it was recorded) |
| yes | yes | no | yes | **remove**, silent |
| yes | yes | no | yes, but `unlink` fails | keep, **warn** (NFR-002: the rejection still exits 0) |

`mission_dirs` is the mission directory `placement_seam(...).read_dir(WORK_PACKAGE_TASK)` returns —
the PRIMARY-partition directory that owns `tasks/<wp>/`, which is where the review prompt anchors the
advertised draft path in every topology (under a coordination topology the RECORD is COORD-partition
while the draft stays here). It is derived through that one seam, never a hand `kitty-specs/<slug>`
join and never the kind-blind `candidate_feature_dir_for_mission` fold, and compared with
`Path.is_relative_to` on resolved paths (never string prefixes), so the rule holds on Windows
separators. The whole retirement — including that resolution — is best-effort: an unexpected error is
logged and the rejection still exits 0 (NFR-002).

## Lifecycle

```text
reviewer writes draft ──► move-task --to planned --review-feedback-file <draft>
                              │
                              ├─ record written + committed ──► durable ──► draft removed
                              └─ record local-only / failed ──────────────► draft kept

draft removed ──► implementer reworks ──► move-task --to for_review
                                             └─ Check 1 sees no blocking file
```
