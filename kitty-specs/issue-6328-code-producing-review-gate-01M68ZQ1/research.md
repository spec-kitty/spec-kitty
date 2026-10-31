# Research: #6328 — enforce the implementation-commit review prerequisite from `code_producing`

Grounding performed on `origin/main` at `dfe9efb0e8` in the mission clone
`/home/exedev/work/sk-6328`, before any planning artifact was written.

## Decision 1 — the defect reproduces, and at exactly one site

The review-readiness pre-flight `_validate_ready_for_review`
(`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`) gates its
entire Check 2 worktree-state prerequisite on a family-name literal:

```python
    # Check 2: For software-dev missions, check worktree for implementation commits
    if mission_type == MISSION_TYPE_SOFTWARE_DEV:
        worktree_result = _validate_worktree_state(...)
```

`MISSION_TYPE_SOFTWARE_DEV` is the string constant from
`src/specify_cli/core/constants.py`. Check 2 is where
`_check_implementation_commit_present` (line 614) lives, which is the
implementation-commit prerequisite the issue names.

Search for the same shape elsewhere in the review-readiness path:
`rg -n "MISSION_TYPE_SOFTWARE_DEV" src/` returns five `src/` hits in total —
`core/constants.py` (the definition), `core/worktree.py` (default mission
template lookup, unrelated), `cli/commands/agent/tasks_parsing_validation.py:1038`
(this site), and two in `runtime/next/*` (`runtime_bridge_io._runtime_template_key`
tier ordering, `runtime_bridge` step-graph guard). Neither runtime site is the
review-readiness prerequisite, and both belong to the `#6315` follow-on work, not
to this issue. **One enforcement site, as the issue states.**

