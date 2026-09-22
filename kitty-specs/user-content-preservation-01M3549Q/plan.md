# Implementation Plan: User-content preservation for mutating flows

**Branch**: `fix/user-content-preservation` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/user-content-preservation-01M3549Q/spec.md`

## Summary

Enforce the charter's existing **User Customization Preservation** invariant (charter
L463–479) across seven mutating flows that today silently destroy or corrupt
user-authored content and report success (epic #4915). The approach is
**extend-don't-invent**: reuse the canonical `asset_preservation.guard_destructive_removal`
+ provers for the removal flows (#4907, #2691), add ONE small shared symlink-aware
`backup_before_overwrite` helper for the single overwrite flow that needs a backup
(#4895 hook), apply a targeted refuse-gate for the other overwrite (#4910 intake),
and land three bespoke faithful-mutation fixes for the distinct sub-shapes (#4896
encoding, #4890 dep-validation, #4888 git-index). Close the removal defect class by
construction by widening the existing non-vacuous routing census gate to
`cli/commands/agent/config.py` — a **closure step that lands last**.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); reuses in-repo `specify_cli.asset_preservation` (guard/provers/backup), `specify_cli.git.commit_helpers`, `specify_cli.policy.hook_installer`; no new third-party dependency
**Storage**: filesystem (command surfaces, git hooks, briefs, spec artifacts) + git index/stash; no database
**Testing**: pytest (`@pytest.mark.regression` red-first per defect), mypy --strict, ruff; targeted per-WP surfaces declared below
**Target Platform**: Linux, macOS, Windows 10+ (cross-platform; symlink + read-only + line-ending edges matter)
**Project Type**: single (CLI library under `src/specify_cli/` + `src/` siblings)
**Performance Goals**: preservation checks add < 250 ms to `remove`/`sync` over a ≤200-file surface vs baseline; all fixed commands stay under the charter's < 2s CLI budget (NFR-002)
**Constraints**: no new dependency; content-based ownership proof only (never name/dir); single canonical guard authority (C-001); overwrite family stays OUT of the removal census (#4901 out of scope, C-002); no blanket `# noqa`/`# type: ignore`/Sonar suppression; complexity ≤15; new branch/helper ⇒ focused test same commit (C-005)
**Scale/Scope**: 7 defects, ~8 source modules, ~8 work packages; one non-draft PR to upstream `main`

### Supply-chain security

No dependency is added, upgraded, or removed by this mission (all fixes reuse in-repo
modules). The `051-supply-chain-install-safety` posture is therefore N/A — recorded
here explicitly (silence is not compliance): no registry/lifecycle-script/LTS decision
is made.

## Constitution Check (Charter Gate)

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

