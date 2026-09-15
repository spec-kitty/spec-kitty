---
affected_files: []
cycle_number: 1
mission_slug: drupalling-dries-profile-01M28X69
reproduction_command:
reviewed_at: '2026-09-11T22:11:47Z'
reviewer_agent: user
wp_id: WP02
---

# WP02 Review Feedback — round 1

**Mission**: `drupalling-dries-profile-01M28X69`
**Work package**: WP02 — Drupalling Dries profile artifact
**Commit under review**: `f6c5013ca` (`packs/built-in/agent_profiles/drupalling-dries.agent.yaml`, 208 lines, +208/-0, one file)
**Verdict**: **REJECT** — one blocking finding. Everything else on the contract passes.

The profile itself is good work. The Drupal content is traceable, the boundary is correct, there are
no invented thresholds, and it is a genuine distillation. It is rejected for a single omission: a new
shipped profile has a registration surface that this change did not update, and an enforced repo test
goes red because of it.

---

## B1 — BLOCKING: the new profile is not listed in either shipped-profile README, and the enforced parity test reds

`tests/doctrine/test_shipped_profiles.py::TestShippedProfilesLoad::test_readme_profile_ids_match_shipped_yaml`
derives the expected id set from the filesystem —

```python
# tests/doctrine/test_shipped_profiles.py:51
EXPECTED_PROFILE_IDS = builtin_profile_ids()
```

— and asserts that **each** of two hand-maintained README tables lists exactly the packaged profile
ids. Adding `drupalling-dries.agent.yaml` without adding a table row breaks both parametrisations.

### Evidence I ran

Base (`1edeb3524`, the mission planning commit — profile not on disk), in a detached worktree:

```
$ .venv/bin/python -m pytest tests/doctrine/test_shipped_profiles.py -q -p no:randomly
351 passed, 1 skipped in 32.89s
```

Lane HEAD (profile on disk):

```
$ uv run --frozen pytest tests/doctrine/test_shipped_profiles.py::TestShippedProfilesLoad::test_readme_profile_ids_match_shipped_yaml -q -p no:randomly
FAILED ...[readme_path0-Profile ID] - AssertionError:
  .../src/charter/offering/agent_profiles/README.md drifted from shipped profiles
  Extra items in the right set: 'drupalling-dries'
FAILED ...[readme_path1-Profile ID] - AssertionError:
  .../packs/built-in/agent_profiles/README.md drifted from shipped profiles
  Extra items in the right set: 'drupalling-dries'
2 failed in 0.88s
```

Green on base, red on this branch → per CLAUDE.md's baseline-red rule this is **category "yours to
fold"**, not a pre-existing red, not a CI-environment failure, not a stale install or stale venv.

### Why it is not someone else's WP

- **No WP in this mission owns either README.** WP07 `owned_files` is
  `src/charter/offering/drg/migration/extractor.py` + the three `*.graph.yaml`. WP08 `owned_files` is
  `verification-report.md`. WP03/WP04 own styleguides/toolguides.
- **Neither README is generated.** `grep -rln "agent_profiles/README" src/ scripts/` returns nothing;
  both tables are hand-maintained, so no regeneration will heal this.
- It is therefore permanently red until WP02 fixes it, and it will red the module/packs CI lanes and
  the merge.

### Required fix

Add one row to each table, in the file's own column shape, placed alphabetically in the leading
alphabetical block (after `doctrine-daphne`, before `frontend-freddy`) to match the surrounding
ordering convention:

`packs/built-in/agent_profiles/README.md` — columns `File | Profile ID | Primary Role`:

```
| `drupalling-dries.agent.yaml` | `drupalling-dries` | implementer (Drupal specialist) |
```

(The `(Java specialist)` / `(Python specialist)` parenthetical is this table's established convention
for language specialists — `java-jenny` and `python-pedro` both carry it.)

`src/charter/offering/agent_profiles/README.md` — columns `Profile ID | Name | Role`:

```
| `drupalling-dries` | Drupalling Dries | implementer |
```

Then re-run `uv run --frozen pytest tests/doctrine/test_shipped_profiles.py -q` and record the count.

### Note for the orchestrator — this contradicts the WP prompt

The WP02 prompt's Definition of Done says "One new file, nothing else touched" and `owned_files` lists
only the YAML. **The prompt is wrong on this point**: a shipped built-in profile has a registration
surface the plan did not account for. The two README rows are the minimum needed to satisfy an
enforced repo invariant, and the implementer should not be penalised for exceeding `owned_files` here.
Either amend `owned_files` to include the two READMEs, or record the deviation explicitly in the
commit message so WP08's closeout verification sees why the diff is three files rather than one.