Corroboration that this is deliberate and known:
`tests/integration/test_coord_loop_depgraph.py:333` carries the comment "the
worktree check is gated on MISSION_TYPE_SOFTWARE_DEV", and the `#6315` changelog
entry in `docs/changelog/CHANGELOG.md:185` ends with "Template precedence and the
code-producing review gate (#6328, which needs the #6327 capability) are out of
scope."

## Decision 2 — `code_producing` does not exist yet; the #6327 prerequisite is unlanded

- `rg -n "code_producing" --type py` → **0 hits**.
- `git log --oneline -S "code_producing" --all` → one hit, `bb27fb9614` ("chore(capability-contract): mission dossier [Refs #6315]"), which is a *dossier*
  commit, i.e. prose about the plan, not the capability.
- `gh issue view 6327` → **OPEN**, no assignee, no PR; `gh pr list --search "6327 OR code_producing"` → empty; `git ls-remote --heads origin` → no
  `6327`/`code_producing` branch.

`#6328` says "Depends on #6327 … This work starts only after that property is
provided". The property is not provided and nobody is providing it. **Decision:
this mission lands the minimal `#6327` prerequisite as an enabling part of the
same PR**, because the consumer literally cannot be written without it and the
alternative is a shipped capability that nothing reads. The prerequisite is kept
to exactly the surface `#6327` describes — field on the DTO, built-in defaults,
layered declaration, resolver, resolved facet, public accessor — and is modelled
on the `requires_substantive_spec` capability that `#6315` already shipped, so it
introduces no new pattern.

## Decision 3 — the #6715/#5939 evidence gates are already in place and are NOT the same surface

Grounded by reading the code and `docs/changelog/CHANGELOG.md` lines 110, 200-201:

| Gate | Where | When it fires | Semantics |
| --- | --- | --- | --- |
| for_review commit gate (#6715) | `src/specify_cli/lanes/for_review_gate.py` | at the `in_progress→for_review` transition, on every topology | surface-neutral; `GateDecision`; fail-closed on an unreadable range |
| evidence axis (#6715) | `consolidation.wp_evidence` | at consolidate | shared `status_only_excluded_prefixes` exclusion list |
| single_branch move/consolidate gates (#5939) | `move-task` / `consolidate` backstop | single_branch topology | `SINGLE_BRANCH_*` error codes |
| **review-readiness pre-flight (#6328)** | `_validate_ready_for_review` Check 2 | **before** the transition, asks "is this WP ready to be reviewed at all" | worktree currency + uncommitted changes + `_check_implementation_commit_present` + kitty-specs contamination |

They are distinct layers, not duplicates: the pre-flight runs first and can block
before the transition gate is ever consulted, and the #6715 gate re-decides on
commit state at the transition. **This mission changes which mission types the
pre-flight applies to; it does not touch the pre-flight's own checks, and it does
not touch any of the three `#6715`/`#5939` surfaces.** The PR records that as a
ratchet requirement (FR-008 / SC-004) and verifies it with an empty-diff assert.

## Decision 4 — how the consumer resolves the capability, and why not a new parameter

`_validate_ready_for_review` takes its `tasks`-resident collaborators as injected
callables precisely so that the existing monkeypatch contract on the `tasks`
namespace keeps applying (see its docstring). Every test in
`tests/agent/`, `tests/tasks/`, `tests/review/` and
`tests/integration/test_coord_loop_depgraph.py` constructs it by keyword. Adding a
**required** parameter would be a churn bomb across the suite.

So the capability resolves *inside* the function from `main_repo_root` and
`mission_type`, through the public seam:

```python
from charter.activation.api import code_producing_for
```

which is exactly the shape `mission_check_prerequisites._requires_substantive_spec`
already uses (`charter.activation.api.requires_substantive_spec_for`, with an
explicit comment that "the boundary gate forbids a new external reach into
`charter.activation` internals"). The narrow-mypy `follow_imports = "skip"` hazard
documented there applies identically, so the same bool-annotated local bind is
used.

## Decision 5 — fail-open vs fail-closed on resolution failure, and the built-in defaults

`code_producing_for` mirrors `requires_substantive_spec_for`: resolve, and on any
exception fall back to the built-in default map. The built-in map is

```
software-dev: True
research:     False
documentation: False
plan:         False
```

which means a resolution failure for `software-dev` still yields `True` — the
pre-existing gate keeps firing, so the *user-visible* behaviour of the built-in
families cannot regress through an unreadable charter config. An unknown or
underspecified custom type falls back to `False`, matching `#6327`'s "the default
when undeclared is conservative (`false`), so no existing custom type silently
gains code-rigour gates."

Note this is *fail-open for the gate*, not fail-open for the check: the check
itself still fails closed once it is applied. The alternative (default `True`
everywhere) would have applied implementation-commit requirements to
documentation and research missions overnight, which the issue forbids.

## Decision 6 — the resolved facet must stay lazy

`resolve_mission_type_context` is on the FSM hot path and `#6315` deliberately
deferred `requires_substantive_spec` behind a thunk so the hot path keeps its
single layered-roster read (the docstring names the NFR-001 100 ms budget). The
same treatment applies: `_code_producing_thunk` + `@cached_property`. A caller
that reads only `action_sequence` must trigger no extra roster/disk read; that is
assertable by counting `resolve_layered_mission_types` calls.

## Evidence gathered

- `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` — enforcement
  site (line 1038), Check 2 body (`_validate_worktree_state`, line 834), the
  implementation-commit check (line 614).
- `src/charter/offering/missions/models.py:239` — `MissionType` (`frozen`,
  `extra="forbid"`), the `requires_substantive_spec: bool | None` precedent.
- `src/charter/activation/mission_type_profiles.py` — `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`
  (line 391), `ResolvedMissionType` facets (line 433+), the construction site
  (line 700+), `_resolve_requires_substantive_spec` (line 1020),
  `requires_substantive_spec_for` (line 1042).
- `src/charter/activation/api.py:53,301` — the public re-export seam.
- `src/specify_cli/cli/commands/agent/mission_check_prerequisites.py:432` — the
  consumer-side idiom to copy.
- `src/specify_cli/lanes/for_review_gate.py` — the `#6715` gate (read, not
  modified).
- `docs/changelog/CHANGELOG.md:110,185,200` — the landed capability work and the
  explicit deferral of this consumer.
- `tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py:474-560`
  — the fixture pattern for a custom mission type declaring a capability.
- `tests/integration/test_coord_loop_depgraph.py:333` — the research-type bypass
  test that must keep passing.

## Open questions for specify/plan

1. Should the capability be injectable into `_validate_ready_for_review` as an
   *optional* keyword for tests, or resolved only internally? (Leaning: resolved
   internally only — an optional injection point is a second seam nobody needs,
   and the real resolver is testable through a real layered pack fixture, which
   is the stronger proof.)
2. Do any of the three other built-ins actually *want* `code_producing` to be
   true later? Out of scope here; the map is the single place to change.
3. Does the warehouse of `documentation`/`plan` missions rely on the worktree
   checks being skipped, or only on the implementation-commit one? (Evidence:
   they currently skip the whole Check 2 block. The issue only asks about the
   implementation-commit prerequisite, so keeping the whole block behind the one
   capability preserves today's behaviour exactly — the smallest correct change.)

## Alternatives considered (Phase 0 extension)

**A. Stop at grounding and report the missing `#6327` dependency.** Rejected. The
consumer is one line and the prerequisite is ~60 lines modelled on a capability
that already shipped; stopping would leave `#6328` unrunnable until someone picks
up an unclaimed issue, and the batch's single-issue-per-agent constraint means no
one else is picking it up today.

**B. Add a required `code_producing` parameter to `_validate_ready_for_review`.**
Rejected: its injected collaborators are a live monkeypatch contract across
`tests/agent/`, `tests/tasks/`, `tests/review/` and
`tests/integration/test_coord_loop_depgraph.py`. Resolution inside the function
keeps every existing call site compiling (C-003).

**C. Add an *optional* injectable for tests.** Rejected: a second seam nobody
needs. The real resolver is testable through a real layered org-pack fixture,
which proves more than an injected stub.

**D. Key the gate on a set of "code" type names in `core/constants.py`.** Rejected
outright: that is the second source of truth `#6327` exists to delete, and it would
still leave custom types ungated.

**E. Re-key every `software-dev` literal in `src/` at once.** Rejected: the runtime
template-tier ordering (`runtime_bridge_io`) and the step-graph guard
(`runtime_bridge`) are different questions with their own `#6315` follow-ups; the
issue names one site ("site 3") and DIRECTIVE_024 (locality of change) agrees.

**F. Gate only `_check_implementation_commit_present` and keep the rest of Check 2
software-dev-only.** Rejected: the non-code types currently skip the whole Check 2
block, so this would newly apply currency / uncommitted-changes / kitty-specs
contamination checks to research and documentation missions — a behaviour change
the issue does not ask for and that could break their review flow. Keying the whole
block on the one capability preserves today's verdicts exactly (SC-003).
