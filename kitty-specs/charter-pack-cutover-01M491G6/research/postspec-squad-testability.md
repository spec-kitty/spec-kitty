# Post-spec testability review: charter-pack-cutover-01M491G6

Reviewer: reviewer-renata, using tactic `acceptance-criteria-non-vacuity`. Read-only. Spec read at HEAD `01476e16` (includes C-006).
Lens: fakeability, non-vacuity, edge cases. Format: **severity** | location | finding | proposed spec change.

---

## A. Blockers

### A1. BLOCKER | FR-011 / FR-012 / FR-016 | The `.kittify/doctrine/` cutover is framed as read-side only, but the live WRITE side still targets `.kittify/doctrine/`
Evidence: `src/kernel/doctrine_root.py` is the "M2 read half" only. Its docstring says "M3 performs the actual on-disk data move and flips write call sites over". Write and compose sites still spell the legacy root:
- `charter/activation/synthesizer/{project_drg.py:460, resynthesize_pipeline.py:370/453/482, staging.py:112/145, write_pipeline.py:600, validation_gate.py:184}`
- `charter/offering/drg/project_scan.py:73/200`, `pack_manager.py:288`, `kind_vocabulary.py:295`
- `mission_type_profile_repository.py:52`, `runtime/next/runtime_bridge_composition.py:286`, `_drg_helpers.py:196`

If the implementation removes the fallback (FR-011) and moves the directory (FR-012) without flipping these writers, `charter synthesize` recreates `.kittify/doctrine/`. The next read then either ignores the new artifacts or hits the "run upgrade" error. FR-016 says "used everywhere this mission touches". That wording is a scoping loophole: a site the mission does not touch is exempt by definition.

Proposed change: add an FR, "Write-side cutover: every reader AND writer of the project pack root resolves it through the FR-016 constant", labelled [build]. Its acceptance test runs `charter synthesize --apply` (or `resynthesize`) through the CLI on a migrated fixture. It asserts that the artifact lands under `.kittify/charter-packs/` and that `.kittify/doctrine/` does not exist afterwards. The positive control, on the same fixture, asserts that the artifact is readable through `charter list --json`. Add an AST/literal gate: no `"doctrine"` path segment is joined to `.kittify` anywhere in `src/`, and the gate has a planted-literal self-test.

### A2. BLOCKER | FR-012, US2-2, Edge case 5 | "Lists that equal the stale `default.yaml`" is not a well-defined predicate
Evidence:
- The rc35 migration (`m_3_2_0rc35_default_charter_pack.py`) copied the *then-current* default lists, and wrote only keys that were absent, one kind at a time.
- `m_4_0_0rc5_retire_single_owner_doctrine_ids` later rewrote some ids, with successors, inside those lists.

So a stale list in the wild equals one of several historical `default.yaml` snapshots, possibly transformed by the rc5 retirement table. It need not equal the current file, which FR-005 deletes anyway. The lists also live in `config.yaml` OR `charter.yaml`, because of the two-file activation source (`PackContext.from_config`, INV-2).

Proposed change: define the predicate explicitly.
- (a) Compare per `activated_<kind>` key, never across the whole config.
- (b) Use order-insensitive set equality after id normalisation, so that the directive stem and `DIRECTIVE_NNN` compare equal.
- (c) Match against a frozen, migration-embedded set of every shipped `default.yaml` snapshot. Include each snapshot both before and after the rc5 retirement transform, because the file is deleted.
- (d) Check both activation sources.
- (e) State what happens to `activated_kinds` (default.yaml lists 8 kinds and omits glossary_packs, anti_patterns and skills) and to `mission_type_activations`.

The test needs one fixture per snapshot, plus a near-miss fixture (snapshot minus one id). The near-miss is the same-fixture negative control: it must be left untouched.

### A3. BLOCKER | FR-005 vs migration chain | Deleting `default.yaml` breaks the rc35 migration for projects upgrading from before rc35
Evidence: `m_3_2_0rc35_default_charter_pack` returns errors when `_DEFAULT_YAML_PATH` is missing (lines 152-156). Other readers of `default.yaml` that the spec never mentions:
- `m_unify_charter_activation`
- `org_charter.py:406`
- `interview.py:127`
- `_resynthesis_preflight.py:37`
- `compiler.prepare_mission_type_activations:620-632`
- `pack_manager.merge_defaults:1123`
- `init.py` (`DefaultCharterPackMissingError`)
- `upgrade.py:479`

