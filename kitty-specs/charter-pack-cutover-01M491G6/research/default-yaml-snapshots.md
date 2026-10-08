# Released `default.yaml` / `minimal.yaml` snapshots (FR-012 comparand)

Plan research for FR-012 "Stale activation lists" and "Stale kind gate", and for post-spec squad findings B3 and B4. The machine-readable data is in [`default-yaml-snapshots.yaml`](default-yaml-snapshots.yaml). WP06 embeds that data in the cutover migration as migration-private data. It must be captured before FR-005 deletes `src/charter/activation/packs/`.

## Method

- **Distribution.** `spec-kitty-cli` (`pyproject.toml` `[project] name`).
- **Release list.** The PyPI JSON API (`https://pypi.org/pypi/spec-kitty-cli/json`) lists **174 releases**, 0.2.20 to 4.0.0rc5, uploaded 2025-11-02 to 2026-10-02. Three are yanked (`3.2.0rc28`, `4.1.5`, `4.2.0a1`). They were still scanned, since a project could have installed them before the yank.
- **Download.** Every release's wheel was downloaded through the agent proxy with TLS verification on. Each sha256 was checked against PyPI's digest (174 of 174 matched). Each wheel was opened with `zipfile` and deleted right after. No wheel code was imported or executed. YAML was read with `python -I` and `yaml.safe_load`.
- **What was searched.** Every `default.y*ml` / `minimal.y*ml` member that contains `activated_`, anywhere in the wheel. Also every member whose path contains `default_charter_pack` (the rc35 migration).
- **Cross-check.** The three wheels just before the first hit (`3.2.0rc28`, `rc29`, `rc30`) were also searched for **any** YAML containing `activated_directives`. There were none.
- **Dedup.** Lists were deduplicated per key as sets, which is the spec's order-insensitive comparison. Then the later id-rewrite migrations were applied to each released document (see "Rewrite rules") and those results were deduplicated too.
- **Scripts.** They were scratch-only and are not committed. The YAML file is their output.

## Version table

| Releases | Wheel path | Distinct `default.yaml` content | `minimal.yaml` | rc35 migration in wheel |
|---|---|---|---|---|
| ≤ 3.2.0rc30, and every 3.1.x release (including 3.1.7 to 3.1.10, published after rc33) | none | — | — | no |
| 3.2.0rc33 – 3.2.0rc35 | `charter/packs/default.yaml` | D1 | none | yes |
| 3.2.0rc36 – 3.2.5 (16 releases) | `charter/packs/default.yaml` | D2 = D1 + `paula-patterns` profile | none | yes |
| 3.2.6rc1 – 3.2.6rc2 | `charter/packs/default.yaml`, `charter/packs/minimal.yaml` | D3 = D2 − toolguide `rtk-search-tooling` | M1 | yes |
| 3.2.6 – 4.0.0rc4 (8 releases: 3.2.6, 3.2.6.1, 3.2.6.2, 3.2.7, 4.0.0rc1–rc4) | `charter/activation/packs/{default,minimal}.yaml` | D4 = D3 + `doctrine-daphne`, `randy-reducer` profiles | M1 | yes |
| 4.0.0rc5 | `charter/activation/packs/{default,minimal}.yaml` | D5 (single-owner retirement; see below) | M2 | yes |

- In total, 30 releases ship a `default.yaml`, with 5 distinct contents, and 11 releases ship a `minimal.yaml`, with 2 distinct contents.
- **Earliest wheel containing `m_3_2_0rc35_default_charter_pack`: 3.2.0rc33.** The module is named after its `target_version` (`3.2.0rc35`), not the release that first shipped it. The runner applies it only when `from < 3.2.0rc35 <= to`. A project whose rc35 write happened at rc33 or rc34 is therefore unlikely, but D1 is identical across rc33 to rc35 anyway.
- The working tree (`4.0.0rc6`, unreleased) has `default.yaml` and `minimal.yaml` set-equal to 4.0.0rc5 on every key. It needs no extra snapshot unless the files change before FR-005 deletes them. If they do change, add that release.
- Releases carry no context-scoped or other extra keys. Every `default.yaml` has exactly the 10 keys: `activated_kinds`, `mission_type_activations`, and 8 `activated_<kind>`. None carries `activated_glossary_packs`, `activated_skills` or `activated_anti_patterns`. Every `minimal.yaml` has `activated_kinds`, `mission_type_activations`, `activated_directives` and `activated_tactics`.

## Per-key distinct lists (`default.yaml`)

