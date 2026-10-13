# Implementation Plan: Command-skill regeneration follow-ups (#6155)

**Branch**: `issue-6155-command-skill-regeneration-followups` | **Date**: 2026-10-13 | **Spec**: `kitty-specs/command-skill-regen-followups-01M4TF9T/spec.md`
**Input**: Mission specification (GitHub #6155) + `research/code-grounding.md` (Phase 0).
**Prerequisite (HOLD)**: PR #6113 (closes #702) must be merged to `main` before implementation. This plan extends #6113's `preserve()` change; the implement run is held until #6113 lands, then rebased onto the merged base.

## Summary

Close the three follow-ups deferred from #6113's landing, all on the DERIVED/git-IGNORED
command-skill surface (`.agents/skills/spec-kitty.<command>/SKILL.md`):

1. **Report (item 1)** — name each regenerated projection path once, in the human output and
   under `--json` `surface_repair`, without changing the exit code or the `UpgradeOutcome`
   kind. Silent for an in-sync projection or one equal to the recorded manifest hash.
2. **Runtime contract read (item 2)** — gate `_CommandBatch.preserve()`'s regenerate branch on
   the live DERIVED/IGNORED classification read from `STATE_SURFACES`
   (`shared_skills_projection`), falling through to the existing consent branch
   (`overwrite_paths` → `consent_required`) when the premise does not hold. Revive the now
   adopt-only `overwrite_paths` check on that fall-through, and reconcile the inline + provider
   comments.
3. **Prune (item 3)** — apply the same gate in `_CommandBatch.remove_entry()` so a retired
   command's drifted, manifest-owned projection and its manifest entry are removed, while a
   directory at the path is still refused and no unowned path is touched.

The behavioural change is concentrated in two methods of one file
(`src/specify_cli/skills/command_installer.py`); reporting threads one new signal through
existing renderers for the three install/upgrade surfaces.

## Technical Context

**Language/Version**: Python 3.11+.
**Primary Dependencies (internal)**: `specify_cli.skills.command_installer` (`preserve`,
`remove_entry`, `install`, `InstallReport`); `specify_cli.state.contract`
(`STATE_SURFACES`, `shared_skills_projection`, `AuthorityClass`, `GitClass`);
`specify_cli.tool_surface.providers.command_skills` (overwrite_paths + provider comment);
`specify_cli.tool_surface.repair` (`DriftPolicySummary`, `render_surface_summary_lines`);
`specify_cli.cli.commands.upgrade` (`_apply_prepared_surface_repairs`,
`_surface_repair_payload`); `specify_cli.cli.commands.init`
(`_install_command_skill_agents`); `specify_cli.cli.commands.agent.config`
(`_register_skill_agent` / `sync_agents`).
**Storage**: filesystem — `.agents/skills/` (ignored) + `.kittify/command-skills-manifest.json`
(tracked).
**Testing**: pytest. Red-first (items 2, 3) through the real reconcile/provider/prune entry
points; output tests (item 1) through `upgrade --yes` human + `--json` and the provider call.
`make test-fast` + the owning skills/provider/upgrade-drift/doctor-skills dirs + the #702
regression file + named architectural gates.
**Target Platform**: Linux/macOS/Windows CLI.
**Project Type**: single (CLI).
**Performance Goals**: N/A — no new hot path; one STATE_SURFACES lookup cached per batch.
**Constraints**: ruff + `ruff format --check --force-exclude` + mypy zero issues; complexity
≤ 15; no suppressions; scope confined to the DERIVED command-skill surface (C-001); exit code
and outcome kind unchanged (NFR-001).
**Scale/Scope**: behavioural change ≈ the `preserve()` drift branch + the `remove_entry()`
top guard; one new installer signal (`InstallReport.regenerated` + a `DriftPolicySummary`
bucket) threaded through three renderers; red-first + output tests; comment reconciliation.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** ✓ — item 2 reads the ONE authority for this surface's class
  (`shared_skills_projection`) at runtime instead of hard-coding the premise; the existing
  premise-guard test is kept and must agree with the runtime read (C-002).
- **Architectural alignment** ✓ — change stays inside the modules that already own
  `.agents/skills/` mutation and its reporting; the only new import
  (`specify_cli.state.contract`) is intra-`specify_cli`, no layer-rule / shared-package-boundary
  impact.
- **DDD + tiered rigour** ✓ — one bounded behaviour (install/prune-time drift disposition on a
  DERIVED surface) plus its reporting; more rigour on the `preserve`/`remove_entry` core than on
  the renderer plumbing.
- **ATDD-first** ✓ — red-first regressions for items 2 and 3 precede the fix; item 1 drives the
  real output.
- **Terminology adherence** ✓ — no new/retired terms; the new user-facing literal is clean of
  the gated terms (`ceremony` / `status commit` / `status-writing`).
- **Smallest-viable-diff / locality-of-change** ✓ — two methods in one module changed; one new
  field/bucket threaded through existing renderers; `existing is None` branch and other managed
  surfaces untouched.

No violations → Complexity Tracking empty.

## Adversarial review at the planning point-cut

The two read-only discovery squads (related-issues + similar-surfaces/code-grounding) ran at
the grounding point-cut and converged (verdicts in `research/code-grounding.md`). The sharp
risks they surfaced, each with its mitigation folded into this plan:

- **Outcome-contract regression (item 1).** Adding a report line could trip
  `test_upgrade_outcome_single_rendering.py` if a presentation function builds output itself.
  → Mitigation: surface regenerated paths as data owned by `InstallReport` /
  `DriftPolicySummary`, consumed by the sanctioned `surface_repair` summary renderer; never
  a bare `console.print` in a presentation function. IC-01.
- **Double-reporting on init (item 1).** init has two legs (direct install + surface repair);
  a path could be named twice. → Mitigation: the direct install leg regenerates first, so the
  repair leg reads the surface as present; assert exactly-once (NFR-003). IC-01.
- **Over-broadening (items 2, 3).** The gate must not leak into the `existing is None`
  (non-manifest) branch or an unowned `remove_entry` path. → Mitigation: keep `existing is None`
  untouched; `remove_entry` iterates manifest entries only; pin both with controls. IC-02/IC-03.
- **Silent-case drift (item 1).** The recorded-hash-equal version-bump re-render must stay
  silent. → Mitigation: capture the signal strictly in the drift branch
  (`before.sha256 not in (content_hash, digest)`), which that case never enters; negative
  control. IC-01.
- **Premise divergence (item 2).** The runtime read must agree with the premise-guard test. →
  Mitigation: read `shared_skills_projection` by name from `STATE_SURFACES`, same fields the
  guard asserts; keep the guard. IC-02.

A further profile-loaded adversarial squad on the aggregate diff is scheduled at closeout
(pre-PR review squad), per `mission-wrap-up-sequence`.

## Project Structure

### Documentation (this mission)

```
kitty-specs/command-skill-regen-followups-01M4TF9T/
├── spec.md                      # mission spec
├── plan.md                      # this file
├── research/code-grounding.md   # Phase 0 grounding + discovery-squad verdicts
├── tasks.md                     # Phase 2 (/spec-kitty.tasks)
└── tasks/WP01-*.md              # work package prompt(s)
```

### Source Code (repository root) — EDIT vs read-only

```
src/specify_cli/skills/command_installer.py   # EDIT: preserve() gate+signal (items 1,2);
                                               #       remove_entry() split (item 3);
                                               #       InstallReport.regenerated + report_kind
src/specify_cli/state/contract.py             # READ: shared_skills_projection / STATE_SURFACES (item 2)
src/specify_cli/tool_surface/providers/command_skills.py  # EDIT: overwrite_paths provider comment (item 2)
src/specify_cli/tool_surface/repair.py        # EDIT: DriftPolicySummary.regenerated bucket + human line (item 1)
src/specify_cli/cli/commands/upgrade.py       # EDIT: _apply_prepared_surface_repairs bucketing + _surface_repair_payload "regenerated" (item 1)
src/specify_cli/cli/commands/init.py          # EDIT: print per-path notice at the install leg (item 1)
src/specify_cli/cli/commands/agent/config.py  # EDIT: print per-path notice at _register_skill_agent (item 1)

tests/specify_cli/skills/test_command_installer.py                       # UPDATE/ADD: preserve gate + remove_entry prune + report signal
tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py  # EXTEND (post-#6113): non-DERIVED fall-through + in-sync silence
tests/specify_cli/tool_surface/providers/test_command_skills.py          # provider comment + overwrite_paths fall-through
tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py       # ADD: surface_repair["regenerated"] + human notice
tests/specify_cli/cli/commands/test_doctor_skills.py                     # item 3 prune leaves doctor green
docs/changelog/CHANGELOG.md                                              # [Unreleased] entry
```

**Structure Decision**: Single CLI project. Behaviour in `command_installer.py`; reporting
threaded through existing `InstallReport` / `DriftPolicySummary` renderers. Final EDIT line
numbers verified against the merged #6113 base at implement time (they shift with the merge).

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

### IC-01 — Name each regenerated path (item 1)

- **Purpose**: Make a regenerate on the DERIVED surface emit exactly one per-path notice in
  human output and `--json` `surface_repair`, without changing the exit code or outcome kind;
  silent for in-sync and recorded-hash-equal projections.
- **Relevant requirements**: FR-001, NFR-001, NFR-003, SC-001.
- **Affected surfaces**: `command_installer.py` (`preserve()` drift branch records the
  regenerated `rel`; `InstallReport` gains a `regenerated` field via a new `report_kind`);
  `repair.py` (`DriftPolicySummary.regenerated` bucket + the human line in
  `render_surface_summary_lines`); `upgrade.py` (`_apply_prepared_surface_repairs` routes the
  regenerated subset; `_surface_repair_payload` adds `"regenerated"`); `init.py` and
  `agent/config.py` print the per-path notice on their install legs.
- **Sequencing/depends-on**: builds on the capture point introduced here; independent of IC-03.
- **Risks**: outcome-contract gate (route via the owned summary, not a presentation
  `print`); double-reporting on init (direct leg regenerates first → assert once); silent
  version-bump case (capture strictly in the drift branch).

### IC-02 — Runtime DERIVED/IGNORED gate + overwrite_paths reconcile (item 2)

- **Purpose**: Gate the regenerate on the live `shared_skills_projection` classification; fall
  through to the consent branch otherwise; revive `overwrite_paths` on the non-adopt path; fix
  the inline + provider comments.
- **Relevant requirements**: FR-002, FR-003, C-002, SC-002.
- **Affected surfaces**: `command_installer.py` (`preserve()` — new intra-layer import of
  `specify_cli.state.contract`, a per-batch cached `_regenerate_ok` lookup, restructured branch);
  `command_skills.py` (provider comment).
- **Sequencing/depends-on**: shares the `preserve()` edit with IC-01; the gate helper is reused
  by IC-03.
- **Risks**: the runtime read must agree with the premise guard; the fall-through must
  reproduce the pre-#6113 `consent_required` + overwrite-consent behaviour exactly; do not touch
  the `existing is None` branch.

### IC-03 — Prune a retired command's drifted projection (item 3)

- **Purpose**: Split `remove_entry()`'s top guard so a directory is still refused but a drifted,
  manifest-owned file is pruned (file + manifest entry removed) under the same gate.
- **Relevant requirements**: FR-004, NFR-002, SC-003.
- **Affected surfaces**: `command_installer.py` (`remove_entry()`); reuses IC-02's gate.
- **Sequencing/depends-on**: IC-02 (shared gate helper).
- **Risks**: must keep refusing a directory; `remove_entry` is manifest-entry-only so an
  unowned path is structurally unreached — pin it with a control; `doctor skills` green after.

### IC-04 — Docs / changelog (folded)

- **Purpose**: A `[Unreleased]` CHANGELOG entry stating the regenerated-path notice, the
  runtime-gated regeneration, and the retired-projection prune. Confirm `docs/api/upgrade-lifecycle.md`
  (touched by #6113) still reads true; extend only if needed.
- **Relevant requirements**: SC-005 (docs/gates green); terminology guard.
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (+ `upgrade-lifecycle.md` if needed).
- **Sequencing/depends-on**: IC-01/02/03 (describe shipped behaviour).
- **Risks**: terminology guard; docs-retrieval-index regen if a page is added (none planned).
