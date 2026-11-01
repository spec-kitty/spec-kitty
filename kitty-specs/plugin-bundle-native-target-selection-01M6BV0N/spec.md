# Mission Specification: Plugin bundle native target selection

**Mission Branch**: `issue-6273-plugin-bundle-native-target-selection`
**Created**: 2026-11-01
**Status**: Ready for Plan
**Input**: Issue #6273 — `doctor tool-surfaces: plugin bundles never stage when Claude and Codex are both configured (Codex .toml and Claude .md profiles collide on one bundle member); probe reports the manifest as "missing"`.

**Operator/triage guidance recorded here**: the issue carries `triage:needs-revision` asking that the
intended target-native selection/rendering and the diagnostic contract be pinned before the collision
guard changes. They are pinned in FR-001, C-001 and FR-004 below.

## Problem

`doctor tool-surfaces --fix` never stages `dist/spec-kitty-plugins/*` in a project that configures
Claude and Codex together. Each projector builds bundle members from *every* configured tool's
surface instances and maps every agent profile onto its own agent filename
(`.codex/agents/<id>.toml` becomes `agents/<id>.md` for the Claude bundle). One bundle member then
has two different byte sequences — `.claude/agents/<id>.md` and `.codex/agents/<id>.toml` — and the
shared-member guard refuses the whole batch. The three manifests stay `missing`, `--fix` exits 0, and
the human output never says that a repair was attempted and failed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-harness project stages every bundle (Priority: P1)

An operator configures Claude and Codex (or Claude, Codex and Copilot) in one project and runs
`spec-kitty doctor tool-surfaces --fix`. The three staging bundles are written and a following audit
reports `missing: 0`.

**Why this priority**: this is the reported defect; without it the bundles can never be staged in a
multi-harness project.

**Independent Test**: run the issue's reproduction (init with `--ai claude,codex,copilot`, then
`doctor tool-surfaces --fix`) and confirm `dist/spec-kitty-plugins/{claude_code_plugin,
copilot_skill_package,vscode_extension}` exist and the re-audit reports `missing: 0`, `ok: true`.

**Acceptance Scenarios**:

1. **Given** a project initialised with `--ai claude,codex,copilot`, **When**
   `doctor tool-surfaces --fix` runs, **Then** the three plugin manifests exist on disk and the
   post-fix report has `missing: 0`.
2. **Given** the same project, **When** the staged bundles are inspected, **Then** each agent member
   was rendered in its own target's native format (Claude `.claude/agents/<id>.md` bytes in the
   Claude bundle; `.github/agents/<id>.agent.md` bytes in the Copilot and VS Code bundles) and no
   Codex `.toml` rendering was renamed into a Markdown agent member.
3. **Given** the same project, **When** `--fix` has staged the bundles, **Then** a second `--fix`
   is a no-op (no rewritten members, no new conflict).

---

### User Story 2 - Genuine shared-member conflicts still refuse (Priority: P2)

A real conflict (two sources of the *same* rendering family disagreeing on one bundle member) still
fails closed: nothing is written, the assessment is incomplete, and the diagnostic names the member.

**Why this priority**: the existing safety guarantee must survive the selection change; the issue
explicitly asks that the intended selection rule, not a weakened guard, be the fix.

**Independent Test**: build a plan with two same-family agent-profile sources for one member that
differ in bytes; assert the assessment is incomplete with the conflict message and no files written.

**Acceptance Scenarios**:

1. **Given** two accepted sources for one bundle member whose bytes differ, **When** the bundle is
   assessed, **Then** the assessment is incomplete, no file is written, and the diagnostic names the
   member.
2. **Given** a source rendered in a format the target does not accept (a Codex `.toml` agent profile
   for the Claude bundle), **When** the Claude bundle is projected, **Then** that source is not a
   candidate for the Markdown agent member at all.

---

### User Story 3 - A failed repair is visible and non-zero (Priority: P2)

When `--fix` cannot repair a surface, the operator is told which surfaces failed and why, and the
command exits non-zero.

**Why this priority**: the issue's expected behaviour includes it, and a silent exit 0 hides the
failure that caused the report.

**Independent Test**: force a bundle assessment to fail (e.g. a malformed required member), run
`doctor tool-surfaces --fix`, and assert the human output names the failed surface and the reason
and the exit code is 1; the JSON `repair.findings_after` carries the cause.

**Acceptance Scenarios**:

1. **Given** a repair that cannot complete, **When** `doctor tool-surfaces --fix` runs, **Then** the
   repair result reports the failed surface ids and the cause, the human output prints them, and the
   process exits 1.
