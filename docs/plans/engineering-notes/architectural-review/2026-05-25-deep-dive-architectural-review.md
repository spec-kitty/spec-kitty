---
title: Architectural deep-dive — 2026-05-25
description: Architect Alphonso's post-mission-122 architectural deep-dive (2026-05-25) across the full src/ tree, emphasizing the charter/doctrine/specify_cli bounded contexts.
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Architectural deep-dive — 2026-05-25

**Reviewer**: Architect Alphonso (post-mission-122 audit)
**Scope**: full `src/` tree, with emphasis on the charter / doctrine / specify_cli bounded contexts and the new `charter_freshness` / `charter_preflight` packages introduced by mission `01KSAF14`
**Inputs**: `docs/plans/engineering-notes/finding/`, `docs/plans/engineering-notes/reflections/`, the post-merge mission-review report, the open-issue tracker

---

## Executive summary

The codebase has a **clean direction-of-dependency** between its three top-level Python packages (`charter`, `doctrine`, `specify_cli`) — no inverse imports from the core domains back into the application layer. That's a real strength to protect.

But there are three observable smells worth addressing in an intermediate remediation mission, in priority order:

1. **`src/specify_cli/` is over-decomposed**: 67 subpackages, of which four (`charter/`, `charter_lint/`, `charter_freshness/`, `charter_preflight/`) all serve adjacent charter-runtime concerns. The split is a *runtime* split (lifecycle vs read-only vs check), not a *domain* split — the boundary between them is leaky.
2. **`src/specify_cli/cli/commands/charter.py` is 3,328 lines** and continues to grow: it's the only "command surface" file for 6+ logically distinct charter subcommands (`status`, `sync`, `synthesize`, `lint`, `preflight`, `bundle`). This was already a smell pre-mission and the mission added to it.
3. **`_apply_org_overrides` and `_apply_project_overrides` in `src/doctrine/base.py`** are near-identical methods that differ only in the source directory shape (`list` vs `Path`) and a hard-coded provenance string. This is textbook logical duplication and a perfect lever for a parameterized overlay-application method that would also clarify the layered-doctrine ADR's intent.

**Verdict (50 words):** the codebase does NOT need immediate architectural attention — it ships, it's used, and it passes its FR contracts. But a focused 4-WP intermediate mission could absorb the 1298-class test stabilisation work AND close 3-4 small architectural debts (logical duplication, charter.py size, charter-* package boundary, doctrine schema discoverability) before they calcify.

---

## 1. Bounded-context map

| Bounded context | Canonical package | Dependency direction | Boundary status |
|---|---|---|---|
| **Charter** (governance source) | `src/charter/` | downstream of nothing in this repo; consumed by `specify_cli` | clean — zero inverse imports |
| **Doctrine** (rulebook + DRG + agent profiles) | `src/doctrine/` | downstream of nothing; consumed by `specify_cli` and `charter` | clean — zero inverse imports (verified via `git grep "from specify_cli" src/doctrine/*.py`) |
| **Constitution** (separate sub-area) | `src/constitution/` | small package; appears self-contained | not investigated in this pass |
| **Dashboard** (presentation/API) | `src/dashboard/` + `src/specify_cli/dashboard/` | consumes everything | bifurcated — see §3 |
| **Mission lifecycle** (specify → plan → tasks → implement → review → merge) | `src/specify_cli/cli/commands/*.py` + `src/specify_cli/runtime/` + `src/runtime/` | applies charter + doctrine | scattered — see §3 |
| **Status / kanban** (lane state machine) | `src/specify_cli/status/` | consumes mission identity | clean per its 060-cleanup; appears bounded |
| **Glossary / terminology** | `src/specify_cli/glossary/` (impl) + `src/doctrine/` (schemas) | bridges doctrine into runtime | acceptable but worth a re-check |

**The good news:** the dependency direction is correct. `charter` and `doctrine` do not import from `specify_cli`, so the core domains stay testable in isolation. This is preserved by 32 lines of `git grep` evidence.

**The smell:** four charter-related packages under `specify_cli/` (`charter/`, `charter_lint/`, `charter_freshness/`, `charter_preflight/`) are siblings with overlapping read paths. Each is fine in isolation but together they form a single "charter operations" surface that is currently spelled four ways.

