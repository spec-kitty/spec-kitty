# DIRECTIVE_052 (Prefer Durable Fixes) — Investigation Record

**Mission:** doctor-mission-state-repair-fidelity-01M2YGV8
**Base confirmed:** defect live on `upstream/main` (local base is 4 commits behind; those 4 are charter/directive/#4785-dossier only and do **not** touch any seam file — verified via `git diff --stat main..upstream/main`).

## 1. Tracker search (whole tracker, not just milestone)

- **Umbrella / epic:** **#2720** — *Mission-state discovery & diagnostic-command output fidelity* (target state: one canonical discovery + writer-schema-sourced validation). This mission advances #2720's *validation-agreement* and *output-fidelity* legs.
- **In scope (same seam):** #4778 (P1), #4780 (P2), #4779 (P2, no milestone — folded).
- **Domain context (bulk-edit doctrine):** #1815, #1790, #4363; closed #2345, #1347, #616 (mission 393, introduced `VALID_CHANGE_MODES`).
- **Milestone #11 recheck (newly minted):** #4782 (`tool-surfaces --fix` reports success without repairing) rhymes thematically ("--fix reports success without repairing") but is the **skills/tool-surfaces** domain — a different command/seam — so excluded. #4755–#4758, #4757 (decisions/index.json), #4764/#4765 (merge/close) are other domains. No further fold.

## 2. Code grounding (file:line, confirmed live on upstream/main)

- `src/specify_cli/mission_metadata.py:99` — `VALID_CHANGE_MODES = frozenset({"bulk_edit"})`; value-check `:502-506`; write-path guard `:824-826`.
- `src/specify_cli/migration/mission_state.py:1642-1650` — `_canonicalize_mission_meta` calls `validate_meta` and **raises `ValueError` on the whole mission** for one inert optional field (the #4778 fatal path). Manifest root `:71` (`.kittify/migrations/mission-state`), write `:724/:763`, quarantine `:1554-1564`, dry-run `:934-1055` (**writes no manifest**).
- `src/specify_cli/cli/commands/_mission_state_doctor.py:290` `_pretty_repair` / `:333` `_pretty_dry_run` — human mode prints **bare counts only**; per-mission detail (`report.missions` / `report.errors`) is discarded (the #4780 defect).
- `.gitignore:76` — `.kittify/migrations/` is git-ignored (backfilled by `m_3_2_4_runtime_dirs_gitignore_backfill.py`, #2384) → per-error evidence is git-invisible (#4779).
- `src/specify_cli/bulk_edit/gate.py:49-95` — read boundary: `change_mode == "bulk_edit"` is the only truthy path; every other value (incl. absence) short-circuits → normalization is **behavior-preserving**.

## 3. Architecture alignment (canonical seam + duplication → DIRECTIVE_044)

- **Canonical seam:** the `doctor mission-state` audit/repair + reporting surface.
- **Structural root cause (folded):** **two validation authorities disagree** on one field — `audit/shape_registry.py:30-68` (writer-schema, key-level) **accepts** `change_mode: regular`, while `mission_metadata.validate_meta` (value-level) **rejects** it. Reconciling them is the DIRECTIVE_044 single-canonical-authority fix → folded as **FR-010 / C-003**.
- **Duplication surfaced, deferred:** three mission scanners (`audit/engine._scan_missions`, `migration/mission_state._select_mission_dirs`, `context/mission_resolver`). Unifying them is epic #2720's "one canonical discovery" leg — **fold-vs-defer surfaced to operator; deferred behind #2720** (out of scope here, C-004).

## 4. ADRs

- `docs/adr/3.x/2026-05-10-1-deterministic-historical-mission-state-repair.md` — **aligned, no amendment.** Repair philosophy: invalid/missing material → deterministic default, and "the manifest and audit output show what was defaulted." `change_mode` normalization (invalid→absent, recorded as `normalized_change_mode`) is this pattern; #4780 fidelity advances the "show what was defaulted" principle; idempotency (NFR-002) matches "running repair twice yields no second diff."
- `docs/adr/3.x/2026-04-14-1-bulk-edit-occurrence-classification-guardrail.md` — **aligned, no amendment.** Confirms `change_mode: bulk_edit` is the guard trigger and absence = ordinary (no guardrail). Normalizing `regular`→absent is semantically correct.
- `docs/adr/3.x/2026-07-14-1-canonical-cli-console-seam.md` — relevant to the reporting change (route per-mission output through the canonical console seam).

## 5. Structural remediation & fold-vs-defer (surfaced before spec)

Operator chose **Full seam** (#4778 + #4780 + #4779 + audit/fix reconciliation FR-010). Scanner unification deferred behind umbrella **#2720**. Fix direction: **normalize, do not re-widen** the vocabulary; keep `VALID_CHANGE_MODES = {bulk_edit}` and the strict write-path guard unchanged (C-001).

**Compliance:** root cause diagnosed to a systemic seam (two authorities); structural remediation folded (reconciliation) with the larger structural item (scanner unification) recorded behind an umbrella epic — not silently dropped, not over-engineered onto an isolated defect.
