# Research: One meaning for an unclassified mission artifact (#5697)

Phase 0 findings. Grounded in two profile-loaded adversarial grounding lenses
(architecture/exhaustive-classification + boundary/parallel-authority) plus
direct code reading on `main` (fast-forwarded to `dea1092aeb`, 2026-10-16).

## Decision 1 — `None` means "not a coordination record" everywhere

- **Decision**: adopt the existing positive authority `coordination.coherence.is_coordination_kind_file` as the one meaning of an unclassified kind: `None → not-coord → primary-bound, never projected`.
- **Rationale**: the write side already decided this (`commit_router._group_files_by_partition`, #2533: "None routes PRIMARY unconditionally"; `_translate_to_owning_surface` raises `PATH_UNROUTABLE` for a `None` path, so the product *cannot* write a `None`-kind file onto coord — a file it cannot write to coord cannot be coord bookkeeping to carry). Three consumers already share `is_coordination_kind_file` (coord_seed, coordination_alias_files, reconciliation). Only two consumers dissent.
- **Alternatives considered**: (a) classify-only (issue direction 1) — rejected as whack-a-field: the `None → coord` predicate survives, so the next unclassified file re-triggers the refuse (this issue is already the 2nd instance after #5552). (b) make `None` mean PRIMARY by a new local branch in the projection — rejected: it adds a *second* authority instead of removing one.

## Decision 2 — fix both dissenters, not just the refuse site

- **Decision**: route both `_post_checkpoint_mission_paths` (projection) and `_partition_paths_by_primary_kind` (workflow commit partition) through `is_coordination_kind_file`.
- **Rationale**: both re-derive `None → coord` locally; the projection is the #5697 refuse site, the workflow partition is the same latent defect. Converging both on the one authority is the charter-correct "retire the parallel authority" move (Standing Order: single canonical authority) and a cheap campsite fold.
- **Alternatives considered**: fix only the projection (minimal #5697 close) — viable but leaves the twin defect; the operator chose the full predicate fix (Option 3).

## Decision 3 — classify all ~12 unclassified PRIMARY files; one kind per family

- **Decision** (operator, DM `01M5367RM475M2RQA5WNE451Q4`): classify every mission file that still falls through to `None`, one new kind per semantic family.
  - `research/` subtree (dir-anchored) → **RESEARCH** (reuse).
  - `findings.md`, `report.md`, `methodology.md`, `synthesis.md`, `literature-review.md` → **RESEARCH_OUTPUT** (new PRIMARY kind, distinct from the sw-dev `research.md` note).
  - `gap-analysis.md`, `audit-report.md` → **ANALYSIS_REPORT** (reuse).
  - `occurrence_map.yaml` → **OCCURRENCE_MAP** (new PRIMARY).
  - `goals.md` → **MISSION_GOALS** (new PRIMARY).
  - `release.md` → **RELEASE_RECORD** (new PRIMARY).
  - `meta.json` (mission root) → **PRIMARY_METADATA** (reuse; closes a latent classifier gap).
- **Rationale**: honest-kind doctrine (the code's own CONTRACT/REVIEW_CYCLE comments) forbids borrowing a kind that makes `mission_file_basenames_for_kind` lie. The research-mission deliverables have a different lifecycle from the sw-dev `research.md` planning note, so they earn their own kind rather than widening RESEARCH's inverse map. Every file is PRIMARY — it lives with the mission on the target branch and is authored by the mission, like `spec.md`.
- **Alternatives considered**: reuse-aggressively (fewest members) and one-kind-per-file (maximum honesty) — the operator chose the balanced middle.

## Decision 4 — deliberately-excluded paths stay `None`

- **Decision**: do NOT classify `lint-report.json`, `docs/**`, `answers.yaml`, `mission-events.jsonl`.
- **Rationale**: `lint-report.json` lives under `<repo>/.kittify/`, `docs/**` is project-root repo content, `answers.yaml` lives under `.kittify/charter/interview/`, and `mission-events.jsonl` is deliberately NOT a `MissionArtifactKind` (#5669, keep-local real-dirt). None is a `kitty-specs/<slug>/` mission artifact.
- **Alternatives considered**: classifying them — rejected; they are not mission artifacts and classifying would mis-route or contradict #5669.

## Decision 5 — #5847 is out of scope

- **Decision**: do not fold the coordination-branch-is-also-lane-merge-branch window (#5847).
- **Rationale**: the issue triage (Ivan-Melck) states "fixing one does not fully fix the other"; it is a distinct projection-window defect. Folding it would expand scope and risk.

## Verified facts (not re-litigated)

- The refuse reproduces on `main`: byte-identical unclassified `research/*.py` were the only paths `_post_checkpoint_mission_paths` projected (kind `None`), all failed the no-driver content replay, squash refused deterministically (issue comment 2026-10-15).
- No existing projection regression assertion flips under the predicate fix: the one selection-pinning test asserts `== [traces/approach.md]`; `traces/` is a coord kind and still projects.
- `decision-log/*-verdict.md` named in the projection docstring is a phantom — no such mission directory exists anywhere in `kitty-specs/`.

## Supply-chain security

No dependency is added, upgraded, or removed. `DIRECTIVE_051` / `supply-chain-install-safety` controls are **not applicable** to this mission. (Recorded explicitly per the plan step contract; silence is not compliance.)