FR-015 names only three of these.

Proposed change: add an FR that inventories every `default.yaml` / `default_pack` consumer and says what each becomes: the effective set, the `default` preset, or retirement as a no-op. Back it with a gate: zero importers of `charter.activation.default_pack`, and the gate has a planted-import self-test. Add a scenario: "a pre-rc35 fixture upgrades straight to the cutover version with 0 migration errors, and its effective set equals the default preset."

### A4. BLOCKER | FR-011, US2-5 | "Any charter command fails naming `spec-kitty upgrade`" contradicts `PackContext.from_config`'s documented totality
Evidence: the docstring says construction "is total and never raises on an unprovisioned project", because PackContext sits on dozens of hot paths (`next`, `implement`, and others). A lazy implementation can satisfy US2-5 with one check in `charter activate`. A thorough implementation breaks `spec-kitty upgrade` itself, if upgrade builds a PackContext before migrating.

Proposed change:
- Name the detection seam: one function, called at the CLI root callback, with exemptions only for `upgrade`, `--version` and `init`.
- Make US2-5 a parametrised CLI test over every top-level command group, `next` and `implement` included, against one legacy fixture.
- Add a positive control: the same fixture after `spec-kitty upgrade` runs every command without the error.
- Add an explicit scenario: "`spec-kitty upgrade` on the legacy fixture succeeds".

### A5. BLOCKER | FR-008, US4-1 | Removing installed old skill copies from consumer projects has no owning FR
US4-1 requires a freshly upgraded project to show no `spk-doctrine-*` or `spec-kitty-*` skill. FR-012's migration scope covers config, the directory and the activation lists only. FR-008 says "generated agent copies regenerated", which is the copies in this repo. The copies under `.claude/skills`, `.agents/skills` and the rest, plus `.kittify/command-skills-manifest.json` and `skills-manifest.json`, are not covered for consumers. A lazy implementation renames the sources and passes a scan of this repo.

Proposed change:
- Add the consumer-side retirement to FR-012, or add a new FR. It must go through `get_agent_dirs_for_project` and respect directories the operator deleted.
- Test it through `spec-kitty upgrade` on a fixture with `.claude` and `.agents` installed. Assert that the old names are absent AND the new names are present on the same fixture, and that the manifest has no orphan entries.

---

## B. Should-fix: per-row fakeability and test shape

