---
work_package_id: WP04
title: Drupal security and performance styleguide
dependencies:
- WP01
requirement_refs:
- FR-006
- NFR-006
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drupal-dries-profile-01M28X69
base_commit: e7b1ce5e2a736555595cf88bbe5250ee29f83fee
created_at: '2026-09-11T20:38:49.231673+00:00'
subtasks:
- T020
- T021
- T022
- T023
- T024
- T025
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/styleguides/drupal-security-performance
create_intent:
- packs/built-in/styleguides/drupal-security-performance.styleguide.yaml
execution_mode: code_change
owned_files:
- packs/built-in/styleguides/drupal-security-performance.styleguide.yaml
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Drupal security and performance styleguide

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`

## Objective

Author `packs/built-in/styleguides/drupal-security-performance.styleguide.yaml` — the "how do I keep
it safe and fast?" half. Target 150–200 lines.

## Context

- **Spec**: FR-006, NFR-006
- **Data model**: [data-model.md](../data-model.md) E5, invariants I5.1–I5.2
- **Contract**: [contracts/styleguide-toolguide-contract.md](../contracts/styleguide-toolguide-contract.md) C-S2, C-S3, C-S8

This file exists because the operator chose a split over one 400-line guide. That decision only pays
off if the boundary is real: **C-S3 requires no pattern name appear in both files**. If you find
yourself writing a general coding convention, it belongs in WP03.

### Your six anti-patterns

**3, 6, 7, 10, 11** from the source's "Never Do This" list — plus **2's security dimension** only as a
cross-reference (WP03 owns the Entity Query pattern itself).

| # | Anti-pattern |
|---|---|
| 3 | `\|raw` in Twig |
| 6 | `#markup` with unsanitized user input |
| 7 | Entity queries without `accessCheck(TRUE)` |
| 10 | Ignored cacheability metadata |
| 11 | `settings.php` committed with credentials |

### Read before writing

```bash
packs/built-in/styleguides/python-conventions.styleguide.yaml   # the shape
```

Source sections: *Security & Performance Guidelines* (line 611+), *Caching Strategies*,
*Server Optimization*, and the numbered anti-patterns.

### ⚠️ Standing rule

Do **not** run `regenerate-graph` and do **not** edit any `*.graph.yaml`. WP07 owns those.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP04`.

---

### Subtask T020: Header and principles

**Steps**:

```yaml
schema_version: "1.0"
id: drupal-security-performance
title: Drupal Security and Performance Styleguide
scope: code
applies_to_languages:
  - php
  - twig

principles:
  - "Escape by default: rely on Twig auto-escaping; `|raw` is a deliberate, justified exception, never a convenience."
  - "Access-check every entity query: implicit access checking was deprecated in Drupal 9.2.0 and throws an error from Drupal 10.0.0 — on the 10.x/11.x baseline `accessCheck()` is mandatory."
  - "Cacheability is not optional: every render array that depends on data declares its tags, contexts, and max-age."
  # ... 5-7 more
```

**Validation**:
- [ ] 8–10 principles
- [ ] Version-sensitive claims carry their version (I5.1)

---

### Subtask T021: Sanitization patterns

**Purpose**: Anti-patterns 3 and 6 — the two that turn user input into cross-site scripting.

**Steps**:

1. **Twig Output Escaping** — bad: `{{ user_input|raw }}`; good: `{{ user_input }}` relying on
   auto-escaping, with `#type => 'processed_text'` or `check_markup()` for intentional HTML. State
   *why*: `|raw` disables the protection Drupal gives you for free.
2. **Plain Text Over Markup** — bad: `['#markup' => $user_supplied]`; good:
   `['#plain_text' => $user_supplied]`, or `Html::escape()` when markup is genuinely needed.

**Validation**:
- [ ] Both entries carry paired examples
- [ ] Each explains the consequence, not just the rule

---

### Subtask T022: Access checking

**Purpose**: Anti-pattern 7, and the clearest version-sensitive claim in the whole mission.

**Steps**:

1. **Entity Query Access Check** — bad: `->getQuery()->condition(...)->execute()`; good: the same with
   `->accessCheck(TRUE)`.
2. State the version facts precisely, and note that the upstream AGENTS.md gets this WRONG at its
   line 701 — do not copy it. Per change record https://www.drupal.org/node/3201242 and core's own
   deprecation message: implicit access checking was **deprecated in Drupal 9.2.0** and **throws an
   error from Drupal 10.0.0**. On this profile's 10.x/11.x baseline an unchecked entity query is
   **already a fatal error**, not a warning, and nothing here is deferred to Drupal 12. C-S8
   spot-checks this claim against official Drupal documentation, so verify, do not transcribe.
