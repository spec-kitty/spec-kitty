# REASONS Canvas — Glossary: activation ledger and active charter

> Mission: glossary-activation-ledger-01M68JH9
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: maintainers and operator agents reading the published glossary

## Requirements

- Problem: after #6496 the activation ledger is the single activation authority, but the core glossary seed still names the pre-ledger location for `active charter` and has no `activation ledger` term; the published glossary page is generated from that seed, so readers cannot look the concept up.
- Acceptance: [spec.md](spec.md) FR-001–FR-007 and SC-001–SC-004 — both entries in seed and pack, pack re-pinned, docstring links, stale guide fixed, docs gates green.
- Definition of done: RED-first glossary test, seed and pack in byte parity at the new pin, docs gates errors=0, one review round, changelog entry, draft PR only.

## Entities

- Activation ledger, Active charter, Built-in glossary pack and Glossary seed keep their [docs/context/charter.md](../../docs/context/charter.md) meanings; no new entity or model.
- The seed and the pack are two copies of one term set; the pack is consumer-facing, the seed drives the published page and the parity gate.

## Approach

- Treat `docs/context/charter.md` (#6496) as the wording authority; condense its entries into glossary-term form rather than inventing new prose.
- Keep the issue's proposed wording substance (ledger file, allow minus exclusions, org-required floor, legacy-location caveat, Migration Ledger distinction) and tighten to the styleguide.
- Author the pack change in `spec-kitty-open-packs`, then re-pin; never edit the fetched tree in core (C-001).

## Structure

- Data: `.kittify/glossaries/spec_kitty_core.yaml` (seed), `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (upstream, fetched), `packs/built-in.source.yaml` (pin).
- Docs: `docs/context/charter.md` (already current), `docs/guides/how-to/governance/troubleshoot-charter.md` (stale line), `docs/changelog/CHANGELOG.md`.
- Code docstrings only: `src/charter/activation/activation_ledger.py`, `src/charter/activation/resolver.py`.
- Tests: `tests/glossary/` focused regression plus the standing `tests/architectural/test_glossary_pack_parity.py`.

## Operations

1. Write the focused glossary regression test and observe it fail on the pre-change tree.
2. Apply the seed entries; author the identical pack entries in open-packs and open that PR.
3. Bump `packs/built-in.source.yaml` with `spec-kitty charter pack vendor`, run `make sync-packs`, and re-run the parity test.
4. Add the docstring links, fix the stale guide line and add the changelog entry.
5. Run the targeted tests and docs gates; independent review; draft PR, then green, then flip.

## Norms

- Canonical sources only: docs/context and ADRs, not older mission copies.
- Definition bodies stay short and human-first; no source paths or issue numbers in prose.
- One tight WP; no broad docs sweep.

## Safeguards

- No behavioural code change; no CLI or runtime edit.
- No weakening of the parity gate; the seed and pack change together.
- Never merge; never push `main`; the operator merges.
- No full heavy suite; targeted tests and the named docs gates only.