| Row | Fake that passes today's wording | Required test shape |
|---|---|---|
| FR-001 / SC-001 | `--preset` hard-codes the `minimal` ids, or `default` writes the full current id list. That passes "equals" today but drifts tomorrow. | A CLI test through `spec-kitty charter activate`, then read back with `charter list --json`. For `default`: assert every `activated_<kind>` key is ABSENT in the activation source, and do not compare id lists. Positive control: a fixture pack whose `default` preset lists one id must write that id, which proves the reader honours preset data. Add a drift test: add a synthetic artifact to a copied built-in pack fixture and assert it is effective after `--preset default` (US1-2). |
| FR-002 | A YAML file in `packs/built-in/presets/` that nothing reads. | Folded into FR-001's drift test. Add a half-by-half check: delete the preset file and the command must fail. |
| FR-003 [ratchet, no-op yes] | `init` keeps a hard-coded mission-type list. | The label is defensible, but the named control is weak. Use a positive control on the same fixture: run `init` against a built-in pack copy whose `default` preset lists a different mission-type set, and assert `init` writes that set. Without this the test cannot tell whether `init` reads the preset. Run it through the `spec-kitty init` CLI, not `provision_default_mission_type_activations`. |
| FR-004 | `pack list` prints only built-in presets. | A fixture with two org packs (one with `presets/`, one without) plus a fetched pack in the cache. Assert the list output per pack. The no-presets pack is the negative control. |
| FR-005, FR-007 | A hidden Typer alias (`hidden=True`) passes a `--help` listing scan while it still works. | Invoke each old spelling (`charter pack apply default`, `doctrine fetch`, `doctrine pack validate`, ...) and assert the Typer "No such command" path and exit 2. Positive control in the same harness: the new spelling exits 0. Add an import probe that `charter_pack_registry` and `BUILTIN_PACKS` are gone. |
| FR-006 / SC-004 | "Every workflow ... verified one by one" with no enumerated list. | Enumerate the current group, verified at HEAD: `doctrine {fetch, regenerate-graph [--check], new, validate, pack validate, pack assemble, org init, org validate, mission-type list, asset list, asset path}`. One parametrised CLI test per row: run the new spelling on the same fixture and compare it with recorded old-command output (exit code plus key output). In-repo callers must move too: `.github/workflows/packs.yml:225/229` runs `spec-kitty doctrine regenerate-graph --check`, `Makefile:47` references it, and so does the CLAUDE.md pack-tier section. Name these in the FR. |
| FR-009 | `CharterPackManager = ActiveCharterManager` alias. | AST/import gate: the old symbols are not importable from any module, and the string `CHARTER_PACK_CONFIG_INVALID` is absent from `src/`, with a planted self-test. `activate.py:106` calls the code "stable" and JSON callers see it, so it must appear in the changelog Before/After. |
| FR-010 / SC-003 / NFR-002 | A gate that scans 0 files, or one whose allowlist is a path glob covering `src/`. | See section D. |
| FR-012 / NFR-004 | Idempotence asserted on a fixture that never had legacy state, which is vacuous. | Run on each NFR-001 fixture: after run 1, assert something changed (positive control), then assert that run 2 changes 0 bytes (tree hash over `.kittify/` plus `.gitignore` plus the agent dirs) and that `detect()` is False. Run it through `spec-kitty upgrade`, not `migration.apply()`. |
| FR-013 | A glossary entry that exists but is not linked. | Assert the four terms resolve through the glossary pipeline. Grep shows zero living citations of `2026-08-22-2`, which is the absence check, and the positive control is that the new citation target exists. The ADR also amends the glossary guard "'active' never describes bundle state"; FR-013 does not say so (see E1). |
| FR-014 | Delete every pin. | Allowed by the wording ("or deleted"). Require a count: each deleted pin is listed with the reason it can never pass. |
| FR-015 / US5 | Seed from `list_available` with the truncated org chain. | The #4399 squad documented exactly this failure in `pack_manager._effective_ids_for_kind`. The fixture needs at least TWO org packs and an artifact whose declared `id:` differs from its filename stem. Run the test per caller through its CLI entry point: `charter interview`, the `charter org`/union command, and `spec-kitty upgrade` for unify. Half-by-half: revert each caller separately. Add this to the "landing no later than FR-002" ordering as a test-ordering constraint in C-006. |
| FR-016 | Constants defined but literals left in place. | Literal gate as in A1. Add a census floor: the gate must find at least N former literal sites at base, so it does not run vacuously. |
| NFR-003 | A 2 s wall-clock limit on a cold Python CLI is flaky across machines and is not pinned to anything. | Measure in-process (CliRunner) under the existing `timing` marker as a median of 5 runs, or as a budget relative to `charter list` on the same fixture. State which run lane executes it. |

---

## C. NFR-001: how to measure the effective artifact set

As written, "effective artifact set before" cannot be measured after the cutover, because FR-011 removes the code that can read the legacy fixture. The "before" set must therefore be a golden file.

Proposed measurement:
1. **Source of truth.** Use `build_activation_aware_doctrine_service(repo_root)`, which is what `pack_manager._effective_ids_for_kind` reads. For each `ArtifactKind` attribute, take the key set of the mapping. Include directives, which that helper skips, so read `service.directives` directly. Add `mission_type_activations` from `PackContext.from_config` and the in-force skills (`required_skills` while `activated_skills` is absent). Expose this as one helper, `effective_set(repo_root) -> dict[kind, frozenset[str]]`. The CLI-level cross-check is `spec-kitty charter list --json`.
2. **Before.** Generate it at the mission base commit, where the pre-cutover code reads the legacy fixtures with its shims. Freeze it as `expected_before/<fixture>.json`, together with a generator script and the base SHA. Do not recompute it with the new code.
3. **After.** Run `spec-kitty upgrade` on a copy, then compute `effective_set`.
4. **Assertion.** `after ⊇ before`, with 0 artifacts lost, for every fixture. Non-stale fixtures also require `after == before`. Stale fixtures require `after == before ∪ (built-in ids at upgrade time)`, so they must regain the right ids, not arbitrary ones.
5. **Fixture list.** Extend it with: stale lists in `charter.yaml` (pointer present); a pre-rc35 project; a post-rc5-retired stale list; `governance.doctrine:` in `charter.yaml`; two org packs; and a stale default in one kind with a custom list in another.

