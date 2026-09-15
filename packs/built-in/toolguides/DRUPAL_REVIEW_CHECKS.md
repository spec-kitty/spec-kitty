# Drupal Review Checks

Automated checks a reviewer should run — or verify the implementer has run — before approving Drupal
module or theme code changes. Each tool catches a different category of defect; no single tool
replaces the others, and a change that only passes the fast checks is not yet reviewable.

## Coding Standards

### phpcs (`Drupal` and `DrupalPractice`)

```bash
vendor/bin/phpcs --standard=Drupal,DrupalPractice .
```

**What passing means:** the diff matches Drupal's coding standards and avoids the common Drupal
API-misuse patterns the community sniffs for.
**Common failure:** a formatting violation (wrong indentation, missing docblock, line-length) reads
very differently from an API-misuse violation — treat them as two separate signals, not one.
**The two standards are not the same check.** `Drupal` enforces *formatting* — indentation, brace
placement, docblocks, naming conventions. `DrupalPractice` enforces *API misuse* — direct use of
`\Drupal::` static calls where dependency injection is expected, missing access checks, deprecated
patterns the formatting-only standard has no opinion on. A change can be `Drupal`-clean and still
fail `DrupalPractice`, and the two failures point a reviewer in different directions.

## Static Analysis

### PHPStan

```bash
vendor/bin/phpstan analyse
```

**What passing means:** clean at the project's configured level. The level is a project-specific
setting (`phpstan.neon`) — this guide does not assert one.
**Common failure:** a type-mismatch or undefined-method finding usually indicates a Drupal API was
called on the wrong entity/plugin interface, or a nullable return was used without a null check.

### drupal-check (deprecated API usage)

```bash
vendor/bin/drupal-check .
```

**What passing means:** the diff calls no deprecated Drupal core or contrib API.
**Common failure:** a deprecated-function finding is the single most consequential failure to fix
ahead of a Drupal major-version upgrade — deprecations left in place become hard breaks on the next
core update, so this check matters more than its "just a warning" tone suggests.

## Tests

Drupal's PHPUnit suite has three tiers, and they are not interchangeable. The mistake this section
exists to prevent is a reviewer accepting a unit test where a kernel test was needed — the canonical
failure being a unit test that mocks the entity type manager so heavily it asserts nothing about
Drupal at all.

| Tier | What it can do | Cost |
|------|----------------|------|
| Unit | No database, no container; pure logic (`UnitTestCase`) | Fast |
| Kernel | Bootstrapped container, a limited module set, database (`KernelTestBase`) | Moderate |
| Functional | Full site install, real HTTP requests via a browser-less client (`BrowserTestBase`) | Slow |

```bash
vendor/bin/phpunit --testsuite unit          # Unit
vendor/bin/phpunit --testsuite kernel        # Kernel
vendor/bin/phpunit --testsuite functional    # Functional
```

**Choosing the tier is the review question, not just running one.** Use Unit when the code under
test has no dependency on Drupal's service container, entity storage, or config system — pure
logic, value objects, helper functions. Reach for Kernel as soon as the code touches entity
storage, plugin discovery, or config — the moment a unit test needs to mock the entity type
manager, node storage, or the config factory to make the code path reachable, that mocking is the
signal the test belongs at Kernel instead: a heavily-mocked unit test can be made to pass while
asserting nothing true about how Drupal actually behaves. Reach for Functional only when the
behavior under test genuinely depends on routing, access control, or the rendered page — form
submission flows, permission-gated pages, multi-request user journeys.

Accessibility-tagged tests run as their own PHPUnit group:

```bash
vendor/bin/phpunit --group accessibility
```

## JavaScript

```bash
npm run test
npm run test:a11y
```

**What this verifies, and what it does not claim:** these commands verify the Drupal-native
theming JavaScript the implementer authored — `Drupal.behaviors`, library-declared assets attached
via a `*.libraries.yml` file. Running these tests is not a claim on generic browser-component
authorship; that territory remains Frontend Freddy's. A Drupal change that only touches
`Drupal.behaviors` and passes these checks has met its own gate without encroaching on Freddy's.

If the project has no `package.json`, there is no JavaScript gate to run — that is not a failure,
just an absent check.

## Environment

Every command above is written for direct execution. A containerized development setup prefixes
each one with its runner instead — `ddev drush cr`, `ddev composer audit`, `lando vendor/bin/phpunit`
— the command itself is unchanged.

## Supply Chain

```bash
composer audit
```

**What it catches:** known security advisories in Composer dependencies. Composer's
`post-install-cmd` and npm's `postinstall` hooks are the deny-by-default lifecycle-script surface
DIRECTIVE_051 targets — an advisory hit alongside an unexpected lifecycle script is a stronger
signal than either alone.

## Before Submitting

Mirrors the source guide's own pre-submission checklist:

- [ ] `vendor/bin/phpcs --standard=Drupal,DrupalPractice .` — code style clean
- [ ] `vendor/bin/phpunit` — tests pass
- [ ] `drush cr` — caches clear without error
- [ ] `drush updatedb` — database updates apply cleanly
- [ ] `composer audit` — no open security advisories

Stop at the first failure and feed back to the implementer. Do not proceed to the slower checks
while the cheap ones are red.

---

Adapted from amazee.io's [`drupal-agents-md`](https://github.com/amazeeio/drupal-agents-md)
(Vanilla variant), `AGENTS.md`, *Testing & Quality Assurance* and *Code Style and Standards*
sections.
