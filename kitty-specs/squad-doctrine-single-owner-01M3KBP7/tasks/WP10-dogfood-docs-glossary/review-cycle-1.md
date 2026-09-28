verdict: approved

# WP10 review, cycle 1 (reviewer-renata)

Scope: `git diff a8e0984b..27160ce9 -- . ':!kitty-specs'` in lane-i (commits 5e5ffd09, d5aa133c, 27160ce9). Contract: WP10 prompt, spec FR-009/010/015/023, SC-001, plan.md "Pinned successor ids". Charter review context loaded. Nothing in the lane was changed. A throwaway clone in the scratchpad was used for the migration and generate re-runs and has been deleted.

## Blocking findings

None against the WP10 contract.

## Real finding, not WP10-blocking: consumer gap in WP01's migration, to route before mission acceptance

**`charter.yaml` `governance.charter.selected_*` is not covered by `RetireSingleOwnerDoctrineIdsMigration`, and runtime still reads it.**

- The block is hand-authored or legacy-composed config. `charter.activation.sync` describes the `governance:` section as "hand-authored config". The `consolidate_charter_bundle_fold` migration (`m_unify_charter_activation_finalize.py:235-266`) builds it from a consumer's legacy `governance.yaml`, so many consumers will have it populated.
- `charter generate --force` keeps the block byte-for-byte. In the clone, the generate output still listed all six retired stems there.
- Evidence from a clone of a8e0984b with only `apply()` + `charter generate --force`, and the governance block left as is:
  - `charter context --action plan|implement|review|specify` exits 0.
  - Each context's text still renders `Selected tactics: … bug-fixing-checklist … locality-of-change … behavior-driven-development … common-docs-curation` and `adversarial-squad-cadence` under styleguides. The source is `context_renderers/selection_block.py:469-509`, which uses `doctrine_selection.selected_*` from `governance.charter`.
  - `doctor doctrine --json` reports `{"id": "bug-fixing-checklist", "source": "charter"}` with `healthy: true`.
  - `charter status`, `bundle validate` and `lint` all pass silently.
- So nothing hard-fails. The problem is that every migrated consumer keeps giving agents dead doctrine ids in their governance context, with no diagnostic.
- FR-009 lists exactly four surfaces, so WP01 met the letter of its spec. The gap is in the spec's surface list, and this dogfood run is what exposed it.
- WP10 worked around it locally by hand-editing this repo's block (see 1b below). That is correct for this repo, but the WP10 commit calls it "out of the migration's documented scope". It is not flagged as a gap, which the charter's canonical-sources rule asks for ("trace the source and file an upstream gap").
- **Fix (WP01 owner / orchestrator):**
  1. Add `charter.yaml` → `governance.charter.selected_<kind>` as a fifth surface in `_retired_activation._surfaces_for`, successor-eligible, only when the list already exists.
  2. Extend the SC-003/SC-008 fixture with a populated `governance.charter` block.
  3. Or, if deferred, file an issue and cite it in the mission PR.

## Scrutiny items

### 1a. Six restored placeholder catalog entries: acceptable

- All six (`STYLEGUIDE:java-conventions`, `TOOLGUIDE:maven-review-checks`, `TOOLGUIDE:typescript-mutation-tools`, `AGENT_PROFILE:{frontend-freddy,java-jenny,node-norris}`) parse identical to base dccf6aa7. a8e0984b's charter.yaml is byte-identical to dccf6aa7's.
- I re-ran migration + `charter generate --force` in a fresh clone of a8e0984b. `diff generated head` shows exactly three things:
  - the governance-block edits;
  - the six placeholder blocks, appended at the end of `catalog.references` (base had them interleaved at 1343..1709; only the order differs);
  - the `generated_at` timestamp.
- Nothing else in the catalog was hand-changed. The net diff against base for those six entries is zero.
- Precedent checked: issue #5257 is open, P2, domain:charter, and describes exactly these six ids and the #5253 "surgical catalog repair".
- This is the prompt's "minimal regeneration fallback, with rationale recorded", not an invented edit.
- Non-blocking: generate also reports `Unresolved reference: toolguide/java-supply-chain` and `toolguide/javascript-supply-chain`. These are language-scoped toolguides, the same #5257 class. They were not in base and are not in `activated_*`, so correctly not restored. Worth adding to #5257 as more evidence.

