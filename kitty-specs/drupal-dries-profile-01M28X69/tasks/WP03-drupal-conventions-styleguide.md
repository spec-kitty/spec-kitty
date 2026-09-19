---
work_package_id: WP03
title: Drupal conventions styleguide
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-008
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drupal-dries-profile-01M28X69
base_commit: 8effda09677de85951aa7f6e42c22bda385b52b2
created_at: '2026-09-11T20:37:16.196455+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/styleguides/drupal-conventions
create_intent:
- packs/built-in/styleguides/drupal-conventions.styleguide.yaml
execution_mode: code_change
owned_files:
- packs/built-in/styleguides/drupal-conventions.styleguide.yaml
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Drupal conventions styleguide

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`

## Objective

Author `packs/built-in/styleguides/drupal-conventions.styleguide.yaml` — the "how do I write this?"
half of the Drupal guidance. Positive patterns plus the eight convention-shaped anti-patterns, each a
`bad_example`/`good_example` pair. Target 150–200 lines.

## Context

- **Spec**: FR-006, FR-008, SC-003
- **Data model**: [data-model.md](../data-model.md) E4, invariants I4.1–I4.3
- **Research**: R-004 explains why the anti-patterns live here and not in the `anti_pattern` graph
  channel — that channel has 13 label-only nodes, no bodies, and holds architectural archetypes
- **Contract**: [contracts/styleguide-toolguide-contract.md](../contracts/styleguide-toolguide-contract.md) C-S1, C-S2, C-S3

### Read before writing

```bash
packs/built-in/styleguides/python-conventions.styleguide.yaml   # 170 lines — the exact shape
```

Note how it handles anti-patterns: not a separate section, just `patterns` entries whose `bad_example`
is the mistake and whose `good_example` is the fix. Mirror that.

### Division of labour with WP04

The 14 source anti-patterns split 8/6. **Yours are 1, 2, 4, 8, 9, 12, 13, 14** (convention-shaped).
WP04 takes 3, 6, 7, 10, 11 (security/performance-shaped). Number 5 — config versus state — is yours;
it is a modelling convention, not a security rule.

C-S3 requires the split be a **real boundary**: no pattern name may appear in both files. Yours answers
"how do I write this?"; WP04's answers "how do I keep it safe and fast?".

### ⚠️ Standing rule

Do **not** run `regenerate-graph` and do **not** edit any `*.graph.yaml`. Those belong to WP07.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP03`.

---

### Subtask T014: Header and principles

**Steps**:

```yaml
schema_version: "1.0"
id: drupal-conventions
title: Drupal Conventions Styleguide
scope: code
applies_to_languages:
  - php
  - twig

principles:
  - "Dependency injection over static calls: services arrive through the constructor; `\\Drupal::` is acceptable only inside `hook_` functions in `.module` files."
  - "Entity API over direct queries: use entity storage and Entity Query rather than hand-written SQL."
  # ... 6-8 more
```

Each principle is one line, imperative, and states the rule plus its boundary. Draw them from the
source guide's *Code Style and Standards* and *Drupal Development Patterns* sections.

**Validation**:
- [ ] 8–10 principles, each one line
- [ ] Every principle traces to a named source section

---

### Subtask T015: Service and entity patterns

**Purpose**: The two patterns that carry the most weight in real Drupal review.

**Steps**: Author `patterns` entries with `name`, `description`, `bad_example`, `good_example`:

1. **Constructor Dependency Injection** — bad: `\Drupal::entityTypeManager()` inside a controller;
   good: constructor injection with a `create()` factory reading from the container.
2. **Entity Query With Access Check** — bad: `db_query('SELECT nid FROM {node}...')`; good:
   `$this->entityTypeManager->getStorage('node')->getQuery()->accessCheck(TRUE)->execute()`.
   Mention that `accessCheck(TRUE)` is mandatory on 10.x/11.x (error from 10.0.0) — WP04 owns the full treatment, so
   cross-reference rather than duplicate.
3. **Config Versus State** (source anti-pattern 5) — bad: `\Drupal::state()->set('site_tagline', ...)`;
   good: `configFactory()->getEditable()`. Config is structured and exportable; state is ephemeral.

**Files**: `packs/built-in/styleguides/drupal-conventions.styleguide.yaml`

**Validation**:
- [ ] Every `bad_example` paired with a `good_example` (I4.2)
- [ ] PHP examples are syntactically valid
- [ ] The `accessCheck` entry cross-references WP04 rather than duplicating it

---

### Subtask T016: Plugin, form, routing, and hook patterns

**Steps**: Continue the `patterns` list:

1. **Plugin With Annotation** — a Block plugin with its annotation block and injected dependencies.
2. **Settings Form On ConfigFormBase** — `getEditableConfigNames()`, `buildForm`, `submitForm`; bad
   example writes config without declaring the editable name.
3. **Route And Controller** — `*.routing.yml` entry with `_permission` requirement; bad example
   hardcodes a path or omits access requirements.
4. **Thin Module File** (source anti-pattern 14) — bad: 200 lines of business logic in `.module`;
   good: a hook that delegates to an injected service.
