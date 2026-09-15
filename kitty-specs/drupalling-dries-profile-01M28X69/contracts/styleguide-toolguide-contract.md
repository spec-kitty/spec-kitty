# Contract: Drupal Styleguides & Review-Checks Toolguide

**Mission**: `drupalling-dries-profile-01M28X69`

Loader and content contracts for the four guidance artifacts. Schema conformance is necessary but
not sufficient — a schema-valid file full of wrong Drupal advice passes every structural check, so
the content clauses below carry equal weight.

---

## C-S1 — Both styleguides load

**Requirement**: FR-006

```
GIVEN  drupal-conventions.styleguide.yaml and drupal-security-performance.styleguide.yaml
WHEN   the styleguide repository loads the built-in pack
THEN   both are present, keyed by id
AND    both validate against the styleguide schema
AND    neither is reported as a load failure
```

Fields required by the peer shape (`python-conventions`, `java-conventions`): `schema_version`,
`id`, `title`, `scope`, `applies_to_languages`, `principles`, `patterns`, plus `tooling` and
`references` where applicable.

---

## C-S2 — All 14 source anti-patterns are carried

**Requirement**: FR-008, SC-003

```
GIVEN  drupal-conventions.styleguide.yaml
WHEN   its patterns collection is read
THEN   each of the 14 numbered "Never Do This" entries from the source guide is represented
AND    each carries both a bad_example and a good_example
AND    any omission is recorded with an explicit reason
```

The 14, for the implementer's checklist:

| # | Anti-pattern |
|---|---|
| 1 | `\Drupal::` static calls in services, controllers, plugins |
| 2 | Direct database queries where Entity Query suffices |
| 3 | `\|raw` in Twig |
| 4 | Monolithic `hook_form_alter()` |
| 5 | Configuration stored in state |
| 6 | `#markup` with unsanitized input |
| 7 | Entity queries without `accessCheck(TRUE)` |
| 8 | Hardcoded entity IDs, user IDs, paths |
| 9 | `hook_views_data()` without table aliases |
| 10 | Ignored cacheability metadata |
| 11 | `settings.php` committed with credentials |
| 12 | Deprecated procedural functions (`node_load()`) |
| 13 | Global `$_GET` / `$_POST` / `$_SERVER` |
| 14 | Business logic in `.module` files |

Entries 3, 6, 7, 10, 11 are security- or performance-shaped and may live in
`drupal-security-performance` instead; the contract is that all 14 appear **somewhere** in the
delivered styleguides, not that they all appear in one file.

---

## C-S3 — The split is a real boundary

**Requirement**: FR-006, I5.2

```
GIVEN  both styleguides
WHEN   their patterns are compared
THEN   no pattern name appears in both
AND    each file stays within roughly 150-200 lines
AND    conventions answers "how do I write this?"
       while security-performance answers "how do I keep it safe and fast?"
```

A split that merely halves a long file by line count would satisfy the size goal and defeat its
purpose. The disjointness clause is what makes it a boundary.

---

## C-S4 — The toolguide descriptor matches its body

**Requirement**: FR-007

```
GIVEN  drupal-review-checks.toolguide.yaml and DRUPAL_REVIEW_CHECKS.md
WHEN   the descriptor is loaded
THEN   guide_path resolves to the committed body file
AND    every command in the descriptor's commands list appears in the body
AND    every gate command in the body appears in the descriptor
```

Descriptor shape follows `maven-review-checks.toolguide.yaml`: `schema_version`, `id`, `tool`,
`title`, `guide_path`, `applies_to_languages`, `summary`, `commands`.

---

## C-S5 — Commands are environment-agnostic

**Requirement**: C-004, R-008

```
GIVEN  the toolguide body and the profile's self-review protocol
WHEN   their commands are read
THEN   no command is prefixed for a specific environment (no bare `ddev`/`lando` prefix)
AND    exactly one adaptation note explains how containerized setups prefix them
```

---

## C-S6 — No invented thresholds

**Requirement**: NFR-006, R-007

```
GIVEN  every delivered artifact
WHEN   its quality gates are read
THEN   no PHPStan level is asserted
AND    no coverage percentage or mutation score is asserted
AND    each named command traces to the source guide's Code Quality Tools
       or Before Submitting Code sections
```

The source names the commands and specifies no level. Supplying one would be a fabrication
presented as guidance, which is exactly what NFR-006 forbids.

---

## C-S7 — Styleguide edges follow the peer precedent

**Requirement**: FR-006, R-002

```
GIVEN  the regenerated styleguide graph fragment
WHEN   edges from styleguide:drupal-conventions are queried
THEN   a suggests edge targets agent_profile:drupalling-dries
AND    a suggests edge targets toolguide:drupal-review-checks
AND    styleguide:drupal-security-performance likewise suggests the profile
```

Mirrors `styleguide:java-conventions`, which suggests `agent_profile:java-jenny`,
`toolguide:maven-review-checks`, and its relevant directives.

---

## C-S8 — Drupal correctness spot-checks

**Requirement**: NFR-006, SC-007

Content assertions a reviewer can verify against official Drupal documentation. These exist
because schema validity says nothing about whether the advice is true:

| Claim | Must state |
|-------|-----------|
| `accessCheck(TRUE)` | Must be set explicitly on every entity query. Implicit access checking was deprecated in Drupal **9.2.0** and throws an error from Drupal **10.0.0** (change record [node/3201242](https://www.drupal.org/node/3201242)). On this profile's 10.x/11.x baseline an unchecked query is already a fatal error — NOT a deprecation warning, and NOT something deferred to Drupal 12. The upstream AGENTS.md states this incorrectly at its line 701; do not copy it. |
| Config vs state | Config for structured exportable settings; state for ephemeral/transient data |
| Twig escaping | Auto-escaping is the default; `\|raw` defeats it; use `#type => 'processed_text'` or `check_markup()` for intentional HTML |
| Dependency injection | `\Drupal::` acceptable only in `hook_` functions in `.module` files, and even there delegation is preferred |
| Cacheability | Render arrays depending on data must declare `#cache` tags, contexts, and max-age |
| Test tiers | PHPUnit unit, kernel, and functional tiers are distinct, with different bootstrap costs and capabilities |

**Sampling rule for SC-007**: a reviewer samples ten claims at random; all ten must trace to the
source guide or official Drupal documentation.
