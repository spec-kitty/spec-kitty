# #6994 research: architectural gate scan scope versus CI path routing

Op `01M6B968RTCCE2EZ0GD8ZM7DMT`. Read against `origin/main` at `ff069727`. Static reading only:
no gate was run. A three-reader squad read 135 heavy gates, and a literal-path pre-scan flagged
the other 117 heavy gates as reading only `src/**` plus in-trigger files. Rows marked (weak) rest
on an indirect read.

## Where each part of the battery runs

| Part | Files | When it runs |
|---|---|---|
| Always-on lanes (`base.deselect`) | 4 | every PR |
| `architectural-fast` (registry `fast_gate.roster`) | 36 | every PR |
| `architectural-heavy` legs 1/2 and 2/2 | 252 | only when a src-backed group, `architectural` (`tests/architectural/**`) or `ci_config` matches, and the diff is not prose-only |

The `ci_config` globs are `.github/workflows/**`, `.github/actions/**`, `scripts/ci/**`,
`pytest.ini`, `pyproject.toml`, `Makefile`, `.github/ci-module-registry.yml` and
`.github/ci-shard-timings.json`. No router group selects the heavy legs for `scripts/**` outside
`scripts/ci`, `tests/**` outside `tests/architectural`, `docs/**`, `kitty-specs/**`, the packs
pin, or the root files.

The clock bans (`test_clock_import_ban.py`, 34 s; `test_clock_call_ban.py`, 71 s) are heavy. The
fast roster holds 280 s of its 300 s budget, so moving them there is not possible.

## Heavy gates whose scan scope is wider than their trigger

Reads that the existing triggers cover are left out. Packs content is fetched and untracked, so
its only in-repo trigger is `packs/built-in.source.yaml` (and `packs/internal.source.yaml`).

| Out-of-trigger scope | Gates (count) | Examples |
|---|---|---|
| `tests/**` (whole tree, or collection over it) | ~40 | clock bans, the home-pin and home-owner family (8), `same_tier_uniqueness`, `interpreter_shard_coverage`, `fast_tier_marker_completeness`, `module_length_agreement`, `no_sys_modules_patch_dict`, `no_retired_subsystems`, `ruff_pytest_style_baseline` |
| `tests/<narrow>` (named files) | ~10 | `retirement_scrub` and `ci_router_transcription_guards` (`tests/release/ci_retirement_scrub.json`), `coverage_breadth`, `review_claim_no_frontmatter`, `gate_remedy_presence`, `bare_prose_corpus_ratchet` |
| packs (pin) | ~26 | `doctrine_regenerate_graph_roundtrip`, `no_dead_doctrine_paths`, `glossary_pack_parity`, `consumer_census_routing`, `pack_manifest_no_author_edit` |
| `docs/**` (often a sub-tree) | ~19 | `no_dead_src_path_literals`, `dead_builtin_doc_paths`, `retired_charter_vocabulary`, `shim_registry_schema` (`docs/migrations/shim-registry.yaml`), `adr_hygiene_convergence_retirement` (`docs/adr/**`) |
| `kitty-specs/**`, `kitty-ops/**`, `.kittify/**`, `research/**` | ~12 | `upgrade_recovery_preservation` and `dead_port_snapshot_recovery` (archive freeze), `doctrine_census`, `home_pin_scan_limbs`, `out_of_matrix_evidence`, `glossary_*_parity` (`.kittify/glossaries/**`) |
| `scripts/**` outside `scripts/ci` | 6 | clock bans, `first_party_hosts_are_owned`, `lifted_evidence` (`scripts/evidence/**`), `lifted_lint`, `no_deprecated_doctrine_command_in_guidance`, `no_retired_subsystems` |
| Root files | ~10 | `README.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`, `.gitattributes`, `ruff.toml`, `.python-version`, the agent command directories (`.claude/**` and the rest) |
| Any tracked path name | 2 | `no_invalid_windows_filenames`, `transition_guard_shrink_only` (`git grep` over the tree) |

Secondary dependency: `scripts/ci/gate_selection.py::_scan_tree` reads `tests/**` for
`spec_kitty_events` importers, so `test_cli_commands_routing` and `test_consumer_census_routing`
also depend on `tests/**`.

Residual: the prose-only down-route skips the heavy legs for a docstring-only `.py` diff. A gate
that reads docstring text, such as `no_deprecated_doctrine_command_in_guidance` over
`scripts/*.py`, is therefore still skipped for such a diff.

## Cost, from the last 600 commits on main (per commit, approximate)

| Routing | Commits that select the heavy legs |
|---|---|
| today | 259 (43%) |
| plus `scripts/**` | 261 |
| plus `tests/**` | 361 (60%) |
| plus `docs/**` | 458 (76%) |

## Options

A. **Coarse.** Every declared scope selects both heavy legs in full. Simple, but tests-only and
   docs-only PRs pay 2 x 7-10 min legs.
B. **Per-gate (recommended).** Each gate's scope is declared once in the registry. One router
   group carries the union of the declared globs, and a test checks that the router copy matches
   the registry exactly. When a diff matches only declared scopes (no code, `architectural` or
   `ci_config` match), each heavy leg runs only its gates whose scope the diff touches. A
   scripts-only PR then runs about 6 gates, not 250. A code PR is unchanged.
C. **`scripts/**` only.** Route `scripts/**` coarse and record the remaining scopes as baseline
   debt. This keeps a known gap open, which Standing Order #5 prices as debt.
