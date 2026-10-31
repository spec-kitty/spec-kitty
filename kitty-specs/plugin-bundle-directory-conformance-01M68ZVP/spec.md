# Mission Specification: Plugin bundle directory conformance

**Mission Branch**: `issue-6479-plugin-bundle-directory-conformance`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "Issue #6479 — `spec-kitty plugin build` bundles fail current directory requirements (Claude bin/ + hooks path + gitignored source, Codex/OpenAI manifest fields, Copilot schema)"

**Issue**: spec-kitty/spec-kitty#6479 (P1, `domain:ci`; operational triage: `triage:needs-revision`, split per target — defects stay Bugs, new listing capability becomes Features)

## Problem

`spec-kitty plugin build --target claude-code|codex` writes bundles that the
directories the plugin is planned for (spec-kitty/spec-kitty-internal-plugins#3)
would reject or degrade, and the plan-level Copilot/VS Code projection writes a
manifest that no Agent Plugins 1.0.0 client recognises. Grounded on
`dfe9efb0e8` (4.0.0rc8), reproduced by building both targets:

- the Claude bundle stages a top-level `bin/spec-kitty-wrapper(.cmd)`; Claude.ai
  and Cowork refuse plugins that contain a top-level `bin/`;
- the Claude manifest redeclares the host-default `hooks/hooks.json`;
- no manifest of any target carries `homepage`, `repository` or `license`, and
  the Claude marketplace entry points at the `.gitignore`d `dist/` tree;
- the Codex manifest's `version` is PEP 440 (`4.0.0rc8`), `skills` is `skills/`
  without the `./` prefix, `interface.shortDescription` is 34 characters under a
  wrong 120-character internal guard, and none of the OpenAI listing fields
  (`longDescription`, `developerName`, category/capabilities URLs,
  `privacyPolicyURL`, `termsOfServiceURL`, `defaultPrompt`, `logo`,
  `composerIcon`) are emitted;
- the Copilot/VS Code projection emits `version: 0.0.0`, an unknown
  `distribution_target` key, no `$schema`, and a `"(staging bundle)"` description.

## Scope boundary

In scope: the in-repo bundle builders and the manifests they generate, plus the
test surface that pins the directory requirements.

Out of scope (tracked, not silently dropped — every item is named in the PR's
`## Deferred` section with its reason and owner):

- marketplace hosting (a plugin-side product call: the catalog must point at a
  committed or released location, which needs a hosting decision);
- bundling the doctrine/charter skills into the Claude bundle (new capability,
  not a defect; needs a decision on which doctrine tier ships);
- the CI validator pin (`@anthropic-ai/claude-code@2.1.270` predates the
  directory fields) and the Codex/Copilot validator + release attestation work,
  which the operator triage routes to #3535.

## User Scenarios & Testing

### User Story 1 - A directory reviewer can install the Claude bundle (Priority: P1)

A plugin-directory reviewer drops the `claude-code` build output into a
Claude.ai/Cowork submission. Today it is refused for its top-level `bin/`. After
this mission the bundle contains only `skills/`, `agents/`, `hooks/` and
`.claude-plugin/`, and its manifest names the project's homepage, repository,
license and SemVer version.

**Why this priority**: the top-level `bin/` is a hard refusal, not a degradation.

**Independent Test**: build the bundle through `spec-kitty plugin build --target
claude-code` and assert the output tree and manifest against the pinned
requirements.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** `spec-kitty plugin build --target
   claude-code` runs, **Then** the bundle tree contains no top-level `bin/`
   directory and no `bin/spec-kitty-wrapper*` file.
2. **Given** the same build, **When** the manifest is parsed, **Then** it equals
   the same bundle's positive control (name/version/description present) and
   carries `homepage`, `repository`, `license: MIT` and a SemVer `version`.

### User Story 2 - OpenAI/Codex directory accepts the manifest (Priority: P1)

An OpenAI plugin-directory reviewer validates the `.codex-plugin/plugin.json`
build output. Today the version is not SemVer, the short description is over the
30-character limit, the `skills` path lacks `./`, and the listing fields are
absent. After this mission the manifest satisfies every pinned field limit and
ships the square brand images it references.

**Why this priority**: each defect is an individual listing rejection reason.

**Independent Test**: build `--target codex`, parse the manifest, assert each
pinned limit and the presence of every referenced asset in the bundle.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** `spec-kitty plugin build --target codex`
   runs, **Then** `.codex-plugin/plugin.json` carries a SemVer `version`,
   `skills: "./skills/"`, `interface.shortDescription` of at most 30 characters,
   and every required `interface` listing field.
2. **Given** that manifest, **When** each declared image path is resolved inside
   the bundle, **Then** it exists, is square, at least 48px, and under 5 MiB.
3. **Given** the same manifest, **When** the forbidden-key guard runs, **Then**
   `hooks` and `agents` are still absent.

### User Story 3 - Copilot/VS Code reads a real Agent Plugins manifest (Priority: P2)

A VS Code or Copilot client reads the projected `plugin.json`. Today the
manifest has no `$schema`, so the client falls back to the legacy format, and it
carries an unknown `distribution_target` key. After this mission the manifest
declares the pinned Agent Plugins 1.0.0 `$schema` and contains only keys that
schema defines.

**Why this priority**: the `$schema` selects the format; without it the client
silently uses a different, weaker path.

**Independent Test**: project the Copilot and VS Code bundles, assert the exact
`$schema` constant and that the key set is a subset of the pinned closed schema,
with a positive control proving the key-set probe can see a real key.

**Acceptance Scenarios**:

1. **Given** a projected Copilot bundle, **When** its manifest is parsed,
   **Then** `$schema` is exactly the pinned Agent Plugins 1.0.0 URL and
   `distribution_target` is absent.
2. **Given** the same manifest, **When** it is compared with the pinned closed
   key set, **Then** every key is allowed and `version` is SemVer, not `0.0.0`.

### Edge Cases

- A PEP 440 pre-release/dev/local version must still produce a SemVer string; an
  unparseable version must fall back rather than raise at build time.
- The hooks file stays staged and valid; only the redundant manifest
  redeclaration goes away, so a hooks-carrying bundle still loads its hooks.
- A bundle rebuilt twice must be byte-identical and must not churn node mtimes
  (the existing idempotency invariant).
- Removing `bin/` must not leave dead code or a dangling doc reference.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Claude bundle has no top-level `bin/` | As a plugin-directory reviewer, I want the Claude bundle to contain no top-level `bin/` so the submission is not refused. | High | Open | [build] | no |
| FR-002 | Claude manifest does not redeclare the default hooks file | As a Claude Code user, I want the manifest to leave hooks discovery on its documented default so no path without the `./` prefix is emitted. | High | Open | [build] | no |
| FR-003 | Every manifest carries homepage, repository and license | As a directory reviewer, I want homepage, repository and `license: MIT` on every generated manifest so the listing can resolve its links and its license. | High | Open | [build] | no |
| FR-004 | Codex manifest meets the pinned OpenAI limits | As an OpenAI directory reviewer, I want the Codex manifest to carry SemVer, `./`-prefixed component paths, a 30-character short description and the required `interface` listing fields so the submission validates. | High | Open | [build] | no |
| FR-005 | Codex bundle ships its referenced images | As an OpenAI directory reviewer, I want every image the manifest declares to exist inside the bundle as a square asset of at least 48px, so the listing renders. | High | Open | [build] | no |
| FR-006 | Copilot/VS Code emit an Agent Plugins 1.0.0 manifest | As a VS Code or Copilot client, I want a root `plugin.json` with the pinned `$schema` and only schema-defined keys so the client reads the portable format. | High | Open | [build] | no |
| FR-007 | One SemVer projection for plugin versions | As a maintainer, I want a single PEP 440 to SemVer projection used by every target so no manifest ships a non-SemVer version. | Medium | Open | [build] | no |
| FR-008 | Conformance suite runs through the build entry points | As a maintainer, I want the directory requirements pinned by tests that call `plugin build` and the projection API, so a regression in wiring fails the suite. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic bundles | Two consecutive builds of the same target produce a byte-identical tree and report no staged effect on the second run (the existing idempotency invariant). | Reliability | High | Open |
| NFR-002 | Pinned field limits | Every declared manifest field stays inside the pinned external limit (shortDescription ≤30, displayName ≤30, longDescription ≤4000, developerName ≤80, defaultPrompt ≤3 items of ≤128 chars, images ≤5 MiB). | Compatibility | High | Open |
| NFR-003 | No build-time network access | Generating a bundle performs no network call; every declared URL and asset is a static constant or a file shipped in the package. | Reliability | High | Open |
| NFR-004 | Clean deletion | Removing the wrapper leaves no unreferenced module, test file or documentation section behind. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No marketplace hosting change | The catalog's hosting location is a plugin-side product call; this mission must not invent a release branch or a second repository. | Business | High | Open |
| C-002 | No CI gate change | Validator pins, extra directory validators and release attestation are routed to #3535; this mission must not weaken or re-pin an existing gate. | Technical | High | Open |
| C-003 | Staging and consent machinery unchanged | The write path keeps its prepared-then-applied staging model, confined output and ownership manifest. | Technical | High | Open |
| C-004 | Doctrine skills stay out | Which doctrine tier ships in the bundle is undecided; this mission must not add a second skill source. | Business | Medium | Open |

### Key Entities

- **Bundle manifest**: the per-target JSON declaration (`plugin.json`,
  `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`) that names the
  plugin identity, version, links and component paths.
- **Directory requirement set**: the pinned field limits and required fields per
  target, carried once in the implementation and asserted by the conformance
  suite.
- **Bundled asset**: a file (today: the square brand logo) that a manifest
  declares by `./`-relative path and that must therefore exist inside the bundle.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Both `plugin build` targets and both plan-level projections produce manifests that pass the conformance suite, with zero fields outside their pinned limits. — [build] · no-op passable: no
- **SC-002**: The Claude bundle tree contains zero top-level `bin/` entries, proven on the same fixture whose positive control finds a real top-level directory. — [build] · no-op passable: no
- **SC-003**: Every image path a manifest declares resolves inside its own bundle, is square, at least 48px and under 5 MiB. — [build] · no-op passable: no
- **SC-004**: The existing plugin-bundle, projection and wrapper-replacement suites plus the new conformance suite pass, and a second build is byte-identical. — [ratchet] · no-op passable: no