2. **Given** a repair that completes, **When** `doctor tool-surfaces --fix` runs, **Then** the exit
   code is 0 and no failure line is printed.
3. **Given** a staged bundle whose members do not match the prepared batch, **When** the audit probes
   it, **Then** the finding carries the underlying cause instead of only the generic
   "missing, drifted, or unavailable members" sentence.

### Edge Cases

- Project configures only Claude: the Copilot/VS Code bundles must still stage from the compatible
  Markdown agent rendering (same rendered body), as today.
- Project configures only Codex: no target accepts the `.toml` rendering, so the bundle has no agent
  members; the guard must not fabricate a `.md` from `.toml` bytes. The Claude/Copilot/VS Code bundles
  remain optional and missing does not flip `ok` (OPTIONAL policy, integration contract).
- A tool alias appears twice in the configured set: entries stay de-duplicated and deterministic.
- `--fix` from a foreign checkout is still refused before any write (existing guard unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Target-native rendering selection | As an operator, I want each plugin bundle to carry only the per-harness rendering native to its distribution target (agent profiles and command/charter skills), named from that rendering's own suffix, so that a Claude+Codex project no longer collides two formats on one member and a Copilot profile is not double-suffixed. | High | Open | [build] | no — same-fixture positive control: the Codex `.toml` instance is excluded while the Claude `.md` instance is selected for `agents/<id>.md` |
| FR-002 | Preserve the conflict guard | As a maintainer, I want the shared-member refusal to still fire for genuinely conflicting accepted sources, so that the fix does not weaken the staging safety contract. | High | Open | [ratchet] | no — paired negative on the same fixture: two differing accepted sources still fail closed |
| FR-003 | Compatible fallback | As an operator configuring one harness, I want the Markdown-family bundles to fall back to the other Markdown-family rendering when the native tool is not configured, so that bundles keep staging as they do today. | Medium | Open | [build] | no |
| FR-004 | Failed repair is reported | As an operator, I want `--fix` to name the surfaces it failed to repair and exit non-zero, so that an unrepaired surface is not mistaken for routine residue. | High | Open | [build] | no — positive/negative control on the same command: repaired run exits 0, forced-failure run exits 1 |
| FR-005 | Incomplete staged bundle keeps its cause | As an operator, I want a probe of a staged bundle that no longer matches its prepared batch to carry the underlying cause, so that the conflict diagnostic is not dropped. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new writes on assessment | An incomplete or refused assessment performs zero filesystem writes; verified by the existing snapshot/audit-hook assertions. | Reliability | High | Open |
| NFR-002 | Deterministic bundle bytes | Re-projecting the same project twice produces byte-identical members and no second-round effects. | Reliability | High | Open |
| NFR-003 | Bounded repair reporting | Repair reporting adds no more than one diagnostic per failed surface; no unbounded message duplication. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | Pinned selection contract | The selection rule is explicit and documented: a target accepts the agent tool keys of its own rendering family (Claude bundle: `claude`; Copilot/VS Code bundles: `copilot`, `vscode`), with the other Markdown family as a lower-priority fallback and non-Markdown families never accepted. | Technical | High | Open |
| C-002 | OPTIONAL policy unchanged | Missing optional plugin-bundle manifests keep `ok: true`; only a failed repair changes the exit code. | Business | High | Open |
| C-003 | No publish/install | The change stays inside staging: no marketplace publication, plugin enablement or install side effect. | Technical | High | Open |

### Key Entities

- **Bundle member**: one in-bundle relative path (`agents/<id>.md`) with exactly one accepted byte sequence.
- **Agent-profile source**: a tool-native rendering of a canonical profile (`.claude/...md`, `.github/...agent.md`, `.codex/...toml`).
- **Repair outcome**: repaired/skipped/failed surface ids plus the findings that explain a failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue reproduction on a fresh `init --ai claude,codex,copilot` project ends with `dist/spec-kitty-plugins/` present for all three targets and `summary.missing == 0` — [build] · no-op passable: no
- **SC-002**: The pre-fix reproduction (same steps) reports `missing == 3`; the same fixture proves the change is not vacuous — [build] · no-op passable: no
- **SC-003**: A forced repair failure exits 1 and prints each failed surface with its reason; a successful repair exits 0 — [build] · no-op passable: no
- **SC-004**: Existing bundle safety tests (conflict refusal, no-write assessment, foreign-checkout refusal) pass unchanged in intent — [ratchet] · no-op passable: no