| Key | Distinct original lists (size: releases) | Extra post-rewrite list | Total distinct |
|---|---|---|---|
| `activated_kinds` | 8: all 30 | — | 1 |
| `mission_type_activations` | 4 (`software-dev`, `documentation`, `research`, `plan`): all 30 | — | 1 |
| `activated_directives` | 19: all 30 | — | 1 |
| `activated_paradigms` | 8: all 30 | — | 1 |
| `activated_procedures` | 13: all 30 | — | 1 |
| `activated_mission_step_contracts` | 17: all 30 | — | 1 |
| `activated_agent_profiles` | 15: rc33–rc35; 16: rc36–3.2.6rc2 (+`paula-patterns`); 18: 3.2.6–4.0.0rc5 (+`doctrine-daphne`, `randy-reducer`) | — | 3 |
| `activated_styleguides` | 8: rc33–4.0.0rc4; 9: 4.0.0rc5 (+`boring-code-review`) | 9-list is also the rc5 rewrite of every 8-list | 2 |
| `activated_toolguides` | 10: rc33–3.2.5 (with `rtk-search-tooling`); 9: 3.2.6rc1–4.0.0rc4; 12: 4.0.0rc5 (+`java-`, `javascript-`, `python-supply-chain`) | 9-list is also the rtk rewrite of the 10-list | 3 |
| `activated_tactics` | 97: rc33–4.0.0rc4; 95: 4.0.0rc5 | **94**: rc5 rewrite of the 97-list (not shipped by any release) | 3 |

Notes on the tactics lists:

- The 95-list (4.0.0rc5) is the 97-list minus `behavior-driven-development`, `boring-code-review`, `bug-fixing-checklist` and `locality-of-change`, plus `bdd-scenario-formulation` and `supply-chain-install-safety`.
- The 94-list is the 95-list minus `supply-chain-install-safety`. A project that took rc35 before 4.0.0rc5 and then ran the rc5 retirement holds this 94-list. Comparing only against today's file would misclassify it as customised. This is the B4 case, now measured.

`activated_kinds` (B3) has one snapshot in every release: `directives, tactics, styleguides, toolguides, paradigms, procedures, agent_profiles, mission_step_contracts`. No rewrite migration touches it, and `m_3_2_x_normalize_activation_absence` leaves it alone explicitly.

## Per-key distinct lists (`minimal.yaml`)

`minimal.yaml` matters for the "`minimal`-equal lists: unchanged, report" row, not for resets.

| Key | Distinct lists | Total |
|---|---|---|
| `activated_kinds` | `[directives, tactics]`: all 11 | 1 |
| `mission_type_activations` | `[software-dev]`: all 11 | 1 |
| `activated_directives` | 5 (001, 010, 024, 028, 030 stems): all 11 | 1 |
| `activated_tactics` | `[acceptance-test-first, boring-code-review]`: 3.2.6rc1–4.0.0rc4; `[acceptance-test-first]`: 4.0.0rc5 (also the rc5 rewrite of the first) | 2 |

Overlap check: no `minimal` list is set-equal to any `default` list for the same key, so the "reset" and "report as minimal" classes never collide.

There is one asymmetry. When the rc5 retirement removes `boring-code-review` from a `minimal`-derived `activated_tactics`, it appends the successor to `activated_styleguides` only if that key exists. A pure `minimal` project has no such key, so it gets no successor.

## Rewrite rules applied

Source tables, read from the repo:

- `m_3_2_6_retire_rtk_search_tooling.py` (target `3.2.6rc1`).
- `m_4_0_0rc5_retire_single_owner_doctrine_ids.py` (`RETIREMENTS`, target `4.0.0rc5`).
- Both run through the shared engine `_retired_activation.py`.

The engine's per-key rule, for each `Retirement(kind_key, stem, successors)` applied in table order:

1. If `stem` is in the `kind_key` list, remove every occurrence.
2. Only if a removal happened, append each successor `(key2, stem2)` to `key2`'s list, provided that list already exists and lacks `stem2`. The engine never creates a key.
3. Skip the whole retirement if a configured org pack still ships `<prefix>s/<stem>.<prefix>.yaml`.

| Migration | Kind key | Retired stem | Successor | Present in a released `default.yaml`? |
|---|---|---|---|---|
| rtk | toolguides | `rtk-search-tooling` | — | yes, rc33–3.2.5 |
| rc5 | styleguides | `adversarial-squad-cadence` | — | no |
| rc5 | tactics | `bug-fixing-checklist` | procedures `test-first-bug-fixing` | yes; successor already present (no-op) |
| rc5 | tactics | `locality-of-change` | tactics `avoid-gold-plating` | yes; successor already present (no-op) |
| rc5 | tactics | `common-docs-curation` | tactics `common-docs-{scaffold,write,find}` | no |
| rc5 | tactics | `boring-code-review` | styleguides `boring-code-review` | yes; **successor added** (styleguides 8 → 9) |
| rc5 | tactics | `behavior-driven-development` | tactics `bdd-scenario-formulation` | yes; **successor added** |
| rc5 | tactics | `iterative-deepening-review` | — | no |
| rc5 | procedures | `tracker-organisation-workflow` | — (org-pack skip applies) | no |

