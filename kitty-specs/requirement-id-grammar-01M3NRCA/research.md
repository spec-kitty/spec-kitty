# Research: Requirement-ID grammar and finalize-tasks diagnostics

Sources: the pre-spec grounding squad (researcher-robbie alignment lens, planner-priti scope lens, architect-alphonso architecture lens), the post-spec adversarial squad (reviewer-renata, paula-patterns), and the brownfield seam scout (architect-alphonso). All were verified on `main` `aedb30cddd`. Each decision below cites its evidence.

## R1 — Are the issues still real?

- **Decision**: #2991 and #2066 stay open. #3519 is narrowed to part 2.
- **Evidence**:
  - A real `finalize-tasks` run in a scratch project erased `SC-001`, `SC-002b` and `FR-006a` from disk (`mission_finalize.py:1432-1434,1644-1649`; `requirement_mapping.py:493-506`).
  - map-requirements erases on the WP it maps (`tasks_map_requirements.py:464-475`).
  - #3519 part 1 was fixed by `c0f775ee4a` (`_declared_ids`, #3396; PR #3395 itself closed unmerged).
  - #2066 Repro A is partly done (`c1b8ad38a1`). Repro B has no parsed spec-ID set. The "FR-014 campsite fold" credited on #2066 was deferred (`kitty-specs/single-planning-surface-authority-01KVPR00/issue-matrix.md:28`).
- **Alternatives considered**: Closing #3519 outright was rejected; part 2 is live and worse than filed (a declared, unmapped suffixed FR passes `--validate-only`).

## R2 — Where does the grammar live?

- **Decision**: `specify_cli/requirement_mapping/grammar.py`. The module becomes a package; every import path is unchanged.
- **Rationale**: One consuming package. The runtime ledger keys on the first-level subpackage (`test_layer_rules.py:195,213`), which is already admitted, so no baseline change.
- **Alternatives rejected**:
  - `kernel`: its README admits only cross-package infrastructure (`src/kernel/README.md:53-56`), and the stdlib-only cores could not import it anyway (`test_bridge_cores_import_boundary.py:46`).
  - `charter`: no consumer, and it adds the `__all__` duty.
  - A new `specify_cli/requirements/` package: it would need a new ledger key.

## R3 — Runtime cores: injection or mirror?

- **Decision**: A required-argument injection through a `Protocol`, carried in `RequirementMappingFacts`.
- **Rationale**: This is the cores idiom ("port gathers; this module decides", `runtime_bridge_cores.py:26`). A mirror constant plus a parity test keeps a second authority alive, which C-001 forbids.
- **Alternatives rejected**:
  - A default-pattern fallback: a silent second authority.
  - Importing the grammar into the cores: this breaks the boundary gate.

## R4 — Value-type shape

- **Decision**: `RequirementId(kind, digits: str, suffix: str | None, mission: str | None)`.
- **Rationale**: Digits are kept as a string because `C-1` and `C-001` are distinct in the corpus (`requirement_mapping.py:273-279`). The suffix is case-sensitive in spec scanning, so the placeholders `FR-00N` (about 37 corpus hits) never parse.
- **Alternatives rejected**:
  - An integer `number`: it collapses digit width.
  - Hyphen qualifiers (`C-007-mission`): they collide with prose compounds (`FR-008-mandated` ×4, `FR-002-only` ×2).

## R5 — Qualified-citation syntax

- **Decision**: `<mission-slug>#<ID>`.
- **Rationale**: 0 existing `slug#ID` uses in `kitty-specs`; all 523 mission directories match the slug charset. A mid-token `#` is not a heading, and GitHub autolinks need digits directly after `#`. The last point is a hypothesis, not tested in a renderer.
- **Alternatives rejected**:
  - `<slug>/FR-013`: collides with paths.
  - The ad-hoc `p#3044/SC-006` seen once in the corpus: ambiguous with issue refs.

## R6 — Where the authoring check attaches