---

## D. SC-003 / NFR-002: the vocabulary gate is under-specified

- **Retired names are not enumerated.** "Doctrine" itself stays legitimate (governance content, C-004), so a bare-word gate is impossible and a judgment-based one is vacuous. The FR should list the forbidden tokens:
  - `doctrine pack`, `spk-doctrine-`, `spec-kitty doctrine`
  - `doctrine.org.packs`, `.kittify/doctrine`, `accompanies_doctrine_pack`
  - `CharterPackManager`, `CharterPackConfigError`, `CHARTER_PACK_CONFIG_INVALID`
  - `charter pack apply`, `Pack Default Charter`, `default charter pack`
  - `BUILTIN_PACKS`, `specify_cli.doctrine`, `spec-kitty-charter-doctrine` and the other folded `spec-kitty-*` skill ids
- **The historical roots are not enumerated.** "Documented historical roots" must be a closed list in the spec: `kitty-specs/<other missions>`, `docs/adr/**`, released `CHANGELOG` sections (the gate needs a section parser, not a whole-file exemption), `docs/reports/**`, archive paths, and `.kittify/evidence|migrations` quarantine. Grep shows `.kittify/evidence/*.md` and a quarantine file already contain `.kittify/doctrine`.
- **Living surfaces are not enumerated.** Say whether `.kittify/charter/charter.yaml` and generated `.claude/commands` copies are in scope. The current `charter.yaml` summaries are generated from artifacts and say "doctrine pack" (line 605). The upgrade migration's own legacy-key literals must be exempted, by token or by file, not by directory.
- **Non-vacuity.** Require all three:
  - a scanned-file floor, at least N files, with N recorded at base;
  - a self-mutation test: plant each forbidden token in a tmp living-surface file, and the gate goes red;
  - an allowlist that is empty at close and shrink-only.

  The existing `test_no_legacy_terminology.py` is the model (fragment-built tokens).
- **NFR-002, "every gate touched by this mission closes empty".** Name the gates: `test_doctrine_census`, `test_lifted_cli_doctrine_retirement`, `test_lifted_cli_doctrine_charter_cr02_compat` (a compat-shim test that should be deleted, not emptied), `test_no_deprecated_doctrine_command_in_guidance`, and `test_no_dead_doctrine_paths`.

---

## E. Edge cases

### Missing from the spec (should-fix unless noted)
1. **Mid-mission lanes.**
   - `spec-kitty upgrade` migrates worktrees and auto-commits onto lane branches (`upgrade.py`, `--no-worktrees`), and `.kittify/doctrine/**` and `config.yaml` are tracked.
   - Needed scenario: a mission with an open lane worktree upgrades. The lane commit is bookkeeping-only (`.kittify/`, so it is outside `approved_bound`), consolidation of the renamed directory on both sides succeeds, and `--no-worktrees` leaves the lane failing with the upgrade error (A4).
   - Required test: upgrade with a lane in `approved`; `consolidate` must not refuse with `LANE_MOVED_AFTER_APPROVAL`.
2. **`.gitignore` rules.** This repo's `.gitignore:103-114` ignores `.kittify/doctrine/**` with re-includes. After the move, those rules no longer apply. `graph.yaml` and the overlays could change tracking status, or ignored scratch could become tracked. The migration must rewrite the rules or document them. No FR covers this.
3. **Dirty or version-controlled config.** `config.yaml`, `charter.yaml` and `.kittify/doctrine/` are tracked. The upgrade moves tracked files: does it use a `git mv`-equivalent? With uncommitted edits in those files, does it refuse, or does it carry them over? Specify the behaviour and test it.
4. **`charter.yaml` `governance.doctrine:`.** It is handled today by `apply_legacy_governance_selection_key_compat` (`sync.py:277`). It is also used at `mission_type_profiles.py:1380` and by `m_unify_charter_activation_finalize`. FR-012 says "legacy config keys" but US2 names `charter.yaml`. Make FR-012 name both files. Add a case: the compat helper's both-present rule ("canonical wins silently") must match edge case 2's "removed and reported". Today it does not report.
5. **Org pack descriptors carrying `accompanies_doctrine_pack`.** `PackDescriptor` is `extra="forbid"` (`pack_descriptor.py:48`), and `packs/built-in/pack.yaml:12` writes `accompanies_doctrine_pack: null`. Org packs, whether scaffolded, copied or fetched from the public-packs repo, that carry the field will fail validation after FR-005. The project migration cannot rewrite another repo's pack. **Owner ruling needed** (C-001 forbids a tolerant reader). At minimum, `charter fetch` or `charter pack validate` must give an actionable error, and a scenario must state it.
6. **Org pack whose own directory or config still says `doctrine`.** For example a `local_path: packs/doctrine-foo`, or pack-relative paths inside a pack. This is not project state. State that the rename applies to vocabulary keys only, never to user-chosen path values.
7. **CI scripts that call `doctrine pack validate` / `regenerate-graph --check`.** This repo's own `packs.yml` is one. Add the in-repo callers to FR-007 and keep the changelog Before/After for consumers.
8. **Windows.**
   - The directory move needs to handle an open handle or AV lock (atomic rename onto an existing target fails on Windows).
   - Path separators in config `local_path` values.
   - Long paths.
   - Add a `windows_ci` marked case for the move.
