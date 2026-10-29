# Contract: evidence and independence refusal codes

Every refusal line starts with the code followed by `: `.

| Code | Alias (single_branch) | Surfaces | Lifted by |
|------|------------------------|----------|-----------|
| `IMPLEMENTATION_MISSING` | `SINGLE_BRANCH_IMPLEMENTATION_MISSING` | move-task (unforced), accept, consolidate, orchestrator-api | `--attest-no-implementation <WP> --attest-reason` (accept, consolidate) |
| `REVIEW_NOT_INDEPENDENT` | `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT` | move-task (unforced, positively-same identity), accept, consolidate, orchestrator-api | nothing |
| `IMPLEMENTATION_UNREADABLE` | `SINGLE_BRANCH_EVIDENCE_UNREADABLE` / `SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE` | all | nothing |
| `EVIDENCE_WINDOW_UNCOMPUTABLE` | `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` | all | nothing (run `finalize-tasks`) |

- `accept --json`: refusal envelope with `error_code` = first code and `error_codes` = all.
- `consolidate`: exit 1 before any mutation; the claim-time refusal text.
- `orchestrator-api consolidate-mission`: `PREFLIGHT_FAILED`, `data.preflight_error_code`,
  `data.preflight_error_codes`.
- `orchestrator-api accept-mission`: `MISSION_NOT_READY`, `data.evidence_error_codes`.
- single_branch keeps emitting the alias codes; `wp_evidence.canonical_code(code)` maps an alias to
  its neutral code.
