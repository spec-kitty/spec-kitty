# Discovery & Research — Glossary: activation ledger and active charter

Mission: `glossary-activation-ledger-01M68JH9`
Issue: spec-kitty/spec-kitty#6562
Base: `origin/main` at `35318ef51c` (2026-10-31)

## Decisions

- **D1 — The defect is in the glossary data, not in `docs/context/charter.md`.**
  `docs/context/charter.md` was already updated by #6496 (commit `f86ced9693`):
  it now carries the "Active charter" entry pointing at
  `.kittify/charter/activation.yaml` and a full "Activation ledger" entry.
  The context page is therefore the wording authority; the remaining defect is
  the glossary term data and the published glossary page.
- **D2 — The published glossary is generated from the seed.**
  `scripts/docs/generate_kitty_specs_docs.py` reads
  `.kittify/glossaries/spec_kitty_core.yaml` (`GLOSSARY_SEED`) to build
  `kitty-specs/glossary.html`; `scripts/docs/glossary_linker.py` uses the same
  seed. The seed still says the active charter lives in `.kittify/config.yaml` /
  `charter.yaml` and has no "activation ledger" term, so the published glossary
  is stale even though the context page is current.
- **D3 — The seed and the built-in pack must stay byte-identical.**
  `tests/architectural/test_glossary_pack_parity.py` compares every seed-present
  field with `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`.
  `packs/built-in/` is not committed here: it is fetched from
  `spec-kitty-open-packs` at the commit pinned in `packs/built-in.source.yaml`
  (`af1c370f3460` at mission start) by `make sync-packs`.
- **D4 — Author the change in `spec-kitty-open-packs`, then re-pin.**
  AGENTS.md ("Pack Tiers" / "Canonical Sources"): to change pack content author
  it in `spec-kitty-open-packs`, then bump the pin with
  `spec-kitty charter pack vendor --pack built-in --ref <sha>` and run
  `make sync-packs`. Editing the fetched tree in core is overwritten and cannot
  be committed. The issue's "To do" says the same.
- **D5 — The issue's proposed wording is the input; the styleguide is the bar.**
  The issue comment carries the proposed definitions; they cite ADRs and the
  `docs/context/charter.md` entries instead of source paths, matching the
  repo's shrink-only provenance style. Keep the substance and tighten to the
  `kitty-glossary-writing` principles (one concept per definition, no circular
  wording, no source-path leaking into the definition body), keeping the
  distinction from the Migration Ledger.
- **D6 — Link the two concepts from the code docstrings that name them.**
  Natural homes: the module docstring of
  `src/charter/activation/activation_ledger.py` (the single activation-ledger
  seam) and the `ActiveCharterService` module docstring in
  `src/charter/activation/resolver.py`. Both name the concepts but neither
  points at the glossary entry.
- **D7 — One stale guide line is in scope.**
  `docs/guides/how-to/governance/troubleshoot-charter.md` still says
  `charter activate --preset` "only writes activation keys into the active
  charter (`.kittify/config.yaml`)". That is the old location and would mislead
  a reader. `docs/migrations/charter-pack-cutover.md` is a historical cutover
  record and is left as it stands.
- **D8 — RED-first test.**
  A focused regression test in `tests/glossary/` asserts the seed carries the
  `activation ledger` term with the right shape and that the `active charter`
  definition names the ledger file and the exclusions. It fails on current
  `main` and passes after the change. The standing pack-parity test is the
  second half of the proof (it fails on a seed-only change and passes once the
  pack is re-pinned).

## Evidence

- `docs/context/charter.md` (~lines 78–104): current "Active charter" and
  "Activation ledger" definitions (commit `f86ced9693`, #6496).
- `.kittify/glossaries/spec_kitty_core.yaml` (~line 746): "active charter"
  still says "in `.kittify/config.yaml` or the charter.yaml it points to"; no
  "activation ledger" term.
- `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (fetched):
  same two defects; its header says it is generated from the seed.
- `packs/built-in.source.yaml`: pin `af1c370f34601f2aa00d45a7a9597ab8d6a46ea1`,
  subtree `packs/built-in`, `clean-tree-sha256` digest.
- `tests/architectural/test_glossary_pack_parity.py`: seed-driven full-key
  parity, plus `_MISSION_ADDED_SURFACES` for pack-only additions.
- ADR `2026-10-19-1-activation-ledger-persists-deactivation.md`: the ledger is
  the single authority; the effective set is allow minus exclusions; an
  exclusion never removes an org-required id.
- Issue #6562 comment (2026-10-21): proposed wording and the file/key-order
  difference between the pack and the seed.

## Open questions

- **Q1 — Re-pin ordering.** The core pin must reference an open-packs commit
  that carries the glossary change. That commit is created by this mission's
  open-packs PR; the operator merges open-packs first, then core. The core PR's
  `## Deferred` names the ordering and the pin commit.
- **Q2 — Changelog target.** This is a user-visible documentation fix. Core
  gets one `[Unreleased]` entry (impact-first, `(#6562)`); open-packs gets its
  own changelog entry under `[Unreleased]`.
- **Q3 — Docstring link form.** No enforced docstring-link gate exists; use a
  plain `Glossary: docs/context/charter.md#…` sentence in the module docstring,
  matching the existing `Glossary:` mentions in
  `src/specify_cli/state/contract.py`.