### 1b. Legacy `governance.charter.selected_*` hand edit: consistent

- Diff against migration + generate output:
  - `selected_styleguides` drops `adversarial-squad-cadence` and adds `boring-code-review`;
  - `selected_tactics` drops `behavior-driven-development`, `boring-code-review`, `bug-fixing-checklist`, `locality-of-change` and `common-docs-curation`, and adds `bdd-scenario-formulation`.
- The other successors (`test-first-bug-fixing` in `selected_procedures`, `avoid-gold-plating`, `common-docs-{scaffold,write,find}`) were already present.
- This matches the pinned successor table exactly.
- The block is not compiled output: generate keeps it unchanged. Editing it therefore does not break FR-010's "no hand-editing compiled output" rule.
- The consumer gap is recorded above.

### 2. Migration fidelity: exact

- `answers.yaml` at 27160ce9 is byte-identical to what `RetireSingleOwnerDoctrineIdsMigration().apply()` produces on a8e0984b.
- `charter.yaml` `activated_*` lists are identical to the migration output.
- The catalog and metadata come from CLI `generate`, apart from the six restored placeholders (1a).
- The only hand edits are the governance block (1b) and the placeholders (1a).
- `charter.md` is not touched by `generate` (checked). It is the hand-authored source, so editing it directly is correct.
- Non-blocking (WP01 engine): the engine's ruamel round-trip (`YAML()` default indent) turns `  - x` sequences into `- x`. Comment lines keep their old 2-space indent, so they now sit deeper than the list items (visible in answers.yaml). The migration alone also reflowed about 1.2k lines of charter.yaml before generate rewrote it. This is cosmetic churn for consumers; consider `yaml.indent(mapping=2, sequence=4, offset=2)` or indent detection.

### 3. Charter / docs single owner: pass

- `charter.md:67-71` Standing Order #1 points at `adversarial-squad-deployment` with no point-cut enumeration and no headcount.
- Lines ~130/196/211 say only "at each planning point-cut" (a generic reference, not a list).
- No retired id appears outside the new `Updated:` header, which describes the change.
- The `Updated: 2026-09-28` line follows the file's `> Updated:` convention.
- `docs/development/agent-fleet.md:53` says only "with an adversarial squad at each planning point-cut", with no list, headcount or retired id. "Already compliant" is correct.
- The standing-orders doc section 1 is now a pointer plus a one-line casting summary. Its claims (point-cut list, casting rule, model-tier via model-task-routing, findings-disposition contract) all exist in `packs/built-in/procedures/adversarial-squad-deployment.procedure.yaml`.
- `implementer-ivan.md:36` now points at the `test-first-bug-fixing` procedure, matching the profile YAML.

### 4. Glossary: pass

- The term was removed from `packs/internal/.../spk-internal.glossary-pack.yaml` and added to built-in `spec-kitty-core.glossary-pack.yaml`, in the built-in entry schema.
- Tier: it is a product term (the owning procedure ships in built-in), so it belongs in built-in.
- The alias uses the schema's `aliases:` field. The red-first test resolves it through `GlossaryPackRepository`.
- The pack manifest change covers only the glossary `content_hash` and `manifest_hash`, and `regenerate-graph --check` reports fresh. That fits CLI regeneration, not a hand edit.
- The internal pack has no hash or manifest for its glossary, so no regeneration was needed there.
- No `#NNNN` references or version numbers in the pack prose.
- Nit: one unrelated trailing-space strip on the "answers to" line of the `mission-owner-confirmation`-style entry (built-in glossary, around line 28). Harmless.

### 5. Docs: pass

- Both touched pages have `updated:` bumped to 2026-09-28.
- The description is unchanged.
- The retrieval index shows no drift, and the kept section headings explain why.

### 6. N1/N3: accurate

- N1: my fresh `load_built_in_graph()` on HEAD gives 354 nodes / 1063 edges (suggests 470, requires 354, scope 201, refines 2). This matches the corrected ledger. The arithmetic also holds: 1050 − 51 + 64 = 1063, and +6 + 6 − 1 + 2 = 13.
  - Nit: the rewritten ledger paragraph states the base→head totals twice, and the "(``tactic:common-\n docs-curation``" wrap is awkward. Cosmetic.
