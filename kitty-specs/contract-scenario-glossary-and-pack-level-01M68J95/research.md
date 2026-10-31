# Discovery — contract scenario glossary and pack level

Issue: #6439 ("Glossary: add 'Contract Scenario'; Pack Level entry says 'tier'").
Grounding date: 2026-10-31, on `origin/main` at `35318ef51c`.

## D1 — The issue still reproduces on current `main`

**Evidence (both halves):**

- `docs/context/governance.md:79`, the **Pack Level** entry, still opens
  "The tier a Charter Pack occupies, declared by the `pack_level` field …" and
  later says "the tier token and the provenance/layer value share a single
  spelling". `git log -S "The tier a Charter Pack occupies" -- docs/context/governance.md`
  finds one commit, `4dd757384d` (docs-only, #6048/#6046) — the wording has not
  been touched since it landed.
- `docs/context/charter.md:54`, the **Charter Pack** entry, carries the same
  claim twice over, as "the tier token".
- `grep -rn "Contract Scenario" docs/` returns nothing but an archived note in
  another mission's `research.md` that explicitly deferred it to this issue
  (`kitty-specs/activate-output-and-identity-01M5ZA9X/research.md:38`).

**Not superseded:** #6403 fixed the `PACK_LEVEL_MISSING` clause of the same
entry (`0778fd53fb`, changelog line under `### Fixed`) and is closed; it left the
"tier" wording alone, which is exactly the split the issue describes. No open PR
touches either entry (`gh pr list --search 6439 OR glossary`). Issue #6439 is
unassigned, unclaimed, and open, with no comments.

## D2 — `docs/context/` is the only surface to author

- `docs/context/glossary-conventions.md` names `docs/context/*.md` as the living
  glossary and `docs/context/index.md` names them "the doctrine-extraction source".
- The seed (`.kittify/glossaries/spec_kitty_core.yaml`) and the shipped built-in
  pack (`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`) are
  gated against **each other** (`tests/architectural/test_glossary_pack_parity.py`),
  and the third authority, `docs/context/charter.md`, is gated only on the
  governing `charter`/`doctrine` term
  (`tests/architectural/test_glossary_authority_parity.py`). Neither gate requires
  a new markdown term to be mirrored anywhere, and neither the seed nor the pack
  carries a **Pack Level** term today (`grep -n "pack_level\|Pack Level"` on both:
  no hits).
- Therefore: author in `docs/context/` only; do not touch the seed, the pack, the
  pack manifest, or the generated glossary page. This is C-001 in the spec.

## D3 — "tier" is the wrong word, and the ADR says so

`docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md` chose
`pack_level` over `pack_tier` and records why, under **Rejected**:

> **`pack_tier` and `layer`.** "Tier" is overloaded (model tiers, tiered rigour).
> `layer` is overloaded by the architectural layer rules.

So the ADR that the entry itself cites already treats "tier" as a rejected word
for a pack's level, and `kernel.pack_tiers` survives as a *module name* only —
decision 2 of the same ADR makes it the one authority for the three level names.
This is the basis for the guard in the new test: strip inline code spans, then
assert "tier" does not appear in the entries this mission edits.

## D4 — What "Contract Scenario" means and where it lives

The proposed entry (issue body) is complete enough to apply verbatim in substance:
a Gherkin scenario that is the behavior half of the charter contract, naming pack
files, calling one operation of `contracts/charter/openapi.yaml` and stating the
answer; `@contract` scenarios run in `verifyAll`, `@provisional` marks behaviour
the conformance corpus has not decided.

- The artifacts it names live in **spec-kitty/spec-kitty-charter**, not here:
  `contracts/` in this repository holds only `mission-status`, `mission-write`,
  `_shared` and lint tooling, and `grep -rn "verifyAll"` finds no hit outside the
  mission spec. The entry therefore has to *describe* a downstream contract, the
  same way **Charter Pack** already describes `charter_packs.org.packs` and
  `presets/<name>.yaml` in consumer projects.
- `grep -rn "Acceptance Scenario\|Conformance Corpus" docs/context/` finds no
  entry for either. The issue asks for "a cross-link from the Acceptance Scenario
  entry"; that entry does not exist in core, so the relation is stated in prose
  (plain text, no dangling link) and the missing cross-link target is recorded as
  a follow-up in the PR's `## Deferred` instead of inventing a second entry here
  (C-003, bounded diff).

## D5 — Where the entry goes, and which rows it carries

- Home: `docs/context/charter.md`, in the Charter Pack cluster. The page's
  headings are flat `###` entries separated by `---` rules; **Charter Pack** is at
  `:50` and the next entry, **Activation preset**, at `:64`, so the new entry goes
  between them (beside Charter Pack, as the issue suggests).
- Rows per `docs/context/glossary-conventions.md`: the four required
  (`Definition`, `Context`, `Status`, `Applicable to`) plus the two optional rows
  that carry the disambiguation the issue asks for: `Do NOT use when` and
  `Related terms`. `Applicable to` matches its neighbour, `4.x`.
- Styleguide `styleguide:kitty-glossary-writing`: one concept per definition, no
  buzzword soup, functional over compositional, define a term without requiring a
  follow-up question, and no "user" where the Human-in-Charge (HiC) holds
  decision authority. The definition is written as "what it does" (names the pack
  files, calls one operation, states the answer) rather than as a composition list.

## D6 — The guard: a standing docs test, not a one-shot edit

The repository already pins glossary prose this way:
`tests/architectural/test_glossary_authority_parity.py:268` asserts the
`Do NOT use when` row on the `charter` entry. The new test follows that shape in
`tests/docs/` (docs-scoped, no new architectural marker):

1. parse the `### Pack Level` and `### Charter Pack` entries out of their pages;
2. strip inline code spans, assert `tier` is absent (case-insensitive), and
   assert `kernel.pack_tiers` is still named — the positive control that stops
   the absence probe from being vacuous;
3. parse `### Contract Scenario` and assert the four required rows plus
   `Do NOT use when` / `Related terms`, and that the definition mentions the
   Gherkin, `@contract` and `@provisional` facts and the `verifyAll` tag behaviour;
4. assert the guard row steers away from "BDD scenarios" and toward the
   acceptance scenarios and the conformance corpus.

Red-first: on the pre-fix tree, (1)–(4) fail — the entry is missing and "tier" is
present in both entries. Half-by-half: reverting only the `governance.md` edit, or
only the `charter.md` entry, reds a distinct assertion.

## D7 — Gates this diff can move

| Gate | How it runs | Why it moves |
| --- | --- | --- |
| docs index | `python -m scripts.docs.docs_index --write`, checked by `tests/docs/test_committed_docs_index_fresh.py` | a new `###` heading changes `docs/development/docs-retrieval-index.yaml` |
| ADR inventory | `python scripts/docs/freshen_adr_inventory.py --check`, `tests/docs/test_freshen_adr_inventory.py` | no new ADR; run it to confirm a no-op |
| docs freshness | `python -m scripts.docs.check_docs_freshness --ci` (errors=0) | inventory lockfile + link health on the edited pages |
| legacy terminology | `pytest tests/architectural/test_no_legacy_terminology.py` | scans `docs/` for its two forbidden terms; neither is ours, but it is docs-scoped so a docs PR runs it |
| spelling | `make docs-lint` (`check_spelling`, `check_changelog_style`) | `docs/context` is US-spelling scoped; the new prose and changelog entry must pass |

## Open questions resolved by decision (no live operator on this run)

- **Q: add the cross-link target entries too?** No — the Acceptance Scenario and
  Conformance Corpus entries do not exist in core; creating them is a second
  scope. Stated in prose, recorded as a follow-up.
- **Q: rename the Organization Tier term?** No — C-003. The word "tier" survives
  there and in *Three-layer DRG* prose; only the pack-level sense is corrected.
- **Q: seed/pack mirror?** No — D2/C-001.

---

# Phase 0 (plan) — decisions carried into the plan

## P1 — Where the guard test lives

- **Decision**: a new module `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py`,
  with no new pytest marker.
- **Rationale**: the test reads `docs/` content, which is exactly the `tests/docs/`
  shard's remit; `tests/architectural/` is for repo-wide architecture invariants
  (`test_glossary_authority_parity` there also carries `pytest.mark.architectural`
  and `doctrine`, and CI selects those shards separately). The docs shard already
  runs on a docs-only PR, so a docs-only diff reds and greens it without touching
  a marker or a CI selection list.
- **Alternatives considered**: extending `test_glossary_authority_parity.py` — rejected
  because that module's scope is pinned to the governing `charter`/`doctrine` pair
  and its docstring says the third authority is deliberately not a full mirror;
  a shell/grep check in `scripts/` — rejected as a non-pytest gate that CI would
  have to be taught to run.

## P2 — What the "tier" probe asserts

- **Decision**: for each of the two entries, strip inline code spans (`` `…` ``)
  first, then assert `re.search(r"(?i)\btiers?\b", body)` is `None`, and assert
  `kernel.pack_tiers` still appears in the Pack Level entry's raw body.
- **Rationale**: `kernel.pack_tiers` is the authority the entry exists to name; a
  naive substring probe would red on it and tempt the next maintainer to allowlist
  the whole guard. Stripping code spans keeps the probe on prose only, which is the
  exact contract the issue asks for ("no longer calls a pack's level a 'tier' in
  prose"). The presence assertion on `kernel.pack_tiers` is the same-fixture
  positive control: it proves the probe can see this entry at all.
- **Alternatives considered**: asserting the exact replacement sentence — rejected as
  brittle prose-pinning; allowlisting `kernel.pack_tiers` — rejected because an
  allowlist inside a new guard is the shape C-002 forbids.

## P3 — Regenerating the docs index

- **Decision**: run `python -m scripts.docs.docs_index --write` from this clone only,
  then verify with `check_docs_freshness --ci`; do not rebuild the CLI reference or
  any surface this diff does not change.
- **Rationale**: the new `### Contract Scenario` heading changes
  `docs/development/docs-retrieval-index.yaml`; that file is generated and a
  committed-freshness test pins it. The brief's shared-machine-state rule warns that
  a *full* CLI-reference rebuild reads a global asset cache other agents rewrite
  concurrently, so the regeneration is scoped to the index this diff moves.
- **Alternatives considered**: letting CI regenerate — not possible, the gate compares
  the committed file.

## P4 — Changelog placement and shape

- **Decision**: one `[Unreleased]` `### Added` entry that leads with the new term and
  covers the wording correction in the same entry, impact-first, `(#6439)`.
- **Rationale**: both halves are one issue and one reader-facing outcome (the
  glossary says what the words mean). The neighbouring #6403 fix sits under
  `### Fixed`; this one adds a term, so `### Added` leads and the correction is
  described as part of the same change, which keeps the entry under the 1,200
  character budget.
- **Alternatives considered**: two entries (one Added, one Fixed) — rejected as
  duplicate noise for a single issue's single edit session.

## D8 — The tier probe is scoped to the entry's definition row (implementation finding)

The first cut of the guard probed the whole entry body, and it went red on the
**Charter Pack** entry for a legitimate occurrence: its `Related terms` row links
`[Organization Tier](#organization-tier)`, a term whose own sense of "tier" is out
of scope (C-003). Fixing that by allowlisting the page or the row would have made the
guard weaker than the claim it pins, so the probe is scoped to the `**Definition**`
row of each entry — that is where the pack-level claim lives, and it is the only row
the issue names. The rest of each entry (error codes, `kernel.pack_tiers`, the
`Related terms` links) is asserted separately by the positive controls. Recorded here
because it narrows the probe from "the entry" to "the claim", and a future maintainer
should see that as a decision with a reason, not as an accident.
