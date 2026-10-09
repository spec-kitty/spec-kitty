# Mission Specification: Canonical org-fragment reference validation

**Mission Branch**: `issue-5833-pack-fragment-validation`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #5833, "Pack validator skips the dangling-edge check for drg/fragment.yaml, the canonical org-pack layout", plus the operator's delegated scope for this mission.

## Intent Summary

- **Primary actor**: an org doctrine pack author (or the CI job that validates a pack) who runs one of the two public pack validation commands, `charter org validate` or `doctrine pack validate`, before publishing a pack.
- **Trigger**: the pack keeps its graph in `drg/fragment.yaml`, the layout `charter org init` scaffolds and the runtime reads, and an edge in that file names an endpoint that does not exist.
- **Desired outcome**: both commands report the broken edge as an error, name the file, the endpoint and its role, and exit non-zero. Today both exit 0 with "0 errors" for every non-augmentation relation (for example `requires`). The exception, which the acceptance tests must not lean on: an `enhances`/`overrides` edge to a missing target already fails today through the separate augmentation-intent `unknown_target` finding, so an exit code alone cannot prove this fix. Every red case is written with a non-augmentation relation and asserts the finding's category, file, endpoint token and role.
- **Rule that must always hold**: both layouts use the existing dangling-membership authority. Canonical `drg/fragment.yaml` tokens bind through the runtime resolver against explicit declarations, schema-trusted file identities and built-ins. The graph-document path preserves its existing registry, file-order snapshots and findings; this mission does not retrofit new binding or schema rules onto it.
- **Boundary**: a standalone pack is validated against the built-in catalog plus that pack alone. It cannot see other org packs, so a qualified edge into a sibling pack's node is reported as dangling, the same as the sharded layout already does.

Discovery was resolved from the issue and the operator's delegated scope, recorded as Decision Moments:
`01M4GC601X606BH0NWHCEN8FX2` (sibling-pack endpoints fail closed), `01M4GC641KD33FRTTV6YGG9PB2` (runtime resolver rules; an ambiguous bare id is an error), `01M4GC680BKTMM3B9A97E0443A` (unknown relation labels are a non-goal).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A broken reference in the canonical layout fails validation (Priority: P1)

A pack author scaffolds an org pack with `charter org init`, adds an edge in `drg/fragment.yaml` that points at an artifact the pack does not ship (a typo, a deleted asset, a directive id that never existed), and runs validation before publishing. Validation reports the broken edge and fails, so the author fixes it before any consumer loads the pack.

**Why this priority**: this is the defect in #5833. A pack in the scaffolded layout can ship a broken reference with a green validation result, and the author finds out only at load time, if at all.

**Independent Test**: scaffold a pack, add the dangling edge with the relation `requires`, run each of the two validation commands, and check the exit code plus the reported finding. Structured assertions (category, file, endpoint token, role) are made against `doctrine pack validate --json`; `charter org validate` has no JSON flag, so it is asserted on its exit code and its rendered finding text.

**Acceptance Scenarios**:

1. **Given** an org pack whose `drg/fragment.yaml` declares an edge `requires` with target `asset:does-not-exist`, **When** the author runs either validation command, **Then** the command exits non-zero and reports a `drg_dangling_edge` error naming `drg/fragment.yaml`, the endpoint `asset:does-not-exist` and its role (`target`).
2. **Given** an edge (relation `requires`) whose *source* is the qualified id `directive:NOPE-999` that neither the pack nor the built-in catalog declares, **When** the author validates, **Then** the same `drg_dangling_edge` error is reported with role `source`.
3. **Given** an edge whose source or target is a bare id (for example `NOPE-999`) that matches no node the pack declares and no built-in node, **When** the author validates, **Then** a `drg_dangling_edge` error is reported for that endpoint with its role.
4. **Given** an edge whose endpoint is URN-shaped but malformed (for example `directive:` with no id), **When** the author validates, **Then** a `drg_dangling_edge` error is reported for that endpoint whose message carries the resolver's malformed-endpoint cause, rather than a silent pass.
5. **Given** an edge whose endpoint is a bare id that matches more than one built-in node of different kinds, **When** the author validates, **Then** a `drg_dangling_edge` error is reported whose message carries the resolver's ambiguity cause and asks the author to qualify the id.
6. **Given** an endpoint whose prefix is not a known node kind (for example the typo `directve:037`), **When** the author validates, **Then** it is resolved as a bare id, fails to resolve, and is reported as `drg_dangling_edge` with its role.