---

## 2. Logical duplication findings

### LD-1 — `_apply_org_overrides` vs `_apply_project_overrides` in `src/doctrine/base.py`

**Severity**: MEDIUM
**Evidence**: lines 210-308 of `src/doctrine/base.py`. The two methods share the same skeleton:
- iterate a source directory
- parse YAML
- validate-then-merge against `built_in[id]` if collision
- otherwise insert fresh
- emit `DoctrineLayerCollisionWarning` on shadowing
- catch `(YAMLError, ValidationError, OSError)` and warn

They differ in exactly two structural ways:
1. Source: `self._org_dirs` (list, iterated) vs `self._project_dir` (single Path, guarded by `.exists()`).
2. Provenance tag: literal `"org"` vs `"project"`.

**Recommended consolidation**: one method, `_apply_overlay_layer(dirs: Sequence[Path], layer_name: str, *, built_in: dict[str, T])`. The "single project dir" case becomes `dirs=[self._project_dir]`. Removes ~50 lines of duplicated logic and makes a future "three-layer or N-layer" extension cheap.

**Why this matters**: the ADR `2026-05-16-1-doctrine-layer-merge-semantics.md` ratifies that org and project overlays use *identical* field-merge semantics. The code makes that identical-by-design intent invisible by writing the merge twice. Anyone modifying one half is one rebase away from forgetting the other.

### LD-2 — Five augmentation field test files

**Severity**: LOW
**Evidence**: `tests/doctrine/test_{tactic,styleguide,paradigm,procedure,agent_profile}_augmentation_fields.py`. Each is a 4-case test of the same `overrides`/`enhances` cross-field validator behaviour, just keyed by artifact type. Total: ~250 lines of test code that could be ~80 with a parametrized factory.

**Recommended consolidation**: one parametrized test in `tests/doctrine/test_augmentation_fields.py` with a fixture matrix `(model_class, sample_yaml, kind_name)`. This is a quick-win refactor.

### LD-3 — Charter freshness reads inside the charter_freshness module

**Severity**: MEDIUM (already surfaced as RISK-2 in mission-review)
**Evidence**: `src/specify_cli/charter_freshness/computer.py:100,103,280,281` — direct reads of `.kittify/charter/synthesis-manifest.yaml` and `.kittify/doctrine/graph.yaml` via `_safe_load_yaml(...)` and `Path.exists()`, bypassing `charter.compiler.ensure_charter_bundle_fresh`. This duplicates the read-and-validate logic the chokepoint already implements.

**Recommended consolidation**: the freshness module should consume a read-only API from `charter.compiler`. Not a single-line rename — but the boundary is wrong.

### LD-4 — Three runtime "preflight" modules and one "status" module overlap

**Severity**: LOW (architectural smell, not a code-correctness defect)
**Evidence**: `src/specify_cli/core/git_preflight.py` (pre-existing), `src/specify_cli/charter_preflight/runner.py` (new from WP03 — 461 lines), and `src/specify_cli/cli/commands/charter.py::status` all produce similar "deterministic JSON result of N checks" payloads. The result/check dataclass shapes are not formally unified.

**Recommended consolidation**: introduce a small `src/specify_cli/preflight/` shared base (a `Check` dataclass + a `PreflightResult[T]` envelope) and let the two domain-specific preflights (git, charter) compose from it. Forward-looking: any future "doctrine preflight", "auth preflight", etc. then follows the same shape.

### LD-5 — Charter-related package proliferation under `src/specify_cli/`

**Severity**: MEDIUM
**Evidence**: `ls -d src/specify_cli/charter*/` returns FOUR directories:
- `charter/` — the existing facade (consumes `src/charter/`)
- `charter_lint/` — decay-detection engine (graph-native checks)
- `charter_freshness/` — staleness / hash-comparison (new from WP02)
- `charter_preflight/` — pre-session readiness check (new from WP03)

These are all "the runtime side of charter", differing only in *when* they fire and *what* they assert. They share state (the freshness module), share output shape concerns (the preflight contract), and share entry-point wiring (all three plug into `cli/commands/charter.py`).

