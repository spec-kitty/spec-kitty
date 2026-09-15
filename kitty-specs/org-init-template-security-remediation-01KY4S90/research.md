# Research: Org Init Template Security Remediation

## Decision: Skip GIT_TOKEN on template path (not global allowlist)

**Rationale**: Spec C-003. Template resolve is the newly exposed user-supplied URL surface. Adding `inject_token=False` for that construction site is minimal and preserves existing authenticated clone behaviour for pack/source fetchers that still need `GIT_TOKEN`.

**Alternatives**: Trusted-host allowlist — more config surface, deferred; remove injection globally — out of scope / breaks private pack fetch.

## Decision: Skip symlink entries

**Rationale**: Simplest fail-safe against `copy2` following link→host file. Doctrine templates should ship real files.

**Alternatives**: Copy as symlinks with `follow_symlinks=False` and reject absolute/escaping targets — more code; skip is enough for FR-003/004.

## Decision: Reject path tokens (no rename engine)

**Rationale**: Spec C-003. Contents still substitute; names with `{{…}}` fail closed with structured rule id.

**Alternatives**: Full path substitution — larger behaviour change than review asked for.

## Decision: Reject http:// and git://

**Rationale**: Align classify/parse with HTTPS/SSH contract; fail before fetch.

## Decision: Move-aside-then-swap for --force

**Rationale**: Prevents empty window where prior pack is deleted and new install fails.

## Decision: Single-pass leftover scan

**Rationale**: Collect content leftovers during substitute write pass; path-token scan is separate (names only).
