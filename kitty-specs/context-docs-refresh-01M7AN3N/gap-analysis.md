# Gap Analysis: Context docs refresh (audience profiles first)

**Mission**: `context-docs-refresh-01M7AN3N` (issue #7522, epic #3891)
**Iteration mode**: `gap_filling`
**Measured on**: mission branch from `origin/main` at `761b0b0c01`, 2026-11-13 (gathered for this analysis).

## Method

- **Inventory.** Every published living page under `docs/context/` (40 pages), read through
  `scripts/docs/staleness_audit.py`'s own per-page record (`_record`), restricted to `context/`.
  The full-repo run was stopped because it walks git history for all 341 pages; the per-page
  logic is the same, so the figures below match what `python -m scripts.docs.staleness_audit`
  reports for these rows.
- **Divio type.** Taken from the `kind:` frontmatter (confidence `high`); the audit's heading
  heuristic adds `mixed` when headings signal another type (confidence `low`, revisited in `validate`).
- **Reader.** Read from the `audience:` frontmatter, the field `scripts/docs/audience_resolver.py`
  checks.
- **Retired surfaces.** `scripts/retired_surfaces.py` patterns, as the `docs-lint` gate applies them,
  cross-checked with `scripts/docs/retired_surface_burndown.yaml`.
- **Drift.** Targeted probes against the CLI (`spec-kitty <cmd> --help`), the source tree and git
  history. Each finding cites the page and the contradicting source. A full claim-by-claim check
  of every page is the `generate` work of each work package, not this step.

## Coverage matrix (area x Divio type)

The section is an Explanation-and-Reference glossary; tutorials do not belong in it (they live
in `docs/guides/`). Cells: `present`, `present-but-stale`, `missing`, `n/a` (not this section's job).

| Area | Tutorial | How-to | Reference | Explanation | Hub |
|---|---|---|---|---|---|
| Audience profiles (10 personas + 3 hubs) | n/a | n/a | n/a | present-but-stale | present-but-stale |
| Footgun and concept glossaries (`orchestration`, `execution`, `topology`, `team-kitty`) | n/a | n/a | n/a | present-but-stale | n/a |
| Governance and charter (`charter`, `charter-overview`, `governance`, `governance-files`) | n/a | n/a | n/a | present-but-stale | n/a |
| Identity (`identity`, `identity-fields`) | n/a | n/a | present-but-stale (mixed) | present-but-stale | n/a |
| Glossary tooling (`contextive-glossaries`, `glossary-conventions`, `lexical`, `historical-terms`) | n/a | present-but-stale | present-but-stale | present-but-stale | n/a |
| Method and practice (`spec-driven`, `practices-principles`, `testing-taxonomy`, `technology-foundations`, `naming-decision-tool-vs-agent`) | n/a | n/a | n/a | present-but-stale | n/a |
| Product and work model (`product-lines`, `ops-vs-missions`, `mission-types`, `planning-and-tracking`, `dossier`, `system-events`, `configuration-project-structure`) | n/a | n/a | present-but-stale | present-but-stale | n/a |
| Section index (`context/README.md`) | n/a | n/a | n/a | n/a | present-but-stale |

No cell is `missing`: the mission adds no page (spec, Selected Divio Types). Every cell is
`present-but-stale` because 37 of 40 pages name no reader and every page needs the claim check.

## Page inventory

| Page | WP | Kind | Content changed | `updated` (age, days) | Reader | Retired surfaces | Missing refs | Text diagrams |
|---|---|---|---|---|---|---|---|---|
| `context/audience/README.md` | WP01 | Hub | 2026-08-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/audience/external/README.md` | WP01 | Hub | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/audience/external/architect-evaluator.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/external/product-manager-evaluator.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/external/project-owner.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/external/tech-lead-evaluator.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/internal/README.md` | WP01 | Hub | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/audience/internal/ai-collaboration-agent.md` | WP01 | Explanation | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/audience/internal/lead-developer.md` | WP01 | Explanation | 2026-06-27 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/internal/maintainer.md` | WP01 | Explanation | 2026-04-05 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/internal/project-codebase.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/internal/spec-kitty-cli-runtime.md` | WP01 | Explanation | 2026-04-05 | 2026-06-12 (154) | **none** | - | - | - |
| `context/audience/internal/system-architect.md` | WP01 | Explanation | 2026-03-10 | 2026-06-12 (154) | **none** | - | - | - |
| `context/execution.md` | WP02 | Explanation | 2026-11-05 | 2026-11-05 (8) | **none** | - | - | - |
| `context/orchestration.md` | WP02 | Explanation (mixed: How-To) | 2026-11-09 | 2026-11-09 (4) | **none** | `spec-kitty merge`, `src/specify_cli/auth`, `src/specify_cli/delivery`, `src/specify_cli/sync` | `spec-kitty merge` | - |
| `context/team-kitty.md` | WP02 | Explanation | 2026-11-10 | 2026-10-14 (30) | internal/ai-collaboration-agent | `Zeitgeist`, `saas_client`, `spec-kitty sync`, `src/specify_cli/sync` | `spec-kitty charter sync`, `spec-kitty sync` | - |
| `context/topology.md` | WP02 | Explanation | 2026-11-08 | 2026-11-07 (6) | **none** | - | - | - |
| `context/README.md` | WP03 | Hub | 2026-10-13 | 2026-10-13 (31) | internal/system-architect | - | - | - |
| `context/charter-overview.md` | WP03 | Explanation | 2026-10-13 | 2026-10-08 (36) | **none** | - | - | - |
| `context/charter.md` | WP03 | Explanation (mixed: How-To, Reference) | 2026-10-31 | 2026-10-31 (13) | **none** | - | - | - |
| `context/configuration-project-structure.md` | WP03 | Explanation | 2026-10-09 | 2026-10-08 (36) | **none** | - | - | - |
| `context/contextive-glossaries.md` | WP03 | How-To | 2026-10-09 | 2026-09-08 (66) | internal/lead-developer | - | `src/specify_cli/my_new_package` | 1 |
| `context/dossier.md` | WP03 | Explanation | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/glossary-conventions.md` | WP03 | Reference | 2026-10-09 | 2026-09-08 (66) | internal/system-architect | - | - | - |
| `context/governance-files.md` | WP03 | Explanation | 2026-10-30 | 2026-10-08 (36) | **none** | - | `spec-kitty charter sync` | - |
| `context/governance.md` | WP03 | Explanation | 2026-10-31 | 2026-10-31 (13) | **none** | - | - | - |
| `context/historical-terms.md` | WP03 | Explanation | 2026-10-09 | 2026-07-16 (120) | **none** | - | - | - |
| `context/identity-fields.md` | WP03 | Explanation (mixed: Reference) | 2026-09-16 | 2026-04-10 (217) | **none** | - | - | - |
| `context/identity.md` | WP03 | Explanation | 2026-09-30 | 2026-09-30 (44) | **none** | `saas_client`, `src/specify_cli/egress.py`, `src/specify_cli/tracker/saas_client.py` | - | - |
| `context/lexical.md` | WP03 | Explanation | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/mission-types.md` | WP03 | Explanation (mixed: How-To) | 2026-10-18 | 2026-09-27 (47) | **none** | - | - | - |
| `context/naming-decision-tool-vs-agent.md` | WP03 | Explanation | 2026-06-14 | 2026-07-16 (120) | **none** | - | - | - |
| `context/ops-vs-missions.md` | WP03 | Explanation | 2026-11-10 | 2026-11-10 (3) | **none** | - | - | - |
| `context/planning-and-tracking.md` | WP03 | Explanation | 2026-09-30 | 2026-09-30 (44) | **none** | - | - | - |
| `context/practices-principles.md` | WP03 | Explanation | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/product-lines.md` | WP03 | Reference | 2026-10-19 | 2026-10-19 (25) | internal/system-architect | - | - | - |
| `context/spec-driven.md` | WP03 | Explanation | 2026-10-10 | 2026-10-10 (34) | internal/system-architect | - | `scripts/bash/validate-task-workflow.sh` | - |
| `context/system-events.md` | WP03 | Explanation | 2026-10-30 | 2026-03-10 (248) | **none** | - | - | - |
| `context/technology-foundations.md` | WP03 | Explanation | 2026-03-10 | 2026-03-10 (248) | **none** | - | - | - |
| `context/testing-taxonomy.md` | WP03 | Explanation | 2026-10-09 | 2026-10-08 (36) | **none** | - | `tests/architectural/test_pytest_marker_convention.py` | - |

Totals (gathered): 40 pages; 37 name no reader; 3 pages carry retired surfaces (11 burn-down pairs,
`#7522`); 1 text-drawn diagram; 5 pages with a missing path or command; 4 pages with mixed-type
headings.

## Drift findings

Wrong information ranks above missing information. Each row names the page and the source that
contradicts it.

| # | Page(s) | Finding | Contradicting source | Priority |
|---|---|---|---|---|
| D1 | all 10 profiles | `Domain / Context` reads "Spec Kitty architecture 2.x". | `pyproject.toml` `version = "4.0.0rc9"`; charter "4.x — Current active line". | High (WP01) |
| D2 | `audience/internal/README.md`, `audience/external/README.md` | The "Linked Journeys" column cites journeys 001-005 and "Architecture 2.x". | `docs/plans/user_journey/` holds only `README.md`; its current-state note says every journey is a retired 2.x snapshot, moved to `docs/archive/plans/user_journey/`. | High (WP01) |
| D3 | `audience/README.md` | Says profiles are used for "actor mapping in `docs/plans/user_journey/*.md`", and does not say profiles are named in `audience:` frontmatter, which is how pages use them today. | Same as D2; `scripts/docs/audience_resolver.py`; `grep -c "profile: internal/\|profile: external/"` over `docs/` (285 `profile:` entries, gathered). | High (WP01) |
| D4 | `audience/README.md` | Link text reads `internal/index.md` / `external/index.md`; the targets are `README.md`. | #6939 README rename. | Medium (WP01) |
| D5 | `project-owner`, `lead-developer`, `tech-lead-evaluator` | "feature" names the unit of Spec Kitty work ("first accepted feature spec", "active feature streams", "pilot features"). | Terminology Canon (`CLAUDE.md`, charter): Mission, never Feature. | High (WP01) |
| D6 | `tech-lead-evaluator`, `spec-kitty-cli-runtime` | Bare "routing" / "branch routing" and "routes mission flows", an overloaded term without its sense. | `orchestration.md#routing` footgun rule. | Medium (WP01) |
| D7 | `team-kitty.md` | Says `spec-kitty charter sync` "syncs charter artifacts". | The command was removed in #5828 (commit `0189965d78`); `spec-kitty charter --help` lists no `sync`. `governance-files.md` already says so. | High (WP02) |
| D8 | `team-kitty.md`, `orchestration.md`, `identity.md` | Name retired surfaces tracked by the burn-down (`Zeitgeist` identifiers, `saas_client`, `spec-kitty sync`, `spec-kitty merge`, `src/specify_cli/{sync,auth,delivery}`, `src/specify_cli/egress.py`, `src/specify_cli/tracker/saas_client.py`). | `scripts/retired_surfaces.py`; `scripts/docs/retired_surface_burndown.yaml`. | High (WP02, WP03) |
| D9 | `context/README.md` | Describes Team Kitty as "the hosted product model: CLI → per-team Zeitgeist relay → Team Kitty Pulse", read as a live flow. | #6164 removed the hosted CLI entries and clients from open-core (CLAUDE.md, Team Kitty section). | High (WP03) |
| D10 | `spec-driven.md` | Names `scripts/bash/validate-task-workflow.sh`, which does not exist. | Path absent from the tree. | Medium (WP03) |
| D11 | `testing-taxonomy.md` | Names `tests/architectural/test_pytest_marker_convention.py`, which does not exist. | Path absent from the tree. | Medium (WP03) |
| D12 | `contextive-glossaries.md` | One text-drawn diagram. The "missing" path `src/specify_cli/my_new_package` is an illustrative placeholder in an example (false positive, low confidence). | `staleness_audit.text_diagrams`. | Low (WP03) |

Out-of-scope drift found on the way (reported to the operator, not fixed here): `CLAUDE.md`
says "`spec-kitty charter sync` is unrelated (it syncs charter artifacts)", contradicted by #5828.
DIRECTIVE_047 (built-in pack) describes `audience:` as a path list; the shipped schema is
`[{profile, guidance_text}]` (#6929). That fix belongs upstream in `spec-kitty-open-packs`.

## Prioritized gap list

1. **Blocks every other section (WP01):** profile vocabulary and goals (D1, D5, D6), hub accuracy
   (D2, D3, D4), and a named reader on all 13 audience pages.
2. **Wrong guidance that agents follow (WP02):** the footgun pages' anchors and definitions,
   `team-kitty.md` (D7, D8), 8 burn-down pairs.
3. **Remaining section (WP03):** D8 (`identity.md`, 3 pairs), D9 to D12, readers on 23 pages, mixed
   types on `charter.md`, `identity-fields.md`, `mission-types.md`.

Low-confidence items for `validate`: the four `mixed` classifications and D12's placeholder path.
