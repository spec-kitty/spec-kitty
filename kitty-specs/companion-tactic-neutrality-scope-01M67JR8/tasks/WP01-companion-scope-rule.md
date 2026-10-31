---
work_package_id: WP01
title: A companion tactic's scope is the project's stack
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6724-companion-tactic-neutrality-scope
merge_target_branch: issue-6724-companion-tactic-neutrality-scope
branch_strategy: Planning artifacts for this mission were generated on issue-6724-companion-tactic-neutrality-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6724-companion-tactic-neutrality-scope unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core fix
history:
- at: '2026-10-30T23:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent:
- tests/charter/synthesizer/test_companion_tactic_neutrality_6724.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/write_pipeline.py
- src/charter/activation/synthesizer/interview_mapping.py
- tests/charter/synthesizer/test_companion_tactic_neutrality_6724.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – A companion tactic's scope is the project's stack

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Make the neutrality gate read a companion tactic's language scope from the
project instead of from a slug that cannot carry one, without weakening the gate
where its contract points (an unconfigured project) and without touching the
banned-term or allowlist files.

## The defect in one paragraph

`write_pipeline._is_generic_scoped` decides *whether to lint* an artifact by
splitting its slug on hyphens and asking whether any component names an observed
or declared language. A companion tactic's slug is machine-derived from the
directive it applies — `how-we-apply-<directive-id>` — so no component ever names
a language, the predicate falls through to "unknown ⇒ generic", and the gate
refuses the companion for naming the project's own test runner. See spec.md
§Context and plan.md §Phase 1 for the reproduction and the rule.

## Subtasks

### T001 — Red-first CLI proof (FR-006, SC-001)

Create `tests/charter/synthesizer/test_companion_tactic_neutrality_6724.py`.
Drive the *real* command:

```python
from specify_cli.cli.commands.charter import app
runner = CliRunner()
result = runner.invoke(app, ["synthesize", "--json"], catch_exceptions=False)
```

Build the fixture the way `tests/charter/synthesizer/test_collision_refusal_6510.py`
does (`git init`, `answers.yaml`, `generate --from-interview`, hand-written
generated artifacts, `charter_cwd_isolation`, `seed_activation_ledger`), plus:

- `pyproject.toml` and a source file so the evidence observes Python;
- `language_scope: [Python]` in `answers.yaml`;
- `activated_directives: ["003-decision-documentation-requirement"]` in the
  activation ledger — without it `resolve_sections()` emits no companion target
  and the gate never sees one (this is the #2577 behaviour, not a bug);
- `.kittify/charter/generated/tactics/how-we-apply-directive-003.tactic.yaml`
  whose step description contains `Run pytest -q before opening the pull request.`;
- the other targets the interview demands (`project-intent-directive`,
  `risk-appetite-directive`, `testing-philosophy-tactic`, `testing-style-guide`,
  `python-style-guide`).

Assert: exit 0, `result == success`, and `written_artifacts` contains
`how-we-apply-directive-003`.

**On the planning base this test MUST fail** with
`NeutralityGateViolation ... tactic:how-we-apply-directive-003 ... 'pytest'`.
Commit that red proof before changing the rule.

### T002 — Unit positive/negative controls (FR-001, FR-004, FR-005, SC-002)

In the same module, from one shared fixture builder (the non-vacuity tactic's
same-fixture rule):

- `_is_generic_scoped(kind="tactic", slug="how-we-apply-directive-003", evidence=<python bundle>, source_section="selected_directives")` is `False`.
- The same call with `evidence=None` and `declared=()` is `True` — this is the
  unconfigured-project half; it must keep refusing.
- `slug="testing-philosophy"` and `slug="java-style-guide"` stay `True` in a
  Python project even when `source_section` is a non-companion section.
- A CLI case on a project with no declared language and no detectable sources:
  exit 1, `NeutralityGateViolation` in the `--json` warnings, and the staging
  directory named in the error still exists.

### T003 — Companion section label to its owner (FR-002, C-003)

`interview_mapping` owns the expansion that produces companion tactics
(`_append_selected_directives`, literal `"selected_directives"`). Export that
literal as a named constant from `interview_mapping`, use it at the existing
write site, and import it in `write_pipeline` — do not restate the string. Add one
assertion in the new test module that the gate's predicate agrees with the
constant's owner (import it, do not re-spell it).

Behaviour must not change at this step; the T001/T002 tests stay red.

### T004 — Narrow the rule (FR-001, FR-003)

In `_is_generic_scoped`:

```python
def _is_generic_scoped(kind, slug, evidence, declared=(), *, source_section=None):
    scope = set(expand_language_families((*_observed_languages(evidence), *declared)))
    if not scope:
        return True                      # unknown scope ⇒ generic (unchanged)
    if _is_companion_tactic(kind, source_section):
        return False                     # the artifact's scope is the project's stack
    return scope.isdisjoint(slug.split("-"))
```

- `_is_companion_tactic(kind, source_section)` is `kind == "tactic" and source_section == COMPANION_SECTION`.
- `_run_neutrality_gate` passes `source_section=prov.source_section` at its one
  call site; nothing else changes.
- Decide and record why the exemption is kind-scoped as well as section-scoped
  (a `styleguide` must never reach it) in the docstring, not in a comment.

Do **not** edit `banned_terms.yaml`, `language_scoped_allowlist.yaml`, or add a
term→language map (C-001).

### T005 — Blast radius and quality gates

Run, and record the counts:

```bash
uv run pytest tests/charter/synthesizer/test_companion_tactic_neutrality_6724.py \
  tests/charter/synthesizer/test_write_pipeline.py \
  tests/charter/synthesizer/test_multi_language_evidence.py \
  tests/charter/synthesizer/test_interview_mapping.py \
  tests/charter/test_neutrality_lint.py tests/charter/test_phase3_integration.py -q
uv run ruff check src/charter/activation/synthesizer/write_pipeline.py src/charter/activation/synthesizer/interview_mapping.py
```

No full heavy-suite run (`NO_FULL_HEAVY_SUITES_IN_MISSION`). If a gate is red for
a reason you cannot attribute to this diff, reproduce on pristine `origin/main`
in a clean worktree and cite the existing issue (#6798/#6801/#6816 family) in the
PR's `## Deferred`.

## Definition of Done

- The red proof exists as a commit that precedes the rule change.
- Both halves of the compound fix are proven: the companion promotes in a
  known-scope project, and the same text still refuses with no scope known.
- `git diff` shows no change to the banned-term list or the language allowlist.
- Tests and `ruff` recorded in the WP notes and the PR body.
