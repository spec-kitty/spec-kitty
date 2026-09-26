# Research: Criterion delivery labels and positive-control review doctrine

Source: pre-spec research squad (`research/pre-spec-squad.md`) + live probes.

## R1 — Label placement
- **Decision**: trailing FR-table columns `Delivery` / `No-op passable?`; SC trailing suffix.
- **Rationale**: `requirement_mapping._declared_ids` takes the first id per line only when it is alone in the first
  table cell or leads a bullet/heading; the first-id `break` is load-bearing (#3394 context). Live probe: labels in
  or before the id cell silently undeclare the FR. `_substantive.py` reads only Title + User Story, so trailing
  columns are invisible to the spec gate.
- **Alternatives considered**: inline prefix in Title (makes an unfilled scaffold look substantive); label in id
  cell (undeclares FR); inline bullet labels (real bullet specs become non-substantive).

## R2 — Host artifact for the rules
- **Decision**: new tactic `acceptance-criteria-non-vacuity` (operator, DM-01M3EWS6CVECE8C6JZ0QP6FH0S).
- **Rationale**: operator call. Squad preferred extending `acceptance-test-first` (already review-scoped via the
  calibrator) — disposition `changed`: rules move to a dedicated tactic; siblings reference it, no duplication.
- **Alternatives considered**: extend `acceptance-test-first`; extend `atdd-adversarial-acceptance`.

## R3 — Where labels are defined
- **Decision**: tactic `notes` (canonical); template legend and prompts point to it.
- **Rationale**: `build` already means a checkout/worktree in the core glossary, and the glossary pack is generated
  (two edit points). A glossary term would collide.

## R4 — Overrides
- **Decision**: full resync of every file under `.kittify/overrides/missions/software-dev/` that has a built-in
  counterpart (DM-01M3EWS93W9MRFDJV1QG1Y5WZK widened by DM-01M3EX8WE96MHDTQTEE5M8WT85). Mapping:
  `command-templates/<cmd>.md` <- `packs/built-in/missions/mission-steps/software-dev/<cmd>/prompt.md`; every other
  path <- the same relative path under `packs/built-in/missions/software-dev/`. 26 files have a counterpart (22
  drifted, 4 already identical); `command-templates/{README,constitution,dashboard}.md` have none and stay untouched.
- **Rationale**: operator call; overrides that drift silently make this repository dogfood different doctrine
  than it ships. Override-only content removed by the resync is inventoried per file in the WP03 notes so nothing
  vanishes unrecorded.
- **Alternatives considered**: minimal additive patch (rejected by operator); deleting identical overrides.

## R5 — Supply chain
No dependency added, upgraded or removed; supply-chain checks not applicable.
