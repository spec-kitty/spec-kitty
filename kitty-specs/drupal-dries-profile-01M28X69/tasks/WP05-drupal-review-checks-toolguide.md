---
work_package_id: WP05
title: Drupal review-checks toolguide
dependencies:
- WP01
requirement_refs:
- FR-007
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drupal-dries-profile-01M28X69
base_commit: 297d1cdbd7274d9d69092c60acf9d068389b82db
created_at: '2026-09-11T20:40:18.063902+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS
create_intent:
- packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md
- packs/built-in/toolguides/drupal-review-checks.toolguide.yaml
execution_mode: code_change
owned_files:
- packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md
- packs/built-in/toolguides/drupal-review-checks.toolguide.yaml
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Drupal review-checks toolguide

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`

## Objective

Author the two-file toolguide: `DRUPAL_REVIEW_CHECKS.md` (the body a reviewer reads) and
`drupal-review-checks.toolguide.yaml` (the descriptor the loader reads). They must agree exactly.

## Context

- **Spec**: FR-007, C-004
- **Data model**: [data-model.md](../data-model.md) E6, invariants I6.1–I6.3
- **Research**: R-007 (commands come from the source; no level invented), R-008 (environment-agnostic form)
- **Contract**: [contracts/styleguide-toolguide-contract.md](../contracts/styleguide-toolguide-contract.md) C-S4, C-S5, C-S6

### Read before writing

```bash
packs/built-in/toolguides/maven-review-checks.toolguide.yaml   # descriptor shape
packs/built-in/toolguides/MAVEN_REVIEW_CHECKS.md               # body shape
packs/built-in/toolguides/PYTHON_REVIEW_CHECKS.md              # a second body for comparison
```

### The commands, and only these

From the source guide's *Code Quality Tools* and *Before Submitting Code* sections:

```
vendor/bin/phpcs --standard=Drupal,DrupalPractice .
vendor/bin/phpstan analyse
vendor/bin/drupal-check .
composer audit
vendor/bin/phpunit
drush cr
drush updatedb
npm run test
npm run test:a11y
```

**The source specifies no PHPStan level.** Do not supply one. Do not invent a coverage percentage or a
mutation score. C-S6 checks this, and NFR-006 makes it a correctness failure rather than a style nit —
an invented threshold is a fabrication presented as guidance.

**Deliberately excluded**: a mutation-testing guide. Python and TypeScript ship one; the Drupal source
has no mutation content, and Java ships none either. Do not create `DRUPAL_MUTATION_TOOLS.md`.

### ⚠️ Standing rule

Do **not** run `regenerate-graph` and do **not** edit any `*.graph.yaml`. WP07 owns those.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP05`.

---

### Subtask T026: Body — coding standards and static analysis

**Purpose**: The first gates a reviewer verifies.

**Steps**: Create `packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md` with a title, a one-paragraph
purpose, and a **Coding Standards** plus **Static Analysis** section. For each check give:

- the command
- what passing means
- what a common failure looks like and what it usually indicates

Cover `phpcs` with the `Drupal` and `DrupalPractice` standards (note the two standards differ:
`Drupal` is formatting, `DrupalPractice` catches API misuse), `phpstan analyse`, and
`drupal-check` for deprecated API usage — the check that matters most ahead of a major-version
upgrade.

**Validation**:
- [ ] Each check states its gate
- [ ] No analysis level asserted
- [ ] The `Drupal` vs `DrupalPractice` distinction is explained

---

### Subtask T027: Body — PHPUnit test tiers

**Purpose**: Drupal's tiers are not interchangeable, and reviewers routinely accept a unit test where
a kernel test was needed.

**Steps**: Add a **Tests** section covering the three tiers:

| Tier | What it can do | Cost |
|------|----------------|------|
| Unit | No database, no container; pure logic | Fast |
| Kernel | Bootstrapped container, limited modules, database | Moderate |
| Functional | Full install, HTTP requests, real browser-less page rendering | Slow |

For each: the command form (`vendor/bin/phpunit --testsuite unit`, etc.), when it is the right tier,
and the failure mode of choosing wrongly — a unit test that mocks the entity type manager so heavily
it asserts nothing about Drupal is the canonical example.

Reference the source's *Unit Test Example*, *Kernel Test Example*, and *Functional Test Example*
sections. Mention `--group accessibility` from the source's quality-tools section.

**Validation**:
- [ ] All three tiers with their commands
- [ ] Guidance on choosing the tier, not just running it
- [ ] No coverage threshold asserted

---

### Subtask T028: Body — JavaScript gates, with the R-006 caveat

**Purpose**: The operator chose to include JS gates. That decision needs its boundary stated here too,
or this guide will read as a claim on Frontend Freddy's territory.