- **Decision**: `setup-plan` (`_evaluate_spec_gate`, after `:445`), exiting 1 on refusal.
- **Rationale**: setup-plan is the existing chokepoint that accepts the spec phase. The orchestrator-api `plan` is a pass-through (`commands.py:2442-2447`) and classifies errors only inside `except typer.Exit` (`:2459-2469`), so the refusal must be a non-zero exit.
- **Alternatives rejected**:
  - `spec-commit`: commit transport that never looks at content, and blocking there would stop WIP commits.
  - A new verb: extra surface for no benefit.

## R7 — Orchestrator-api error code

- **Decision**: The envelope is `PLAN_SETUP_FAILED` (registered), and the reason goes in data. This is an operator ruling, Decision Moment `01M3NSKEGC7QNXA1G3711AP77X`.
- **Rationale**: `core/upstream_contract.json` is upstream-derived (`_source_saas_commit`), and the charter requires the owning repo to change first. `_classify_delegate_error:2342-2345` otherwise leaks any payload code. The same latent leak exists for `SPEC_FILE_MISSING` today; this mission fixes it only locally in `plan`.

## R8 — Verdict table

- **Decision**: `malformed` fails; `unknown_spec_id` fails for every kind; `foreign_qualified` never fails. A rejected ref never suppresses the valid refs on the same WP. This is an operator ruling, Decision Moment `01M3NSKBMEKR60XKRJSYQC41G3`.
- **Rationale**: Once refs are kept on disk, the all-or-nothing rule (`mission_finalize.py:1176-1180`, `runtime_bridge_cores.py:266-277`) would let one foreign ref un-map a WP's valid FRs.

## R9 — On-disk form

- **Decision**: finalize never rewrites an item. map-requirements appends new refs in canonical form and deduplicates by canonical form. This is an operator ruling, Decision Moment `01M3NSKHE8T6TBKNFPSJ6BRD2G`.
- **Rationale**: This is the strongest reading of "never erase". It keeps the dossier parity hash (`dossier/hasher.py:194`) stable for refs that are not otherwise changed.

## R10 — Template and pack constraints

- **Findings**:
  - `spec-template.md:101` holds `| FR-EXAMPLE |` inside an HTML comment, so the lint must skip HTML comments.
  - `test_builtin_pack_provenance_ratchet.py:49` counts `FR-\d+` against a tight baseline, so examples must avoid new `FR-` digits.
  - `test_command_template_cleanliness.py:138` rejects real slugs.
  - Prompts and templates are not `pack-manifest.yaml` constituents, so they need no regen. The glossary pack is a constituent and needs `doctrine regenerate-graph`.

## R11 — Supply chain

- There is no dependency change, so the supply-chain section is not applicable (`051-supply-chain-install-safety` was not triggered).

## Adversarial evidence (contested findings and disposition)

| Finding | Source | Disposition |
|---|---|---|
| Uppercase-suffix tolerance would parse placeholders | renata #1 | changed: spec scanning is lowercase-only; tolerance applies only when matching refs |
| Gating of kept rejected refs undefined | renata #2, paula row 4 | changed: FR-019 verdict table (operator ruling) |
| SC discard warning becomes a lie | renata #3, paula row 3 | changed: retired (FR-007) |
| New error code violates the upstream contract | renata #4, paula row 9 | changed: reason in data (operator ruling) |
| "Declared position" undefined; 4 corpus specs would be refused | renata #5 | changed: FR-013 definition; NFR-001(b) lists them |
| Scattered `.upper()` and three tokenizers | paula rows 1, 2, 7 | changed: C-001 covers canonicalisation and tokenisation, plus an arch gate |
| US1 vacuous under `--validate-only` | renata #7 | changed: real write, proven by other written fields |
| Retrospective/substantive regexes | scope lens | deferred_with_rationale: frozen divergence plus follow-up ticket (locality, C-001 allowlist). Note: the consolidation retention constraint-row regex is NOT deferred; WP01 migrates `consolidation/retention.py` onto the grammar (HiC ruling, Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`), so the allowlist holds only these two frozen entries |
| #5079 concern warning | scope lens | deferred_with_rationale: `wps_manifest.py` is not otherwise touched (locality) |
