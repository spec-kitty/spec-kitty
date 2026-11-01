# Mission Specification: Charter identity single authority

**Mission Branch**: `issue-6433-charter-identity-single-authority` (planning base and merge target `main`)
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue #6433 "Route charter compile and consistency check through the IdentityIndex so one stem↔id authority remains" (parent epic #6518), plus the grounding finding that #6406/#6457 (`a8dd1812a6`) and #6749 already routed compile, the consistency check, the DRG activation filter, preset application and the project layer through `IdentityIndex`.

## Intent Summary

- **Primary actor**: an operator running `spec-kitty charter activate`/`deactivate` with `--cascade`, and a maintainer reading the charter identity-resolution seam.
- **Trigger**: an activation token is spelled as a `<kind>:<id>` URN or as a normalised directive id (`24`), both of which the write path and the runtime gate accept today.
- **Desired outcome**: one stem↔declared-id authority (`IdentityIndex`) decides every token, in every direction, on every surface; `kind_vocabulary.resolve_artifact_urn` becomes a facade over it instead of a second implementation of the rule.
- **Invariant**: layer precedence, fail-closed behaviour for a genuinely unknown token, and the refusal of a directive declared id that no filename can represent all stay exactly as they are (C-001). Only spellings the gate already accepts are newly accepted by the facade.

## Grounding (#6433 on current `main`)

The issue lists four parallel paths. Three are already closed by landed work:

