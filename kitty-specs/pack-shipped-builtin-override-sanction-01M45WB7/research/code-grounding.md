# Code Grounding: Pack-shipped built-in override sanction (#5767)

- **Grounded against:** `origin/main` @ `14d653bb` (the rc6 candidate), on 2026-10-05.
- **Squad:** a brownfield point-cut grounding squad, run before specify. Each profile was loaded canonically with `spec-kitty agent profile show <id>`:
  - architect-alphonso (architecture lens)
  - doctrine-daphne (doctrine-integrity lens)
  - researcher-robbie (related-issue lens)
  - reviewer-renata (test-suite lens)
- **Orchestrator reproduction:** run through the real CLI.

## 1. How the allowlist is loaded today (consumer file only)

| Claim | Evidence |
|---|---|
| The policy path is hard-wired to the consumer repo. | `src/charter/offering/drg/override_policy.py:46` sets `POLICY_RELPATH = Path(".kittify/doctrine/replaceable-builtins.yaml")`. |
| The loader reads only `repo_root / POLICY_RELPATH`. A missing or empty file gives an empty policy that forbids everything. A malformed file raises `OverridePolicyError`. | `override_policy.py:117-155` |
| The detector keeps only `{urn: kind}` and **drops the `<pack>` part of `org:<pack>` provenance**. | `override_policy.py:182-203` |
| An unlisted URN fails with `not on .kittify/doctrine/replaceable-builtins.yaml`. A directive also needs a non-empty reason. | `override_policy.py:206-239` |
| The only runtime caller is `_adjudicate_org_overrides`, which reads the consumer file and nothing else. | `src/specify_cli/cli/commands/_doctrine_collect.py:863-891` |
| Findings go to `org_drg["unsanctioned_overrides"]` and `org_drg["errors"]`, which flips `report.healthy`. | `_doctrine_collect.py:834-848` |
| An unhealthy report exits 1. The hint names only the consumer file. | `src/specify_cli/cli/commands/doctor.py:1130`, `1173-1191` |
| `doctrine fetch` installs nothing into consumer governance files. | `src/specify_cli/cli/commands/doctrine.py:131-209` → `src/specify_cli/doctrine/snapshot.py:679-728` |
| Fetch keeps the whole tree for git and https sources (including `templates/`). Api sources write only the advertised artifact dirs plus `drg/`. | `snapshot.py:701-704`, `snapshot.py:71-228`, `sources/api_source.py` |
| Nothing in `src/` reads a pack's `templates/setup/`. The path is purely a convention inside the external packs. | repo-wide grep (related-issue lens) |