---

### User Story 2 - Valid references keep passing (Priority: P1)

A pack author whose fragment edges are all correct gets the same clean result as before: edges to built-in nodes, to nodes the fragment declares, and to the pack's own valid artifacts (including assets with a valid manifest), in qualified or bare form.

**Why this priority**: a validator that starts rejecting correct packs is worse than the defect. `packs/internal`, which CI validates on every pack change, must stay clean.

**Independent Test**: validate a pack whose fragment edges use each valid endpoint form, and validate `packs/internal`; both report no `drg_dangling_edge` finding.

**Acceptance Scenarios**:

1. **Given** fragment edges that reference built-in nodes in qualified form and in unambiguous bare form, **When** the author validates, **Then** no dangling-edge finding is reported.
2. **Given** fragment edges between nodes the fragment declares, in qualified and bare form, **When** the author validates, **Then** no dangling-edge finding is reported.
3. **Given** a fragment edge to the pack's own asset whose manifest exists and passes its schema, **When** the author validates, **Then** no dangling-edge finding is reported.
4. **Given** the repository's own `packs/internal` org pack, **When** it is validated with either command, **Then** it reports 0 errors, as it does today.
5. **Given** a bare endpoint naming the pack's own schema-valid artifact file that the fragment does **not** list in an explicit `nodes:` block, **When** the author validates, **Then** no dangling-edge finding is reported (the schema-checked artifact registry is a valid endpoint source); **and** the twin fixture, whose artifact file fails its schema check, does report `drg_dangling_edge`.

---

### User Story 3 - The asset rules match the sharded layout (Priority: P2)

An author whose fragment edge points at the pack's own asset gets the same answer in both layouts. Two rules, which are not in conflict: a node the fragment lists in an explicit `nodes:` block is a valid endpoint with no backing file at all (as the sharded layout already accepts declared graph nodes); an endpoint that is backed by *neither* an explicit declaration *nor* a schema-valid manifest is dangling.

**Why this priority**: #5827 made the sharded layout fail closed on these cases. The canonical layout must not be the softer one.

**Independent Test**: the same pack, in each layout, with the asset manifest present, absent, and schema-invalid.

**Acceptance Scenarios**:

1. **Given** a fragment edge to `asset:<id>` with no manifest for that asset **and** no explicit `nodes:` declaration of it, **When** the author validates, **Then** a `drg_dangling_edge` error is reported.
2. **Given** a fragment edge to `asset:<id>` whose manifest fails its schema and which is not explicitly declared, **When** the author validates, **Then** both the existing `schema_invalid` error for the manifest and a `drg_dangling_edge` error for the edge are reported, as the sharded layout reports today.
3. **Given** a fragment edge to `asset:<id>` that the fragment's own `nodes:` block declares, and no manifest file, **When** the author validates, **Then** no `drg_dangling_edge` error is reported for that endpoint (explicit declaration is the author's assertion that the node exists; any missing-file finding stays owned by the existing artifact checks).

---

### User Story 4 - Load failures read the same as today (Priority: P2)

An author whose `drg/fragment.yaml` cannot be loaded at all (malformed YAML, schema violation, unreadable file) sees the same load finding as today, and no extra dangling-edge findings derived from a fragment the validator could not read.

**Why this priority**: a load failure is the root cause; piling dangling-edge noise on top of it hides that cause.

**Independent Test**: validate a pack with a schema-invalid or unparseable fragment and compare the findings to today's.

**Acceptance Scenarios**:

