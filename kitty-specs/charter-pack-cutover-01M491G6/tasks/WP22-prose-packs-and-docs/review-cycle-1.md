---
affected_files: []
cycle_number: 1
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-08T21:47:04Z'
reviewer_agent: claude
wp_id: WP22
---

# WP22 review feedback, cycle 1

Reviewer: reviewer-renata (claude). Implementer: lexical-larry.
Reviewed: lane-v at 4526761e (WP22 commits 04640291..57947aef).
Verdict: **changes requested**. There are two blockers and two small fixes. The
rest of the WP is sound and needs no rework (see "Verified" below).

## Blockers

### B1. Completion manifest is stale, so a gate is red

`src/specify_cli/_completion_manifest.json` is generated from the Typer surface.
Commit 6791c91b changed five help strings (`charter fetch`,
`charter pack validate`, `charter pack assemble`, `charter org`,
`charter org validate`) but did not regenerate the manifest. It still holds
"org doctrine pack(s)", "Validate a doctrine pack ...", "Assemble multiple
doctrine packs ...", "Manage org-layer doctrine pack authoring ..." and
"Validate an org doctrine pack ...".

- Red: `uv run --frozen pytest tests/architectural/test_completion_manifest_freshness.py -q`
  fails with 1 failed: "completion manifest is stale".
- Regenerating shows that the whole drift is these five WP22 strings and nothing else.
- Fix: run `uv run --frozen python -m specify_cli.completion --regenerate`, commit
  the result as a `chore(generated)` commit, then re-run the gate.

### B2. Example config in `docs/api/environment-variables.md` uses the retired key

Lines ~99-105 (the `SPEC_KITTY_PACK_HOME` example) still show:

```yaml
doctrine:
  org:
    packs:
```

The sentence just above it was renamed to `charter_packs.org.packs[].local_path`,
so the page now contradicts itself. A consumer who copies this block gets a
config that the CLI-root `LEGACY_CHARTER_STATE` gate refuses, because FR-011
removed the fallback. Change it to `charter_packs:`. The `acme-doctrine` paths in
the example are only an org's own name, so changing them is optional.

## Fix in the same cycle (missed tier/module senses in owned files)

- `docs/api/configuration.md:44` reads "never collides with `doctrine.org`'s
  `extra="forbid"` schema". The block is `charter_packs.org`
  (`src/charter/offering/drg/org_pack_config.py`, `_CANONICAL_ORG_PACKS_KEY`).
- `docs/architecture/calibration/README.md:52` cites the dead module path
  `doctrine.drg.loader.merge_layers()`. The live path is
  `charter.offering.drg.loader.merge_layers()`; `specify_cli.calibration.walker`
  imports it from there.

The FR-018 token list does not include these spellings, which is why the prose
slice stayed green. They still fall under the Context rule "config keys ... /
module paths" in the WP prompt.

## Notes (non-blocking; record them in the Activity Log)

- `docs/architecture/profile-load-reliability.md` belongs to WP23 under the WP
  prompt. You edited it to apply the WP21-review carry-over, and the edit is
  correct, but the deviations list does not name it. Add it.
- The `retired_identifiers.yaml` exclusion of `docs-retrieval-index.yaml` is
  ratified by the orchestrator as a logged WP01 follow-up. `doctrine_mode` in
  `batch-api-contract.md` is deferred to WP25. Neither is a WP22 defect.

## Verified (no action needed)

- **Journey page.** `docs/architecture/charter-pack-usage-journey.md` matches the CLI
  (`charter activate --help`, `charter generate --help`, `charter pack list --help`)
  and the source. Checked:
  - replace semantics plus the org's required ids (`preset_application.py`);
  - `--force` applies only to customised keys (`PresetWouldOverwriteError` names
    the keys);
  - `--pack` defaults to `built-in`, and `--json` prints the applied preset;
  - `--compile` only refreshes an existing `charter.yaml`
    (`recompile_catalog`: an early return when `CHARTER_YAML` is absent);
  - the preset path runs the same `recompile_or_notify` tail;
  - `--resynthesize` takes precedence over the default compile;
  - `charter generate --no-from-interview` exists and needs a git working tree;
  - the built-in pack ships `presets/default.yaml` and `presets/minimal.yaml`;
  - `minimal` activates no agent profiles, so the dispatch-net table holds.