**Pack skills (#5694) do not add a second load path.** `src/charter/offering/pack_skills/repository.py:12-13,141-145` refuses an `overrides:` of a built-in skill outright, and `packs/built-in/skills/` holds only `.gitkeep`. ADR `2026-09-27-1:163-164` defers built-in skill replacement to "slice 3". Any design here should stay kind-agnostic so that slice can reuse it.

## 2. Red-first reproduction (real CLI, `spec-kitty doctor doctrine`)

Setup:
- A local-path org pack `acme-org` overrides `directive:MINUTES_STAND_ALONE`, which has been a built-in since rc3.
- The pack ships `templates/setup/replaceable-builtins.yaml`, sanctioning that URN with a reason.
- The consumer has no `.kittify/doctrine/replaceable-builtins.yaml`.

Result: `Unsanctioned built-in override(s) — 1 not allowlisted`, **RC=1**.

## 3. Built-in promotion history (built-in DRG node URN set per tag)

| Step | + | − |
|---|---|---|
| v3.2.7 → rc1 → rc2 | 0 | 0 |
| rc2 → rc3 | 4 (the four reported minutes URNs) | 1 (`agent_profile:minutes-maker-mahad`) |
| rc3 → rc4 | 5 (drupal set, `DIRECTIVE_052`) | 0 |
| rc4 → rc5 | 8 | 9 |
| **rc5 → main (rc6 candidate)** | **0** | **0** (identical 354-URN set) |

The reported symptom dates from **rc3**. rc6 adds no new built-in ids, so it does not widen the break.

## 4. Merge facts that constrain scoping

- **Provenance identifies the pack.** Provenance is `org:<pack_name>`, where `pack_name` is the **consumer's registry name**, not a name the pack declares. Evidence: `merge.py:993,1123`, `org_pack_loader.py:562`, `org_pack_discovery.py:89`. A sanction can therefore be keyed to the pack the consumer configured.
- **The last org pack wins at a built-in URN** (`merge.py:927` assigns unconditionally). This contradicts the docstring at `merge.py:1208` ("earlier fragments take precedence"). Only the winning node's provenance survives, so only the override that actually ships is adjudicated. That matches the doctor's "what governs this repo" question. The docstring drift is a boy-scout fix.
- **`charter lint` merges against an empty built-in** (`src/charter/lint.py:169-192`). It cannot adjudicate overrides of built-ins.

## 5. Placement constraints

- **Layering.**
  - `charter.offering` must not import `charter.activation` (`tests/architectural/test_layer_rules.py:513-528`).
  - `override_policy.py` (in `charter.offering`) can use `load_pack_registry` / `OrgPackConfig.effective_root`, which are also in `charter.offering` (`org_pack_config.py:374,436`).
  - It cannot use `OrgCharterPolicy` (`specify_cli/doctrine/org_charter.py:116`, top layer).
- **Strict schemas: forward-compat hazard.** `OrgCharterPolicy` uses `extra="forbid"` (`org_charter.py:133`). So do `OrgPackConfig` (`org_pack_config.py:246`), `_OrgDRGNode` and `OrgDRGFragment` (`org_pack_loader.py:364`).
  - A new key in any of these makes **every pre-fix CLI reject the pack or config**: `charter interview`, `charter lint`, `charter context`, `pack_validator`.
  - Org packs are shared by consumers on mixed CLI versions, so that would break consumers who never upgraded. That is worse than the defect.
- **Not an `ArtifactKind` fact.** `org_requirable` and `selection_overlayable` (`artifact_kinds.py:207-227,312-338`) are per-kind capabilities. A sanction is a pack-level statement about specific URNs, with reasons.
- **Tolerant consumer file.** `load_replaceable_builtins` ignores unknown top-level keys (`override_policy.py:142-148`), so the consumer file can grow keys additively without breaking older CLIs.

## 6. Options evaluated

| Option | Verdict | Why |
|---|---|---|
| **(a) Pack-declared sanction, unioned in doctor** | **Chosen** (placement: §7) | Keeps fail-closed behaviour, the consumer file and per-pack scoping. Read in place, so there is no copy to drift. #2594 can absorb it as "the pack's declared overlay intent". |
| (b) `doctrine fetch` installs/merges the template into the consumer file | Rejected | It keeps a generated copy that still drifts on the next promotion, and the copy is pack-agnostic, so scoping is lost. Fetch does not run for local-path packs. It mutates consumer governance as a fetch side effect, and the copied file has no ownership or uninstall story (#5243). |
| (c) Per-node `replaces: <builtin urn>` + reason | Rejected for now | On promotion, the pack's same-id node becomes an override with no edit to the pack, so the marker is missing exactly when it is needed. It widens `_OrgDRGNode` (`extra="forbid"`) and the merge path, and points the opposite way from #2216 `component-type`, which the owner of the *replaced* artifact sets. |

## 7. Placement decision for (a): pack-root file vs `org-charter.yaml` key

The architect lens preferred an `org-charter.yaml` key, on the grounds of co-location with the future `AUTHORITATIVE` switch. The doctrine-integrity lens accepted either option, as long as the sanction is read through the registry. The orchestrator decided:

**Use `<pack root>/replaceable-builtins.yaml`, with the same grammar as the consumer file.**

- The `org-charter.yaml` key (§5) would make packs that adopt it fail to load on every pre-fix CLI.
- A pack-root file is ignored by older CLIs.
- It reuses one entry grammar and one parser.
- Pack authors move their existing template to the pack root, which is a one-file move.

Because `OrgCharterPolicy` uses `extra="forbid"`, #2594 can later fold the file into the unified surface (or into the org charter) behind a schema version. That is recorded in the ADR authored by this mission.

## 8. Related work (related-issue lens)

- #2082 / PR #2211 (`5c759dde3`): consumer allowlist plus its doctor wiring. Its tests are the contract that must stay green. The original spec is `kitty-specs/doctrine-governance-fidelity-01KW42KY/spec.md`:
  - FR-010 (line 222): doctor reports unsanctioned overrides.
  - FR-012 (line 224): the project tier is ungoverned.
  - **NFR-004 (line 233): fail-closed.**
- #2216 (epic) → #2591 / #2592 / #2593 → **#2594** (blocked; folds replaceable-builtins into `component-type`). The constraint from this chain is **no second authority**. Do not touch `merge.py` behaviour, and do not invent an `AUTHORITATIVE`-like flag.
- #5760: an invalid project override is silently dropped. Same failure class, so a malformed pack sanction must fail loudly.
- #5243: org-pack lifecycle gap. This argues for reading the sanction in place, not installing it.
- #3523: precedent for reading pack content in place.
- #3732: the doctrine-pack → charter-pack rename. Avoid new "doctrine pack" prose.
- **No open PR touches** `override_policy.py`, `_doctrine_collect.py`, `doctor.py`, `doctrine.py`, `snapshot.py`, `org_charter*.py` or `org_pack_loader.py`. Excluded (owned by running missions): `implement.py` (#5635), `mission_creation.py` (#5634), consolidation rollback/reconciliation (#5686 / #5668, PR #5724), and the upgrade runner (#5457 / #4925).

## 9. Test surface (test-suite lens)

### Baseline on origin/main
- **Targeted doctor, override-policy, merge, org-charter, snapshot and fetch suites (15 files):** 303 passed, 1 skipped, 0 failed.
  - Files: `test_doctor_override_diagnostics.py`, `test_doctor_doctrine.py`, `test_doctor_cli_surface_golden.py`, `test_doctrine_collect.py`, `test_doctor_doctrine_selections_snapshot.py`, `test_override_policy_predicates.py`, `test_drg_merge.py`, `test_org_drg_cannot_override_shipped_invariants.py`, `test_builtin_override_policy.py`, `test_charter_kind_vocabulary_single_authority.py`, `test_kind_table_derivation.py`, `test_org_charter.py`, `test_snapshot.py`, `test_doctrine_org_commands.py`, `test_doctor_skills.py`.
- **`tests/cross_cutting/packaging/test_packaging_safety.py`:** 7 passed.
- **Pack-skills and org-charter union/parity:** 37 passed.
- **Pre-existing reds:** none.

### Pins that constrain the design
- `test_doctor_override_diagnostics.py:250,276` call `_adjudicate_org_overrides(merged, built_in_urns, repo_root)` directly, so the signature must stay call-compatible. `:273` requires that `why` contains the substring `replaceable-builtins`. `:204` requires that the `unsanctioned_overrides` key is absent when no packs are configured.
- `test_doctor_doctrine.py:509` freezes the top-level `profile_health` key set (re-pinned by #5729, which added `skills`). New keys must nest under `org_drg`. No test pins `set(org_drg)`.
- `test_doctor_cli_surface_golden.py:376-399` snapshots the `doctor doctrine` docstring. Editing it requires an honest re-pin in the same change.
- `tests/architectural/test_builtin_override_policy.py:66` runs the live repo merge against `load_replaceable_builtins(_REPO_ROOT)`. This repo configures `packs/internal` as an org pack, so the test is **a second load path**. It and the doctor collector must go through ONE shared effective-policy loader, or they diverge.
- `test_kind_table_derivation.py:73` would break if any `required_*` org-charter field were added. That is moot here, because no org-charter field is added (C-001).
- No test currently pins the human block or hint (`doctor.py:1173-1191`) or a malformed consumer allowlist at doctor level (`_doctrine_collect.py:766` → "org-layer post-merge check failed"). Both are gaps to close.

### Pack-root resolution
`load_org_drg` (`charter/activation/drg_activation.py:66`) → `load_pack_registry` → `pack.effective_root(repo_root)` (`org_pack_config.py:374`). That call expands env vars, resolves relative paths, applies `subdir` and checks containment. Fetched and local packs share it. `load_org_pack` stamps `source_ref=str(pack_root)` next to `pack_name` (`org_pack_loader.py:563-564`).

### Red-first tests (to be planned)
**Fixture change:** parametrise `_write_org_override_pack` (pack dir, pack name, sanction).

**Acceptance A:** pack sanction, no consumer file or a stale one. Expect RC=0 and the consumer tree byte-unchanged. Run it with `DIRECTIVE_001` and with the real promoted `directive:MINUTES_STAND_ALONE`.

**Negatives:**
- N2: directive sanctioned with an empty reason.
- N3: cross-pack sanction.
- N5: malformed pack file.
- Union: the consumer sanctions one URN and the pack sanctions another.
- Revocation.

**Other tests:**
- Pure predicate tests in `tests/doctrine/drg/test_override_policy_predicates.py`.
- An architectural parity test: the gate and doctor use the same loader.
- Pin the human hint lines.
