---
work_package_id: WP06
title: Frontend Freddy reciprocal boundary
dependencies:
- WP02
requirement_refs:
- FR-004
- NFR-007
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drupal-dries-profile-01M28X69
base_commit: de33d2d59d949d66ac2f0db2b6d8ec1ee1d64efe
created_at: '2026-09-12T08:19:01.898355+00:00'
subtasks:
- T031
- T032
- T033
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/agent_profiles/frontend-freddy
create_intent: []
execution_mode: code_change
owned_files:
- packs/built-in/agent_profiles/frontend-freddy.agent.yaml
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Frontend Freddy reciprocal boundary

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`

## Objective

Amend one field of one pre-existing profile: `specialization.avoidance-boundary` in
`packs/built-in/agent_profiles/frontend-freddy.agent.yaml`.

This is the **only** change this mission makes to an artifact that already shipped. It is isolated in
its own work package for exactly that reason — a reviewer should be able to audit the entire
outside-the-mission blast radius in a single small diff (NFR-007).

## Context

- **Spec**: FR-004, NFR-007, SC-004, User Story 3
- **Data model**: [data-model.md](../data-model.md) E8, invariants I8.1–I8.3
- **Research**: R-006 — the verification/authorship distinction, and why it exists
- **Contract**: [contracts/profile-contract.md](../contracts/profile-contract.md) C-P6

### Why this package exists

The spec gave Dries both Drupal backend **and** Drupal-native theming. Freddy already claims
`html`, `css`, `javascript`, `typescript`. Twig templates and `Drupal.behaviors` therefore sit in
contested space, and an operator with a "frontend work on a Drupal site" task has two plausible
profiles and no way to choose.

FR-004 requires the answer be readable from **both** profiles. A one-sided declaration is how
boundaries rot: Dries says it defers to Freddy, Freddy says nothing, and the next person to read
Freddy alone has no idea Dries exists.

### Freddy's existing boundary — the voice to match

```yaml
  avoidance-boundary: >
    Server-side Node.js processes and HTTP handler authoring (deferred to Node Norris),
    database access and persistence logic, UX/UI design decisions (deferred to Designer
    Dagmar), backend API design and contract authoring, architectural decisions, managing
    other agents
```

Note the established pattern: *concern* (deferred to *Named Profile*). Your addition follows it. Do
not restructure the field, do not reorder the existing clauses, do not "improve" the prose. One
clause added, in the existing voice.

### ⚠️ Standing rule

Do **not** run `regenerate-graph` and do **not** edit any `*.graph.yaml`. WP07 owns those.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP06`.

---

### Subtask T031: Amend the avoidance boundary

**Purpose**: Give Freddy's reader the other half of the boundary.

**Steps**:

