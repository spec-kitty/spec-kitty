# Mission Specification: Consolidate — canonical lane-consolidation terminology

**Mission Branch**: `feat/consolidate-canonical-terminology` (mission `consolidate-canonical-terminology-01M3GSSV`)
**Created**: 2026-09-27
**Status**: Draft
**Input**: GitHub issue #3080 — make `consolidate`/`consolidation` the canonical term for the lane-consolidation sense of `merge` (command, code, glossary, docs, prompt templates, gate-step name, drift guard).

> **Scope note (change from #3080 AC, operator-approved).** #3080's acceptance criteria mandate a *deprecated back-compat alias* for `spec-kitty merge`. The operator overrode this during discovery: because the repo is at **4.0.0rc4 (pre-stable)**, `spec-kitty merge` is **removed this cycle** as a clean rename (a hidden stub exits with a "renamed to `consolidate`" migration error — not a working alias). This divergence is recorded in C-004 and will be noted on the issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One unambiguous word for folding lanes (Priority: P1)

An operator or agent finishes a mission's work packages and folds the lane branches into the target ref. Today they type `spec-kitty merge`, a word that also means "git-merge two refs" and "publish to trunk". After this mission they type `spec-kitty consolidate`, and the lane-consolidation operation has exactly one name that cannot be confused with the other two senses.

**Why this priority**: This is the core value — a single canonical command word for the lane-consolidation operation. Without it the P0 overload persists.

**Independent Test**: Run `spec-kitty consolidate` end-to-end on a fixture mission and confirm lanes fold identically to the former `merge`; run `spec-kitty merge` and confirm it no longer performs consolidation (exits with a migration error naming `consolidate`).

**Acceptance Scenarios**:

1. **Given** an accepted mission with approved WPs, **When** the operator runs `spec-kitty consolidate --mission <handle>`, **Then** the lanes fold into the target ref with the same outcome, state persistence, and retention behavior the former `merge` produced.
2. **Given** the same mission, **When** the operator runs `spec-kitty merge`, **Then** the command exits non-zero with a message that the command was renamed to `spec-kitty consolidate` (no silent consolidation, no bare "unknown command").
3. **Given** an interrupted consolidation with a persisted `state.json`, **When** the operator runs `spec-kitty consolidate --resume`, **Then** it resumes from the persisted state exactly as `merge --resume` did.

---

### User Story 2 - Reviewers and agents never re-collapse the three senses (Priority: P1)

A reviewer or adversarial squad reads lane-lifecycle prose, code identifiers, and command output. Today "merge" forces a per-read disambiguation and has already produced two false "unfixable" BLOCKERs. After this mission the lane-consolidation sense reads only as `consolidate`/`consolidation`; git-integration reads as "merge"/"integrate"; trunk-publication reads as "publish".

**Why this priority**: The motivating incident was a real false-verdict cost. Eliminating the overload at the surfaces readers actually consume is the point of the mission.

**Independent Test**: Grep the converted surfaces and confirm no active lane-consolidation-sense "merge" remains; confirm git-merge and publish tokens are untouched; confirm the frozen keeps (below) still read "merge".

**Acceptance Scenarios**:

1. **Given** the converted code and docs, **When** a reader encounters `consolidate`/`consolidation`, **Then** it always means the lane-consolidation operation and never git-integration or publish.
2. **Given** git-integration mechanics (`git merge`, merge drivers, merge commits/conflicts, `MergeStrategy`), **When** the rename lands, **Then** those keep the word "merge" verbatim.

---

### User Story 3 - A drift guard keeps the canon honest (Priority: P2)

A maintainer adds new code or prose. If they use "merge" in the lane-consolidation sense, a fast architectural guard fails; if they use it for git-integration or publish, the guard stays green.

**Why this priority**: Without a ratchet the canon silently erodes; but a bare "merge" forbidden-term would flood on legitimate git usage, so the guard must target lane-consolidation-sense phrasings and the removed command surface.

**Independent Test**: Add a fixture line using lane-consolidation-sense "merge" → guard fails (red-first); add a `git merge`/`publish` line → guard stays green.

**Acceptance Scenarios**:

1. **Given** the extended guard, **When** a new `spec-kitty merge` appears in active prose/command surface (outside the historical allowlist), **Then** the guard fails.
2. **Given** a legitimate `git merge --no-ff` or "publish to origin" line, **When** the guard runs, **Then** it passes.

### Edge Cases

- `spec-kitty merge --resume/--abort/--dry-run` after removal → migration error, and the equivalent `consolidate` flag still reads the same `state.json`.
- An in-flight `state.json` written before the rename must resume successfully after it (no state-file key or filename churn).
- `baseline_merge_commit` present in an already-merged mission's `meta.json` must still be read by phase derivation (frozen key — see C-002).
- `MergeStrategy` config value `"merge"` must remain a valid serialized value (frozen — C-002).
- git merge-driver commands (`merge-driver-*`) tied to `.gitattributes`/git-config must be untouched.
- All 13 agent copies + command-skills must regenerate to `consolidate` via `spec-kitty upgrade`; hand-editing copies is forbidden (C-005).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `spec-kitty consolidate` command performs lane consolidation with the full former-`merge` flag set (`--resume/--abort/--dry-run/--keep-branch/--keep-worktree/--mission/--feature/--target`) | As an operator, I want one canonical command to fold lanes so that I never conflate it with git-merge or publish. | High | Open | [build] | no |
| FR-002 | `spec-kitty merge` is removed as a working command; a hidden stub exits non-zero with a "renamed to `consolidate`" migration message | As an operator, I want the old name to fail loudly with guidance so that no one silently invokes the overloaded word. | High | Open | [build] | no — paired with FR-001 on the same CLI fixture |
| FR-003 | Lane-consolidation behavior (state persistence, `--resume`, `--abort`, retention, gates, forecast) is preserved unchanged under `consolidate` | As an operator, I want zero behavior change so that only the name moves, not the mechanics. | High | Open | [ratchet] | no — paired with FR-002 (old name no longer resolves) on the same fixture |
| FR-004 | Code identifiers renamed for the lane-consolidation sense: `MergeState`→`ConsolidationState`, lane-sense symbols in `src/specify_cli/merge/` and `src/specify_cli/lanes/merge.py`; files physically renamed; all internal importers + tests updated | As a maintainer, I want code to read in the canonical term so that identifiers stop re-teaching the overload. | High | Open | [build] | no |
| FR-005 | Deliberate KEEPS remain verbatim: `MergeStrategy` enum + `"merge"` value, `baseline_merge_commit` meta.json key, `state.json` filename, merge-driver commands, git-integration vocabulary | As a maintainer, I want the git/publish senses and serialized contracts untouched so that config, phase derivation, and conflict resolution keep working. | High | Open | [ratchet] | no — paired with a renamed-sense control on the same fixture |
| FR-006 | Gate-step/command surface renamed: `command_installer.py` list/description/command-map `merge`→`consolidate`; skill `spk-gate-merge`→`spk-gate-consolidate`; slash command `spec-kitty.merge`→`spec-kitty.consolidate`; all 13 agent copies + command-skills regenerate via `spec-kitty upgrade` | As an agent, I want the mission gate-step named `consolidate` so that the runtime step matches the canonical command. | High | Open | [build] | no |
| FR-007 | Prompt templates + toolguides scrubbed of lane-consolidation-sense `spec-kitty merge`→`spec-kitty consolidate` (`mission-steps/software-dev/accept/prompt.md`, `specify/prompt.md`, `toolguides/POWERSHELL_SYNTAX.md`, and any other `packs/**` prompt.md) | As an agent, I want template guidance to name the canonical command so that generated instructions never re-teach the old word. | High | Open | [build] | no |
| FR-008 | Glossary + high-value docs: `consolidate` confirmed canonical, `spec-kitty merge` removed from active command vocabulary, the lane-consolidation sense of "merge" marked removed/legacy; the ~5 high-value doc files converted; CLAUDE.md:396 stale `merge-state.json` reference corrected | As a reader, I want the canonical docs to use one word so that lane-lifecycle prose is unambiguous. | Medium | Open | [build] | no |
| FR-009 | Drift-ratchet guard extended: a command-surface `"spec-kitty merge"` + lane-consolidation-phrasing ratchet with its own baseline + historical allowlist; scans `src`, `docs`, **and `packs/`**; red-first "bites a new violation" + "green on legit git-merge/publish" proofs | As a maintainer, I want new merge-sense drift blocked so that the canon does not silently erode. | High | Open | [build] | no |
| FR-010 | Phase-naming coherence: residual lane-consolidation-sense merge names (`MissionReviewMode.POST_MERGE` and ~8 refs) converge onto landed `CONSOLIDATED`/`PUBLISHED`/`PRE_CONSOLIDATION`; no new `POST_CONSOLIDATION` symbol reintroduced | As a maintainer, I want one coherent phase vocabulary so that the naming is not half-and-half. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No hard break to persisted/in-flight state | An in-flight consolidation `state.json` and every already-merged mission `meta.json` (incl. `baseline_merge_commit`) resume/read successfully after the rename; 100% of the existing consolidation (former `tests/merge/`) behavior suite passes, 0 regressions | Reliability | High | Open |
| NFR-002 | No unresolved imports / consumer break | Post-rename: 0 unresolved internal imports; any renamed symbol imported by an external consumer retains a re-export alias (else confirmed internal-only); `clean-install-verification` + shared-package-boundary + import tests green | Compatibility | High | Open |
| NFR-003 | Maintainability ceiling held | Touched functions stay at cyclomatic complexity ≤15 (ruff C901 / Sonar S3776); every new branch/helper has focused tests; no new blanket `# noqa`/`# type: ignore`/per-file ignores | Maintainability | Medium | Open |
| NFR-004 | Quality gates clean | `ruff check .`, `ruff format --check .`, and `mypy` report zero issues; `tests/architectural/test_no_legacy_terminology.py` green | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Semantic rename, never find-replace | Every touched occurrence is classified in `occurrence_map.yaml` as rename-now / rename-deferred / keep before any edit (DIRECTIVE_035 bulk-edit guardrail); no bare `sed s/merge/consolidate/` | Technical | High | Open |
| C-002 | Frozen wire-keys/values | `baseline_merge_commit` (meta.json key — drives phase derivation at `mission_runtime/lifecycle_phase.py:237-239`), `MergeStrategy` `"merge"` value, and the `state.json` filename MUST NOT be renamed | Technical | High | Open |
| C-003 | Other two senses stay put | git-merge/branch-integration keeps "merge"/"integrate"; publish-to-origin keeps "publish" | Technical | High | Open |
| C-004 | Alias-removal overrides #3080 AC | The mandated deprecated back-compat alias is intentionally NOT provided; `spec-kitty merge` is removed this cycle (pre-stable 4.0.0rc justification), with a migration-error stub only. Recorded divergence to be noted on the issue | Business | High | Open |
| C-005 | Edit source, not generated copies | The 13 agent dirs + command-skills are generated; edit sources (`command_installer.py`, `packs/**` templates) and regenerate via `spec-kitty upgrade`; never hand-edit copies | Technical | High | Open |
| C-006 | Immutable history untouched | ADR bodies and `kitty-specs/` snapshots are not rewritten | Technical | Medium | Open |
| C-007 | Version + changelog on `__init__.py` | Any `__init__.py` change carries a `pyproject.toml` version bump + `CHANGELOG.md` entry | Technical | Medium | Open |
| C-008 | Long-tail prose deferred | v1 scope = command + code + gate-step + prompt templates + guard + high-value docs; long-tail/archival prose stays grandfathered (shrink-only guard blocks new uses) and is boyscouted over time | Business | Medium | Open |

### Key Entities

- **Lane-consolidation operation**: the `consolidate` command and the act of folding lane branches into the Target Ref (formerly the lane-consolidation sense of `merge`).
- **ConsolidationState** (formerly `MergeState`): the persisted `state.json` capturing consolidation progress for resume.
- **Occurrence classification map** (`occurrence_map.yaml`): per-site verdict of rename-now / rename-deferred / keep across the three senses.
- **Drift-ratchet guard**: the architectural test that fails new lane-consolidation-sense "merge" without false-positiving git/publish uses.
- **Frozen wire-keys**: `baseline_merge_commit`, `MergeStrategy="merge"`, `state.json` — serialized contracts that must not move.

### Domain Language *(canonical terms)*

- **consolidate / consolidation** — canonical for the lane-consolidation sense (glossary Sense 1). Verb `consolidate`, noun `consolidation`, state `CONSOLIDATED`.
- **merge / integrate** — git branch-integration sense only (glossary Sense 2). KEEP.
- **publish** — push/PR to origin/trunk (glossary Sense 3). KEEP.
- Numbering follows the landed canonical glossary (`docs/context/orchestration.md:568,595`), not the pre-spec brief's inverted numbering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The lane-consolidation operation has exactly one canonical command name (`spec-kitty consolidate`); `spec-kitty merge` returns a migration error, not a silent consolidation — [build] · no-op passable: no.
- **SC-002**: Zero regressions across the existing consolidation (former `merge`) behavior suite; in-flight `state.json` and legacy `meta.json` still resume/read — [ratchet] · no-op passable: no (paired with FR-001/FR-002 rename assertions).
- **SC-003**: The drift guard fails a newly-introduced lane-consolidation-sense "merge" and passes on legitimate git-merge/publish usage (red-first + green-on-legit both proven) — [build] · no-op passable: no.
- **SC-004**: All 13 agent surfaces + command-skills expose `consolidate` (not `merge`) after `spec-kitty upgrade`, verified on at least `.claude`, `.codex`, `.opencode` — [build] · no-op passable: no.
- **SC-005**: Deliberate keeps intact — `baseline_merge_commit`, `MergeStrategy="merge"`, merge-drivers unchanged; phase derivation still resolves `PRE_CONSOLIDATION`/`CONSOLIDATED` correctly — [ratchet] · no-op passable: no (paired with a renamed-sense positive control).

## Assumptions

- `baseline_merge_commit` is frozen at the wire-key level; only its local code identifiers/prose may be boyscouted, never the persisted key or the phase-derivation contract.
- The modern consolidation state file is already `state.json` under `.kittify/runtime/merge/<id>/`; the filename is kept. The stale CLAUDE.md:396 `merge-state.json` claim is corrected as a campsite fix (FR-008).
- All 13 agent command copies + command-skills regenerate deterministically from one source edit via `spec-kitty upgrade`.
- Re-export aliases are added only where an external consumer imports a renamed symbol; plan-phase analysis confirms which symbols (if any) are consumer-facing versus internal-only.
- The already-landed foundation (canonicalizing ADR `2026-07-30-1`, glossary `consolidate` entries, `_LANE_CONSOLIDATION_FORBIDDEN_PHRASES`, `CONSOLIDATED`/`PRE_CONSOLIDATION` phase naming) is extended, not re-created.
