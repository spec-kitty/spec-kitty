# Verification Report — Drupal Dries Agent Profile

**Mission**: `drupal-dries-profile-01M28X69`
**Work package**: WP08 — Closeout verification (T039–T043)
**Verified at**: 2026-09-12
**Verification surface**: `.worktrees/drupal-dries-profile-01M28X69-lane-g`, branch
`kitty/mission-drupal-dries-profile-01M28X69-lane-g`
**Merge-base with `main`**: `beab3c5fc4` (`test(landing): correct the deferred-inputs NOTE…`)
**Planning artifacts read from**: the repository-root checkout
(`kitty-specs/drupal-dries-profile-01M28X69/`), never a lane copy — see Known Issue KI-4.

**Headline verdict: RELEASABLE.** All eight contract clauses, all seven success criteria, and
12 of 13 functional requirements verify clean. Four findings are recorded below; none is a
blocker, the most severe is Low, and one requirement (NFR-003, diff coverage) is a CI-owned
gate this package did not execute and does not claim.

---

## 1. Tests run

Paste-ready for the pull request. Every count below was observed in this session; nothing is
quoted from another agent's run.

```
### Tests run

# Mission-authored / mission-edited test files (the mission's own assertions)
uv run pytest tests/doctrine/agent_profiles/test_drupal_dries_profile.py \
              tests/doctrine/drg/test_drupal_dries_lineage.py \
              tests/doctrine/styleguides/test_drupal_styleguide_presence.py \
              tests/doctrine/agent_profiles/test_context_sources_migration.py \
              tests/doctrine/drg/migration/test_extractor.py -q
    -> 116 passed in 30.06s

# Owning subsystem 1 of 2 (src/charter/offering/** blast radius)
uv run pytest tests/doctrine/ -q
    -> 3188 passed, 10 skipped, 87 warnings in 252.12s

# Owning subsystem 2 of 2
uv run pytest tests/charter/ -q
    -> 2830 passed, 22 skipped, 121 warnings in 707.94s (exit 0)

# Terminology guard (mission adds user-facing prose)
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
    -> 90 passed in 11.55s

# Lint
uv run ruff check .
    -> All checks passed!

# C-006 — zero new runtime dependencies
git diff --stat main -- pyproject.toml uv.lock
    -> (empty)

# Type gate on the one src/ file this mission touches
uv run mypy --strict src/charter/offering/drg/migration/extractor.py
    -> 2 errors [no-any-return] at lines 107, 140 — PRE-EXISTING, see KI-1
```

### Broad suites deliberately NOT run

Stated explicitly rather than quoting a number that was not observed:

- **`make test-fast` was NOT run.** The mission's blast radius is `src/charter/offering/**`
  plus five pack data files; `make test-fast` covers `tests/unit tests/status tests/cli
  tests/specify_cli/runtime`, none of which this diff touches. The two owning-subsystem
  directories that CLAUDE.md names for `src/charter/offering/**` — `tests/charter/` and
  `tests/doctrine/` — were both run in full instead.
- **`make test-full` was NOT run** (CLAUDE.md assigns whole-repo runs to the CI agent).
- **`tests/architectural/` was NOT run in full.** CLAUDE.md scopes the full architectural suite
  to cross-cutting changes (pytest.ini, pyproject.toml, conftest, markers, packaging); this
  diff touches none of those. The terminology guard was run individually as WP08 requires.
- **`ruff format --check .` repo-wide was NOT run to completion as a recorded gate.** The
  single file it would flag inside this diff's blast radius — `extractor.py` — was checked
  directly and is pre-existing-dirty on `main` (KI-1).
- **`diff-cover` was NOT run** (NFR-003) — it is a `ci-aggregate.yml` gate requiring a CI
  coverage artefact this package cannot produce locally.

---

## 2. Requirement coverage

### Functional requirements (13)

