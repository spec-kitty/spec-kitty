# REASONS Canvas — Red-main references repointed to the directive

> Mission: issue-6693-red-main-refs-to-directive-01M66YZX
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: the built-in red-main rule moved from a procedure to a directive upstream
  (`spec-kitty-open-packs#74`), so every core reference that still names the retired
  `procedure:red-main-release-discipline` either dangles or asserts something the
  fetched packs no longer ship ([research.md](research.md), D1–D4).
- Acceptance: [spec.md](spec.md) FR-001–FR-006 and SC-001–SC-004; the six red tests at
  the bumped pin, this repository's own charter warning, and the stale-reference sweep.
- Definition of done: the red is witnessed at the bumped pin before any fix; every
  reference repointed with no assertion loosened; a guard test that fails on the
  un-repointed ledger; changelog entry; independent review; PR only, no merge.

## Entities
- Pin lockfile (`packs/<pack>.source.yaml`): the only tracked representation of pack
  content; `commit`, `subtree`, `tree_digest`, `requires_core`.
- Fetched pack tree (`packs/built-in/`, `packs/internal/`): untracked, digest-verified,
  produced by `make sync-packs`; the source every doctrine test reads.
- Activation ledger (`.kittify/charter/activation.yaml`) and the compiled catalog
  (`.kittify/charter/charter.yaml`): the project's own activation authority and its
  compiled projection; the catalog is regenerated, never hand-edited.
- Curated artifact edge: a non-default DRG relation core adds on top of the pack's own.

## Approach
- Vendor first, observe the red second, repoint third: the pin bump is what makes the
  defect visible, and the six pre-existing tests are the reproduction — no invented
  surrogate test stands in for them.
- Pin to the commit that carries the change (`72cb7dbc`), not to open-packs `main`, so
  the review surface is the red-main move and nothing else.
- Two reference shapes, not one: some sites key on the artifact id (activation ledger,
  a procedure's `references[]`), others on the composed URN (`procedure:` →
  `directive:`); treating them uniformly is the classic bulk-edit failure
  (DIRECTIVE_035, `occurrence_map.yaml`).
- Tradeoff: rewording one WP01 comment to stop reproducing the retired URN verbatim
  buys a literally checkable stale-reference sweep (NFR-002/SC-004) at the cost of one
  less-greppable migration note.

## Structure
- Doctrine: `spec-kitty-open-packs` (upstream), reached here only via
  `packs/built-in.source.yaml` and `packs/internal.source.yaml`.
- Core reference surfaces: `src/charter/offering/drg/migration/extractor.py`
  (`_CURATED_ARTIFACT_EDGES`), five test files, the `minimal_org_pack_2` fixture,
  `.kittify/charter/activation.yaml`, the compiled catalog + synthesis manifest, the
  project DRG layer, and `.kittify/charter/charter.md`.
- New surface: one fast test module, `tests/charter_offering/test_red_main_ledger_resolution.py`,
  exercising the production readers (`load_activation_ledger`, `IdentityIndex.build`,
  `ledger_findings`).
- No production code is added; the only `src/` change is a curated-edge tuple and its
  comment. No dependency, contract or data-model change.

## Operations
1. Vendor both pins with `spec-kitty charter pack vendor --ref 72cb7dbc` and
   `make sync-packs`; verify with `--check`.
2. Witness the red: run the four named files at the bumped pin and record six failures
   with their reasons.
3. Repoint the curated edge; prove `TestDRGZeroDelta` green; prove the fix non-vacuous by
   reverting the edge.
4. Repoint the five test sites and the fixture; re-run the named files plus the
   historical #4253 test (which must stay green untouched).
5. Write the ledger guard test, watch it fail on the un-repointed ledger, then
   deactivate-then-activate through the CLI seam and delete the stale deny entry.
6. Verify doctor / consistency-check / context, update the charter pointers and the
   changelog, run docs-lint, commit, independent review, PR.

## Norms
- Canonical sources only: the pack is the doctrine authority, the CLI is the ledger
  writer, `make sync-packs` is the fetcher.
- Targeted tests only: no full architectural/e2e/performance/`test-full` sweep
  (NO_FULL_HEAVY_SUITES_IN_MISSION).
- Bulk-edit classification recorded (`change_mode: bulk_edit`, eight categories, four
  preserved-history exceptions, two structural targets for the pin lockfiles).
- Reviewer ≠ implementer; review by re-running the evidence, not by reading the diff.

## Safeguards
- Never hand-edit `packs/built-in/**` or `packs/internal/**`: `make sync-packs`
  overwrites them and the digest check fails.
- Never hand-edit `.kittify/charter/charter.yaml` or `synthesis-manifest.yaml`: both are
  the CLI's regeneration output.
- Never weaken, skip or xfail a gate to reach green; the four remaining red files were
  fixed by repointing, not by relaxing.
- Historical records keep their wording: changelog history, merged ADRs, past
  `kitty-specs/**`, recorded evidence, the #4253 narrative and the pre-relocation
  `content-manifest.json`.
- No push to `main`, no merge, no auto-merge: the operator merges.

## Deviations (append-only)

- 2026-10-30 · WP01 · Added two pin lockfiles as declared `structural_targets`: the
  occurrence map's `serialized_keys: rename` would otherwise be read as claiming the
  pins carry the renamed term, which they do not (they carry SHAs only).
- 2026-10-30 · WP03 · Out-of-ownership edit to the WP01 curated-edge comment (its own
  commit, rationale in the message): the comment repeated the retired URN verbatim,
  which made NFR-002/SC-004 un-checkable by a plain `git grep`.
- 2026-10-30 · WP03 · Deleted the `deactivated_procedures` entry that
  `charter deactivate` wrote. The doctor's own remedy prescribes it: no layer provides
  the retired procedure, so the deny entry can only ever report `DENY_UNKNOWN_ID`.
