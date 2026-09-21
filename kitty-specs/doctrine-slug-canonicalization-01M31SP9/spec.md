# Mission Specification: Canonical doctrine artifact slug convention

**Mission Branch**: `fix/doctrine-slug-canonicalization`
**Created**: 2026-09-21
**Status**: Draft
**Input**: Fixes #4832 + #4833 (P1); keeps #4834/P2-6 as an independent correctness fix. Design of record: research+design comments on #4832, #4833, the convergence note on epic #2519, and the post-plan brownfield adversarial point-cut (see `research.md` § Adversarial evidence). **Scope note (post-plan revision):** the filename migration/self-heal was **dropped** — the manifest-driven validator (FR-004) makes existing SCREAMING-filename repos validate green *without* renaming, and a rename would risk silently dropping stem-keyed directive activations (#3816 class). Go-forward only.

## User Scenarios & Testing *(mandatory)*

The actor throughout is a **Spec Kitty operator (or an agent acting for them) authoring project-tier doctrine** in a consumer repository. Today the `charter new` scaffolder, the project-registration engine, and the bundle validator each derive an artifact's on-disk slug differently, so `charter bundle validate` rejects the engine's own records — the field report needed three rounds of manual file surgery to reach a clean state.

### User Story 1 - Authoring a project-tier directive validates cleanly (Priority: P1)

An operator scaffolds a project directive with `charter new directive LOVE_THY_ENEMY`, fills it in, activates it, and runs `charter bundle validate`. It passes with zero errors and no manual renaming.