**Recommended consolidation**: a single `src/specify_cli/charter_runtime/` package with three submodules (`lint/`, `freshness/`, `preflight/`) makes the cohesion explicit. The current sibling layout reads like three concurrent missions each adding a new top-level package because the existing one was "owned" by the previous wave — which is exactly what happened.

---

## 3. Module-scope findings

### MS-1 — `src/specify_cli/cli/commands/charter.py` is 3,328 lines

**Severity**: HIGH
**Why it matters**: a single command-surface file owning 6+ subcommands (`status`, `sync`, `synthesize`, `lint`, `preflight`, `bundle`, `resynthesize`, plus several others) means every WP that touches a charter subcommand contends for the same file. Mission 01KSAF14 alone re-edited this file three times across separate lanes (WP01, WP02, WP03 wired their commands here). The merge-conflict risk is now reliably realised at each mission.

**Recommended split**: one file per subcommand under `src/specify_cli/cli/commands/charter/` (a package). The typer-app registration pattern (`app.command("lint")(charter_lint)`) supports this trivially.

### MS-2 — 67 subpackages under `src/specify_cli/`

**Severity**: MEDIUM
**Why it matters**: that's a *lot* of top-level packages for one application layer. Many are 1-3 files (`bulk_edit/`, `calibration/`, `compat/`, `encoding.py`, `frontmatter.py` etc.) and could be grouped. Conversely, related concerns (the four `charter*` directories above; potentially also `runtime/`, `kernel/`, `core/`) are scattered.

**Recommended treatment**: NOT a sweeping reorganization — that's too disruptive. Instead, a *moratorium* on adding new top-level `specify_cli/*/` packages until the existing layout is grouped logically. New runtime concerns should land in an existing parent or under `src/specify_cli/charter_runtime/`, `src/specify_cli/mission_runtime/`, etc.

### MS-3 — Three "preflight" modules with three different `Result` dataclass shapes

**Severity**: LOW (LD-4 covers this)

---

## 4. Mapping to existing engineering notes

The 10 findings in `docs/plans/engineering-notes/finding/2026-05-24-mission-01KSAF14-orchestration-findings.md` and the 1 reflection in `docs/plans/engineering-notes/reflections/2026-05-24-drg-profile-routing-missed-first-pass.md` are mostly *operator-side* observations. Where they have an architectural corollary:

