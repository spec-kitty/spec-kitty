# Phase 0 Research — Doctor mission-state legacy repair & report fidelity

Deep grounding lives in [durable-fix-investigation.md](./durable-fix-investigation.md) (DIRECTIVE_052). This file records the design decisions.

## Decision 1 — Normalize legacy `change_mode`, do not re-widen the vocabulary
- **Decision**: In `_canonicalize_mission_meta`, drop any `change_mode` whose value is not `bulk_edit` (record a `normalized_change_mode` action) before `validate_meta` runs. Keep `VALID_CHANGE_MODES = frozenset({"bulk_edit"})` and the `set_change_mode` write-guard unchanged.
- **Rationale**: `change_mode` is optional; absence == ordinary mission; every read boundary (`bulk_edit/gate.py`) already treats `!= "bulk_edit"` as absence, so removal is lossless. Adding `regular` to the vocabulary would mint a canonical term the writer never produces (violates Use-Canonical-Sources / Terminology Canon).
- **Alternatives rejected**: (a) widen `VALID_CHANGE_MODES` — mints a foreign term; (b) relax `validate_meta` globally — weakens the write-path guard that legitimately blocks garbage; (c) special-case only `regular` — misses other legacy/malformed values (FR-011).

## Decision 2 — Reconcile audit and fix on one authority
- **Decision**: Make `--audit` (writer-schema/shape-registry) and `--fix` (`validate_meta`) classify a legacy `change_mode` consistently: repairable, not "valid-and-final" by one and "unrecoverably fatal" by the other. Validation stays writer-schema-sourced (C-003); no divergent hand-rolled list.
- **Rationale**: Two authorities disagreeing on one field is the epic-#2720 anti-pattern and the deeper root cause of #4778 (DIRECTIVE_044 single canonical authority).
- **Alternatives rejected**: leaving the divergence latent (fails DIRECTIVE_052 durability — the next legacy field re-triggers the class).

## Decision 3 — Terminal/`--json` are the authoritative evidence surface
- **Decision**: `--fix` and `--teamspace-dry-run` render per-mission slug + reason to terminal and emit the same structured records in `--json`. The dry-run reaches shape parity with the repair report. The git-ignored manifest remains an internal audit sidecar; triage no longer depends on it.
- **Rationale**: The detail already exists in `report.missions` / `report.errors`; human mode simply discards it. Reusing it adds no second scan (NFR-004). #4779's git-invisibility stops mattering for triage once terminal/json carry the reasons.
- **Alternatives rejected**: un-git-ignoring `.kittify/migrations/` — churns runtime files into git, is a policy change beyond the seam, and is not required (C-006).

## Decision 4 — No new dependencies
- **Decision**: Reuse typer + rich. **Supply-chain security section N/A** — no dependency added/upgraded/removed (DIRECTIVE_051 not triggered).

## Adversarial evidence (post-plan brownfield squad)
No security-impacting dependency decision. Two brownfield lenses (boundary scout + regression challenge) ran at the post-plan point-cut. Dispositions:

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | `implement.py:1340` (`gate_result.change_mode is not None`) distinguishes legacy-value from absent → normalization flips bulk-edit inference skip→run for the 21 legacy missions; NFR-001/SC-006 as written are false. | BLOCKER | **CHANGED** — operator chose "fold durable fix": added FR-012 (align reader to `== "bulk_edit"`, pin `GateResult.change_mode ∈ {bulk_edit, None}`), reworded NFR-001, added US1 scenario 6. Scope widened to `implement.py`/`gate.py` (Concern A2). |
| 2 | FR-002/per-mission rendering assumed a report `actions` field that does not exist; `_canonicalize_meta` actions are discarded at `mission_state.py:~1499`. | BLOCKER-adjacent | **CHANGED** — added FR-013 + new `meta_actions` field on `MissionRepairResult` (data-model corrected). |
| 3 | FR-010 achievable without editing `audit/shape_registry.py` (change_mode is a known key); editing it adds a finding-code + #2720 drift. | SHOULD | **ACCEPTED** — `shape_registry.py` dropped from scope; FR-010 = `--fix` no longer fatal. |
| 4 | Normalization action must be recorded **conditionally** (field present) or idempotency breaks. | NOTE | **ACCEPTED** — folded into Concern A (mirror `removed_meta_key:*`). |
| 5 | Dry-run refusal semantics (`valid`/`fatal_errors`/`Exit(1)`) must stay additive-only. | NOTE | **ACCEPTED** — Concern B marked additive-only; review guard. |
| 6 | `mission_id` seed excludes `change_mode` (idempotency safe); writer-parity safe if no key added. | NOTE | **ACCEPTED** — regression assertions planned. |
| 7 | Arch gates: helpers out of `__all__`, no new `load_meta` read, golden-count annotations, ruff-format, keep tests in existing files. | NOTE | **ACCEPTED** — folded into Concern C / task guards. |

No contested finding dropped silently.