3. Note the deliberate-bypass case: `accessCheck(FALSE)` is legitimate for genuinely internal queries
   and must be explicit and commented — never the result of forgetting.
4. Cross-reference WP03's Entity Query pattern rather than restating it.

**Validation**:
- [ ] Version claims match C-S8 exactly
- [ ] The legitimate `accessCheck(FALSE)` case is covered, not just prohibited
- [ ] Cross-reference, no duplication

---

### Subtask T023: Cacheability metadata

**Purpose**: Anti-pattern 10 — the performance bug that presents as a correctness bug (stale content).

**Steps**:

1. **Render Array Cacheability** — bad: a render array built from entity data with no `#cache`; good:
   `#cache` with `tags`, `contexts`, and `max-age`.
2. **Cache Contexts For Personalized Output** — bad: user-specific content cached without a user
   context, leaking one user's content to another; good: `contexts: ['user']`. This is the case where
   a cache mistake becomes a security incident — say so.
3. **Cache Tag Invalidation** — invalidating on entity save so content does not go stale.
4. Add a short caching-strategy note from the source's *Caching Strategies* section.

**Validation**:
- [ ] Three patterns with paired examples
- [ ] The personalization-leak case is explicitly called out

---

### Subtask T024: Query discipline and credential hygiene

**Purpose**: Anti-pattern 11 plus the performance practices.

**Steps**:

1. **Credentials Out Of Version Control** — bad: `settings.php` with a live database password; good:
   environment variables or `settings.local.php` excluded via `.gitignore`. Note that a committed
   credential is compromised even after removal — history retains it.
2. **Query Efficiency** — avoid N+1 entity loads; use `loadMultiple()`; add range limits. Draw from
   *Performance Best Practices*.
3. **Batch And Queue For Long Operations** — long-running work belongs in Batch or Queue API, not a
   request cycle that times out.

**Validation**:
- [ ] Three patterns with paired examples
- [ ] The credential entry states that history retention makes removal insufficient

---

### Subtask T025: Disjointness check and audit

**Steps**:

1. Extract pattern names from both files and prove the sets are disjoint:
   ```bash
   uv run python - <<'PY'
   import yaml, pathlib
   a = yaml.safe_load(pathlib.Path("packs/built-in/styleguides/drupal-conventions.styleguide.yaml").read_text())
   b = yaml.safe_load(pathlib.Path("packs/built-in/styleguides/drupal-security-performance.styleguide.yaml").read_text())
   na = {p["name"] for p in a.get("patterns", [])}
   nb = {p["name"] for p in b.get("patterns", [])}
   print("overlap:", na & nb)
   PY
   ```
   Overlap must be empty (C-S3). If WP03 has not landed yet, run this at integration and record it.
2. `tooling` and `references`: credit amazee.io `drupal-agents-md` (FR-010); link the official Drupal
   security documentation.
3. `wc -l` → 150–200. Validate YAML parses.
4. Record in the WP notes which of your five anti-pattern numbers maps to which pattern — WP08 audits
   14 of 14 across both files.

**Validation**:
- [ ] Overlap set empty
- [ ] 150–200 lines; parses as YAML
- [ ] Provenance present
- [ ] Number-to-pattern map recorded

---

## Definition of Done

- [ ] One new file, nothing else touched
- [ ] 150–200 lines; parses as YAML
- [ ] Anti-patterns 3, 6, 7, 10, 11 all represented with paired examples
- [ ] Zero pattern-name overlap with WP03 (C-S3)
- [ ] `accessCheck` version claims match C-S8 exactly
- [ ] Provenance credited; no invented threshold
- [ ] Number-to-pattern map in the WP notes
- [ ] No `*.graph.yaml` touched

## Risks

| Risk | Mitigation |
|------|-----------|
| Drifting into general conventions | If it is not about safety or speed, it is WP03's |
| Getting the `accessCheck` versions wrong | C-S8 spot-checks this claim; verify against Drupal's own change record |
| Overlapping with WP03 | T025's script is the proof, not an impression |
| Security advice that is merely a prohibition | Each entry states the consequence and the correct alternative |

## Reviewer Guidance

Verify the version claims in T022 against official Drupal documentation — a wrong version here
actively misleads. Run T025's overlap script yourself. Confirm the cache-context entry explains the
personalization leak rather than treating caching as purely a performance topic. Confirm exactly one
file changed.
