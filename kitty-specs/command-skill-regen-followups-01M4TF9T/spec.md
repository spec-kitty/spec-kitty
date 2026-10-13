# Mission Specification: Command-skill regeneration follow-ups (#6155)

**Mission Branch**: `issue-6155-command-skill-regeneration-followups`
**Created**: 2026-10-13
**Status**: Draft
**Input**: GitHub issue #6155 — "Command-skill regeneration follow-ups: name regenerated paths, read the state contract at runtime, prune drifted retired projections". Three follow-ups deferred from the landing of PR #6113 (#702).
**Prerequisite**: PR #6113 (closes #702) must be merged to `main` before implementation; this spec extends its `preserve()` change. Research/plan/tasks proceed now; implement is held.

## User Scenarios & Testing *(mandatory)*

PR #6113 made the command-skill installer **regenerate** a manifest-owned
`.agents/skills/spec-kitty.<command>/SKILL.md` projection whose on-disk bytes match neither
the recorded manifest hash nor the current render, on the normal (non-`adopt_only`) reconcile.
That surface is DERIVED / git-IGNORED (`shared_skills_projection`,
`src/specify_cli/state/contract.py`), so the regenerate is correct. Three gaps remained,
each the subject of one user story below:

1. The regeneration is **silent** — `upgrade`, `init` and `agent config sync` print nothing
   per file, and the tree is git-ignored, so a replaced hand edit cannot be recovered or even
   noticed.
2. The regenerate branch is **unconditional**; the DERIVED/IGNORED premise is held only by a
   guard test, not read at runtime, so if the surface class ever changed the installer would
   keep clobbering.
3. `remove_entry` (retired-command prune) still reports `consent_required` for a drifted,
   manifest-owned projection — the same false "kept edit" #702 fixed for install, in the other
   direction.

### User Story 1 — Name each regenerated command skill (Priority: P1)

An operator running `spec-kitty upgrade` (or `init`, or `agent config sync`) on a checkout
whose generated `spec-kitty.<command>/SKILL.md` bytes differ from both the recorded manifest
hash and the current render wants to **see which generated command skills were regenerated**,
so a replacement of a hand edit on this git-ignored surface is visible rather than silent.

**Why this priority**: The surface is git-ignored, so a silently replaced edit is
unrecoverable and unnoticed. This is the operator-facing visibility gap #6155 leads with.

**Independent Test**: Scaffold a command-skill (codex/vibe/pi/letta) project, mutate one
manifest-owned projection so its bytes differ from both the recorded hash and the render, run
the reconcile through the real `upgrade --yes` entry point, and assert the path is named
exactly once in the human output and once in `--json` under `surface_repair`, while the exit
code and `outcome` kind are unchanged.

**Acceptance Scenarios**:

1. **Given** a manifest-owned projection whose on-disk bytes match neither the recorded
   `content_hash` nor the current render, **When** the reconcile regenerates it, **Then** the
   human output and the `--json` `surface_repair` payload each name that path exactly once
   (for example `Regenerated a generated command skill that differed from the current version: <path>`).
2. **Given** a projection already in sync with the current render, **When** the reconcile runs,
   **Then** no regenerated line is emitted for it (silent in-sync negative control).
3. **Given** a projection whose on-disk bytes equal the recorded manifest hash but not the
   current render (a stale-output / version-bump re-render), **When** the reconcile runs,
   **Then** no regenerated line is emitted for it (silent-for-recorded-hash negative control).
4. **Given** any regenerating reconcile, **When** it completes, **Then** the process exit code
   and the `outcome` kind are exactly what they were before this change (no new failure/drift).

---

### User Story 2 — Read the surface classification from the state contract at runtime (Priority: P1)

A maintainer wants the regenerate decision to be **gated on the live DERIVED/IGNORED
classification** of `shared_skills_projection` read from `STATE_SURFACES` at runtime, so the
installer regenerates only while that premise actually holds and otherwise falls back to the
existing consent behaviour — the one authority, not a hard-coded assumption.

**Why this priority**: Single canonical authority (charter). An unconditional regenerate is a
latent hazard: if the surface were ever reclassified, the installer would silently clobber a
genuinely protected file. Reading the contract makes the premise self-checking.