| Site named by #6433 | State on `main` (`dfe9efb0e8`) |
| --- | --- |
| `compiler.resolve_config_activated_roots` | routed through `IdentityIndex` (#6457, `a8dd1812a6`) |
| `consistency_check` (both sites, and the project layer) | routed through one `IdentityIndex` (#6457, #6749) |
| `drg_activation` / `preset_application` fallbacks | routed through `IdentityIndex` |
| `kind_vocabulary.resolve_artifact_urn` and its callers | **still a second implementation** — this Mission |

The residual defect reproduces through the shipped CLI (both cases verified before specifying):

1. **Cascade source resolution refuses a token the gate accepts, silently.** `charter activate directive directive:DIRECTIVE_024 --cascade all` on a ledger-seeded project activates the directive but prints no `Cascade-activated:` line, while the same activation by stem prints `Cascade-activated: directive/reconcile-change-scope-tensions`. `_source_urn` resolved through `resolve_artifact_urn`, which refuses a URN; the command treats "no source URN" as "cascade is a no-op", so the cascade and the referenced-but-not-cascaded warning both disappear without a diagnostic.
2. **The same happens to the shared-artifact safety report on deactivate.** `charter deactivate directive directive:DIRECTIVE_024 --cascade all` prints no `Skipped (shared artifact): directive:RECONCILE_CHANGE_SCOPE_TENSIONS (still referenced by agent_profile:analyst-annie)` line that the by-stem deactivation prints.
3. `charter activate directive 24` (a normalised directive id the runtime gate resolves) also activates the artifact but drops the cascade, for the same reason.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The cascade source resolves every spelling the gate accepts (Priority: P1)

An operator activates or deactivates an artifact by `<kind>:<id>` URN or by a normalised directive id and passes `--cascade`. The command must walk the same source node it would have walked for the file stem, and report the same cascade and shared-artifact lines.

**Why this priority**: today the write succeeds and the cascade silently does nothing, so dependent artifacts are not activated (or a shared artifact's retention is not reported) with no warning — a silent-wrong-state failure, not a cosmetic gap.

**Independent Test**: run `charter activate directive <token> --cascade all` and `charter deactivate directive <token> --cascade all` for the stem, the URN and the normalised id on the same ledger-seeded fixture; all three outputs and ledgers are identical.

**Acceptance Scenarios**:

1. **Given** a project whose activation ledger lists the built-in directives, **When** the operator runs `charter activate directive directive:DIRECTIVE_024 --cascade all`, **Then** the output names `Cascade-activated: directive/reconcile-change-scope-tensions`, exactly as activating `024-locality-of-change` does.
2. **Given** the same fixture, **When** the operator runs `charter deactivate directive directive:DIRECTIVE_024 --cascade all`, **Then** the shared-artifact skip line naming `agent_profile:analyst-annie` prints, exactly as deactivating by stem does.
3. **Given** the same fixture, **When** the operator activates or deactivates by the normalised id `24`, **Then** the result is identical to the by-stem run.

---

### User Story 2 - One stem↔id rule, in both directions (Priority: P1)

A maintainer needs `resolve_artifact_urn` (stem/id → URN) and its inverse to answer from the same index the rest of the system uses, so the rule cannot drift back.

**Why this priority**: two implementations of one rule is the defect class #6433 exists to close; today the facade's answer already differs from the index for URNs and normalised ids.

**Independent Test**: a parity matrix over every activatable kind, every layer (built-in, org, project) and every spelling (stem, declared id, URN, normalised directive id) asserts the facade and the index agree, in both directions.

**Acceptance Scenarios**:

1. **Given** any artifact the index knows, **When** `resolve_artifact_urn` is called with any spelling the index accepts, **Then** it returns `<kind>:<declared id>` and no second discovery rule runs.
2. **Given** any declared id the index can map to a stem, **When** `resolve_config_id` is called with its URN, **Then** it returns that stem, and a directive whose file name another layer binds to a different id still refuses with `UnrepresentableDirectiveIdError`.
3. **Given** a token no searched layer knows, **When** either direction is asked, **Then** it raises `UnknownArtifactIdError` naming the searched layers, with the message it raises today.

---

### User Story 3 - One pinned behaviour per surface for an unknown token (Priority: P2)

A maintainer needs each surface's unknown-token policy stated once and pinned by test, so a future refactor cannot quietly change warn-and-keep into a refusal or vice versa.

**Why this priority**: #6433's "pin one behaviour for unknown tokens" is the half of the issue that survived its own routing work.

**Independent Test**: one test module names the four surfaces and their policies; each assertion fails if its surface changes policy.

**Acceptance Scenarios**:

1. **Given** an unknown activation token, **When** the runtime gate resolves it, **Then** it warns and keeps the token best-effort (unchanged).
2. **Given** an unknown activation token, **When** the consistency check runs, **Then** it reports the token once in `unknown_references` and keeps the stored list (unchanged).
3. **Given** an unknown activation token, **When** compile runs, **Then** it refuses with `UnknownArtifactIdError` (unchanged); **When** the cascade-source resolution runs, **Then** it yields no source and does not raise (unchanged), and the command still reports the activation it performed.

### Edge Cases

- A URN whose id part is a stem rather than a declared id (`tactic:qa-tactic-seven`): the index resolves it like the bare token; the facade must agree, not raise.
- A declared directive id whose file name another layer binds to a different id: `resolve_artifact_urn` and `resolve_config_id` keep refusing (writes refuse it too); the *index* keeps returning the declared id for read-only callers (compile, consistency check), which is today's documented split and must not change.
- An `anti_pattern` token: the kind has no files, so the index knows nothing; `resolve_artifact_urn` keeps raising for it.
- A mission type (`mission-type` is not an `ArtifactKind`): the facade is never called with it; the CLI's mission-type branch is unchanged.
- A file whose YAML cannot be parsed: the index's fast-id path returns the id where the full parse returns nothing (documented, accepted limitation); the facade inherits it rather than reintroducing a second reader.
- An org root that is missing on disk: both the facade and the index skip it; no new error.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `resolve_artifact_urn` delegates to the index | As a maintainer, I want the stem/id→URN resolver to answer from `IdentityIndex` so that one rule decides every token. | High | Open | [build] | no — today it returns a different answer (or refuses) for a URN and a normalised directive id; positive control: a stem still resolves |
| FR-002 | `resolve_config_id` delegates to the index | As a maintainer, I want the inverse (URN→stem) to answer from the same index, keeping `UnrepresentableDirectiveIdError` and its message. | High | Open | [ratchet] | no — asserted on a directive whose stem another layer shadows (positive control: a unique stem returns) |
| FR-003 | Selection stem mapping delegates to the index | As a maintainer, I want `resolve_selected_id_to_stem`'s stem probe to use the index, so no filesystem scan remains behind a third function. | Medium | Open | [ratchet] | no — same-fixture parity with the current answers for stem, declared id and unknown |
| FR-004 | Cascade source resolves through the index | As an operator, I want `activate`/`deactivate --cascade` to resolve the source token through the index, so a URN or normalised id cascades exactly as the stem does. | High | Open | [build] | no — red-first CLI test: the URN run prints no cascade line today (positive control: the stem run does) |
| FR-005 | Deactivate's active-URN set resolves through the index | As an operator, I want `deactivate --cascade`'s shared-reference safety set to resolve every active token through the index, so a URN spelling never silently drops an active URN. | High | Open | [build] | no — red-first CLI test: the shared-artifact skip line is missing today (positive control: present by stem) |
| FR-006 | Resynthesis preflight source resolves through the index | As an operator, I want `activate --resynthesize` to resolve its cascade source through the index, so the preflight walks the same node as the write. | Medium | Open | [build] | no — the URN source raises today |
| FR-007 | One unknown-token policy per surface | As a maintainer, I want gate/check/compile/source-resolution unknown-token policies pinned in one test module. | Medium | Open | [ratchet] | no — each assertion names its surface's observable behaviour; a policy flip fails it |
| FR-008 | One scan per resolution pass | As a maintainer, I want a facade call inside a caller's `ResolutionPass` to reuse that pass's scan and id memo, so threading `resolution_pass` keeps its current cost. | Medium | Open | [ratchet] | no — counts layer scans for a multi-call pass (positive control: one pass, one scan) |
| FR-009 | Changelog and docs | As an operator, I want an `[Unreleased]` entry and the identity-resolution doc to say the facade answers from the index and which spellings cascade accepts. | Medium | Open | [build] | yes — docs; verified by review |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Quality gates | Every touched file passes `ruff check`, `ruff format --check` and `mypy` with zero new findings; no new `noqa` or `type: ignore`. | Maintainability | High | Open |
| NFR-002 | Complexity | Every touched function stays at cyclomatic complexity <= 15. | Maintainability | High | Open |
| NFR-003 | Diff coverage | Changed source lines at >= 90% diff coverage. | Maintainability | Medium | Open |
| NFR-004 | No scan regression | A resolution pass that resolves N tokens performs at most one layer scan per kind, measured by counting `_iter_artifact_paths` scan-dir walks. | Performance | High | Open |
| NFR-005 | No behavioural drift | The 100+ existing tests over `resolve_artifact_urn`, `resolve_config_id`, `resolve_selected_id_to_stem`, compile, the consistency check and the cascade stay green, unmodified where they pin current behaviour. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakened | Acceptance widens only to spellings the runtime gate already accepts (URNs, normalised directive ids). A genuinely unknown token still refuses in compile and source resolution; the directive representable-stem refusal is preserved. | Technical | High | Open |
| C-002 | Public signatures unchanged | `resolve_artifact_urn`, `resolve_config_id` and `resolve_selected_id_to_stem` keep their names, parameters, return types and exception types; `UnknownArtifactIdError` messages are unchanged. | Technical | High | Open |
| C-003 | One authority, no cache | The index stays per-call and in-memory; no module-level or persisted identity cache is introduced. | Technical | High | Open |
| C-004 | Layer rule unchanged | Precedence stays project → org packs last-declared-first → built-in, and stem-before-declared-id for every kind except a directive *id*, which the index resolves id-first as it does today. | Technical | High | Open |
| C-005 | Scope | Compile, consistency check, DRG filter and presets are already routed (#6457, #6749) and are not reworked here beyond what the shared facade requires. | Technical | Medium | Open |

### Key Entities

- **IdentityIndex**: per-invocation, layer-aware map from any spelling (stem, declared id, URN) to an artifact's declared id and stem; the authority this Mission routes everything through.
- **Facade**: `kind_vocabulary.resolve_artifact_urn` / `resolve_config_id` / `resolve_selected_id_to_stem`, kept as named entry points for their many callers, answering from the index.
- **Cascade source URN**: the DRG node the `--cascade` walk starts from; resolved from the operator's token.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every activatable kind and every spelling on a built-in/org/project fixture, the facade and the index return the same identity (0 disagreements), where today URN and normalised-id spellings disagree in 4 of 4 probed cases. — [build] · no-op passable: no
- **SC-002**: `activate --cascade` and `deactivate --cascade` produce byte-identical operator output for a stem, a URN and a normalised id on the same fixture (3 of 3 identical), where 2 of 3 currently lose the cascade report. — [build] · no-op passable: no
- **SC-003**: A resolution pass that resolves many tokens performs no more layer scans than it does today (one per kind), so the facade adds no filesystem work. — [ratchet] · no-op passable: no
- **SC-004**: Zero existing identity, compile, consistency-check or cascade tests change their asserted behaviour; no gate is skipped, xfailed or loosened. — [ratchet] · no-op passable: no
