---
work_package_id: WP03
title: Full .kittify/overrides resync
dependencies:
- WP01
- WP02
requirement_refs:
- FR-010
planning_base_branch: claude/research-squad-remediation-mission-fvdk93
merge_target_branch: claude/research-squad-remediation-mission-fvdk93
branch_strategy: Planning artifacts for this mission were generated on claude/research-squad-remediation-mission-fvdk93. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/research-squad-remediation-mission-fvdk93 unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 2 - Dogfood
history:
- at: '2026-09-26T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .kittify/overrides/missions/software-dev/
create_intent:
- tests/cross_cutting/test_kittify_override_parity.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- .kittify/overrides/missions/software-dev/**
- tests/cross_cutting/test_kittify_override_parity.py
- tests/dossier/test_manifest.py
- packs/built-in/missions/software-dev/actions/implement/guidelines.md
- packs/built-in/missions/software-dev/actions/review/guidelines.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Full .kittify/overrides resync

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

- Every file under `.kittify/overrides/missions/software-dev/` that has a built-in counterpart is **byte-identical** to
  it after this WP, including WP01/WP02's changes. (FR-010; operator decisions DM-01M3EWS93W9MRFDJV1QG1Y5WZK,
  DM-01M3EX8WE96MHDTQTEE5M8WT85)
- Overrides with no counterpart — `command-templates/{README,constitution,dashboard}.md` — are untouched.
- `expected-artifacts.yaml` override is **deleted** (operator, DM-01M3EXVSGFRQ8YKVFCCBWVSVZD) and its `software-dev`
  entry removed from `tests/dossier/test_manifest.py::TestOverrideMirrorDeprecation` (the research/documentation
  mirrors and their entries stay).
- Override lines that are **newer** than built-in are ported into the built-in source first (see T013a).
- Nothing is lost unrecorded: override-only content is inventoried before overwrite.

## Context & Constraints

- **Mapping** (verify against the resolver `src/charter/offering/resolver.py` before copying):
  - `command-templates/<cmd>.md` ← `packs/built-in/missions/mission-steps/software-dev/<cmd>/prompt.md`
  - every other path ← same relative path under `packs/built-in/missions/software-dev/`
- 26 counterpart files, 22 drifted at planning time (see `research.md` R4). Recompute — do not trust the count.
- Overrides are project-owned; the operator (owner) authorised this resync. Only `.kittify/overrides/missions/software-dev/`
  is in scope (not `scripts/`, not `AGENTS.md`).
- Read the post-plan squad findings in `kitty-specs/criterion-labels-positive-controls-01M3EWRT/research/post-plan-squad.md`
  — it is present and binding for this WP: per-file stale/intentional table, the 524-pass baseline command, and the
  live `mission-runtime.yaml` note (resync moves this repo from the v2.1.0 `tasks_*` DAG to the v2.2.0 `tasks` step;
  legacy ids are normalised by `runtime_bridge_composition.py` `_LEGACY_TASKS_STEP_IDS`).

## Branch Strategy

- **Planning base branch**: `claude/research-squad-remediation-mission-fvdk93`
- **Merge target branch**: `claude/research-squad-remediation-mission-fvdk93`
- Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP03 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T013 – Inventory override-only content

- For each drifted counterpart file: count override-only lines (`diff override builtin | grep -c '^<'`) and summarise
  what they are (stale older text vs. a local-only rule). Record the inventory with
  `spec-kitty agent tracer-append --mission criterion-labels-positive-controls-01M3EWRT --category design-decisions --actor <you> --entry "<table>"`.
- If a local-only rule looks like live, intentional repository doctrine that the built-in lacks, **do not drop it
  silently**: list it explicitly in the Activity Log as a candidate to upstream (follow-up issue at closeout).

### Subtask T013a – Port newer override lines upstream (part of T013)

- `actions/implement/guidelines.md` (override line ~11) and `actions/review/guidelines.md` (override lines ~9, ~21) use
  the disambiguated terms "repository root checkout" / "merged into the mission's target branch"; the built-in copies
  still say "main repository" / "merged to main" (the `primary`/`merge` footgun). Edit the two
  `packs/built-in/missions/software-dev/actions/*/guidelines.md` files to carry the newer wording, so the resync copies
  it back. Run `pytest tests/architectural/test_no_legacy_terminology.py`.

### Subtask T014 – Resync

- Copy each counterpart built-in file over its override (script it; print each path). Leave no-counterpart files alone.
- `git rm .kittify/overrides/missions/software-dev/expected-artifacts.yaml`; drop the `software-dev` key from
  `TestOverrideMirrorDeprecation`'s path map (and adjust any count assertion); keep the class for the other two.

### Subtask T015 – Parity regression test

- `tests/cross_cutting/test_kittify_override_parity.py`: for every file under the repo's
  `.kittify/overrides/missions/software-dev/` with a counterpart (same mapping), assert byte equality.
- **Positive control**: assert the enumerated counterpart set is non-empty and contains at least
  `templates/spec-template.md`, `command-templates/review.md`, `actions/review/index.yaml` (so an empty walk cannot pass),
  and that the three no-counterpart files are reported as such (the mapping discriminates).
- Also assert `expected-artifacts.yaml` is absent from the software-dev override dir.
- Mark `fast`; keep it pure file I/O.

### Subtask T016 – Fallout

- Run `make test-fast`, `pytest tests/runtime/ tests/next/ -q -n auto --dist loadfile`, and the post-plan squad's
  baseline command (research/post-plan-squad.md; expect 524-ish passes minus the removed software-dev entry). Classify every red per CLAUDE.md's baseline-red gotcha (compare with
  the lane base); fix only fallout caused by the resync.

## Test Strategy

```bash
source .venv/bin/activate
pytest tests/cross_cutting/test_kittify_override_parity.py -q
make test-fast
pytest tests/runtime/ -q -n auto --dist loadfile
ruff check tests/cross_cutting/test_kittify_override_parity.py && ruff format --check tests/cross_cutting/test_kittify_override_parity.py && mypy tests/cross_cutting/test_kittify_override_parity.py
```

## Definition of Done

- Parity test green; inventory tracer entry exists; no-counterpart files untouched; fallout classified and fixed.

## Risks & Mitigations

- Losing intentional local content → T013 inventory + follow-up list.
- Resolver mapping wrong for a file → verify with the resolver before copying.

## Review Guidance

- Spot-check 3 files byte-equal; confirm inventory exists; confirm the parity test fails if one override is mutated.

## Activity Log