| Charter rule | Status | Note |
|--------------|--------|------|
| Single canonical authority (L28–32, C-001) | ✅ | Removals reuse the ONE guard; overwrite backup gets ONE new shared helper in `asset_preservation/backup.py`, not a per-site hand-rolled name |
| User Customization Preservation (L463–479) | ✅ | This mission IS the enforcement of that section across the remaining flows |
| Architectural gate discipline / non-vacuous gate (Standing Order #5) | ✅ | FR-013 widens the existing census gate (shrink-only, set-equality pinned, self-mutation both directions); no gate-unmask self-validates |
| ATDD-first / red-first (C-011, DIRECTIVE_030/034/041) | ✅ | Each defect lands a RED-on-base `@pytest.mark.regression` repro through the pre-existing entry point before the fix; transitional repros become focused unit tests after |
| Content-based proof, not name/dir (L470, C-003) | ✅ | Manifest hash / hook signature / canonical bytes; the whole point of the bug class |
| Locality + smallest-viable-diff + boy-scout (RECONCILE) | ✅ | Each WP is scoped to its owning module(s); campsite only within touched files; no cross-file scope creep |
| Terminology canon (Mission not Feature) | ✅ | No new user-facing `feature*` identifiers introduced |
| PRs only; operator merges (L385, DIRECTIVE_045) | ✅ | One non-draft PR to upstream; operator merges |
| No suppression / complexity ≤15 / tests-with-branches (Sonar) | ✅ | C-005 |

**Result: PASS** — no violations; Complexity Tracking table empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/user-content-preservation-01M3549Q/
├── plan.md              # This file
├── spec.md              # Committed, substantive
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/           # Phase 1 output — preservation-contract.md (extends ownership-guard-contract.md)
├── tracer/              # tooling-friction / approach / design-decisions (seeded, appended during implement)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root) — files each fix owns

```
src/specify_cli/
├── asset_preservation/
│   ├── guard.py                 # (reuse as-is) guard_destructive_removal chokepoint
│   ├── provers.py               # (reuse as-is) ManifestProver etc.
│   └── backup.py                # WP-A: + backup_before_overwrite() shared symlink-aware helper
├── cli/commands/
│   ├── agent/config.py          # WP-B: route _remove_project_agent_surface (3 literals) via guard; verdict-driven messaging (#4907, #2691 removal)
│   │                            #        + guard manifest-pin rewrite in sync (#2691 manifest)
│   ├── intake.py                # WP-D: existence-only overwrite gate at :296 AND :156 (#4910)
│   └── upgrade.py               # WP-G: render SafeCommitRecoveryFailed (stash ref + SHA) (#4888)
├── policy/hook_installer.py     # WP-C: detect foreign hook by signature, backup_before_overwrite + surface (#4895)
├── lanes/implement_support.py   # WP-C: caller wiring (surface the backup/warn)
├── text_sanitization.py         # WP-E: scoped decode, binary sniff, line-ending preserve, honest "Fixed" (#4896)
├── cli/commands/validate_encoding.py  # WP-E: driver adjustments if needed (#4896)
├── cli/commands/agent/tasks_finalize.py            # WP-F: validate effective persisted graph (#4890)
├── cli/commands/agent/tasks_finalize_validation.py # WP-F: same
├── git/commit_helpers.py        # WP-G: safe_commit via temp index / --only (#4888 root)
└── upgrade/autocommit.py        # WP-G: narrow except to propagate SafeCommitRecoveryFailed (#4888)

tests/architectural/test_mutation_ownership_routing.py  # WP-H (LAST): widen census to config.py (3 synchronized edits)
tests/... (mirrors)             # per-WP regression + unit tests
```

**Structure Decision**: single-project CLI layout; each WP owns disjoint source
file(s) so lanes do not collapse at finalize-tasks (lanes collapse by WRITE-SCOPE, not
dependency). The one shared file is `cli/commands/agent/config.py` — both #4907 and
#2691's removal half live in `_remove_project_agent_surface`, so they are ONE WP (WP-B).

## Parallel Work Analysis

### Dependency Graph

```
WP-A (backup_before_overwrite helper)  ──►  WP-C (#4895 hook backup)
                                       └──► (WP-D intake needs NO backup — independent)

WP-B (#4907 + #2691 removal + manifest)  ──►  WP-H (census widening — LAST, needs config.py routed+literal-free)

WP-D (#4910 intake)        ─┐
WP-E (#4896 encoding)       ├─ fully independent, parallel (disjoint files)
WP-F (#4890 dep-validate)   │
WP-G (#4888 git-index)     ─┘

Ordering intent: P0 lanes first (WP-B #4907, WP-C #4895), then P1 lanes in parallel,
then WP-H closure. WP-A is a tiny enabler landing just before WP-C.
```

### Work Distribution

- **Sequential**: WP-A → WP-C (helper before hook); WP-B → WP-H (route before census pin).
- **Parallel streams**: {WP-B}, {WP-A→WP-C}, {WP-D}, {WP-E}, {WP-F}, {WP-G} are write-disjoint and run concurrently; WP-H last.
- **Agent assignments (model discipline)**: implement = sonnet (profile-loaded python-pedro), review = opus (reviewer-renata). WP-G (`git/commit_helpers.py`, hottest surface, ~28 callers) gets extra targeted-test breadth and an opus review.

### Coordination Points

- **Integration risk**: only WP-B ↔ WP-H share knowledge of `config.py` (route then pin). WP-A ↔ WP-C share the helper signature (fix the contract in WP-A's tests).
- **Verify**: after consolidation, run each WP's targeted surface + the widened census self-mutation test; full `tests/architectural/` only at the cross-cutting closure (WP-H) per the no-full-arch-suite-locally rule (CI owns breadth).

## Complexity Tracking

*No Charter violations — table intentionally empty.*

## Notes carried to /spec-kitty.tasks

The design tracer (`tracer/design-decisions.md`) holds the post-spec squad's
implementation-level findings that each WP card must absorb: WP-B's three destructive
literals + verdict-driven messaging + dir-level single guard call; WP-H's three
synchronized gate edits (module set, pinned set-equality, `:142` rmdir allowlist);
WP-A/WP-C's symlink handling; WP-G's single-seam root fix + per-caller `upgrade`
propagation. `/spec-kitty.tasks` must fold these into the WP prompts, each with its
red-first repro and declared targeted test surface.