- N3: verified with `resolve_context` per software-dev action, comparing the current graph against one where the DIRECTIVE_001→paula edge is flipped back to `requires`:
  - paula is present under `requires` but absent under `suggests` for `specify` and `plan`;
  - it is present in both for implement and review;
  - it is absent in both for tasks and retrospect.
  - The comment's scoping is therefore accurate.
- The out-of-map extractor.py edit is recorded with a rationale, as the prompt requires.

### 7. Red-first test non-vacuity: pass

- The HEAD version of `tests/doctrine/test_dogfood_single_owner.py`, run against a8e0984b content, gives **8 failed, 2 passed**. The 2 that pass are the detector positive control (passes by design) and `test_charter_md_has_no_headcount_language_in_standing_order_1`, which passes at base too because the old text had no headcount. That second test is a forward guard only; non-blocking.
- On HEAD, all tests pass.
- Between red (5e5ffd09) and green, the test was changed: `boring-code-review` came out of the substring list and got a precise tactic-vs-styleguide pin, and a narrow regex now whitelists DIRECTIVE_024's own `locality-of-change` mentions. Both are justified and not weakening.
- Non-blocking: the substring test scans the whole of `charter.yaml`, including `governance`. That is what forced the 1b hand edit, so here it worked as a real consumer-gap detector.

### 8. "No --force flags used" report claim

- This is a report inaccuracy, not a defect. The d5aa133c commit body openly records `charter generate --force`.
- `--force` there is the documented "Overwrite existing charter bundle" flag, which you need to regenerate over an existing bundle. It bypasses no gate or safety check.
- The orchestrator should correct the wording when relaying the report.

### Other notes (non-blocking)

- `.kittify/charter/graph.yml` still names `adversarial-squad-cadence`, `tactic:boring-code-review` and `tactic:common-docs-curation`. So the prompt's check that "grep under .kittify shows only history/evidence" is not strictly met.
  - It was left on purpose: there is no src reader, `test_retired_activation.py` pins Rule 6 as a regression guard, `generate` does not write it, and hand-editing is forbidden.
  - The justification is sound. Consider a residue-cleanup issue.
- The WP prompt's test strategy names `tests/doctrine/test_squad_glossary_term.py`, which does not exist in the lane. This is a tasks-prompt drift; the glossary coverage is in the WP10 test file instead.

## Commands run (lane-i at 27160ce9 unless noted)

```
.venv/bin/python -m pytest tests/doctrine/test_dogfood_single_owner.py \
  tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent \
  tests/charter/test_model_task_routing_resolves.py::test_charter_references_surface_model_task_routing_body \
  tests/charter/test_activate_resolves_no_answers_edit.py tests/architectural/test_no_legacy_terminology.py -q
  -> 112 passed in 130.22s

.venv/bin/python -m pytest tests/doctrine/glossary_packs tests/glossary \
  tests/cross_cutting/packaging/test_packaging_safety.py \
  tests/architectural/test_builtin_pack_provenance_ratchet.py \
  tests/doctrine/drg/migration/test_extractor_projection.py -q -m "not slow" -n 8 --dist loadfile
  -> 222 passed, 3 skipped, 1 warning in 14.91s

PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs .venv/bin/python -m specify_cli doctrine regenerate-graph --check
  -> DRG graph is fresh (rc=0)

charter context --action plan|implement|review --json (lane-local)  -> rc=0 each; plan context names only
  locality-of-change via DIRECTIVE 024 (legit)

PYTHONPATH=$PWD .venv/bin/python scripts/docs/check_docs_freshness.py --ci
  -> exit=0 findings=22 errors=0 warnings=22 (all LINK-HEALTH network probes)
PYTHONPATH=$PWD .venv/bin/python scripts/docs/docs_index.py --strict
  -> exit=0 generated=833 committed=833 drift=False

# non-vacuity (throwaway clone @ a8e0984b + HEAD test file)
pytest tests/doctrine/test_dogfood_single_owner.py -> 8 failed, 2 passed

# migration fidelity (throwaway clone @ a8e0984b)
RetireSingleOwnerDoctrineIdsMigration().apply(.) -> success, 18 changes; answers.yaml == HEAD byte-identical
charter generate --force --json -> files_written [charter.yaml]; charter.md untouched;
  diff vs HEAD = governance block + 6 placeholders (appended) + generated_at only
```

Orchestrator-measured suite result (8 environment false-reds, same as the WP09 baseline) accepted as given.