**Independent Test**: A unit test that monkeypatches the `shared_skills_projection` contract
entry to a non-ignored (or non-derived) class and drives a drifted manifest-owned projection
through `preserve()`/the reconcile, asserting it is kept as `consent_required` again (the
pre-#6113 behaviour); and the existing #702 regression + premise-guard tests stay green under
the real DERIVED/IGNORED classification.

**Acceptance Scenarios**:

1. **Given** `shared_skills_projection` is DERIVED and IGNORED (the real contract), **When** a
   drifted manifest-owned projection is reconciled, **Then** it is regenerated (US1 behaviour
   preserved).
2. **Given** the contract entry is monkeypatched to a non-ignored (or non-derived) class,
   **When** the same drifted projection is reconciled without overwrite consent, **Then** it is
   kept as `consent_required` (fall-through to the existing consent branch).
3. **Given** the fall-through path, **When** the operator supplies exact-path overwrite consent
   (`overwrite_paths`), **Then** the projection is overwritten — i.e. the `overwrite_paths`
   check is reachable again on the non-adopt path, not dead code.

---

### User Story 3 — Prune a retired command's drifted projection (Priority: P2)

When a command is retired, its manifest-owned projection whose bytes have drifted should be
**removed along with its manifest entry** under the same DERIVED/IGNORED condition — not kept
as `consent_required` — so a git-ignored generated surface does not accumulate orphaned
drifted files and `doctor skills` stays green.

**Why this priority**: Same reasoning as US1/US2 applied to the prune direction; lower only
because retired-command prune is a narrower, less-frequent path than the install/upgrade
reconcile.

**Independent Test**: A test where a retired command's drifted, manifest-owned projection is
reconciled through the real prune entry point; assert the file and its manifest entry are
removed, an unowned file at a `spec-kitty.*` path is kept, a directory at the projection path
is still refused, and `spec-kitty doctor skills` is green afterwards.

**Acceptance Scenarios**:

1. **Given** a retired command's manifest-owned projection whose bytes differ from the recorded
   hash, **When** the prune reconcile runs under the DERIVED/IGNORED gate, **Then** the file is
   removed and its manifest entry dropped.
2. **Given** an unowned (non-manifest) file at a `spec-kitty.*` projection path, **When** the
   prune runs, **Then** it is preserved and never removed.
3. **Given** a directory at the projection path, **When** the prune runs, **Then** it is still
   refused (unchanged).
4. **Given** the prune has run, **When** `spec-kitty doctor skills` is invoked, **Then** it
   reports green (no residual drift/orphan for the retired command).

### Edge Cases

- A projection whose bytes equal the recorded manifest hash but not the current render (a clean
  version-upgrade re-render): already handled — re-rendered, not flagged, and (US1) **silent**;
  this mission must not regress it or emit a regenerated line for it.
- A `spec-kitty.*` parent that is a symlink (owned package link) or non-directory: the
  installer's existing unsafe-path / package-link handling is unchanged.
- The fall-through (US2, non-DERIVED/IGNORED) path must reproduce the pre-#6113 `consent_required`
  disposition and the tool-surface drift reporting exactly.
- `remove_entry` is only ever called on manifest entries, so an unowned path is structurally
  never reached; US3 scenario 2 pins that it stays so.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Name each regenerated command-skill projection path once, in human and `--json` output | As an operator, I want each regenerated `spec-kitty.<cmd>/SKILL.md` named once in the human output and under `--json` `surface_repair`, so a replaced edit on the git-ignored surface is visible. | High | Open | [build] | no — paired with the in-sync and recorded-hash-equal silent negative controls (US1 scenarios 2–3) |
| FR-002 | Gate the regenerate on the runtime DERIVED/IGNORED classification | As a maintainer, I want the regenerate branch to read `shared_skills_projection` from `STATE_SURFACES` and regenerate only while it is DERIVED and IGNORED, else fall through to the existing consent branch. | High | Open | [ratchet] | no — a monkeypatched non-ignored class keeps the drifted projection as `consent_required` |
| FR-003 | Reconcile the `overwrite_paths` consent check and the provider comment | As a maintainer, I want the now-adopt-only `overwrite_paths` check revived on the non-adopt fall-through path (US2), with the `preserve()` inline comment and the `command_skills.py` provider comment rewritten to match. | High | Open | [folded] | no — covered by US2 scenario 3 (overwrite consent reachable on the non-adopt path) |
| FR-004 | Prune a retired command's drifted manifest-owned projection under the same gate | As an operator, I want `remove_entry` to remove a retired command's drifted projection and its manifest entry on the DERIVED/IGNORED condition, still refusing a directory and never touching an unowned path. | Medium | Open | [build] | no — paired with the unowned-file-preserved and directory-refused controls (US3 scenarios 2–3) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Exit code and outcome kind unchanged | No change to the process exit code or the `UpgradeOutcome` kind for any run; item 1 adds a report line only, routed through the sanctioned `surface_repair` summary so `test_upgrade_outcome_single_rendering.py` stays green (ADR 2026-10-04-3). | Correctness | High | Open |
| NFR-002 | Non-manifest / third-party paths untouched | Across every regenerating or pruning reconcile, 0 manifest-foreign paths under `.agents/skills/` are created, modified, or deleted (installer NFR-002). | Safety | High | Open |
| NFR-003 | Report exactly once, deterministically | Each regenerated path is named exactly once per run, in both human and `--json` output; in-sync and recorded-hash-equal projections produce no line; output is deterministic across repeated runs. | Reliability | High | Open |
| NFR-004 | No suppressions; gates green | New/changed code passes ruff, `ruff format --check --force-exclude`, and mypy with zero issues; cyclomatic complexity ≤ 15; no `# noqa` / `# type: ignore` / Sonar suppression added to pass a gate. | Technical | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Scope held to the shared command-skill surface | Change is limited to the DERIVED `.agents/skills/` command-skill installer path (codex/vibe/pi/letta) and its reporting. No change to tracked slash-command surfaces, the `.claude/skills/**` managed-file installer, `.claude/agents/*.md` profiles, or plugin-bundle components — ADR 2026-10-04-3 Decision 5 stays unchanged. The unresolved-drift exit code (#5745) is out of scope. | Technical | High | Open |
| C-002 | State contract is the single authority | The regenerate/prune decision reads `shared_skills_projection` (`authority=DERIVED`, `git_class=IGNORED`) at runtime; the existing premise guard test stays green and agrees with the runtime read. | Technical | High | Open |
| C-003 | Red-first for behaviour; output tests for reporting | Items 2 and 3 (behaviour corrections) witness the bug before the fix through the real reconcile/provider/prune entry points (revert → RED), mirroring #6113's red-first style; item 1 is tested through the human and `--json` output. No test is skipped/disabled/xfailed/quarantined; no retry-to-green. | Technical | High | Open |

### Key Entities

- **Command-skill projection**: `.agents/skills/spec-kitty.<command>/SKILL.md` — DERIVED,
  git-ignored generated output; one per canonical command per shared-root agent.
- **Command-skills manifest**: `.kittify/command-skills-manifest.json` — tracked record of
  each projection's owning agents, `content_hash`, install time, version.
- **Disposition / report_kind**: the installer's per-path verdict
  (`added`/`reused_shared`/`unchanged`/`preserve`/`consent_required`, plus a new
  `regenerated` signal). `consent_required`/`preserve` are the "unresolved" states the
  tool-surface provider surfaces as drift.
- **Regenerated report line**: the new per-path notice surfaced in human output and under
  `--json` `surface_repair` (via a new `InstallReport.regenerated` field for the
  install()-based legs and a new `DriftPolicySummary.regenerated` bucket for the upgrade leg).
- **State surface**: `shared_skills_projection` in `STATE_SURFACES` — the single authority for
  this surface's `authority`/`git_class`, read at runtime (US2).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `spec-kitty upgrade --yes` on a project with a drifted command-skill projection
  names that path exactly once in the human output and once in `--json` under `surface_repair`,
  and the exit code and `outcome` kind are identical to the pre-change run on the same fixture
  — [build] · no-op passable: no
- **SC-002**: A unit test monkeypatching the `shared_skills_projection` contract entry to a
  non-ignored/non-derived class shows the drifted projection kept as `consent_required`, and the
  existing #702 regression + premise-guard tests stay green under the real classification
  — [ratchet] · no-op passable: no
- **SC-003**: A test shows a retired command's drifted manifest-owned projection and its
  manifest entry removed; an unowned file at a `spec-kitty.*` path kept; a directory at the
  path refused; and `spec-kitty doctor skills --json` green afterwards — [build] · no-op
  passable: no
- **SC-004**: The behaviour corrections (SC-002, SC-003) are RED before the fix and GREEN after
  (revert → RED) through the real reconcile/provider/prune entry points, for codex plus one
  more shared-root agent where multi-agent coverage applies — [ratchet] · no-op passable: no
- **SC-005**: `make test-fast`, the skills / command-skills-provider / upgrade-drift / doctor-skills
  suites, the #702 regression file, and the named architectural gates
  (`test_no_legacy_terminology.py`, `test_upgrade_outcome_single_rendering.py`) are green on the
  diff (modulo honestly-classified pre-existing baseline reds), with ruff, `ruff format --check
  --force-exclude`, and mypy clean and complexity ≤ 15 — [ratchet] · no-op passable: no