1. **Given** a `drg/fragment.yaml` that fails to parse or fails its schema, **When** the author validates, **Then** the existing load finding is reported with its current category and file, and no `drg_dangling_edge` finding is reported for that fragment.
2. **Given** a pack whose fragment loads but whose governance-profile (or other artifact) load fails, **When** the author validates, **Then** the existing fault is reported: a governance-profile selection fault prevents the loader from returning a fragment, so the whole canonical endpoint pass is skipped; an individual artifact schema fault excludes that identity from schema trust while authored edges of a successfully loaded fragment are still checked. The valid twin reports its dangling edge, so the pair cannot both pass vacuously.

### Edge Cases

- A pack that ships both `drg/fragment.yaml` and sharded `drg/*.graph.yaml` files: each file's edges are checked, each finding names the file it came from, and the existing sharded-layout checks and the root-graph check behave as today.
- Only edges the fragment itself authors in its `edges:` block are checked. The org loader also mints edges from artifact files (an artifact's own `enhances:` field, governance profiles); those are not fragment-authored and must not be reported against `drg/fragment.yaml`.
- An augmentation edge (`enhances`/`overrides`) whose target is missing: the existing `unknown_target` finding is unchanged (C-004). The authored missing endpoint additionally raises `drg_dangling_edge`; `unknown_target` appears only where the current intent pass would already emit it (its existing skips remain). This applies to qualified and bare targets without changing the #5494 fallback. Generated augmentation edges receive no new fragment-attributed endpoint finding.
- Unknown relation labels do not suppress endpoint-existence checks; the label itself is neither validated nor coerced into an enum.
- Schema trust is projected from successful validations in the same existing scan, separately from the legacy sharded registry. A profile uses `profile-id`; a legacy both-intent shortcut does not establish schema success.
- No new kind-drift or duplicate-edge advisory is introduced for the canonical layout: only the endpoint-existence check is extended (each layout keeps its own registry assembly).
- A pack with no `drg/` directory, or a `drg/` directory with no fragment: no new findings.
- An edge that is broken at both ends: one finding per broken endpoint, each naming its role.
- A bare id that matches a node the fragment declares and also a built-in node: the pack's own node wins (the runtime's nearest-scope rule), so it is not ambiguous.
- A qualified edge into a sibling org pack's node: reported as dangling; the documentation explains that standalone validation sees only the built-in catalog and the pack itself.
- The built-in graph is unavailable (stripped environment): validation still runs against the pack's own nodes, as the sharded layout does today.
- An artifact file that the runtime loader would turn into a node but whose schema check fails: it does not count as a valid endpoint.

## Domain Language

