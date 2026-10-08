# Op evidence: #4836 (PR https://github.com/spec-kitty/spec-kitty/pull/5827)

Tests and red-first proof: see the PR body's Tests run section. Tracer files of the run (shared by the #5538 and #4836 Ops) follow.

---

# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-10-06 — `spec-kitty charter context --action <x>` prints the same `typescript-mutation-tools` CharterCatalogMissWarning twice (once as a logged warning, once via `warnings.warn`) on every action load; noise only, but it pushes the useful bootstrap summary below the fold.
- 2026-10-06 — The mission-tracer-files procedure only names `kitty-specs/<mission>/traces/` as the home; an Op (`spec-kitty dispatch`) has no tracer location, so ops-vehicle work has to pick one ad hoc.
- 2026-10-06 — Any pytest invocation pays ~2 min of startup (collection/imports) before the first test, so a single-file red-first loop costs 2 min per iteration; batching the red proofs into one run mattered.
- 2026-10-06 — `ruff format --check --force-exclude` silently skips ratchet-listed files ("4 files already formatted" for 10 paths); easy to misread as all-clear.
- 2026-10-06 — The docs ledger's "doctrine-only commands" list came from the deprecation banner, which is the only place that enumerates what has no `charter` successor; deriving the migrated set from Typer callback identity is more reliable than the banner text (the banner could drift).
- 2026-10-06 — CI tests (docs) caught what my local runs didn't: the ADR description was 206 chars (band 50-180). I never ran tests/docs locally for a docs-only addition; fixed in 5662e4ee and ran the whole tests/docs dir (1742 passed). Lesson: a new docs page means running tests/docs.
- 2026-10-06 — CI architectural battery 2/2 caught a layering defect: specify_cli may not import charter.offering directly (test_runtime_charter_doctrine_boundary). Three of my #5538 imports did; switched to the charter.drg facade. I had run test_layer_rules and test_charter_no_specify_cli_import, but not this boundary test — the specific-gate selection missed the one that applies to new charter.offering imports from specify_cli.

---

# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-10-06 — Started by grounding #5538 myself before the squad: the named mirror is a *function-local* dict, which the #5409 gate deliberately does not scan, so "widen the gate's scope" alone would not catch it. The widened gate must also cover function-local assignments, or the mirror class survives by moving into a function body.
- 2026-10-06 — While grounding #4836 Finding C, found a sibling defect class: a mechanical `doctrine.` → `charter.offering.` rewrite (the src/doctrine → src/charter/offering module move) also rewrote *config-key* references in operator text — `charter.offering.org` (real: `charter_packs.org`, legacy `doctrine.org`), `governance.charter.offering.*` (real: `governance.charter.*`), `charter.offering.template_set`. A structural check is cheap: every `charter.offering.<x>` token on a living surface must name an importable module under `charter.offering`.
- 2026-10-06 — #5538 red-first: committed the widened gate + pack_validator test alone (2a5190cc). Red evidence: gate named 7 sites; pack_validator totality red for template/asset/glossary_pack/anti_pattern/skill; asset edge reported "dangling DRG edge — target URN 'asset:company-logo' not in built-in or pack artifact set".
- 2026-10-06 — The "8 classic kinds" (restated at 5 drain sites) has no honest existing predicate — glossary_pack/skill/asset share the same layered repository base, and SELECTION_OVERLAYABLE matches by set but not by meaning. Named it once as `ArtifactKind.core` / `CORE_KIND_PLURALS` and kept each site's behaviour; the coverage gaps go to a follow-up rather than silently widening doctor output.
- 2026-10-06 — Near-miss: deriving `_kind_singular` from ORG_PLURAL_TO_SINGULAR_KIND (as the squad suggested) would have regressed `mission_step_contracts` (the org universe keys it on `mission_steps`) — exactly the convention trap #5538 described. Caught by printing all 11 reachable inputs before running tests; now pinned by a parametrised test over the augmentation plurals.
- 2026-10-06 — #5538 blast radius green on the fix tree (d32a46ba content): 7922 passed, 34 skipped, 0 failed in 12m31s (-n auto --dist loadfile over tests/charter, tests/doctrine, tests/specify_cli/doctrine, the doctor/doctrine CLI test files, the selections snapshot, and gates test_charter_kind_vocabulary_single_authority, test_kind_table_derivation, test_charter_no_specify_cli_import, test_no_dead_symbols).
- 2026-10-06 — #4836 grew from three named surfaces into two derived gates. The config-key-as-module-path class (18 hits) and the migrated-command class both had more members than the issue listed: the SPDD skill pointed operators at a governance.yaml key the helper never reads (it reads activated_* in config.yaml / the pointed charter.yaml) — my first "fix" moved it to another wrong key, caught only by reading activation.py; and runtime remediation messages (charter context catalog-miss, compiler, org-pack discovery, the `charter new`/`charter org init` hints and the org-pack README template) told operators to run the deprecated spelling. The command gate now also scans non-docstring Python string literals; docstrings/comments describing the deprecated group stay.
- 2026-10-06 — Gate scoping decisions: design plans (docs/plans/) describe delivered work packages and are not instructions, so rewriting their commands would falsify the record — excluded from the command gate; generated outputs (cli-commands.md, docs-retrieval-index.yaml) excluded because they regenerate from source.
- 2026-10-06 — #4836 blast radius: 8181 passed, 35 skipped, 2 failed (13m40s). Both failures were stale pins of the deliberately changed catalog-miss hint (bare "doctrine validate", missed by my prefixed sed); re-pinned → tests/charter/test_context_catalog_miss.py 33 passed.
- 2026-10-06 — make test-fast on 14fe15e4-equivalent tree: 2281 passed, 8 skipped, 0 failed (5m48s). Terminology guards (tests/contract/test_terminology_guards.py + test_no_legacy_terminology.py): 113 passed.
- 2026-10-06 — Closeout: squashed the three adjacent review-fold commits (non-reordering), rebased onto origin/main 0d4c7583 cleanly, re-ran the gates (143 passed), lint/format/freshness clean, force-pushed own branch with lease, opened draft PR #5827 and subscribed to its activity.
- 2026-10-06 — The packs.yml internal-pack job I edited (`charter org validate packs/internal`) is path-filtered and skipped on #5827; verified the command locally instead: 0 errors, 0 advisories, exit 0.