| Mission finding | Architectural corollary |
|---|---|
| F-01 (bulk-edit gate schema undiscoverable) | The validator's allowed action vocabulary is defined inline in the validator code, not in a schema artifact a pack author can see. → Documentation surface gap; also touches issue #1163. |
| F-02 (lane workspaces don't inherit upstream commits) | The `agent action implement` command's worktree-creation step does not consume `lanes.json::dependencies`. → Architectural; would close a known orchestration footgun. |
| F-03 (squash-merge loses done transitions) | The squash-merge code path does not emit the post-merge done events on the target branch. → Architectural; small but real. |
| F-04 (retrospective auto-gen empty) | The generator's source heuristics do not mine `status.events.jsonl` for `--force` / `arbiter` transitions, nor compare baseline-vs-post pytest counts. → Algorithm gap. |
| F-05 (cutover surfaces unrelated test fragility) | NFR-003 ("zero regressions") is measured against a stale baseline. → Process; not architectural. |
| F-06 (ADR cross-refs cross-WP) | The lane ownership model has no `lane-cross-cutting` class for integrative work. → Architectural (workflow design). |
| F-07 (acceptance-matrix schema undiscoverable) | No template, no `init` command, no schema docs. → Small UX; partially addressed by #1163 (issue-matrix scaffolding). |
| F-08 (acceptance-matrix vs issue-matrix duplication) | Two artifacts, similar role, different schema/location. → **Logical duplication** (LD-X candidate); already filed as #1163. |
| F-09 (protected-branch guard friction) | Fixed in commit `64ddadc5f`. |
| F-10 (`linked_issues` field rejected) | `WPMetadata` is `extra="forbid"` and lacks a tracker-refs field. → Schema; small. |

The mission-review report's RISK-2 (chokepoint bypass) maps to **LD-3** above.

---

## 5. Open-issue triage — candidates for an intermediate remediation mission

These are small-to-medium open issues that match the "logical duplication / bounded-context / small refactor" theme of an intermediate mission. Listed in order of fit:

| Issue | Title | Effort | Why it fits |
|---|---|---|---|
| **#1298** | Pre-existing test failures (251 failures) | L | The headline. Already partially remediated (`64ddadc5f` closed 9). |
| **#1163** | `/spec-kitty.tasks` should scaffold `issue-matrix.md` when missions reference GitHub issues | S | Closes F-07 / F-08 / mission-review Gate-4 N/A. |
| **#1166** | `.kittify/doctrine/` is gitignored — synthesized doctrine artifacts cannot be shared across team | S | Adjacent governance smell. |
| **#1231** | Improve stale-WP indicator: incorporate `shell_pid` liveness | S | Small workflow polish. |
| **#1295** | CI: canonical-producer-lint flakes on cross-repo PR merge ref | S | Flake fix, unblocks CI signal. |
| **#1164** | Make terminus retrospective always-on; require explicit opt-out via charter clause | S | Maps to F-04 (empty auto-retro). |
| **(architectural, no issue yet)** | LD-1 — consolidate `_apply_org_overrides` / `_apply_project_overrides` | S | This review's primary code finding. |
| **(architectural, no issue yet)** | LD-5 — group `charter_*` packages under `charter_runtime/` (or land a moratorium policy) | M | Reduces merge contention for future charter work. |
| **(architectural, no issue yet)** | MS-1 — split `cli/commands/charter.py` into a per-subcommand package | M | Closes the largest single-file merge-contention risk. |

**Out of scope for an intermediate mission** (too large or different theme):
- The `Beads state` epic (#1168 + 10 children) — that's a 3.3.0 backend swap, separate concern.
- The schema-versioning launch-blocker cluster (#1198, #1200, #1203, #1281) — separate sub-epic.
- Doctrine import work (#1276-1280) — content authoring, not refactoring.

---

## 6. Recommended next-mission scope

**Mission name suggestion**: `test-stabilization-and-architectural-debt-pass`

**Single mission, three slices** (per the wave pattern that worked for 01KSAF14):

**Slice T — Test stabilization (closes #1298 and pieces of #1298 a/b/c/d):**
- T1: triage the 242 remaining failures by surface; produce a per-cluster mini-report.
- T2: fix the `tests/sync/test_events.py` `ModuleNotFoundError` cluster (likely 1-2 vendored-events import fixes).
- T3: fix `tests/test_dashboard/test_scanner.py` tolerance window.
- T4: fix `tests/tasks/test_move_task_git_validation_unit.py` commit-message contract drift.
- T5: file follow-up tickets for any subsystem-specific failures that need their own mission.

**Slice A — Architectural debt (closes LD-1, MS-1):**
- A1: consolidate `_apply_org_overrides` + `_apply_project_overrides` into `_apply_overlay_layer` (LD-1).
- A2: split `src/specify_cli/cli/commands/charter.py` into per-subcommand modules under `src/specify_cli/cli/commands/charter/` (MS-1).
- A3 (stretch): adopt `charter_runtime/` umbrella package and move `charter_lint`, `charter_freshness`, `charter_preflight` underneath (LD-5).

**Slice Q — Small quality fixes (closes #1163, #1295, F-04, F-10):**
- Q1: `/spec-kitty.tasks` scaffolds `issue-matrix.md` (#1163).
- Q2: CI: fix `canonical-producer-lint` cross-repo flake (#1295).
- Q3: retrospective auto-gen mines `--force`/`arbiter` events from status log (F-04).
- Q4: `WPMetadata` gains optional `tracker_refs: list[str]` field (F-10).

**Constraints to honour:**
- Stay below 8 work packages (last mission was 10 — felt heavy on review cycles).
- Slice A's A3 is *stretch* — drop if the WP count creeps.
- Slice T does NOT promise zero failures — it promises a clean per-cluster status and triage doc.

---

## 7. Out of scope for this review

- Performance review (no NFR gated benchmark was breached).
- Security pass (the mission review already did one; nothing new since `df7717303`).
- Full diff between baseline and HEAD for every line — covered by the per-WP reviews and the mission review.
- `Beads state` 3.3.0 work — separate epic.
- Constitution package architecture — not investigated in this pass.

---

End of review.