**Steps**:

1. Add a **JavaScript** section with `npm run test` and `npm run test:a11y`.
2. State the caveat plainly: these verify **Drupal-native theming JavaScript** — `Drupal.behaviors`,
   library-declared assets — that the implementer authored. Authorship of generic browser components
   remains Frontend Freddy's. Running a test is not a claim on the territory.
3. Note that a project without a `package.json` simply has no JS gate; that is not a failure.

**Validation**:
- [ ] Both commands present
- [ ] The verification-versus-authorship caveat is explicit (R-006)
- [ ] The no-`package.json` case is handled

---

### Subtask T029: Body — environment adaptation and pre-submit checklist

**Steps**:

1. Add a short **Environment** note, exactly once (C-S5): commands are written for direct execution;
   containerized setups prefix them — `ddev drush cr`, `ddev composer audit`, `lando phpunit`. Do not
   dual-list every command; one note covers all of them.
2. Add a **Before Submitting** checklist mirroring the source's section: `phpcs`, `phpunit`,
   `drush cr`, `drush updatedb`, plus `composer audit`.
3. Add a **Supply chain** line: `composer audit` for advisories; note that Composer's
   `post-install-cmd` and npm's `postinstall` are the deny-by-default lifecycle-script surface
   DIRECTIVE_051 targets.

**Validation**:
- [ ] Exactly one environment note
- [ ] Checklist matches the source's *Before Submitting Code*
- [ ] Lifecycle-script surface named

---

### Subtask T030: Descriptor YAML

**Purpose**: I6.1–I6.3. The descriptor is what the loader sees.

**Steps**:

```yaml
schema_version: "1.0"
id: drupal-review-checks
tool: drupal-quality-stack
title: Drupal Review Checks
guide_path: packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md
applies_to_languages:
  - php
  - twig
summary: >
  Catalog of automated checks a reviewer should run or verify have been run before
  approving Drupal code. Organized by category: coding standards, static analysis,
  deprecation scanning, test tiers, JavaScript, and supply-chain advisories.
commands:
  - vendor/bin/phpcs --standard=Drupal,DrupalPractice .
  # ... the rest
```

Then prove body and descriptor agree:

```bash
uv run python - <<'PY'
import yaml, pathlib
d = yaml.safe_load(pathlib.Path("packs/built-in/toolguides/drupal-review-checks.toolguide.yaml").read_text())
body = pathlib.Path(d["guide_path"]).read_text()
missing = [c for c in d["commands"] if c.split()[0] not in body]
print("guide_path exists:", pathlib.Path(d["guide_path"]).exists())
print("commands missing from body:", missing)
PY
```

**Validation**:
- [ ] `guide_path` resolves (I6.1)
- [ ] Every descriptor command appears in the body, and vice versa (I6.2)
- [ ] Parses as YAML

---

## Definition of Done

- [ ] Two new files, nothing else touched
- [ ] Descriptor and body agree — the T030 script reports no missing commands
- [ ] All three PHPUnit tiers documented with tier-selection guidance
- [ ] JS gates present with the R-006 caveat
- [ ] Exactly one environment adaptation note
- [ ] **No PHPStan level, coverage percentage, or mutation score anywhere** (C-S6)
- [ ] No `DRUPAL_MUTATION_TOOLS.md` created
- [ ] Provenance credited
- [ ] No `*.graph.yaml` touched

## Risks

| Risk | Mitigation |
|------|-----------|
| Inventing a PHPStan level to feel concrete | The source names none. "The project's configured level" is the honest form |
| Descriptor and body drifting | T030's script is the check; run it, do not eyeball it |
| Dual-listing every command for both environments | Doubles the guide for no information. One note |
| JS section reading as a territory claim | The R-006 caveat is not optional here |

## Reviewer Guidance

Grep the body for a digit after "level" and for `%` — either is likely an invented threshold and is an
NFR-006 failure, not a nit. Run the T030 agreement script. Confirm the tier table gives guidance on
*choosing* a tier, since that is the mistake this guide exists to prevent. Confirm two files changed,
and that no mutation-tools guide appeared.

## Activity Log

- 2026-09-11T20:50:00Z – claude – shell_pid=10883 – Implementation complete and committed (7582d3795); subtasks T026-T030 marked done. move-task --to for_review is blocked by the kitty-specs lane-contamination guard (WP02/WP03/WP04 status artifacts leaked onto lane-e via dependency-lane merges, pre-existing and unrelated to WP05's diff). The guard's own suggested remediation (git restore --source feat/drupal-dries-profile -- kitty-specs/ && commit) and --force were both blocked by the sandbox permission classifier. Awaiting operator to either grant the commit permission or run move-task manually.