Forms computed for every released document were `original`, `rtk`, `rc5` and `rtk+rc5`, in runner order (rtk's target is lower than rc5's). Each result was deduplicated against the originals.

The org-pack skip only ever applies to `tracker-organisation-workflow`, which no released `default.yaml` contains. So it creates no extra variant.

The rewrites cross keys: `boring-code-review` moves from tactics to styleguides. The rewrite must therefore be applied to the whole document before the per-key split, which is how it was computed here. The per-key comparison still works on mixed projects, because each key's post-rewrite set is fixed whatever the other keys hold, provided the successor's list exists.

**Why both pre- and post-rewrite forms are needed.** FR-012 runs before every other pending migration. A project upgrading from below 3.2.6rc1 or below 4.0.0rc5 therefore reaches the cutover migration before rtk and rc5 have rewritten its lists, and holds the original form. A project that already passed those migrations holds the rewritten form. Both are in the set, as the spec's inventory row says.

No other migration rewrites ids inside `activated_*`. A search for `activated_` under `src/specify_cli/upgrade/migrations` finds four other migrations; what each one does, and why none adds a snapshot:

| Migration | What it does to `activated_*` | Effect on the snapshot set |
|---|---|---|
| `m_unify_charter_activation` | Appends answers-only ids. For an absent key it first materialises the then-current `default.yaml` ids, then appends. | A superset list, which compares as customised. See gap G2. |
| `m_unify_charter_activation_finalize` | Moves the keys verbatim from `config.yaml` to `charter.yaml`. | None, but FR-012 must check both files, as its inventory row says. |
| `m_3_2_x_normalize_activation_absence` | Writes `[]` for absent per-artifact keys only. | None. See gap G1. |
| `m_3_2_0rc35_default_charter_pack` | Writes D1 to D5 verbatim, absent keys only. | None. |

## Id normalisation

- **Directives.** Every released `default.yaml` and `minimal.yaml` writes stems (`001-architectural-integrity-standard`). No release contains `DIRECTIVE_`, so the snapshots themselves need no normalisation.
- **Normalisation is still needed for project lists.**
  - `answers.yaml` `selected_directives`, which can end up promoted, may use `DIRECTIVE_NNN`. `m_unify_charter_activation` documents this ("the two forms this repository's own answers/config pair actually differ by").
  - Hand-edited configs may also use `DIRECTIVE_NNN`.
- **Mapping for the 19 default directives.** Every built-in numbered directive has `id: DIRECTIVE_<NNN>` where `<NNN>` is the stem's numeric prefix. All 32 numbered built-ins were checked and none differs. A static map `DIRECTIVE_NNN` ↔ the stem embedded beside the snapshots is therefore sufficient, and avoids a runtime doctrine-root lookup (`kind_vocabulary.resolve_config_id`) in a run-first migration.
- **Unnumbered directives** use UPPER_SNAKE ids, for example `use-c4-model-techniques` ↔ `USE_C4_MODEL_TECHNIQUES`. None is in any snapshot, but a generic normaliser should fold that form too.
- **Other kinds.** Ids are file stems in every release, and no kind other than directives has a second id form in the activation lists.

## Gaps and caveats

- **Version coverage.** None missing. All 174 PyPI releases were scanned, including yanked ones. Git history was not needed (the repository is shallow).
- **G1: `[]` from `normalize_activation_absence`.** From 3.2.6rc1 this migration writes `activated_<kind>: []` for per-artifact keys that `default.yaml` never had (`activated_glossary_packs`, and any later per-artifact key in `ACTIVATION_YAML_KEYS`). Under FR-019, `[]` means "none". That is not a `default.yaml` snapshot, so FR-012 as written keeps it. If the intent is "upgraded projects regain new built-ins" (SC-002), the spec needs a decision on whether a migration-written `[]` is stale. Flag for the plan.
- **G2: supersets.** Several writers merged default-pack ids with other ids, so the result equals no snapshot and is reported as customised, which matches the spec's rule:
  - `m_unify_charter_activation` promotion (default ids plus answers-only ids);
  - org-charter `required_*` promotion (`specify_cli/doctrine/org_charter.py`);
  - interview promotion;
  - `_resynthesis_preflight`.
  The upgrade summary should make this case clear to operators.
- **G3: mixed-version projects.** rc35 and `pack_manager.merge_defaults` write only absent keys, so one project can hold keys from different releases. The per-key comparison handles this; a whole-document comparison would not.
- **G4: `charter pack apply`.** It writes `default` or `minimal` with `--force` at any version, using the same released contents. These are covered.
- **G5: tracker org-pack skip.** It has no effect on the snapshots (see "Rewrite rules applied").
- **G6: the `minimal` kind gate (B3 latent defect).** Every released `minimal.yaml` has `activated_kinds: [directives, tactics]`. A project that applied `minimal` is therefore kind-gated off every other kind. The "report, unchanged" row leaves it in place. FR-002 and FR-019 should decide whether that is acceptable.