| ID | Verdict | Evidence |
|----|---------|----------|
| FR-001 | **MET** | `packs/built-in/agent_profiles/drupal-dries.agent.yaml` exists, `roles: [implementer]`, `description` distinguishes it as a Drupal specialist. `doctor doctrine --json` built-in pack `discovered_count` 25 → **26**. |
| FR-002 | **MET** | `specialization.primary-focus` names all six areas: services + constructor DI, Entity API & entity queries, Plugin system, hook implementations, Forms API (incl. AJAX), routing & controllers, configuration management. Long-running-operation patterns in `secondary-awareness` (Batch API, Queue API). |
| FR-003 | **MET** | All five theming areas named in `primary-focus`: Twig templates, `*.libraries.yml` asset definitions, `Drupal.behaviors` JavaScript, render arrays, preprocess functions. |
| FR-004 | **MET** | Dries `avoidance-boundary` defers "generic browser component authorship (deferred to Frontend Freddy)"; Freddy `avoidance-boundary` defers "framework-native theming layers — server-side template engines, asset-library declarations and behavior-attachment APIs (deferred to the stack specialist for that framework, when one is active)". Reciprocal; Freddy's side is deliberately framework-generic (see Post-review revision). |
| FR-005 | **MET** | `extractor.py` `_CURATED_ARTIFACT_EDGES` gains `("agent_profile:drupal-dries", implementer-ivan, Relation.SPECIALIZES_FROM)`; `agent_profile.graph.yaml` carries the `specializes_from` edge plus six `requires` edges to DIRECTIVE_010/024/025/030/034/051 and four tactic edges. Discipline inherited, not restated. |
| FR-006 | **MET** | Two standalone styleguides: `drupal-conventions` (17 patterns) and `drupal-security-performance` (9 patterns), each schema-shaped like the `python-`/`java-conventions` peers (`schema_version`, `id`, `title`, `scope`, `applies_to_languages`, `principles`, `patterns`, `tooling`, `references`). |
| FR-007 | **MET** | `drupal-review-checks.toolguide.yaml` (9 commands) + `DRUPAL_REVIEW_CHECKS.md` body with a gate stated per command; coding-standard (phpcs), static-analysis (phpstan, drupal-check), and test-tier (phpunit unit/kernel/functional) commands all present. |
| FR-008 | **MET** | 14 of 14 source anti-patterns recorded — see §4. |
| FR-009 | **MET** | `self-review-protocol.steps` — 10 steps, each with a `gate`: coding-standards, static-analysis, deprecation-scan, tests, js-tests, js-accessibility, dependency-audit, cache-rebuild, acceptance-review, locality-review. |
| FR-010 | **PARTIAL** | 4 of 5 artifacts credit amazee.io `drupal-agents-md` (Vanilla). `drupal-review-checks.toolguide.yaml` carries **zero** attribution tokens. See **F1**. |
| FR-011 | **MET** | "Drupal 10.x/11.x on PHP 8.3+" stated in `purpose` and restated in `initialization-declaration`. |
| FR-012 | **MET** | `.kittify/charter/charter.yaml` `selected_agent_profiles` lists 23 profiles, none of them `drupal-dries`; `.kittify/agent_profiles_manifest.json` → 0 drupal hits; `.kittify/charter/graph.yml` → 0 drupal hits. Repository left unactivated. |
| FR-013 | **MET** | `doctor doctrine --json` → `profile_health.packs[builtin]` = `{discovered_count: 26, valid_count: 26, healthy: true, invalid_profiles: []}`; `org_drg.dangling_endpoints: []`, `errors: []`. The load-failure surface exists and reports the new profile as valid. |

### Non-functional requirements (7)

| ID | Verdict | Evidence |
|----|---------|----------|
| NFR-001 | **MET** | `drupal-dries.agent.yaml` = **209 lines**, inside the declared 140–215 peer band. |
| NFR-002 | **MET** | `invalid_profiles: []`, `dangling_endpoints: []`, `errors: []`, `collision_warnings: []`. Zero skipped profiles, zero unresolved lineage edges. |
| NFR-003 | **NOT VERIFIED (not claimed)** | Diff coverage ≥90% is enforced by the `ci-aggregate.yml` diff-cover gate. This package did not run it and makes no claim. Mitigating signal: the mission's five test files contribute 116 passing assertions and the only `src/` change is five declarative lines in an existing tuple literal, covered by `tests/doctrine/drg/migration/test_extractor.py` and `tests/doctrine/drg/test_drupal_dries_lineage.py`. |
| NFR-004 | **MET** | `ruff check .` → "All checks passed!"; terminology guard 90 passed; `tests/doctrine/` 3188 passed; `tests/charter/` 2830 passed. **Zero new suppressions**: `git diff main -- '*.py' \| grep '^+.*(# noqa\|# type: ignore\|# nosec\|per-file-ignores)'` → no matches. Pre-existing `mypy`/`ruff format` dirt on `extractor.py` is KI-1, not new. |
| NFR-005 | **MET** | `spec-kitty charter context --action implement --json` run in both trees: **md5 `087fdede88bec3fb850eb3ceb1a0dc5f` on both**, 19117 bytes each, `diff` empty. `grep -ci drupal` on the post-mission context → **0**. Byte-identical. |
| NFR-006 | **MET, with two understatements recorded** | C-S6 threshold grep returns nothing (§5); ten-claim sampling in §3 traces 10/10 to official sources. Two entries understate a version fact relative to the 10.x/11.x baseline — **F2** (`#markup`) and **F3** (`node_load()`). Neither is an invented API, command, or convention. |
| NFR-007 | **MET (revised)** | The only pre-existing **profile** modified is `frontend-freddy.agent.yaml`. Its diff is one clause appended to `specialization.avoidance-boundary` plus, in `initialization-declaration`, the deletion of the single clause "if it runs in a user's browser, it is my concern" (which contradicted the boundary). No Drupal-specific wording enters `initialization-declaration`. Two roster `README.md` index files and `pack-manifest.yaml` also changed — generated/bookkeeping surfaces, not profiles. (Original verdict said "entire diff inside avoidance-boundary"; see Post-review revision.) |

### Constraints (8)

