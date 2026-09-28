# Java Supply-Chain Install Safety

Ecosystem-specific mechanics for the `supply-chain-install-safety` tactic's
checklist in a Maven/Gradle project. The tactic states the ecosystem-neutral
checklist shape and evidence contract (registry authenticity, freshness,
install-time hook scripts, lockfile-driven reproducibility, incident/IoC
posture); this guide gives the exact commands and file names for the Java
stack. It builds on, and does not restate, the `dependency-hygiene` tactic's
Maven-specific pinning, BOM, and exclusion steps.

## Registry authenticity

Confirm the resolved artifact and version come from Maven Central (or an
organization's approved private repository/mirror) and not an unexpected
repository.

```bash
mvn dependency:tree                 # confirm the resolved artifact coordinates
mvn help:effective-settings         # confirm the configured repositories match policy
mvn help:effective-pom              # confirm which repositories this module actually resolves from
```

`mvn dependency:tree` does not show which repository each artifact resolved
from — use `help:effective-settings`/`help:effective-pom` for that.

## Freshness

The Maven Central search API does return a `timestamp` field per artifact
version (`https://search.maven.org/solrsearch/select?q=g:<groupId>+AND+a:<artifactId>+AND+v:<version>`),
so a first-seen timestamp is available, just not as a single well-known
per-version endpoint the way PyPI's JSON API is. Query it, or use the
repository search UI or the artifact's own release notes, to confirm a
newly-added or upgraded version is not suspiciously new during a known
active-incident window, and record what was checked.

## Install-time hook scripts

Maven and Gradle do not run arbitrary install-time hook scripts the way
npm's lifecycle scripts do, but an annotation processor, a custom Maven
plugin, or a Gradle build-script dependency executes at build time with the
same risk profile. Treat a new build-time plugin or annotation processor
dependency as equivalent to an install-time hook script and require the same
explicit, justified allowlisting before accepting it.

## Lockfile-driven reproducible installs

Maven and Gradle need different mechanics here — Maven does not read a
`gradle.lockfile` or `verification-metadata.xml`, and there is no
resolve-from-committed-lock-alone verification command in Maven the way
Gradle's lockfile machinery provides.

**Maven**: pin every direct dependency version explicitly via
`dependencyManagement` (see `dependency-hygiene`), and enforce checksum
verification on every resolve so a download that does not match the
checksum the repository publishes fails the build instead of installing
silently:

```bash
mvn -C dependency:resolve      # -C / --strict-checksums: fail the build if a checksum does not match
```

Maven's `checksumPolicy` can also be set to `fail` per-repository in
`settings.xml`/`pom.xml` so the strict check applies to every build, not
just an explicit `-C` invocation. This catches transfer corruption and a
mismatch against the checksum the *same* repository serves — it does
**not** defend against a substituted artifact on a compromised repository
or mirror, because a compromised source can serve a matching checksum for
the substituted artifact. For pinned-hash or signature integrity against
that threat, use a verify plugin instead or in addition — for example a
PGP-signature-verification plugin, or a checksum plugin that checks
against hashes committed to the repository rather than hashes fetched
from the same source being verified.

**Gradle**: use an explicit dependency lockfile plus checksum-verification
metadata for a build that must reproduce byte-for-byte:

```bash
gradle dependencies --write-locks                       # commit gradle.lockfile — only persists resolution for configurations with dependency locking enabled
gradle --write-verification-metadata sha256 help         # commit verification-metadata.xml (run against any task, e.g. help)
```

`--write-locks` is a no-op unless dependency locking is enabled in the
build script first — `dependencyLocking { lockAllConfigurations() }` (or
locking specific configurations individually); without that, there is no
locked configuration for `--write-locks` to persist.

Review lockfile/verification-metadata diffs the same way `pom.xml`/
`build.gradle` diffs are reviewed — a lockfile-only change can still
introduce a new transitive dependency or resolve to a different version.

## Checksum verification summary

Gradle's `--write-verification-metadata sha256` compares a download
against hashes committed in the repository, so it also catches a
substituted artifact from a compromised repository or mirror. Maven's
`-C`/`--strict-checksums` (or a repository-level `checksumPolicy: fail`)
plus pinned versions via `dependencyManagement` gives fail-closed
checksum verification at resolve time, but only against the checksum
the *same* repository serves — Maven has no separate "verification
metadata" file compared against committed hashes, so this is not the
same guarantee as Gradle's. For that stronger guarantee, add a
signature- or committed-checksum-verification plugin.

## Incident/IoC posture

Watch for class-level indicators of compromise: an unexpected network call
from a build-time plugin or annotation processor, credential/token
exfiltration attempts, or a dependency substitution attack via a compromised
mirror. Cite the CAS/vendor incident feed consulted; do not hardcode a
specific incident package/version list here.