5. **Focused Form Alter** (source anti-pattern 4) — bad: a monolithic `hook_form_alter()` switch;
   good: delegation to a service with focused methods.
6. **Views Data With Table Aliases** (source anti-pattern 9) — bad: ambiguous column names; good:
   explicit aliases.

**Validation**:
- [ ] Six patterns, each with paired examples
- [ ] Annotation syntax correct for Drupal 10/11

---

### Subtask T017: Drupal-native theming patterns

**Purpose**: FR-003. This is the territory the FR-004 boundary assigns to Dries, so the guidance has
to actually exist.

**Steps**:

1. **Twig Auto-Escaping** (source anti-pattern 3 is WP04's; here cover the *positive* practice) —
   rely on auto-escaping; for intentional HTML use `#type => 'processed_text'` or `check_markup()`.
   Cross-reference WP04 for the `|raw` prohibition.
2. **Library Declaration** — `*.libraries.yml` with dependencies, attached via `#attached`; bad
   example inlines a `<script>` tag in a template.
3. **Drupal Behaviors** — `Drupal.behaviors.myModule` with `once()`; bad example uses a bare
   `document.ready` that re-binds on AJAX.
4. **Preprocess Function** — `template_preprocess_node()` adding variables; bad example computes
   values inside the Twig template.
5. **Render Array Over Markup** — a structured render array; bad example concatenates an HTML string.

**Validation**:
- [ ] Five theming patterns
- [ ] `once()` usage is current for Drupal 10/11 (the old `.once()` jQuery form is deprecated)
- [ ] No overlap with WP04's sanitization entries

---

### Subtask T018: Convention-shaped anti-patterns

**Purpose**: FR-008, SC-003. Your eight of the fourteen.

**Steps**: Confirm each is represented — several arrive naturally as the `bad_example` of a pattern
above, which is the intended shape. Add explicit entries for any not yet covered:

| # | Anti-pattern | Likely home |
|---|---|---|
| 1 | `\Drupal::` static calls in services/controllers/plugins | T015 pattern 1 |
| 2 | Direct DB queries where Entity Query suffices | T015 pattern 2 |
| 4 | Monolithic `hook_form_alter()` | T016 pattern 5 |
| 5 | Config stored in state | T015 pattern 3 |
| 8 | Hardcoded entity IDs, user IDs, paths | needs its own entry |
| 9 | `hook_views_data()` without table aliases | T016 pattern 6 |
| 12 | Deprecated procedural functions (`node_load()`) | needs its own entry |
| 13 | Global `$_GET` / `$_POST` / `$_SERVER` | needs its own entry |
| 14 | Business logic in `.module` files | T016 pattern 4 |

For 8, 12, 13 write dedicated entries. Number 12 should show `node_load()` versus
`entityTypeManager()->getStorage('node')->load()`; 13 should show `$_GET['id']` versus the injected
Symfony `Request` object.

**Validation**:
- [ ] All eight represented, each with paired examples
- [ ] Record in the WP notes which pattern carries which number — WP08 audits 14 of 14 and needs the map

---

### Subtask T019: Tooling, references, and size audit

**Steps**:

1. `tooling`: `formatter`, `linter` (`phpcs --standard=Drupal,DrupalPractice`), `analyzer`
   (`phpstan` / `drupal-check`). Name tools, not thresholds (NFR-006).
2. `references`: credit amazee.io `drupal-agents-md` (Vanilla variant) (FR-010) and link the official
   Drupal coding standards.
3. `wc -l` → 150–200. Over? Move theming to its own section or tighten examples — do not spill into
   WP04's file, which you do not own.
4. Validate YAML parses.

**Validation**:
- [ ] 150–200 lines
- [ ] Provenance present
- [ ] Parses as YAML
- [ ] No threshold asserted

---

## Definition of Done

- [ ] One new file, nothing else touched
- [ ] 150–200 lines; parses as YAML
- [ ] 8–10 principles; ~14 patterns with paired bad/good examples
- [ ] All eight assigned anti-patterns represented, with a number-to-pattern map in the WP notes
- [ ] No pattern name duplicates one planned for WP04 (C-S3)
- [ ] Provenance credited; no invented threshold
- [ ] `uv run pytest tests/doctrine/styleguides/ -q` — the presence assertion for this file passes
- [ ] No `*.graph.yaml` touched

## Risks

| Risk | Mitigation |
|------|-----------|
| Overlap with WP04 | The 8/6 split is fixed above. Cross-reference; never duplicate |
| PHP examples that do not compile | Examples are the product here — a wrong one teaches the wrong thing |
| Drifting past 200 lines | Examples are terse by design in `python-conventions`; match that density |
| Anti-pattern silently dropped | Record the number-to-pattern map; WP08 audits against it |

## Reviewer Guidance

Check every `bad_example` has a `good_example` — an unpaired bad example is a complaint, not guidance.
Verify the eight assigned anti-patterns are each locatable, using the WP notes map. Spot-check three
PHP examples for syntax and for Drupal 10/11 currency, especially `once()` in the behaviors entry.
Confirm no pattern name appears in both this file and WP04's.
