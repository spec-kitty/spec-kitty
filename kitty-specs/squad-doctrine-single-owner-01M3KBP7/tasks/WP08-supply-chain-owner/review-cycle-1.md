---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T11:39:46Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review, cycle 1: changes requested

**Reviewer:** reviewer-renata (claude). **Verdict:** reject. The fixes are narrow. Structure, ownership, tests and the expected-red list are all good. What blocks approval is the normative force of DIRECTIVE_051 and the command accuracy of the new toolguides, which ship to consumers as security guidance.

## What passed (keep as is)
- Red to green: at fbfdb03c the test gives 11 failed and 4 passed. At head it gives 15 passed. Later edits to the test file were formatting only.
- Mutations are caught: deleting a pillar fails (found 0), restating a pillar fails (found 2), an `npm` token in the tactic fails, and a JS guide with headings only fails.
- Scope: WP08's commits touch only owned_files (plus status). There are no prompt, guideline, profile, graph, manifest or default.yaml edits, no `#NNNN` references, and no new version numbers.
- DoctrineService (lane-local) loads DIRECTIVE_051 (enforcement `required`), both tactics and all three toolguides.
- Test suites: `test_supply_chain_single_owner.py` plus `test_supply_chain_security_layer.py` give 24 passed. The filtered doctrine suite gives 394 passed and 7 skipped.
- Expected-red: exactly the declared regeneration tests are red (`test_shipped_graph_is_fresh_and_byte_identical`, `test_regenerate_leaves_authored_files_byte_unchanged`, `regenerate-graph --check`).
- The Java toolguide is justified. `java-jenny.agent.yaml` binds 051 to Maven/Gradle.

## Required fixes

### 1. DIRECTIVE_051 lost outcome rules (weakening, C-005)
The base `integrity_rules` said three things:
- an unexpected registry, mirror or namespace is never silently accepted and needs explicit operator attention;
- blanket lifecycle-script enablement is a *violation*, not a workaround;
- the base also required that the freshness signal be acknowledged.

The new rule "None of the five controls may be silently skipped" only forbids *skipping the check*. It no longer forbids *accepting an adverse result*. These are rules, and rules belong in the directive: a tactic's `failure_modes` is not normative.

Add one or two integrity rules that do not repeat the counted pillar phrases. For example:
- "An adverse result from any control in `intent` (unexpected registry or namespace, suspiciously new version, un-allowlisted install-time hook, lockfile drift, incident match) is never silently accepted; it requires explicit operator acknowledgment before the change proceeds."
- "Blanket enablement of install-time hook scripts is a violation of this directive, not a valid workaround."

### 2. PYTHON_SUPPLY_CHAIN.md accuracy
- `uv sync --frozen  # ... fails on drift` is wrong. `--frozen` installs from `uv.lock` *without* checking that it is up to date. `--locked` is the mode that errors when the lock is stale. Use `uv sync --locked` as the CI/drift gate. `--frozen` may be mentioned separately, for "install exactly the lock".
- `pip index versions <package>` neither confirms the resolved index nor shows timestamps, and it is experimental. It is listed under both "registry" and "freshness". For the index, use `pip config list` and the `index-url` settings (or `pip download --no-deps -v`, whose output shows the URL used). For freshness, keep the PyPI JSON `upload_time` query.
- Index pinning, the explicit WP ask, is missing its main hazard: dependency confusion through `--extra-index-url` or multiple indexes. Say to avoid `--extra-index-url` for private names, or to scope them with uv `[[tool.uv.index]]` and `explicit = true`, and keep uv's default `first-index` strategy.
- Hashes: say how they are produced (`uv pip compile --generate-hashes`, or `pip-compile --generate-hashes`), and note that `uv.lock` and `poetry.lock` already record hashes.
- Minor: `poetry install --sync` is deprecated in Poetry 2 in favour of `poetry sync`. Mention both.

### 3. Java toolguide accuracy
- `java-supply-chain.toolguide.yaml` `commands:` lists `mvn verify -Dgpg.skip=false`. That command *signs the project's own artifacts* with maven-gpg-plugin; it verifies nothing about dependencies. Remove it, or replace it with a real dependency-integrity check such as `mvn --strict-checksums` (`-C`). If you want signature verification, use a PGP-verify plugin.
- In JAVA_SUPPLY_CHAIN.md the lockfile block has `mvn -o dependency:go-offline  # verify the build resolves from the committed lock/metadata alone`. Maven does not read `gradle.lockfile` or `verification-metadata.xml`, and `-o` contradicts `go-offline`, which exists to download. Split Maven from Gradle: Maven gets pinned versions plus `-C`/strict checksums; Gradle gets `--write-locks` and `--write-verification-metadata sha256` (run with a task, for example `gradle --write-verification-metadata sha256 help`).
- The summary claims "checksum verification" but only Gradle covers it. Add the Maven equivalent as above.
- `mvn dependency:tree` does not show repositories, so drop "and repositories" from its comment (`help:effective-settings` and `help:effective-pom` do show them).
- Minor: the Maven Central search API does return a `timestamp` per artifact version, so "does not publish a first-seen timestamp API" overstates the gap.

### 4. JAVASCRIPT_SUPPLY_CHAIN.md (moved text, but this toolguide now owns it)
- `pnpm config set enable-pre-post-scripts false` controls pre/post hooks of the project's *own* `pnpm run` scripts, not dependency lifecycle scripts. For dependencies, use `ignore-scripts=true` or pnpm's `onlyBuiltDependencies` allowlist, which also matches the "scoped allowlist" rule.
- `yarn install --frozen-lockfile` applies to Yarn classic. Yarn Berry uses `yarn install --immutable`. Name both.

## Non-blocking notes
- The test does not check that the JS commands are present: removing `npm ci` and `--frozen-lockfile` still passes. Consider asserting `npm ci` and `--ignore-scripts`, and add a load assertion for the Java toolguide.
- `dependency-hygiene` still has "Restrict dependency resolution to approved registries" and a `uv lock` pin example. These are build-config hygiene, so they are acceptable, but its `when:` text could cite the `javascript-supply-chain` toolguide by id, as the WP asked.