| ID | Verdict | Evidence |
|----|---------|----------|
| C-001 | **MET** | `git diff --name-only main` matched against the 12 agent-copy directory prefixes (`.claude/`, `.github/`, `.gemini/`, `.cursor/`, `.qwen/`, `.opencode/`, `.windsurf/`, `.kilocode/`, `.augment/`, `.amazonq/`, `.kiro/`, `.agent/`, `.agents/`) → **no matches**. All authoring is in `packs/built-in/`. |
| C-002 | **MET** | Lineage is a DRG edge with canonical `<kind>:<id>` endpoint form — `source: agent_profile:drupal-dries`, `target: agent_profile:implementer-ivan`, `relation: specializes_from`. No per-profile lineage field anywhere in the declaration. |
| C-003 | **MET** | Mechanical distillation check against the fetched upstream `Vanilla/AGENTS.md` (1492 lines): **zero shared 8-word prose runs** in any of the five artifacts. The only shared 10-word runs are canonical Drupal API code idioms inside `good_example` blocks (`public static function create(ContainerInterface $container): static`, `$build = ['#theme' => 'item_list', …]`) — facts and structure, which C-003 permits. Three sampled substantial passages confirm this by eye: the `Entity Query Access Check` description (wholly rewritten, and corrects the source), the `Credentials Out Of Version Control` description (adds the rotation-vs-deletion argument absent upstream), and the toolguide's "Choosing the tier is the review question" paragraph (no upstream analogue). |
| C-004 | **MET** | No command in any artifact carries an environment prefix. `grep -oiE "ddev\|lando\|docker compose"` across all five artifacts hits exactly two locations, both adaptation notes, never a command: `DRUPAL_REVIEW_CHECKS.md:103` (the `## Environment` note) and `drupal-dries.agent.yaml:172` (the cache-rebuild gate parenthetical). See the C-S5 note in §5. |
| C-005 | **MET** | "Drupal 10.x/11.x on PHP 8.3+" declared; `drupal-security-performance` reasons explicitly from that baseline ("on Drupal 10/11 an unchecked query is a hard failure"). |
| C-006 | **MET** | `git diff --stat main -- pyproject.toml uv.lock` → **empty**. Zero new runtime dependencies. |
| C-007 | **MET** | `git diff --name-only main` outside `kitty-specs/` contains no mission-type or mission-step path. No workflow introduced. |
| C-008 | **MET** | `tests/architectural/test_no_legacy_terminology.py` → 90 passed (gates the two retired terms). Review-enforced half: see **F4** — one `Drupal features` occurrence, in the Drupal-domain sense, not the Spec Kitty domain object. |

---

## 3. Success criteria

| ID | Verdict | Result |
|----|---------|--------|
| **SC-001** | **MET** | A Drupal work package is assignable in one selection step: `drupal-dries` is a discovered, valid, implementer-role built-in profile, and the conventions + security/performance + review-checks artifacts supply the Drupal conventions the operator previously hand-fed. |
| **SC-002** | **MET** | All six FR-002 competence areas and all five FR-003 theming areas are readable from `specialization.primary-focus` alone, with no other artifact required. |
| **SC-003** | **MET** | 14 of 14 source forbidden-practice entries recorded. Zero omissions, therefore zero omission-reasons required. Full table in §4. |
| **SC-004** | **MET** | Ten-task boundary audit run twice independently (implementer, then reviewer — recorded in `tasks/WP06-frontend-freddy-reciprocal-boundary/review-cycle-1.md`), both giving **1, 3, 5, 7, 9 → Dries; 2, 4, 6, 8, 10 → Freddy, no ties**. Spot-re-checked four rows here against the two boundary texts alone: #1 (Twig template) → Dries via Freddy's "Twig templates … deferred to Drupal Dries"; #3 (`Drupal.behaviors` handler) → Dries via the same clause; #6 (webpack bundle budget) → Freddy via "bundle concerns"; #10 (keyboard nav in a framework modal) → Freddy via "framework components, accessibility compliance". All four decidable from the boundaries alone. |
| **SC-005** | **MET** | Zero skipped profiles (`invalid_profiles: []`, 26/26 valid), zero unresolved lineage edges (`dangling_endpoints: []`, `errors: []`). |
| **SC-006** | **MET** | Rendered governance context byte-identical pre/post (md5 match, §NFR-005), and zero `drupal` occurrences in it. |
| **SC-007** | **MET — 10 of 10 traceable** | See the sampling table below. |

### SC-007 — ten-claim Drupal sampling

Sampled across all five artifacts and traced to official Drupal documentation (not to the
source guide, where an official source exists). Treated as a real audit: two claims came back
imprecise and are recorded as findings rather than waved through.