| Canonical term | Meaning here | Avoid |
|---|---|---|
| Org pack | A doctrine pack loaded at the organisation tier, validated by the two commands below | "plugin", "extension pack" |
| Canonical layout | A pack whose graph lives in a single `drg/fragment.yaml` — the shape the charter calls the org-tier extension fragment, and the shape `charter org init` scaffolds | "legacy layout" |
| Sharded layout | A pack whose graph lives in one or more `drg/*.graph.yaml` graph documents | "split layout" |
| Authored edge | An edge written in a fragment's or graph document's own `edges:` block, as opposed to an edge the loader mints from an artifact file | "declared edge" (ambiguous with declared nodes) |
| Explicit node declaration | An entry in a fragment's or graph document's own `nodes:` block | "generated node" (that is the loader's output, not an author's declaration) |
| Edge endpoint | The `source` or `target` token of a graph edge, either qualified (`<kind>:<id>`) or bare (`<id>`) | "reference id", "link" |
| Dangling edge | An edge with an endpoint that resolves to no known node | "orphan edge" |
| Built-in catalog | The nodes of the built-in doctrine pack shipped with Spec Kitty | "default pack" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Qualified dangling endpoints fail in the canonical layout | As a pack author, I want an edge **authored in `drg/fragment.yaml`'s own `edges:` block** whose qualified source or target names no known node to be reported as a `drg_dangling_edge` error that names `drg/fragment.yaml`, the endpoint token and its role (`source`/`target`), so that a broken reference never passes validation. Loader-minted edges (artifact `enhances:` fields, governance profiles) are out of this requirement and must not be attributed to the fragment. | High | Open | [build] | no |
| FR-002 | Unresolved bare endpoints fail | As a pack author, I want a bare source or target that matches neither an explicit node declaration in my fragment, nor an entry of my pack's schema-checked artifact registry, nor exactly one built-in node to be reported as a `drg_dangling_edge` error, so that a typo in a bare id is caught. A token whose prefix is not a known node kind (for example `directve:037`) is resolved as a bare id and judged by this rule. | High | Open | [build] | no |
| FR-003 | Malformed endpoints fail with a stated cause | As a pack author, I want a URN-shaped endpoint that is malformed (a known kind prefix with an invalid or empty id) to be reported as a `drg_dangling_edge` error that names the endpoint and carries the runtime resolver's malformed-endpoint cause in its message, so that one category covers every unbindable endpoint and the reason is still legible. No new finding category is added; the existing category registry is extended in documentation only if its description no longer covers these causes. | High | Open | [build] | no |
| FR-004 | Ambiguous bare built-in ids fail with a stated cause | As a pack author, I want a bare endpoint that matches more than one built-in node to be reported as a `drg_dangling_edge` error whose message carries the resolver's ambiguity cause and asks me to qualify the id, so that validation agrees with how the runtime refuses the same edge. | Medium | Open | [build] | no |
| FR-005 | Valid endpoints keep passing | As a pack author, I want edges to built-in nodes, to nodes my fragment declares, and to my pack's own schema-valid artifacts, in qualified or unambiguous bare form, to raise no dangling-edge finding, so that correct packs stay green. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture pack: the valid edges pass while the dangling edge fails |
| FR-006 | Invalid assets are not valid endpoints; explicit declarations are | As a pack author, I want an edge to my pack's own asset to count as dangling when the asset has neither a schema-valid manifest nor an explicit `nodes:` declaration (any schema failure still reported as today), and to keep passing when the fragment explicitly declares the node, so that the canonical layout matches the sharded layout's #5827 behaviour without rejecting declared graph nodes. | High | Open | [build] | no |
| FR-007 | Load failures are reported as today, without dangling noise | As a pack author, I want a `drg/fragment.yaml` that cannot be loaded to produce the same load finding (category and file) as today and no `drg_dangling_edge` finding for that fragment, and I want a governance-profile selection failure to skip the canonical endpoint pass because no fragment is returned, while an individual artifact schema failure excludes that identity but does not skip authored edges of a successfully loaded fragment, so that the root cause stays visible. | Medium | Open | [ratchet] | yes — paired with FR-001: the same fixture with a loadable fragment does report the dangling edge |
| FR-008 | Sharded layout unchanged | As a pack author using `drg/*.graph.yaml`, I want the existing dangling-edge, kind-drift, duplicate-edge and root-graph findings to stay exactly as they are, so that this fix changes nothing for that layout. | High | Open | [ratchet] | yes — paired with FR-001: the same dangling edge fails in both layouts |
| FR-009 | Both public commands carry the fix | As a pack author or CI job, I want `charter org validate` and `doctrine pack validate` to report the same findings and exit non-zero for a dangling `drg/fragment.yaml` edge, so that the answer does not depend on which command I run. | High | Open | [build] | no |
| FR-010 | The repository's own org pack stays clean | As a maintainer, I want `packs/internal` to validate with 0 errors after the change, so that the CI pack lane stays green. | High | Open | [ratchet] | yes — paired with FR-001: the same check that passes `packs/internal` fails the dangling fixture |
| FR-011 | Authors are told what changed | As a pack author, I want a changelog entry in `docs/changelog/CHANGELOG.md` (impact first, citing #5833) and an in-place update of `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` (its error table, its bare-id paragraph and its troubleshooting section) stating that both layouts are now checked and that the check fails closed, so that a newly red pack is explained. | Medium | Open | [build] | no |
| FR-012 | The standalone sibling-pack boundary is stated with a remediation path | As a pack author whose fragment legitimately references a sibling pack's node, I want the documentation and the touched docstrings to say plainly that standalone validation sees only the built-in catalog plus this pack, that such an endpoint therefore fails closed here while the runtime's merged graph still resolves it, and what to do about it (explicitly declare the sibling node's graph identity with the correct plural kind and keep the edge qualified; configure the sibling pack and use `doctor doctrine` to verify the actual assembled runtime context, which does not by itself make standalone validation pass), so that the deliberate divergence from the documented runtime semantics is visible rather than contradicted in silence. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added load pass, no timing gate | The endpoint check consumes data the validator already loads: it adds no second full load/parse pass over `drg/fragment.yaml` and no extra built-in graph assembly per edge. Verified structurally (loader/registry call sites in the diff), not by a wall-clock threshold — no timing assertion is added, since a host-relative threshold is neither portable nor honestly checkable in this suite. | Performance | Medium | Open |
| NFR-002 | Deterministic findings | Two consecutive validations of the same pack produce byte-identical JSON output (same findings, same order). | Reliability | Medium | Open |
| NFR-003 | New code is tested | At least 90 % line coverage of new and changed lines, measured by the targeted tests; every new branch or helper has a focused test in the same commit. | Maintainability | High | Open |
| NFR-004 | New code stays simple and clean | Every new or changed function has cyclomatic complexity of 15 or less; the changed files pass the repository's lint, format and strict type checks with zero new findings and zero new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One endpoint-resolution policy, named authorities | Endpoint resolution reuses the runtime's existing endpoint rules (pack-local bare id, then qualified URN, then a bare id matching exactly one built-in) owned by `src/charter/offering/drg/merge.py::_resolve_edge_endpoint`; the "dangling" verdict stays owned by `src/charter/offering/drg/validator.py::dangling_endpoints` / `validate_dangling_references`. The inline endpoint check in `src/specify_cli/doctrine/pack_validator.py` (~:837-852) is replaced by the shared predicate rather than copied a third time; one rule serves both layouts. If reuse needs a seam, it is exposed through the `charter.drg` facade — a private cross-package import is not acceptable undocumented, and any remaining gap is recorded as explicit debt in the plan. | Technical | High | Open |
| C-002 | One pack registry, declarations distinguished from generated nodes | The known-node set is a schema-trusted identity projection of the SAME existing artifact scan, plus the loader's authored-node provenance accessor and the built-in catalog. Keep this projection distinct from the legacy graph-document registry, including its both-intent shortcut. Use `profile-id` for schema-valid profiles, ordinary `id` for other validated artifacts; no schema registry expansion or second filesystem scan. Nodes the loader mints from artifact files that failed their schema check do not count, and a loader-generated node is never read as an author's explicit declaration. | Technical | High | Open |
| C-003 | No rename or move | The command names, module paths and test paths stay as they are; the overlapping rename in PR #5962 is not performed here. | Technical | High | Open |
| C-004 | Augmentation intent untouched | The `enhances`/`overrides` intent pass and its bare-target fallback (#5494) keep their current behaviour. | Technical | High | Open |
| C-005 | Runtime rules untouched | The runtime merge's dangling-endpoint warning/error rules and the `doctor doctrine` check are not changed. | Technical | High | Open |
| C-006 | Standalone scope only, divergence recorded | No cross-pack resolution or inheritance is designed; validation sees the built-in catalog plus the one pack. This is a deliberate fail-closed narrowing against the documented runtime full-graph semantics (`drg/merge.py` sibling-pack resolution, `drg/validator.py` dangling policy): the divergence, its justification and its remediation are written down (FR-012) and the docstrings of the touched surfaces are reconciled with that text per DIRECTIVE_037 rather than left contradicting it. | Technical | Medium | Open |
| C-009 | Validation commands are bounded during this mission | Mission-time validation runs targeted test files and the specific implicated architectural gate files only (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Any command that reaches `make test-fast` (including the configured pre-review gate) runs with `PYTEST_XDIST_AUTO_NUM_WORKERS=2` and `UV_NO_SYNC=1`, with this clone's `.venv/bin` prepended to `PATH`; manual targeted runs use `.venv/bin/python -m pytest`. The gate is never disabled or skipped, and neither `.kittify/config.yaml` nor the `Makefile` is edited to achieve this. | Process | High | Open |
| C-007 | Red first, no lingering regression markers | An issue-pinned failing reproduction through the existing validation entry points is committed before the fix; after the fix it becomes a focused functional test with no leftover regression marker. | Process | High | Open |
| C-008 | Small file set | The change stays inside the pack validator, its focused tests, the org-pack how-to and changelog, plus the charter loader/resolver/validator/facade seams and their focused tests. Those charter additions are justified by loader-owned authorship provenance and reuse of existing endpoint/dangling authority; they introduce no second parser or endpoint policy. No version bump. | Process | Medium | Open |

### Key Entities

- **Org pack**: a directory with artifact folders, an optional `drg/` folder and optional org charter; validated as one unit.
- **Graph fragment**: `drg/fragment.yaml` (canonical) or a `drg/*.graph.yaml` file (sharded); declares nodes and edges.
- **Edge endpoint**: the source or target token of an edge; qualified or bare.
- **Known node set**: built-in catalog nodes, the pack's schema-valid artifacts, and nodes the fragment declares.
- **Validation finding**: severity, category (for example `drg_dangling_edge`), file, artifact id and message.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six broken-endpoint cases from the issue and the delegated scope (qualified source, qualified target, bare source, bare target, malformed, ambiguous bare), each authored with the non-augmentation relation `requires`, make both public validation commands exit non-zero, 12 of 12 command runs; and for each case `doctrine pack validate --json` carries a `drg_dangling_edge` finding naming `drg/fragment.yaml`, the endpoint token and the role. — [build] · no-op passable: no
- **SC-002**: `packs/internal` (87 edges today) reports 0 errors with both commands after the change. — [ratchet] · no-op passable: yes — paired with SC-001 on the same check
- **SC-003**: Every dangling-edge finding for the canonical layout names the fragment file, the offending endpoint token and its role, 100 % of findings in the acceptance tests. — [build] · no-op passable: no
- **SC-004**: The existing sharded-layout and fragment load-failure tests pass unchanged (0 regressions in the targeted test files). — [ratchet] · no-op passable: yes — paired with SC-001

## Assumptions

- Standalone pack validation is the right place for this check; the runtime's merged-graph check remains the place where sibling-pack references are judged.
- No existing consumer pack in this repository relies on a dangling fragment edge; the grounding probe found 0 broken endpoints across `packs/internal`'s 87 edges, with the explicit-declaration and schema-checked-registry rules of C-002 applied.
- The rule "an explicitly declared node is a valid endpoint without a backing file" is no longer an assumption: it is stated in FR-006 and US3 together with the complementary rule that an undeclared, unbacked endpoint is dangling.

## Non-Goals

- The charter-pack rename and path moves in PR #5962.
- Cross-pack resolution or inheritance design.
- Validating unknown relation labels on fragment edges (deferred; decision `01M4GC680BKTMM3B9A97E0443A`).
- Changing the augmentation-intent fallback (#5494).
- Changing the runtime merged-graph warning/error rules or `doctor doctrine`.
- Global cleanup or refactoring of the pack validator module beyond the touched seams.

## Dependencies

- Parent tracking issue: #1868 (context only).
- Builds on PR #5827 (merged), which registered a pack's own asset URNs for the sharded layout.
- Overlaps PR #5962 (draft) on file paths only; whichever lands second rebases. Verified still open/draft at this revision; no path migration is performed here (C-003).

## Post-Spec Review Dispositions

Two independent profile-loaded post-spec reviews (reviewer-renata, doctrine-daphne; both read-only, both `ready-with-changes`) are folded here. Every disposition below is derived from the GitHub issue, the already-recorded Decision Moments and the operator's delegated scope — **no new human answers were taken for this revision**, and the three Decision Moments keep their original evidence attribution.

| Finding | Disposition | Where |
|---|---|---|
| renata HIGH-1 — exit-code-only acceptance is fakeable; `enhances` already errors `unknown_target` | Folded: red cases use the non-augmentation relation `requires` and assert category, file, endpoint token and role through `doctrine pack validate --json` | Intent Summary, US1, SC-001, SC-003 |
| renata HIGH-2 / daphne MED-4 — no category for malformed/ambiguous | Folded: one consistent `drg_dangling_edge` category carrying the runtime resolver's cause in the message; no new category; registry description updated only if it no longer covers these causes | FR-003, FR-004, US1.4-1.5 |
| renata HIGH-3 — declared-node assumption contradicted US3 AC1 | Folded: explicit `nodes:` declaration is valid without a manifest; an endpoint with neither a declaration nor a schema-valid manifest is dangling | US3, FR-006, Assumptions |
| renata MED-1 — loader-generated edges misattributed to the fragment | Folded: authored edges only | FR-001, Edge Cases, Domain Language |
| renata MED-2 — bare id into an undeclared but schema-valid artifact needs coverage, plus an invalid twin | Folded | US2.5, FR-002 |
| renata MED-3 — per-layout registries; no new advisories | Folded: only the endpoint check is extended | Edge Cases, C-002 |
| renata MED-4 — unknown-kind qualified prefix | Folded: treated as a bare id and judged by FR-002 | FR-002, US1.6 |
| renata MED-5 — augmentation edge parity (`unknown_target` plus dangling) | Resolved by parent-adjudicated architect recommendation: authored missing endpoints raise dangling findings; unchanged intent findings coexist where the existing intent pass emits them, including its skips | Edge Cases |
| renata LOW-1 / NFR-001 — host-relative speed threshold is unportable and fakeable | Folded: the timing threshold is removed; no timing gate is added. NFR-001 is now a structural no-extra-load-pass requirement | NFR-001 |
| renata LOW-2 — `charter org validate` has no `--json` | Folded: structured assertions belong to `doctrine pack validate --json`; the charter command is asserted on exit code and rendered text | US1 Independent Test |
| renata LOW-3 — add role to SC-003 | Folded | SC-003 |
| renata LOW-4 — twin fixtures; governance-profile fault path | Folded | US4.2, FR-007 |
| daphne HIGH-1 — single-pack fail-closed contradicts documented runtime semantics, with no remediation | Folded: the divergence is acknowledged, justified, given a remediation path, and the touched docstrings are reconciled (DIRECTIVE_037) | FR-012, C-006 |
| daphne MED-1 — C-001 named no authorities; one shared predicate must replace the inline check | Folded: resolver, dangling SSOT and the inline copy are named; the inline check is replaced | C-001 |
| daphne MED-2 — #5494 bare-target fallback versus resolver rule 3 judging the same edge | Bounded: #5494 semantics are untouched (C-004) and the expected paired findings are specified by the supplied architect recommendation without changing the intent pass; no new follow-up issue is filed while shipping | C-004, Edge Cases |
| daphne MED-3 — layout vocabulary collides with charter/ADR/how-to wording | Folded: Domain Language now names the org-tier extension fragment and the graph-document shape, and distinguishes authored edges from generated ones | Domain Language |
| daphne LOW-1 — how-to path, three sections, #5962 content overlap | Folded: canonical path and the three sections named; #5962 overlap recorded | FR-011, Dependencies |
| daphne LOW-2 — runtime parity overstated (loader mints schema-invalid nodes) | Folded: C-002 states registry and declaration rules; parity claims are scoped to endpoint-existence semantics | C-002, Intent Summary |
| daphne LOW-3 — private `merge._resolve_edge_endpoint` import would bypass the `charter.drg` facade | Folded: reuse goes through the facade, or the remaining gap is recorded as explicit debt in the plan | C-001 |
| scope-squad — unknown relation labels | Unchanged non-goal, with the existing Decision Moment as its rationale; no follow-up issue filed while shipping | Non-Goals |

Mission-time validation bounds (worker cap, no venv resync, no gate edits) are recorded as C-009 so the work packages inherit them.
