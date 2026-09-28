---
affected_files: []
cycle_number: 2
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T13:01:00Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review, cycle 2: changes requested (narrow)

**Reviewer:** reviewer-renata (claude). **Verdict:** reject. Only a few lines need to change. Everything else in cycle 1 is resolved.

## Resolved (keep)
- DIRECTIVE_051: the two restored integrity rules ("adverse result ... never silently accepted; requires explicit operator acknowledgment" and "Blanket enablement of install-time hook scripts is a violation of this directive, not a valid workaround") read naturally and bind the reader. They are not contorted: "install-time hook scripts" is the term `intent` (3) itself defines. Compared line by line with the base, nothing is weaker. Node LTS moved to the JS toolguide as FR-026 requires.
- uv `--locked`/`--frozen`, the `pip index versions` removal, `--extra-index-url` + `explicit = true` + `first-index`, `--generate-hashes`, `poetry sync`, the gpg/go-offline removals, `dependency:tree` wording, the Maven Central timestamp, pnpm `--ignore-scripts`/`onlyBuiltDependencies` (valid in pnpm 10 `pnpm-workspace.yaml`), Yarn classic/Berry flags: all verified against the installed tools.
- Tests are non-vacuous. Weakening the blanket rule and reverting `uv sync --locked` to `--frozen` each go red.

## Required fixes (consumer-shipped security guidance must not overclaim)

### 1. JAVA_SUPPLY_CHAIN.md overstates what Maven `-C` guarantees
- The "Checksum verification summary" says `-C`/`checksumPolicy: fail` "gives the same fail-closed guarantee" as Gradle verification metadata. That is false. Maven's strict checksums compare a download against the `.sha1`/`.md5` that the **same repository** serves. This catches transfer corruption, but a compromised repository or mirror serves matching checksums. Gradle's `verification-metadata.xml` compares against hashes **committed in the repo**. These are different guarantees.
- The Maven lockfile paragraph says the same thing: "so a mutated or substituted artifact fails the build". Fix: say that `-C` catches transfer corruption or mismatch against the checksums the repository publishes, and that it does not defend against a substituted artifact on a compromised repository. For pinned-hash or signature integrity, name a verify plugin (for example a PGP-verify plugin, or a checksum plugin with committed checksums). Update the toolguide yaml `summary` ("checksum verification") so it does not imply parity.

### 2. PYTHON_SUPPLY_CHAIN.md drift gate defeats itself
- `uv lock && uv sync --locked  # fails the build if uv.lock is out of date`: running `uv lock` first rewrites a stale lock, so `--locked` then always passes. The CI drift gate should be `uv sync --locked` alone, or `uv lock --check` (verified in `uv lock --help`). Keep `uv lock` as the separate developer step that refreshes the lock. The same applies to `poetry lock && poetry sync` if it is presented as a gate: `poetry check --lock` is the check.

### 3. Gradle `--write-locks` precondition (small)
- `gradle --help`: "--write-locks  Persists dependency resolution for **locked configurations**". It does nothing unless dependency locking is enabled in the build script (`dependencyLocking { lockAllConfigurations() }`). Say so next to the command.

## Non-blocking
- JS guide, Yarn Berry: "disable dependency scripts globally and allowlist per-package instead" gives no allowlist mechanism. Either name the one you have verified (`dependenciesMeta` in package.json) or drop "allowlist per-package".
- `pip download -v` shows the artifact URL (files host). `-vv` also shows the index page fetched. Consider `-vv`.
- `_PILLAR_TERMS` counts term mentions, which will keep pressuring the doctrine wording. The current wording is fine, so I am not requiring a change. A future hardening could count the enumerated pillar statements `(1)`..`(5)` in `intent` instead.

Keep the RED/GREEN discipline: add pins (for example, no "same fail-closed guarantee" wording; no `uv lock && uv sync --locked` on one line; `lockAllConfigurations` or `dependencyLocking` mentioned) before fixing.