| # | Claim (artifact) | Traced to | Result |
|---|---|---|---|
| 1 | Implicit entity-query access checking was deprecated in **9.2.0** and throws an error from **10.0.0** (`drupal-security-performance` → `Entity Query Access Check`; echoed in `drupal-conventions` → `Entity Query Over Raw SQL`) | Change record [drupal.org/node/3201242](https://www.drupal.org/node/3201242), fetched: deprecation warning introduced in **Drupal 9.2**, "For Drupal 10 this will be enforced by throwing an exception" | **TRACES — and corrects the source.** The upstream `AGENTS.md` line 701 was fetched and confirmed to read "Drupal 10.2+ requires explicit access checking … throws deprecation warnings and will be required in Drupal 12" — the known upstream error. Neither styleguide states the wrong claim as a live assertion; `drupal-security-performance` `references` records the upstream error explicitly and by line number. |
| 2 | `accessCheck(FALSE)` remains legitimate for internal non-user-facing queries but must be explicit and commented (`drupal-security-performance`) | Same change record: developers must call "either `accessCheck(TRUE)` … or `accessCheck(FALSE)`" | **TRACES** |
| 3 | `Drupal.behaviors` + `core/once`; a bare `$(document).ready` re-runs on every AJAX update instead of once per element (`drupal-conventions` → `Drupal Behaviors`, `Library Declaration`) | [drupal.org JavaScript API overview](https://www.drupal.org/docs/drupal-apis/javascript-api/javascript-api-overview): `core/once` declared as a library dependency; `attach()` is called on initial DOM load **and after any AJAX call**; `once()` marks elements via `data-once` | **TRACES** |
| 4 | Render arrays that depend on data must declare `#cache` tags, contexts and max-age (`drupal-security-performance` → `Render Array Cacheability`) | [Cacheability of render arrays](https://www.drupal.org/docs/drupal-apis/render-api/cacheability-of-render-arrays): "always supply the cache contexts, tags, and max-age" | **TRACES** |
| 5 | A user-specific render array cached without a user cache context serves one visitor's output to another (`drupal-security-performance` → `Cache Contexts For Personalized Output`) | [Cache contexts](https://www.drupal.org/docs/drupal-apis/cache-api/cache-contexts): contexts are "analogous to HTTP's Vary header"; a personalized render array "varies per user, and you'd vary by the `user` cache context" | **TRACES** |
| 6 | Entity-based cache tags are invalidated automatically by the entity system on save, so tagging beats relying on `max-age` (`drupal-security-performance` → `Cache Tag Invalidation`) | [Cache API](https://www.drupal.org/docs/8/api/cache-api/cache-api) — tags express dependency on modifiable data; max-age expresses time-limited validity | **TRACES** |
| 7 | `hook_views_data()` columns must be aliased, with `'real field'` carrying the true column name (`drupal-conventions` → `Views Data With Table Aliases`) | [`hook_views_data`](https://api.drupal.org/api/drupal/core!modules!views!views.api.php/function/hook_views_data/10) — `'field'` may be "the real database field name to override the Views name"; ambiguity arises when a joined table repeats a column name (core issue [#3353546](https://www.drupal.org/project/block_content_permissions/issues/3353546)) | **TRACES** |
| 8 | `#plain_text` is the correct element for untrusted content, in preference to `#markup` (`drupal-security-performance` → `Plain Text Over Markup`) | [Render API overview](https://api.drupal.org/api/drupal/core!lib!Drupal!Core!Render!theme.api.php/group/theme_render/9.1.x) / `Renderer::ensureMarkupIsSafe`: "Render arrays can escape text instead of XSS filtering by setting the `#plain_text` property instead of `#markup`" | **TRACES (guidance correct) — mechanism sentence imprecise, see F2** |
| 9 | `node_load()` is a deprecated procedural loader to be replaced by the entity type manager (`drupal-conventions` → `Entity Type Manager Over Deprecated Loaders`) | api.drupal.org deprecation records: `node_load()` deprecated in Drupal 8.x and **removed from Drupal 9.0.0**; replacement `\Drupal::entityTypeManager()->getStorage('node')->load()` | **TRACES (replacement correct) — "deprecated" understates for a 10.x/11.x baseline, see F3** |
| 10 | Twig auto-escapes by default; `\|raw` defeats it; intentional HTML goes through a text format (`#type => 'processed_text'` / `check_markup()`) (both styleguides) | [Writing secure code for Drupal](https://www.drupal.org/docs/administering-a-drupal-site/security-in-drupal/writing-secure-code-for-drupal): "Drupal uses Twig's auto-escape feature … automatically escapes any HTML that is not known to be safe" | **TRACES** |

Supporting checks in the same audit:

- The upstream source's `Aim for ≥ 80% code coverage` (line **721** of the fetched
  `Vanilla/AGENTS.md`, confirmed verbatim) is **not carried** into any delivered artifact —
  confirmed by the C-S6 grep returning nothing. The implementers' deliberate omission holds.
- The upstream source's PHPStan invocation names no level, and neither does the delivered
  toolguide: `DRUPAL_REVIEW_CHECKS.md` says "clean at the project's configured level. The level
  is a project-specific setting (`phpstan.neon`) — this guide does not assert one."

---

## 4. Anti-pattern audit — 14 of 14

The cross-cutting audit no content package could perform. Source list confirmed by fetching
`Vanilla/AGENTS.md` and reading its numbered "Never Do This" entries at lines 689–715.

| # | Source anti-pattern (upstream line) | Resolved owner | Delivered entry | `bad_example` | `good_example` |
|---|---|---|---|---|---|
| 1 | `\Drupal::` static calls in services/controllers/plugins (689) | `drupal-conventions` | Constructor Dependency Injection | ✅ | ✅ |
| 2 | Direct DB queries where Entity Query suffices (691) | `drupal-conventions` | Entity Query Over Raw SQL | ✅ | ✅ |
| 3 | `\|raw` in Twig (693) | `drupal-security-performance` | Twig Output Escaping | ✅ | ✅ |
| 4 | Monolithic `hook_form_alter()` (695) | `drupal-conventions` | Focused Form Alter | ✅ | ✅ |
| 5 | Configuration stored in state (697) | `drupal-conventions` | Config Versus State | ✅ | ✅ |
| 6 | `#markup` with unsanitized input (699) | `drupal-security-performance` | Plain Text Over Markup | ✅ | ✅ |
| 7 | Entity queries without `accessCheck(TRUE)` (701) | `drupal-security-performance` | Entity Query Access Check | ✅ | ✅ |
| 8 | Hardcoded entity IDs, user IDs, paths (703) | `drupal-conventions` | Avoid Hardcoded IDs And Paths | ✅ | ✅ |
| 9 | `hook_views_data()` without table aliases (705) | `drupal-conventions` | Views Data With Table Aliases | ✅ | ✅ |
| 10 | Ignored cacheability metadata (707) | `drupal-security-performance` | Render Array Cacheability **+** Cache Contexts For Personalized Output **+** Cache Tag Invalidation | ✅ (each) | ✅ (each) |
| 11 | `settings.php` committed with credentials (709) | `drupal-security-performance` | Credentials Out Of Version Control | ✅ | ✅ |
| 12 | Deprecated procedural functions (`node_load()`) (711) | `drupal-conventions` | Entity Type Manager Over Deprecated Loaders | ✅ | ✅ |
| 13 | Global `$_GET` / `$_POST` / `$_SERVER` (713) | `drupal-conventions` | Injected Request Over Superglobals | ✅ | ✅ |
| 14 | Business logic in `.module` files (715) | `drupal-conventions` | Thin Module File | ✅ | ✅ |

**Result: 14 / 14 present. Zero omissions, therefore zero omission-reasons owed (SC-003).**
The split matches the planned ownership exactly — the nine conventions entries are 1, 2, 4, 5,
8, 9, 12, 13, 14; the five security/performance entries are 3, 6, 7, 10, 11. Every one of the
16 delivered anti-pattern entries carries both a `bad_example` and a `good_example`, satisfying
C-S2 in full. (Anti-pattern 10 is carried by three entries rather than one — a deliberate
expansion, not a duplication; cacheability, cache contexts, and tag invalidation are distinct
failures with distinct fixes.)

---

## 5. Contract clauses C-S1 – C-S8

| Clause | Verdict | Evidence |
|---|---|---|
| **C-S1** — both styleguides load | **MET** | Both present and keyed by id; `doctor doctrine --json` reports no styleguide load failure; `tests/doctrine/styleguides/test_drupal_styleguide_presence.py` green within the 116-test run. Peer-shape fields all present. |
| **C-S2** — all 14 anti-patterns carried, each with both examples | **MET** | §4. |
| **C-S3** — the split is a real boundary | **MET** | Pattern-name sets extracted mechanically: 17 names in `drupal-conventions`, 9 in `drupal-security-performance`, **intersection empty**. The boundary is semantic, not a line-count halving: conventions answers "how do I write this?" (DI shape, plugin annotation, form base class, route permission), security/performance answers "how do I keep it safe and fast?" (escaping, access check, cacheability, secrets, N+1, batch). Sizes 210 and 199 lines — within the "roughly 150–200" band, conventions 10 lines over. |
| **C-S4** — descriptor matches body | **MET, with one note** | `guide_path` resolves to the committed `DRUPAL_REVIEW_CHECKS.md` (5883 bytes). **All 9** descriptor commands appear verbatim in the body. Reverse direction: the body additionally shows four tier-selection variants of a listed command — `vendor/bin/phpunit --testsuite unit\|kernel\|functional` and `vendor/bin/phpunit --group accessibility` — which are not separately enumerated in the descriptor. They are argument forms of the listed `vendor/bin/phpunit`, not distinct gates; recorded for completeness, not as a defect. |
| **C-S5** — commands environment-agnostic | **MET, with one note** | Zero commands carry an environment prefix. Adaptation is stated twice, once per surface: `DRUPAL_REVIEW_CHECKS.md` `## Environment` ("A containerized development setup prefixes each one with its runner instead — `ddev drush cr`, `ddev composer audit`, `lando vendor/bin/phpunit` — the command itself is unchanged") and the profile's `cache-rebuild` gate parenthetical. A strict reading of "exactly one adaptation note" across both surfaces counts two; the clause's intent — no silent environment assumption, and no per-command repetition — is satisfied, since each surface states it exactly once. |
| **C-S6** — no invented thresholds | **MET** | `grep -rniE "level [0-9]\|[0-9]{1,3}% coverage\|mutation score\|[0-9]{2}%"` across all five artifacts → **no output, exit 1**. No PHPStan level asserted, no coverage percentage, no mutation score. The upstream `Aim for ≥ 80% code coverage` (source line 721, confirmed by fetch) was deliberately not carried, and that omission still holds. |
| **C-S7** — styleguide edges follow the peer precedent | **MET (fixed in WP07 — see KI-3)** | `styleguide.graph.yaml` now carries exactly the three required edges and no others: `styleguide:drupal-conventions → agent_profile:drupal-dries (suggests)`, `styleguide:drupal-conventions → toolguide:drupal-review-checks (suggests)`, `styleguide:drupal-security-performance → agent_profile:drupal-dries (suggests)`. Mirrors `styleguide:java-conventions`. Zero forbidden edges remain. |
| **C-S8** — Drupal correctness spot-checks | **MET** | All six content assertions verified: accessCheck (row 1 of the SC-007 table, corrected vs source); config-vs-state (`Config Versus State`, exportable vs ephemeral, last-cron-run example); Twig escaping (auto-escape default, `\|raw` defeats it, `#type => 'processed_text'` / `check_markup()` named); dependency injection (`\Drupal::` acceptable only in `hook_` functions in `.module` files, with delegation preferred — see the `Thin Module File` good_example); cacheability (tags, contexts, max-age); test tiers (unit / kernel / functional table with distinct bootstrap cost and capability, plus the "choose the tier" review guidance). |

---

## 6. Findings

Four findings. None blocking.

### F1 — `drupal-review-checks.toolguide.yaml` carries no source attribution — **Low**

**Requirement**: FR-010, C-P8, C-003 (attribution).
**Evidence**:

```
$ grep -ci "drupal-agents-md\|amazee" packs/built-in/toolguides/drupal-review-checks.toolguide.yaml
0
```

The other four artifacts credit the source (agent profile: 2 hits, conventions styleguide: 1,
security/performance styleguide: 2, toolguide body: 1). T039's stated bar is "Every file must
report at least 1"; this file reports 0.

**Why it is Low and not Medium**: the descriptor is a machine-readable manifest whose
`guide_path` points at `DRUPAL_REVIEW_CHECKS.md`, and that body carries a full attribution
line naming amazee.io, the repository URL, the Vanilla variant, and the specific source
sections. A human reading the toolguide reaches the credit; only a reader of the descriptor in
isolation does not.

**Recommended fix (not applied — WP08 verifies, it does not fix)**: a two-line YAML comment
header on the descriptor mirroring the one already on `drupal-dries.agent.yaml` lines 1–2.

### F2 — `#markup` is described as unescaped; core XSS-filters it — **Low**

**Requirement**: NFR-006 (distillation fidelity).
**Location**: `drupal-security-performance.styleguide.yaml`, pattern `Plain Text Over Markup`.
**Text**: "`#markup` inserts its string as trusted HTML with no escaping."

Per the Render API overview and `Renderer::ensureMarkupIsSafe`, `#markup` that is not already
a `MarkupInterface` is filtered through `Xss::filter()` with the **admin** tag list (overridable
via `#allowed_tags`). A `<script>` tag in `#markup` is stripped, not executed. The accurate
statement is that `#markup` is XSS-filtered against a deliberately permissive admin tag list,
which is not a substitute for escaping untrusted input — which is why core itself documents
`#plain_text` as the escape-instead-of-filter option.

**The guidance is correct and unchanged by this**: "use `#plain_text` for untrusted content"
is exactly core's own recommendation. Only the mechanism sentence overstates. The claim is
traceable to the source guide (upstream line 699 says "Never use `#markup` with unsanitized
user input"), so NFR-006's "source guide **or** official documentation" test is met either
way — this is recorded because WP08 was asked to treat the sampling as a real audit, and
because the mission has already set the precedent of correcting the source where official docs
disagree (the accessCheck entry).

### F3 — `node_load()` called "deprecated"; it was removed in Drupal 9.0.0 — **Low**

**Requirement**: NFR-006, C-005 (declared version baseline).
**Location**: `drupal-conventions.styleguide.yaml`, pattern
`Entity Type Manager Over Deprecated Loaders` (name, description, and `bad_example`
`$node = node_load(123);`).

`node_load()` was deprecated in Drupal 8.x and **removed from Drupal 9.0.0**. On this profile's
declared 10.x/11.x baseline it does not exist; calling it is a fatal
`Error: Call to undefined function`, not a deprecation warning.

This is structurally the same understatement the mission correctly caught and fixed upstream in
the accessCheck entry: a source-guide claim that is true of an older version and stale against
the declared baseline. The prescribed replacement
(`$this->entityTypeManager->getStorage('node')->load(123)`) is correct and unaffected, and the
example remains didactically useful for readers porting legacy code — which is why this is Low
rather than a correctness defect.

**Recommended wording (not applied)**: "Procedural entity loaders were removed in Drupal 9.0.0
— on this baseline `node_load()` is an undefined function, not a deprecation."

### F4 — "Drupal features" in the profile prose — **Informational**

**Requirement**: C-008 (terminology canon, review-enforced half).
**Location**: `drupal-dries.agent.yaml:86` —
"Building new Drupal features — modules, plugins, forms, and Drupal-native theming".

The Terminology Canon prohibits `Feature`/`Features` "when the domain object is a Mission".
Here the word denotes Drupal site functionality, not a Spec Kitty Mission, so in my reading it
is outside the prohibition. The gated half of the canon agrees: `test_no_legacy_terminology.py`
gates only `ceremony` and `status-writing`, and passes. Recorded so a human reviewer can rule
rather than discover it after merge; rewording to "Drupal functionality" would remove the
question entirely at zero cost.

---

## 7. Failures and classifications

**No test failure was observed on this branch.** Every red encountered during verification is a
pre-existing gate gap on `main`, classified below against CLAUDE.md's four baseline-red
categories.

| Red | Category | Evidence for the classification |
|---|---|---|
| `mypy --strict src/charter/offering/drg/migration/extractor.py` → 2 × `no-any-return` at lines **107** and **140** | **Category 1 — pre-existing on honestly-red `main`** | Reproduced identically by a prior reviewer at the merge-base `beab3c5fc4`. The mission's entire change to this file is five declarative lines appended to the `_CURATED_ARTIFACT_EDGES` tuple at ~line 292 — nowhere near lines 107/140, and containing no `return` statement at all. Not this mission's. |
| `ruff format --check src/charter/offering/drg/migration/extractor.py` → "would reformat" | **Category 1 — pre-existing on honestly-red `main`** | `ruff format --diff` localises the complaint to four hunks at lines **140, 226, 718, 789** (two missing blank lines and two line-wrap decisions), none of them inside the mission's ~line-292 hunk, whose formatting matches its neighbouring tuple entries exactly. Also reproduced by a prior reviewer at `beab3c5fc4`. |

No category-2 (CI-environment), category-3 (stale-install), or category-4 (stale-venv)
failures were encountered. Nothing was green-washed and nothing was misattributed: the two
reds above are recorded as pre-existing **and** carried forward as KI-1 rather than dismissed.

---

## 8. Known issues carried forward

### KI-1 — `extractor.py` fails `mypy --strict` and `ruff format --check` on `main` itself — **upstream gate gap**

A charter-module source file sits red on two quality gates on the integration branch, not
because of this mission. Two `no-any-return` errors (lines 107, 140) and four formatting hunks
(lines 140, 226, 718, 789). Both reproduce on unmodified `main` and both were independently
reproduced here.

This is worth an upstream issue in its own right: `src/charter/offering/**` is governed code,
CI runs `ruff format --check .` repo-wide, and a file that is already dirty on `main` means the
next contributor to touch it inherits a red gate they did not cause — exactly the
misattribution trap CLAUDE.md's baseline-red section warns about. This mission's five-line
addition is deliberately *not* accompanied by a drive-by reformat, because reformatting four
unrelated hunks would violate Locality of Change and bury the mission's diff.

### KI-2 — Frontend Freddy's `purpose` now contradicts its own `avoidance-boundary` — **deliberate, bounded**

Freddy's `purpose` still reads "if it runs in a user's browser, it is my concern". Its new
`avoidance-boundary` defers `Drupal.behaviors` — which runs in a browser — to Dries. The two
fields now disagree.

Left unfixed **deliberately**: NFR-007 bounds the entire outside-the-mission blast radius to
Frontend Freddy's boundary declaration, and WP06 was scoped to one field precisely so a
reviewer could audit that blast radius in a single small diff. Widening it to a second field
would have traded a readable contradiction for an unauditable one. The operative field for
routing is `avoidance-boundary`, which is now correct and reciprocal; `purpose` is descriptive
prose. Recommended as a follow-up mission, not a patch here.

### KI-3 — WP03 and WP04 passed review non-compliant with C-S7 — **process gap, fixed in WP07**

Both styleguides were approved at their own review gates while carrying two forbidden `suggests`
edges and missing two required ones. Two mechanisms let it through:

1. `extractor.py` mints DRG edges from bare `references:` path strings, so listing a peer
   artifact's path in `references` silently produces an edge — including edges the contract
   forbids.
2. `regenerate-graph` reports no error for an edge that is structurally valid but semantically
   wrong, so the regeneration step could not catch it either.

Corrected in WP07; the final `styleguide.graph.yaml` carries exactly the three C-S7 edges and
nothing else, verified above. Carried forward because the **mechanism** is unfixed: the next
styleguide author will hit the same trap, and no gate will tell them. A guard asserting
`references`-derived edges against the contract would close it.

### KI-4 — lane worktrees carry stale `kitty-specs/` copies — **process hazard**

Lane worktrees hold their own copies of the mission's planning artifacts, and those copies are
stale. `lane-d` in particular still carries a **superseded contract C-S8** with the wrong
`accessCheck` facts (the upstream "10.2 / deprecation warning / required in Drupal 12" claim).
Auditing delivered artifacts for fidelity against a lane copy would therefore "restore" a known
factual error into shipping guidance.

All planning artifacts cited in this report were read from the repository-root checkout
(`/Users/nicolas/Projects/spec-kitty/kitty-specs/drupal-dries-profile-01M28X69/`), never
from a lane. Any later reviewer must do the same.

---

## 9. Node delta (C-P5)

WP01's test could not assert an exact node delta — its prompt forbade frozen literals while the
contract asked for an exact count, a tension introduced during planning. Asserted here instead.

| Graph fragment | Nodes added | Nodes removed | Edges added | Edges removed |
|---|---|---|---|---|
| `agent_profile.graph.yaml` | **1** (`agent_profile:drupal-dries`) | 0 | 11 | 0 |
| `styleguide.graph.yaml` | **2** (`styleguide:drupal-conventions`, `styleguide:drupal-security-performance`) | 0 | 3 | 0 |
| `toolguide.graph.yaml` | **1** (`toolguide:drupal-review-checks`) | 0 | 0 | 0 |
| **Total** | **4** | **0** | **14** | **0** |

**Exactly 4 new nodes — 1 agent_profile, 2 styleguide, 1 toolguide. No unsanctioned fifth, and
nothing removed.** Corroborated on two independent surfaces: `pack-manifest.yaml` gains exactly
four constituents (`drupal-dries`, `drupal-conventions`, `drupal-security-performance`,
`drupal-review-checks`) and no others, and `doctor doctrine --json` moves the built-in pack's
profile count from **25** (repository-root checkout, at the mission's integration branch
`feat/drupal-dries-profile` @ `f31dcf115`) to **26** (lane-g) — a delta of exactly one
agent profile, with `valid_count` tracking `discovered_count` on both sides.

---

## 10. Outstanding work

- **NFR-003 (diff coverage ≥90%) is unverified by this package** and is not claimed met. It is
  enforced by the `ci-aggregate.yml` diff-cover gate and needs a CI run on the pull request.
- **F1, F2, F3, F4 are reported and not fixed**, per WP08's mandate to verify rather than
  patch. F1 is the only one touching a stated contract bar (T039's "every file must report at
  least 1"); F2–F4 are precision improvements. All four are one-line-to-two-line edits in the
  owning artifact and none blocks merge.
- **KI-1 and KI-3 warrant upstream issues** — a pre-existing quality-gate gap on a charter
  module, and a graph-minting mechanism that lets contract-forbidden edges pass review
  unremarked. Neither is this mission's to fix.

Nothing else is unfinished. The five deliverables, the two edits, and the three regenerated
graph fragments are complete, consistent, and coherent with each other.

---

## Post-merge review correction (2026-09-14)

This report was approved by the orchestrator without independent review. That gap was closed
afterwards by an independent Opus review of this document. **The verdict RELEASABLE holds** — every
load-bearing claim (14/14 anti-patterns, node delta, C-003, C-S6, C-S7, NFR-005 byte-identity,
C-006) was reproduced independently. Three claims below were wrong and are corrected here.

### KI-1 was WRONG — there is no broken gate, and no upstream issue is owed

This report claimed `src/charter/offering/drg/migration/extractor.py` fails the charter's mandated
`mypy --strict` and `ruff format --check` gates, and recommended filing an upstream issue. Both
halves are false, verified directly:

- **`ruff format`**: `extractor.py` is listed in `[tool.ruff.format].exclude` (`pyproject.toml:389`),
  as is `tests/doctrine/drg/migration/test_extractor.py` (`pyproject.toml:1510`). This is the
  documented shrink-only formatter-debt ratchet (#473/#531/#559), enforced by
  `tests/architectural/test_ruff_format_exclude_ratchet.py`. `ruff format --check .` — the exact
  command CI runs — **passes repo-wide on this branch**.
- **`mypy`**: no CI workflow runs mypy at all. `make typecheck` runs `mypy --strict` against exactly
  two files (`src/specify_cli/runtime/agent_commands.py`, `src/specify_cli/git/commit_helpers.py`),
  neither of which is `extractor.py`.

So KI-1's premise — "the next contributor inherits a red gate they did not cause" — does not hold.
This was over-alarm, not green-wash, but acting on it would have sent someone chasing a non-issue.

### KI-2 named the wrong field, and understated itself

The contradicting text is NOT in Frontend Freddy's `purpose`. It is at
`packs/built-in/agent_profiles/frontend-freddy.agent.yaml:90`, inside **`initialization-declaration`**.
That makes the finding MORE operative than recorded, not less: this report's mitigation was
"`purpose` is descriptive prose", which does not apply to the load-time declaration an agent actually
reads. An agent loading Freddy is told it owns anything running in a browser, while its own
`avoidance-boundary` now defers Drupal-native theming to Drupal Dries.

### Line counts

`drupal-conventions.styleguide.yaml` is **210** lines (the acceptance matrix's FR-006 row said 208).
`drupal-dries.agent.yaml` is **208** lines (§NFR-001 of this report said 209). Neither flips a
verdict.

### Also noted by the review

- `.kittify/command-skills-manifest.json` (commit `3d0455b3f`) rides this branch — unrelated CLI
  upgrade churn, not enumerated in NFR-007's blast-radius list. It will land in the PR and can be
  dropped if a mission-only diff is preferred.
- Contract C-S2's GIVEN names only `drupal-conventions` as carrying all 14 anti-patterns, while C-S3
  mandates the two-file split. The 9/5 delivery satisfies C-S3 and contradicts C-S2's literal text;
  the sensible cross-file reading was applied but the clause as written was unsatisfiable.
- The acceptance matrix carries rows for FR-001…FR-013 only — no rows for the 7 NFRs or 8
  constraints, including the explicitly-unclaimed NFR-003.
- KI-4 (stale lane `kitty-specs/` copies) is now moot: the worktrees have been removed.


## Post-review revision (maintainer adversarial-squad review of PR #4396)

The branch was revised after this report was first written. Where the text above conflicts
with this section, this section governs.

- **Rename.** `drupalling-dries` / "Drupalling Dries" became `drupal-dries` / "Drupal Dries", to match the
  README rule that specialist profiles are prefixed with the language/framework name
  (`java-jenny`, `node-norris`) and the sibling `drupal-*` artifacts. Mission slug, tests and graph ids follow.
- **Frontend Freddy (KI-2 resolved; NFR-007 corrected).** The `initialization-declaration` contradiction
  is fixed by deleting only "if it runs in a user's browser, it is my concern"; no Drupal wording is added
  to Freddy's load-time declaration. Freddy's `avoidance-boundary` clause is framework-generic
  ("framework-native theming layers ... deferred to the stack specialist for that framework, when one is active"),
  because Dries is filtered out of non-PHP catalogs (`catalog.py` `applies_to_languages`) and Freddy must not name
  a profile a JS-only project cannot resolve. The earlier statement that Freddy's whole diff lay inside
  `avoidance-boundary` was inaccurate for the original two-field commit; the row above is corrected.
  NFR-005 byte-identity was measured on charter context only, not on the profile body surface.
- **Anti-patterns.** The fourteen anti-patterns now live in each styleguide's `anti_patterns:` field
  (9 in `drupal-conventions`, 5 in `drupal-security-performance`); previously they were under `patterns:`.
- **Activation scope.** `yaml` removed from Dries's `applies_to_languages`; Drupal YAML remains covered by `file-patterns`.
- **Accessibility gate.** The `js-accessibility` gate is scoped to Drupal-native theming JS and cross-references
  `phpunit --group accessibility`; WCAG doctrine and generic component audits stay with Frontend Freddy.
- **Extractor test.** The frozen lineage count (4 -> 5) was replaced by non-rotting assertions.
- **C-S2.** The "unsatisfiable" reading above was overstated: the contract states all 14 must appear
  somewhere, not in one file. No contract edit is needed.