1. **Read Dries's boundary first.** Open
   `packs/built-in/agent_profiles/drupal-dries.agent.yaml` (WP02's output) and read
   `specialization.avoidance-boundary` verbatim. Your clause must be its mirror. Quote it in the WP
   notes — do not paraphrase from memory, because a paraphrase is how the two sides drift.
2. Add one clause to Freddy's `avoidance-boundary`, in the existing voice:

   > Drupal-native theming — Twig templates, `*.libraries.yml` declarations, `Drupal.behaviors`,
   > render arrays and preprocess functions (deferred to Drupal Dries)

3. Keep every existing clause intact and in order.

**Files**: `packs/built-in/agent_profiles/frontend-freddy.agent.yaml`

**Validation**:
- [ ] Drupal Dries named explicitly
- [ ] The named artifacts are specific (Twig, libraries, behaviors, render arrays, preprocess), not
      the vague "Drupal frontend"
- [ ] Existing clauses unchanged and in original order
- [ ] Matches Dries's side — verified by reading, not recalling

---

### Subtask T032: Carry the verification-versus-authorship distinction

**Purpose**: R-006. Without this, the two profiles contradict each other.

Dries's self-review protocol runs `npm run test`. A reader comparing the two profiles will notice that
Dries executes JavaScript tests while deferring JavaScript to Freddy, and will reasonably conclude one
of the profiles is wrong.

**Steps**:

1. Add a short qualifier so Freddy's boundary states the same distinction Dries's does: Dries
   **verifies** the Drupal-native theming JavaScript it authored; Freddy **authors** generic browser
   component work — framework components, accessibility compliance, bundle concerns.
2. Keep it to one sentence. This is a boundary declaration, not an essay.
3. Confirm the wording is consistent with Dries's. If the two differ in substance, stop — one of them
   is wrong, and reconciling them is this WP's job.

**Validation**:
- [ ] The distinction is stated, not implied
- [ ] Consistent with Dries's wording
- [ ] One sentence

---

### Subtask T033: Blast-radius and boundary audit

**Purpose**: NFR-007 and SC-004. Prove the reach and prove the result is usable.

**Steps**:

1. **Blast radius** — confirm only the boundary field changed:
   ```bash
   git diff packs/built-in/agent_profiles/frontend-freddy.agent.yaml
   ```
   Every changed line must be inside `avoidance-boundary`. Any other field touched is an NFR-007
   violation — revert it. Freddy's `roles`, `capabilities`, `applies_to_languages`,
   `routing-priority`, and self-review protocol are all out of scope.

2. **Ten-task boundary check (SC-004)** — assign each of these using only the two boundary
   declarations. Every one must resolve to exactly one profile, with no ties:

   | # | Task |
   |---|------|
   | 1 | Add a Twig template for a custom block |
   | 2 | Build a React component for a decoupled front end |
   | 3 | Add a `Drupal.behaviors` handler for an AJAX-loaded form |
   | 4 | Fix a WCAG contrast failure in a design system token |
   | 5 | Declare a new asset library in `*.libraries.yml` |
   | 6 | Reduce a webpack bundle below a performance budget |
   | 7 | Add a preprocess function to expose a field to a template |
   | 8 | Implement a responsive grid in plain CSS for a marketing site |
   | 9 | Convert a render array to use a custom theme hook |
   | 10 | Add keyboard navigation to a framework-based modal |

   Record each assignment and the clause that decided it. Expected shape: 1, 3, 5, 7, 9 → Dries;
   2, 4, 6, 8, 10 → Freddy. **If any task is ambiguous, the boundary text is not finished** — sharpen
   it and re-run. This is the actual deliverable of the audit, not a formality.

3. Confirm YAML still parses and Freddy still loads:
   ```bash
   uv run pytest tests/doctrine/agent_profiles/ -q
   ```

**Validation**:
- [ ] `git diff` confined to `avoidance-boundary`
- [ ] Ten tasks, ten unambiguous assignments, each with its deciding clause recorded
- [ ] Freddy still loads; no new skipped profile

---

## Definition of Done

- [ ] Exactly one file changed, exactly one field within it
- [ ] Drupal Dries named by name
- [ ] Verification/authorship distinction present and consistent with Dries's side
- [ ] Ten-task audit complete and recorded, with no ties
- [ ] `uv run pytest tests/doctrine/agent_profiles/ -q` passes
- [ ] No `*.graph.yaml` touched

## Risks

| Risk | Mitigation |
|------|-----------|
| Boy-scouting Freddy while in the file | NFR-007 bounds this to one field. Tidying elsewhere breaks the audit guarantee |
| Paraphrasing Dries's boundary from memory | T031 requires reading and quoting it. Paraphrase is how the halves drift apart |
| A vague "Drupal frontend" clause | Names the artifacts: Twig, libraries, behaviors, render arrays, preprocess |
| Skipping the ten-task check as ceremony | It is the only test of whether the boundary actually works; ties mean unfinished text |

## Reviewer Guidance

Start with `git diff --stat` — one file, few lines. Then read the diff and confirm every changed line
is inside `avoidance-boundary`. Read both profiles' boundaries side by side and try to assign task 3
("`Drupal.behaviors` handler") and task 10 ("keyboard navigation in a framework modal") yourself; if
either feels ambiguous, the text needs another pass. Check the WP notes contain the ten-task table
with its deciding clauses — an empty or hand-waved audit is a rejection.
