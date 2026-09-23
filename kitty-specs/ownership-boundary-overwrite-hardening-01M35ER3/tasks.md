# Tasks: Ownership-Boundary Overwrite Hardening

**Mission**: `ownership-boundary-overwrite-hardening-01M35ER3` | **Branch**: `issue-4931-ownership-boundary-overwrite-hardening`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Issues**: #4931 (P0), #4926 (P2), #4921 (P2) — epic #4915

## Dependency Graph

```
WP01 (#4921 + shared guard_destructive_overwrite primitive + BriefExistsError)   ← foundational, no deps
WP03 (#4931 init prover re-wire + manager.py backup-before-overwrite)            ← independent, no deps   (parallel with WP01)
        │                         │
        └──────────┬──────────────┘
                   ▼
WP02 (#4926 research prove-or-preserve + arch-gate extension/re-pin)             ← depends on WP01 AND WP03
```

WP01 and WP03 run in parallel. WP02 depends on **both**: on WP01 for the `guard_destructive_overwrite` primitive it consumes, and on WP03 because WP03's `init.py` edits shift the line-pinned allowlist in `tests/architectural/test_mutation_ownership_routing.py` — which WP02 solely owns and must reconcile alongside its own research-scanning extension.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `guard_destructive_overwrite` + `OverwriteVerdict` to `asset_preservation/guard.py` (truth table) | WP01 | |
| T002 | Add typed `BriefExistsError` | WP01 | [P] |
| T003 | RED-first #4921 regression: writer-layer refusal on existing complete brief | WP01 | |
| T004 | `write_mission_brief(overwrite=False)` routes through the guard, raises `BriefExistsError`, preserves XOR recovery | WP01 | |
| T005 | Delegate the two `intake.py` gates to the chokepoint error; collapse the duplication | WP01 | |
| T006 | Unit tests: guard truth table + brief controls (force overwrites, orphan-sidecar recovery) | WP01 | |
| T010 | RED-first #4931 regression: `init` deletes user `.kittify/templates/` via the guard path AND the full-copy path | WP03 | |
| T011 | Re-wire `init.py` cleanup `ManagedPathProver`: drop `.kittify/templates` from `managed_relpaths`; pass `run_created` only for dirs this invocation created | WP03 | |
| T012 | `template/manager.py`: `back_up_operator_subtrees(["templates"])` before the rmtree/copytree (overwrite seam) | WP03 | [P] |
| T013 | Audit-sweep every `guard_destructive_removal` call site for other `managed_relpaths`-by-name shortcuts; report (do NOT touch #4907's `agent/config.py`) | WP03 | |
| T014 | Unit/functional tests: init preserve + manager backup + control (genuinely run-created templates still cleaned) | WP03 | |
| T020 | RED-first #4926 regression: research fabricates 0-byte + `--force` truncates — all four assets — via the CLI | WP02 | |
| T021 | Route `research.py` `_copy_asset` + CSV loop through `guard_destructive_overwrite` (substantive = template resolved); decide **before** any `unlink`; no fabrication; no false "ready" | WP02 | |
| T022 | Report a clear "no research template for mission type X" outcome instead of a green panel when nothing resolves | WP02 | [P] |
| T023 | Extend `test_mutation_ownership_routing` to scan `research.py` (route its `unlink` away) AND re-pin any `init.py` allowlist lines shifted by WP03 | WP02 | |
| T024 | Unit/functional tests: research all-four-assets + controls (templated path copies, no-force preserve) | WP02 | |

Completion is event-sourced: `spec-kitty agent tasks mark-status Txxx --status done` (single/batch). Reference rows above are not checkboxes.

---

## WP01 — #4921 brief chokepoint + shared overwrite primitive (foundational)

- **Goal**: introduce the single `guard_destructive_overwrite` primitive (one authority, beside `guard_destructive_removal`) and use it to push the brief overwrite invariant into the `write_mission_brief` chokepoint, retiring the duplicated `intake.py` gates. **Priority: P2** (#4921); foundational for WP02.
- **Independent test**: call `write_mission_brief` with a present complete brief and `overwrite=False` → typed `BriefExistsError`, brief untouched. No CLI needed.
- **Subtasks**: T001, T002, T003, T004, T005, T006 (~6). **Prompt**: [tasks/WP01-brief-chokepoint-overwrite-primitive.md](./tasks/WP01-brief-chokepoint-overwrite-primitive.md)
- **Dependencies**: none. **Requirement refs**: FR-003, FR-005, NFR-003, C-001, C-004.
- **Risks**: the new gate must sit AFTER the XOR partial-state cleanup (`mission_brief.py:73-75`) so orphan-sidecar recovery is preserved (R2).

## WP03 — #4931 init prover re-wire + manager backup-before-overwrite (independent)

- **Goal**: fix BOTH #4931 destroyers with their distinct correct mechanisms — the removal seam (`init.py` prover: name → `run_created` provenance) and the overwrite seam (`manager.py`: backup-before-overwrite via the in-file `back_up_operator_subtrees` precedent). **Priority: P0** (#4931, release-blocking).
- **Independent test**: seed a user `.kittify/templates/spec-template.md`, run `init --non-interactive`; assert preserved/backed-up + "not package-owned" diagnostic, exit 0.
- **Subtasks**: T010, T011, T012, T013, T014 (~5). **Prompt**: [tasks/WP03-init-prover-manager-backup.md](./tasks/WP03-init-prover-manager-backup.md)
- **Dependencies**: none. **Requirement refs**: FR-001, FR-005, NFR-001, NFR-002, C-002, C-003, C-004.
- **Risks**: `run_created` must be true ONLY when this invocation created the tree (R3) — a false positive re-introduces the deletion. Do NOT edit `test_mutation_ownership_routing.py` (WP02 owns it and reconciles your init line-shift); your targeted test surface is init + manager tests.

## WP02 — #4926 research prove-or-preserve + arch-gate extension (depends on WP01, WP03)

- **Goal**: consume the WP01 primitive in `research.py` for all four assets (no 0-byte fabrication, no `--force` truncation, decide-before-unlink); extend the removal-routing arch gate to scan `research.py` and re-pin any init allowlist lines WP03 shifted. **Priority: P2** (#4926).
- **Independent test**: fresh software-dev mission → `research` creates no 0-byte artifacts; `research --force` over a non-empty user asset with no template preserves it.
- **Subtasks**: T020, T021, T022, T023, T024 (~5). **Prompt**: [tasks/WP02-research-prove-or-preserve.md](./tasks/WP02-research-prove-or-preserve.md)
- **Dependencies**: WP01 (primitive), WP03 (init allowlist line-shift). **Requirement refs**: FR-002, FR-004, FR-005, NFR-001, C-002, C-003, C-004.
- **Risks**: `substantive` must mirror the current successful-copy predicate so the legitimate templated path does not start refusing (R1); the arch-gate extension must stay non-vacuous (concrete floor + self-mutation check, R4).

## MVP

WP03 (#4931, P0) is the release-blocking slice and stands alone. WP01+WP02 close the P2 overwrite/latent-recurrence pair.