**Why this priority**: This is the deterministic P1 (#4832). Every project that authors a project-tier directive hits two bundle-validate errors per directive today; without this, project-tier directive authoring is unusable end to end.

**Independent Test**: Scaffold → register → `charter bundle validate` exits 0. Fully testable without the migration or the profile path.

**Acceptance Scenarios**:

1. **Given** a repo with no project doctrine, **When** the operator runs `charter new directive LOVE_THY_ENEMY`, **Then** the artifact file is written as `love-thy-enemy.directive.yaml` with `id: LOVE_THY_ENEMY` preserved inside the body.
2. **Given** a scaffolded-and-activated project directive, **When** the operator runs `charter bundle validate`, **Then** it reports zero errors (no "has no provenance sidecar", no "references non-existent artifact").
3. **Given** any directive id matching `^[A-Z][A-Z0-9_-]*$`, **When** the scaffolder, the registration engine, and the validator each derive its slug, **Then** all three produce the identical slug.

---

### User Story 2 - Activating a project profile (or procedure) validates cleanly (Priority: P1)

An operator activates a project-local agent profile (the documented `charter activate agent-profile` workflow) or registers a project procedure, then runs `charter bundle validate`. It passes.

**Why this priority**: This is the second deterministic P1 (#4833). The registration engine writes a provenance sidecar for five kinds but the validator recognises only three, so activating a project profile — or registering a project procedure — trips an "unknown kind" error on the engine's own honest record.

**Independent Test**: Activate a project agent profile via the real engine → `charter bundle validate` exits 0 with no "unknown kind" error. Repeat for a project procedure.

**Acceptance Scenarios**:

1. **Given** a project that activates a project agent profile, **When** the operator runs `charter bundle validate`, **Then** no "Provenance file has unknown kind 'agent_profile'" error is reported.
2. **Given** a project that registers a project procedure, **When** the operator runs `charter bundle validate`, **Then** no "unknown kind 'procedure'" error is reported.
3. **Given** a provenance sidecar with no backing artifact on disk (genuine corruption), **When** the operator runs `charter bundle validate`, **Then** it still reports a "references non-existent artifact" error — corruption detection is not weakened.

---

### User Story 3 - Existing SCREAMING-filename directives validate cleanly, unchanged (Priority: P2)

A repo that already authored project directives the old way (SCREAMING-case filenames) runs `charter bundle validate` and it passes — **with no file renaming and no manual sidecar deletion** — because the validator resolves registered artifacts through the synthesis manifest (which already records the kebab slug) rather than re-parsing the filename.

**Why this priority**: This is the field-report's own scenario. The post-plan brownfield squad established that the manifest-driven validator (FR-004) fixes existing repos as-is; a filename migration is unnecessary (cosmetic) and would risk silently dropping stem-keyed directive activations. Delivering the green outcome *without* mutating authored source is strictly safer.

**Independent Test**: Seed a repo with an on-disk `LOVE_THY_ENEMY.directive.yaml` registered via the real engine (manifest slug `love-thy-enemy`), run `charter bundle validate`, assert green with the file untouched.

**Acceptance Scenarios**:

1. **Given** an existing `LOVE_THY_ENEMY.directive.yaml` registered by the real engine (manifest slug `love-thy-enemy`), **When** `charter bundle validate` runs, **Then** it reports zero errors and the file is **not** renamed or modified.
2. **Given** a registration pass over an artifact whose content hash is unchanged but whose resolved path or provenance path drifted, **When** registration runs, **Then** the manifest entry is re-written (the #4834 early-`continue` no longer skips path/provenance drift) without deleting the sidecar — an independent correctness fix, no longer migration-critical.

---

### Edge Cases

- A directive id containing digits (e.g. `DIRECTIVE_025`): the kebab slug never begins with a pure-digit segment (ids require a leading letter), so the validator's optional `NNN-` prefix strip can never falsely truncate a converted slug.
- A namespaced/slash-bearing identifier (e.g. an `agent_profile` id `team/ops-responder`): `slug_for` must URL-encode via `quote(…, safe="")` (as the engine does today at `project_registration.py:187`) so the provenance sidecar path cannot escape `.kittify/charter/provenance/`. An existing test (`test_project_registration.py:165-166`) pins this — `slug_for` must not regress it.
- A non-directive kind whose id is already kebab (`agent_profile`, `procedure`, `tactic`, `styleguide`): its slug stays the (quoted) verbatim id; it must **not** be case-folded like a directive.
- A legacy project with no synthesis state at all: `charter bundle validate` still passes (existing back-compat contract preserved).
- An on-disk doctrine artifact absent from the synthesis manifest: the orphan sweep must still catch it (validator stays **hybrid** — manifest for registered artifacts, filesystem walk for orphan/legacy), so the manifest-driven switch does not silently skip an unregistered artifact.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Scaffolder emits canonical filename | As an operator, `charter new directive <ID>` writes `<kebab-id>.directive.yaml` while preserving the authored `id` inside the file. | High | Open |
| FR-002 | Directive authoring validates clean | As an operator, after scaffolding + activating a project directive, `charter bundle validate` reports zero errors. | High | Open |
| FR-003 | Validator recognises all registration-writing kinds | As an operator, `charter bundle validate` recognises every kind the engine writes a sidecar for (directive, tactic, styleguide, procedure, agent_profile); activating a project profile or procedure produces no "unknown kind". | High | Open |
| FR-004 | Single slug authority + hybrid manifest-driven validation | As a maintainer, the scaffolder and registration engine derive the slug through one shared authority, and the validator resolves *registered* artifacts via the recorded manifest entry rather than re-parsing the filename — while retaining the filesystem walk for the orphan/legacy directions. | High | Open |
| FR-005 | Kebab (quoted) for directives, quoted-verbatim for other kinds | As a maintainer, `slug_for(kind, id)` returns `quote(kebab(id), safe="")` for directives and `quote(id, safe="")` for other kinds — preserving the engine's existing URL-encoding (no path escape for namespaced ids); `id` and slug are formally decoupled. | High | Open |
| FR-006 | Existing repos validate green without modification | As an operator, a repo with pre-existing SCREAMING-filename project directives passes `charter bundle validate` with **no** file rename and **no** manual sidecar deletion (delivered by FR-004's manifest-driven resolution; no migration/self-heal). | Medium | Open |
| FR-007 | Manifest re-write on path/provenance drift (#4834) | As a maintainer, a registration pass re-writes a manifest entry when the artifact's resolved path or provenance path changed even if content hash is unchanged (independent correctness fix; the early-`continue` no longer skips drift), without deleting the sidecar. | Medium | Open |
| FR-008 | Record the convention as an ADR | As a maintainer, the canonical-convention decision (kebab filename, id/slug decoupling, single slug authority, hybrid manifest-driven validation) is recorded as an ADR. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Corruption detection preserved (both directions) | A provenance sidecar with no backing artifact AND an on-disk artifact absent from the manifest both still fail `charter bundle validate`; the hybrid switch (manifest for registered, filesystem walk for orphans) trades no false-positive for a false-negative in either direction. | Reliability | High | Open |
| NFR-002 | No silent re-drift (importable SSOT) | The validator's recognised-kind set is derived from a single importable module-level constant (`DIRECT_WRITE_KINDS`) that the scanner, the manifest kind `Literal`, and the validator all reference — not a hand-duplicated tuple; a parity test asserts all consumers agree, so a future registration-writing kind cannot silently desync them. | Maintainability | High | Open |
| NFR-003 | Backward compatibility | A legacy project with no synthesis state still passes `charter bundle validate` (existing C-012-style back-compat unchanged). | Compatibility | High | Open |
| NFR-004 | Deterministic derivation | `charter new` filename derivation and `slug_for` are deterministic and pure for a given (kind, id). | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | id is canonical identity | The authored `id` is the canonical machine identity; the filename/slug is a derived human handle. Never rename or mutate the authored id to satisfy the filename. | Technical | High | Open |
| C-002 | Preserve engine URL-encoding; do not case-fold non-directive kinds | `slug_for` preserves `quote(…, safe="")` (no path escape for namespaced ids); procedure/agent_profile/tactic/styleguide are not case-folded like directives (would break `_find_artifact` resolution and regress `test_project_registration.py:165-166`). | Technical | High | Open |
| C-003 | Lint/type clean, no suppressions | New/changed code passes ruff + mypy with zero issues; no blanket `# noqa`/`# type: ignore`/per-file-ignore additions. | Technical | High | Open |
| C-004 | No authored-source mutation | The fix mutates only derived state (validator table, manifest, sidecars); it does not rename or rewrite authored doctrine artifact files (the registration module's load-bearing invariant is preserved — migration dropped per the post-plan squad). | Technical | High | Open |
| C-005 | Sequence within the mission | The 5-kind validator table + importable `DIRECT_WRITE_KINDS` (#4833) and the shared `slug_for` surface (#4832) touch the same code; land the foundation (constant + table + slug_for) first, then scaffolder + hybrid validator, to avoid a self-collision. | Technical | Medium | Open |

### Key Entities

- **Doctrine artifact**: a directive / tactic / styleguide / procedure / agent_profile. Carries an authored `id` (canonical identity) and a derived on-disk slug/filename.
- **Provenance sidecar**: `<kind>-<slug>.yaml` under `.kittify/charter/provenance/`, written by the registration engine for every registration-writing kind.
- **Synthesis manifest**: records `(kind, slug, path, provenance_path)` per registered artifact; the authority the validator should trust instead of re-deriving from filenames.
- **Slug authority (`slug_for`)**: the single derivation shared by the scaffolder and the registration engine — `quote(kebab(id), safe="")` for directives, `quote(id, safe="")` otherwise (extracted verbatim from `project_registration.py:187`).
- **`DIRECT_WRITE_KINDS`**: the single importable module-level constant listing the five registration-writing kinds; the scanner, the manifest kind `Literal`, and the validator kind table all reference it (NFR-002).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator authoring a project-tier directive reaches a green `charter bundle validate` with **zero** manual file-surgery rounds (down from the field report's three).
- **SC-002**: An operator activating a project agent profile — or registering a project procedure — reaches a green `charter bundle validate` with no "unknown kind" error.
- **SC-003**: A repo with pre-existing SCREAMING-filename project directives reaches green `charter bundle validate` with **zero** file modifications (no rename, no sidecar deletion) — delivered by manifest-driven resolution alone.
- **SC-004**: Corruption is still detected in 100% of cases in **both** directions (orphan sidecar with no artifact; on-disk artifact with no manifest entry), verified by dedicated guard tests, plus the namespaced-id path-escape guard stays green.
- **SC-005**: Adding a hypothetical sixth registration-writing kind requires editing only the single `DIRECT_WRITE_KINDS` constant, or trips the parity guard (proves the drift class is closed by construction).