---

## L1 — LOW: the `js-accessibility` step does not carry the R-006 caveat

`self-review-protocol.steps[5]` (`js-accessibility`, `npm run test:a11y`) has the bare gate `passes`,
while step 5 (`js-tests`) carries the full caveat.

Two mission sources disagree here:

- `data-model.md` **E2 table** gives step 6 the gate `passes` with no caveat — and the WP prompt's
  Context section designates E1/E2 as "the specification for this file".
- `data-model.md` **I2.3** says "Steps 5-**6** carry the verification-scope caveat", and the WP
  prompt's T011 rule 3 / validation checkbox both use the plural "JS steps".

The implementer followed the more specific field-by-field table, which is defensible, and the
substantive protection R-006 exists for is present three times over (the `avoidance-boundary`, the
`initialization-declaration`, and step 5's gate text, which says "generic browser component test
authorship remains Frontend Freddy's" — covering the whole `js-*` family). **Not blocking.** If you
are touching the file anyway for B1, tightening step 6 to reference the same scope closes the gap
cheaply and removes a question WP08 would otherwise have to adjudicate.

## L2 — LOW: DIRECTIVE_010's rationale is the thinnest of the six

> Module, configuration, and theming changes must faithfully reflect the design specification without
> unauthorized deviation from the approved Drupal architecture

Compare `java-jenny`'s: "Implementations must faithfully reflect design specifications without
unauthorized deviations". The Dries form is the Jenny sentence with Drupal nouns substituted. It is
domain-adapted rather than a bare restatement of the directive's title, so it clears the T012 bar —
but it is the one rationale of the ten that carries no Drupal-specific *mechanism*, unlike 024
("core overrides"), 025 ("missing cache tag"), 030 (PHPCS/PHPStan/drupal-check/PHPUnit), 034 ("kernel
and functional tests define the Drupal contract"), and 051 (Packagist + npm). Optional improvement.

## I1 — INFORMATIONAL: markdown emphasis inside a YAML scalar

`avoidance-boundary` uses `*verifies*` / `*authors*`. No peer profile uses asterisk emphasis, and the
same distinction is stated without asterisks in both the `initialization-declaration` and the step-5
gate. When the boundary is surfaced to an operator as plain text the asterisks render literally.
Cosmetic only. **WP06 should mirror the substance, not the asterisks.**

---

## What I verified and found correct — do not re-do this work

All of the following was run, not read, in
`/Users/nicolas/Projects/spec-kitty/.worktrees/drupalling-dries-profile-01M28X69-lane-b`.

| Check | Result |
|-------|--------|
| NFR-001 / I1.1 size band 140–215 | `wc -l` = **208** ✅ |
| YAML parses | `yaml.safe_load` OK ✅ |
| I1.2 no `specializes-from` | `grep -n specializes` → no match ✅ |
| NFR-006 / R-007 no thresholds | `grep '%'` → empty; `grep -E 'level\s*[0-9]'` → empty ✅ |
| WP01 C-P1 assertions | `tests/doctrine/agent_profiles/test_drupalling_dries_profile.py` → **7 passed** ✅ |
| Full profile suite | `tests/doctrine/agent_profiles/` → **159 passed** ✅ |
| Diff scope | `git show --stat f6c5013ca` → 1 file, +208, no `*.graph.yaml` ✅ |
| Working tree vs commit | `git diff f6c5013ca -- <file>` empty; `git status --porcelain` clean ✅ |
| E1 field completeness | top-level key set **identical** to `java-jenny`, `node-norris`, `frontend-freddy` — no missing block ✅ |
| FR-005 directive/tactic resolution | all 6 directive files and all 4 tactic files exist in `packs/built-in/` — WP07's edges will resolve ✅ |
| 051 rationale names both registries | names Packagist-via-Composer **and** npm ✅ |
| C-003 distillation not reproduction | 0 shared 7-word shingles with the 1,492-line source ✅ |
| FR-010 provenance | header comment credits amazee.io `drupal-agents-md` Vanilla with URL ✅ |
| C-004 / I2.2 exactly one env note | exactly 1 (`ddev drush cr`, on the `cache-rebuild` gate) ✅ |
| FR-011 / C-005 / I1.5 version baseline | "Drupal 10.x/11.x on PHP 8.3+" in `purpose` and `initialization-declaration`; source L23/L25 ✅ |

**R-006 boundary (the highest-risk item) — correct.** The text names **Frontend Freddy** explicitly,
carries the verification-vs-authorship distinction in substance ("Dries *verifies* the Drupal-native
theming JavaScript it authored via `npm run test`; Freddy *authors* generic browser component work"),
and refuses architectural decisions ("Architectural decisions (deferred to the architect)"). It is in
the same voice as Freddy's existing "(deferred to Node Norris)" / "(deferred to Designer Dagmar)"
parentheticals, so **WP06 can mirror it directly.**

**I1.4 / SC-007 Drupal correctness — 24 claims traced**, all to the source guide unless noted:
Drupal 10.x/11.x (L23), PHP 8.3+ (L25, L33), constructor DI over `\Drupal::` statics (L689),
cacheability tags/contexts/max-age on render arrays (L626–631), `Drupal.behaviors` not
`document.ready` (L1340–1347), `*.libraries.yml` (L60, L1370), Batch API (L1097), Queue API (L1153),
Migration source/process/destination plugins (L1284–1299), content moderation & workflows (L1397),
Forms API + `#ajax` (L386, L417, L1199), Symfony components as Drupal's own usage (L194, L713),
`accessCheck(TRUE)` on entity queries in Drupal 10.2+ (L251, L701), phpcs Drupal/DrupalPractice
(L164–165), `phpstan analyse` with **no level named** (L853 — corroborating R-007),
`vendor/bin/drupal-check` (L857), `composer audit` (L858), `npm run test` / `npm run test:a11y`
(L871–872), `drush cr` (L881), `composer-patches` (L1334), `packages.drupal.org` endpoint (L1336),
thin `.module` delegating to services (L715), PHPUnit unit/kernel/functional tiers (L728–730), and
config schema/sync (L94, L891, L937).

**I1.3 `file-patterns` match the source's own scaffolding block (L51–80, L328, L889–890):**
`modules/custom/my_module/` with `.info.yml`, `.module`, `.routing.yml`, `.services.yml`,
`.permissions.yml`, `.libraries.yml`, `src/Form/`, `src/Plugin/`; themes at `themes/custom/<name>`
with `*.html.twig` (matched by the `themes/**/*.twig` glob).

**Two claims are not in the source guide and that is acceptable**, recorded so a later reviewer sees
a determination rather than an omission:
- `multisite` (in `secondary-awareness`) — absent from the guide, but an officially documented Drupal
  core capability, and I1.4 permits "source guide **or** official Drupal docs".
- the `ddev` note — deliberately absent from the Vanilla variant; it is mandated by R-008 / C-004 and
  the operator decision `01M28XMB432H0PPSHG8J3V4VG5`, not invented here.

## Failures I classified as NOT this WP's

From a full `uv run --frozen pytest tests/doctrine/ -q -p no:randomly` (**3139 passed, 43 failed,
13 skipped, 3 errors**):

- `tests/doctrine/drg/*` graph-sharding / regen-roundtrip / unknown-kind / loader-fail-closed reds and
  `test_drupalling_dries_lineage.py` — **WP07's** (graph regeneration and the curated lineage edge);
  `regenerate-graph --check` reporting STALE is expected at this point in the mission.
- `tests/doctrine/styleguides/test_drupal_styleguide_presence.py` — **WP03/WP04's**, in flight.
- `tests/doctrine/test_packaging_parity.py` (3 errors) — pre-existing environment failures that
  reproduce on the base branch.

A targeted run over the profile-referencing tests outside `tests/doctrine/` ended in **13 collection
errors** (`tests/architectural`, `tests/auth/*`, `tests/core/test_upgrade_probe_and_notifier`,
`tests/review/test_verdict_save_performance`, `tests/specify_cli/{compat,distribution,next,saas_client}/*`,
`tests/zeitgeist_client/test_resolution`). These are **exactly** the 13 entries already recorded in
this WP's own `baseline-tests.json`, captured on base commit `f0485ade9` before implementation began
— pre-existing environment collection failures, not this diff. The full `tests/charter/` directory did
not complete inside the review window and is recorded as not-run rather than claimed; it is not where
a pack-YAML-only change would red beyond what `tests/doctrine/` already covers in full.

## Not held against this WP

Commit `a73bf4e87` ("remove planning artifacts from lane branch") is the CLI's own suggested
lane-hygiene remediation, already analysed at orchestrator level. `f6c5013ca` — the deliverable — is
verified to touch **only** the profile YAML.

---

## To clear this review

1. Add the two README rows (B1). Optionally fold L1 while you are in the file.
2. Re-run and record: `uv run --frozen pytest tests/doctrine/test_shipped_profiles.py tests/doctrine/agent_profiles/ -q`.
3. Note in the commit message why the diff exceeds `owned_files` (see the orchestrator note under B1).