---

# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-10-06 — Decision: #3732 gets classification + proposed naming only, then a hard stop for Stijn's ruling. Alternatives: rename the uncontested RESIDUE class now. Rationale: operator instruction; and the settled contract (PR #3791) fixes the target words but not the occurrence map, which the epic says must be reviewed before any edit.
- 2026-10-06 — Overlap check (tracker lens): PR #5816 merged today and touches only .kittify charter state; runtime_bridge chain (#2560/#2561/#2562) has no open PR and no shared files. Only conflict surface is docs/changelog/CHANGELOG.md (three open PRs append to Unreleased) → write the changelog entry last, right before the rebase. Link (not absorb): #5770 (pack_assembler required_* list — may trip the widened gate), #5499 (pack_validator edge-endpoint parser duplicate), #4835, #2352. #4098 is closed; `charter new`/`validate` exist, so #4836 is unblocked.
- 2026-10-06 — #3732 rulings escalated to Stijn (R1 `charter pack` CLI group ownership; R2 `minimal` as a Pack Default Charter; R3 spk-doctrine-* alias vs keep — tracker records contradict; R4 alias removal milestone). Docs ledger adds an R1 sub-question: five commands live only under `doctrine` (regenerate-graph, pack validate, pack assemble, asset, mission-type list) and need a charter home. Also found, not a ruling: `.kittify/doctrine` is a split path contract (readers prefer `.kittify/charter-packs/`, writers still hard-code `.kittify/doctrine`); the path rename waits on that data move.
- 2026-10-06 — #4836 scope widened by evidence: onboarding procedure names no command for validation (:35,:204,:213) or graph regen (:198-200); skill lines 154/480/490 (legacy path, wrong override path, doctrine-only mission-type list) join the named :136/:485/:295. `doctrine mission-type list` stays (doctrine-only; the charter variant lists only activated types) and gets an explicit "expected banner" note instead of a rewrite.
- 2026-10-06 — Correction (code ledger, verified): "charter pack" has THREE live code senses, not two. The third — the project's activation state in `.kittify/config.yaml` (`CharterPackManager`, `CharterPackConfigError`, error code `CHARTER_PACK_CONFIG_INVALID`, 134 lines) — has no term in the settled contract and is not the Charter Bundle (that is the `.kittify/charter/` tree). I had told Stijn it was Charter Bundle residue; withdrawn and escalated as R5. Also verified: ADR 2026-08-22-2, cited by docs/context/charter.md and charter.md for §74/§76-77, is not in the repo (follow-up issue, not this run).
- 2026-10-06 — VEHICLE: a series of two governed Ops (one `spec-kitty dispatch` each, closed with `profile-invocation complete`), not a full mission. Alternatives: `spk-mission-from-issue` for both. Rationale: neither #5538 nor #4836 changes a consumer-visible contract (no config key, CLI name or pack path moves) — #5538 is internal derivation + a test gate (one behaviour change: a false `drg_dangling_edge` on asset edges goes away, a fix not a contract), #4836 is help/skill/procedure text plus one doctor hint string. Every contract-bearing rename sits in #3732, which is held for Stijn's ruling and would be the mission. Both ops land as separately sliced commits in ONE PR because the session is bound to a single branch (`claude/brave-dirac-1vpewx`).
- 2026-10-06 — #5538 gate shape: widen scope from src/charter to every package under src/ AND from module/class level to every literal at any depth (function-local and bare return displays), keeping rules R1–R3 unchanged. That flags 7 sites; all drained, allowlist stays empty. scripts/ is out of scope (not a package; generate_schemas.py holds frozen ratcheted lists). Alternatives: also add the squad's proposed R1' (padded universe), R4 (glob-valued maps), R5 (operator-token maps), R6 (enum identity maps) now. Rationale: each new rule widens the drain list into files owned by other open work (#5770 pack_assembler) — filed as a follow-up instead, so this gate still closes empty in this change.
- 2026-10-06 — #5538 behaviour: derive `_plural_to_urn_kind` uniformly from ArtifactKind (assets included). Squad probe: a pack with an asset sidecar and a DRG edge to `asset:<id>` fails today with a false `drg_dangling_edge`; derived, it passes. `asset` is a NodeKind. Rejected: preserving the 8-kind set via `_NON_AUGMENTATION_ELIGIBLE_KINDS` — semantic mismatch (augmentation eligibility ≠ URN-addressable). Red-first test pins the asset case.
- 2026-10-06 — Stijn's model (in discussion): a Charter Pack = interconnected charter components + enforced activations + default activations; the project side is the "active charter". Verified the presets are built-in only (hard-coded BUILTIN_PACKS; files in src/charter/activation/packs/, outside packs/built-in/, unreferenced by pack.yaml). Stijn flagged the location as involuntary duplication; measured it: default.yaml claims "all built-in ids" but misses 91 shipped artifacts across 7 kinds, and the rc35 migration / `charter pack apply default` write it as an allowlist, so those projects silently lose newer built-ins. Existing issues #5323 (directives only) and #4400 (promote_activations seam) are point-fix framings; added the full measurement + structural direction to #5323 rather than filing a duplicate. Fix is consumer-visible (changes active sets) → belongs to the #3732 mission after the ruling, not this run.
- 2026-10-06 — RULING (Stijn, #3732 R1/R2/R5): model = charter offering vs active charter; a Charter Pack is a bundle of interconnected charter components with a set of *activation presets*. Built-in presets: `default`, `minimal`. Applying a preset is an activation: `charter activate --pack <pack> --preset <preset>`; `--pack` defaults to `built-in`. Skipping charter activation at `init` == `--pack built-in --preset default`. Packs are intended to ship from the spec-kitty public-packs sidecar repository. Consequences: "Pack Default Charter" is replaced by "activation preset" (amends the #3791 contract); `charter pack apply` folds into `charter activate`; presets become pack-local data (not the hard-coded BUILTIN_PACKS registry in specify_cli). Verified fresh `init` already matches the rule for artifact kinds (writes only mission_type_activations; per-kind keys absent = all built-ins); the drifted default.yaml lists only bite the rc35 migration, `charter pack apply default`, and the #4400 promote_activations callers.
- 2026-10-06 — RULING (Stijn, #3732 R3/R4): skills option B — spk-doctrine-* splits into spk-charter-* (governance, profile-load, glossary, spdd-reasons) and spk-practice-* (bulk-edit, semantic-compression, show-me); the older spec-kitty-* layer is folded in and deleted. `doctrine-daphne` keeps its id and name (known, in use). Aliases: none — full cutover, existing shims removed. My stated interpretation (in the ADR, open to correction): persisted project state is rewritten once by an upgrade migration; no read-side fallback afterwards. Captured as ADR 2026-10-06-1 in this PR (separate docs commit, Refs #3732) so the mission binds to it from the start.
- 2026-10-06 — Stijn confirmed the one-time upgrade migration for persisted state. Rationale recorded in ADR §7: earlier backwards-compatibility layers left mixed naming and code structures that confuse agents and contributors and make users' harnesses contradict themselves.
- 2026-10-06 — Pre-PR review fold (reviewer-renata correctness, paula-patterns structure; both independent of the implementer). Folded: ruff E501/format blocker in runtime/doctor.py (+ red-first test, red on main); mission-type list already has a charter successor (`--include-inactive`) — skills, the doctrine banner and the ADR corrected; maintainer-only built-in branch removed from the consumer-shipped onboarding procedure; terminology-exempt roots unified into tests/_support/terminology_scope.py with gate extras recorded in the policy doc; SYNTHESIZABLE_KINDS public; bare backticked command form + .github/workflows + file floor in the command gate; ADR date-pinning. Kept, with follow-ups: `ArtifactKind.core` (S1) stays as the behaviour-preserving named set — the per-site capability predicates change doctor/lint output and are filed as #5824; gate blind spots #5823; tier/path vocabulary #5825; missing ADR 2026-08-22-2 #5826. Not changed: collision-list order (core order swaps agent_profiles/mission_step_contracts in an unsorted --json list) — called out in the PR, and #5824 suggests sorting.