9. **Pre-rc35 project upgrading straight across.** See A3.
10. **`--preset` versus org-enforced activations.** An org `required_<kind>` versus "active charter equals the preset exactly" (US1-1/3). Decide whether the preset replaces or merges, and whether required items survive. Same question for `activated_skills`, whose `effective_when_absent` is "required".
11. **Destructive preset switch.** `--preset minimal` on a customised project silently discards the customisations. Is a confirmation, `--force` or backup required? This needs an owner call.

### Resolutions that appear invented (no evidence in the code or the ADR; flag for owner)
- **Edge 1**, "merge without overwriting and report ids present in both". Nothing in the ADR. The live reader is canonical-wins (`doctrine_root.py:79`), and merging is a different semantics. Choose one deliberately.
- **Edge 3**, "a preset naming an artifact *the pack does not ship* fails". This is wrong for org presets, which naturally list built-in ids. Reword to "an id that does not resolve in the effective pack set".
- **Edge 5**, "reported for the operator to review". There is no reporting channel in the migration contract. Define the output, or drop it.
- **Edge 2**, "removed and reported". This contradicts the existing silent canonical-wins compat behaviour.
- **FR-012**, "including this repository's own `doctrine.org.packs`". **This is false at HEAD**: `.kittify/config.yaml:31` already uses `charter_packs:`. The repository's real legacy state is the tracked `.kittify/doctrine/` tree and the `.gitignore` rules. Correct the FR.

---

## F. ADR ↔ spec drift (owner confirmation)
1. **Silently dropped from the ADR:**
   - §1, the glossary guard amendment ("active charter" is allowed for bundle state). Not in FR-013.
   - §4, `charter pack path <pack>`: the argument changes meaning from a preset name to a pack. FR-006 lists `path` without the semantic change.
   - §4, "`charter pack` holds operations on Charter Packs; activation stays on activate/deactivate". This is the design rule, and no FR states it.
   - Consequences: the changelog Before/After table should be an FR or SC, not an assumption.
2. **Added beyond the ADR:**
   - The name `charter check`. The ADR says only "a top-level `charter` subcommand", and `charter validate`, `lint`, `preflight` and `bundle` already exist, so there is a collision or confusion risk.
   - The presets directory name `presets/`.
   - FR-016 (#5825 path half).
   - C-006.
   - NFR-003's 2 s budget.
   - The merge semantics of edges 1, 2 and 5.
   - The test_reachability scope (FR-014).
3. **Possible additional scope that C-001 implies:** `charter sync` ("No-op kept for compatibility"), the `_apply_legacy_governance_selection_key_compat` private alias, and the `LegacyDoctrineRootWarning` class are compatibility residue. Should they be removed under C-001, or does C-001 cover only doctrine-vocabulary shims? This needs an owner ruling.

---

## G. Nits
- Rename "No-op passable?" to match the tactic's legend, and give each FR a one-line acceptance statement. The spec's ACs live only in user stories, which do not cover FR-005, 009, 010, 013, 014 or 016.
- SC-002 "built-in artifacts shipped at the time of the upgrade": make it measurable as "the upgrading CLI's built-in inventory".
- US2-1 "project artifacts live in `.kittify/charter-packs/`": also assert that `.kittify/doctrine/` is absent.
- NFR-004 should cover the whole of `spec-kitty upgrade`, not only "the migration", because other migrations in the chain could flap.