- **Related pages.** `setup-governance.md`, `troubleshoot-charter.md`,
  `charter-overview.md` and `charter-commands.md` are accurate. The project layer is
  `.kittify/charter-packs/` (`kernel.charter_pack_paths`), and the synthesize
  fresh-project seed is `PROVENANCE.md` there.
- **Cited symbols.** Every module or symbol the renamed prose cites exists, including:
  - `CharterOfferingService`, `ArtifactLoadError`, `ArtifactResolutionCycleError`;
  - `BaseArtifactRepository`, `ArtifactLayerCollisionWarning`;
  - `ActiveCharterService`, `charter.activation._drg_helpers._resolve_org_root`;
  - `resolve_org_roots`, `charter.offering.assets.models.AssetManifest`;
  - `charter.offering.missions.action_index.load_action_index`;
  - `charter.activation.mission_type_profiles.MissionTypeProfile`;
  - `charter_pack_synthesizer/apply.py`, `test_charter_facades_reexport_offering.py`.
  The org-pack-not-found message in `org-doctrine-layer.md` matches
  `org_pack_loader.py:308-313` word for word.
- **Sense classification.** I spot-checked more than 40 renamed and more than 40
  kept lines across `packs/built-in`, `packs/internal`, skills, `docs/architecture`,
  `docs/context`, `docs/guides`, `docs/development` and `AGENTS.md`. Kept lines are
  content sense ("doctrine asset", "doctrine artifacts", DIRECTIVE_018), C-004 names
  (`doctrine-daphne`), historical contract slugs, or code-matched values
  (`doctrine-maintenance` and `"doctrine/**/*"` in curator-carla). I found no
  wrong-sense rename. In AGENTS.md, "charter skill" matches the
  `docs/context/execution.md` glossary.
- **Files and generated outputs.**
  - AGENTS.md and CLAUDE.md are byte-identical.
  - No doc page was renamed and no redirect was added.
  - No generated agent copy was hand-edited.
  - `charter pack regenerate-graph --check` passes, the CLI-reference freshness
    check passes, and a docs retrieval index rewrite leaves git clean.
  - `inventory_lockfile --strict` shows no drift.
  - The provenance ratchet only shrinks (`repo_paths` 4 -> 0).
- **Red first.** At 04640291, `test_fr010_retired_identifiers_absent` gives 1 failed
  and 3 passed. The assertion is unchanged, and the test is green at HEAD.
- **Consumer-visible names.** No command, JSON key, error code or Python name was
  renamed; the changes are help wording only.

## Commands run (standalone clone at lane-v)

- `uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -n 4 --dist loadfile`:
  310 passed, 1 skipped, 43 xfailed, 0 failed, 0 xpassed.
- `uv run --frozen pytest tests/docs -q -n 4 --dist loadfile`: 1741 passed, 8 skipped,
  1 failed. The failure is the known `test_no_new_dangling_module_doc_pointer` (WP24).
- Gate files, 152 passed, 0 failed:
  - `test_pack_manifest_no_author_edit`, `test_docs_cli_reference_parity`;
  - `test_no_legacy_terminology`, `test_no_dead_doctrine_paths`;
  - `test_no_deprecated_doctrine_command_in_guidance`,
    `test_builtin_pack_provenance_ratchet`;
  - `test_profile_load_resolver_guidance`, `test_packaging_safety`.
- `tests/architectural/test_completion_manifest_freshness.py`: **1 failed (B1)**.
- `make test-fast`: 2281 passed, 8 skipped.
- `make docs-lint`: 0 errors (13 pre-existing warnings).
- `ruff check .`: clean. `ruff format --check .`: 3447 files already formatted.
