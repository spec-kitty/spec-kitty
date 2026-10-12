<!--
DRAFT PR — target branch: main — DO NOT MERGE (operator merges).
These are PROPOSED governance amendments for operator review.
Title: [governance] Realign 4.x governance to the October direction (PROPOSED amendments)
Branch: governance-realign-oct-direction
-->

## Issue

**Refs** (no single issue; this closes none): #5528 (Mission Status Read API epic), #645
(stable application API / charter-import move), #3101 (charter wheel/repo split), #3504 /
#3022 (open-packs provenance), and the two implicated ADRs
(`docs/adr/4.x/2026-10-01-2-...`, `docs/adr/4.x/2026-10-06-1-...`). Supporting references in
prose only: #5529, #957, #5558, ADR `2026-08-02-1`, ADR `2026-04-25-1`, ADR `2026-08-16-2`,
ADR `2026-08-16-3`. **No `Closes #…`** — this mission moves and re-milestones nothing on the
tracker; a separate tracker pass owns that.

## Change

**For the operator/maintainer:** this is a **documentation/governance-only** change that
realigns the project's governance surface — the charter, `AGENTS.md`/`CLAUDE.md`, the 4.0.0
roadmap, the executive overview, the three domain plans, and two ADRs — to a set of
**operator-ratified strategic decisions (2026-10-12)**. **These are PROPOSED amendments for
your review and merge.** No product code, reducer, gate, or test logic changes. The
confidential strategy material behind the decisions was **not quoted, cited, attributed, or
reconstructed**; the decisions are expressed as repo-public governance in the project's own
words, grounded in the existing epics, ADRs and roadmap.

The six decisions encoded (exactly these, no more):

1. **4.0.0 GA is no longer date-gated.** GA ships "done when done"; RCs keep shipping to early
   adopters off `main`; red-CI-no-release (Standing Order #9) still holds **per RC**. The
   2026-10-16 target is removed from the GA framing in the docs. (The GitHub milestone object's
   due date is handled outside this change.)
2. **The GA gate expands beyond local integrity** to also gate on (a) charter modular
   extraction and (b) the mission-status API backend. The roadmap's "local-integrity-only"
   framing is reframed around this (now a three-leg gate).
3. **Charter modular extraction → its own repository** — an independently-released external
   contract package consumed through `charter.offering.api`, like
   `spec-kitty-events`/`spec-kitty-tracker`. #645 (move the ~129 `specify_cli → charter`
   imports onto the stable API) is its precondition and is **now GA-gating**. `AGENTS.md`
   "Modularity SSOT" / "Shared Package Boundary" record that the enforced layer chain and the
   shared-package-boundary gates **will** gain charter as an external contract package —
   **direction only; no gate code changed.** Grounded in #3101, ADR `2026-08-02-1`, ADR
   `2026-04-25-1`.
4. **The mission-status read API is Build Kitty / open-core (producer side),** not a Team Kitty
   surface. Its Java service (`services/mission-status-api/`) starts **in-repo as a modular
   component** and is **extracted as needed as an open-core surface, never into a Team Kitty
   repo**; `contracts/mission-status/` and the conformance fixtures stay canonical beside the
   Python reducer. **ADR `2026-10-01-2` moves Proposed → Accepted** with a dated amendment
   recording this.
5. **Team Kitty = "Multiplayer Mode," the consumer side.** UI/multiplayer (mission-ui, pack
   composer) consume the open-core API across its contract boundary. The
   "do not build toward Team Kitty" rule is **scoped-lifted** for (a) consumer-side
   UI/multiplayer on the mission-status API and (b) the produce/drain adapter seam
   (`status/adapters.py`); everything else hosted (zeitgeist auth, the hosted backend, the SaaS
   surface) stays frozen unless the operator asks. **ADR `2026-10-06-1` gains a dated,
   append-only amendment** (its original decision is unchanged).
6. **`packs/internal/` + `packs/built-in/` source home → `spec-kitty-open-packs`.** A
   **source-location move only.** The no-bundle invariant is unchanged: internal stays excluded
   from the wheel/sdist (`test_packaging_safety.py` untouched); built-in stays present in the
   consumer install. **Not** a reversal of ADR `2026-08-16-3`. Grounded in #3504/#3022.

Changed, grouped by area:

- **ADRs** (`docs/adr/4.x/`): `2026-10-01-2` Proposed → **Accepted** + Amendment 2026-10-12
  (open-core producer; in-repo-now / extract-when-frozen; GA-gating backend). `2026-10-06-1`
  gains Amendment 2026-10-12 (scoped lift), original content preserved byte-for-byte.
- **Charter** (`.kittify/charter/charter.md`): dated header note; GA = done-when-done + the
  three-leg gate; scoped Team Kitty / Multiplayer-Mode model; charter-as-external-contract-
  package direction; pack-tier open-packs source home (invariant restated intact). *The charter
  is the authority; `AGENTS.md` mirrors it.*
- **`AGENTS.md`/`CLAUDE.md`**: Team Kitty section rewritten to the producer-API-vs-consumer-UI
  model; Pack Tiers open-packs source home; Modularity SSOT + Shared Package Boundary direction
  note (charter as external contract package). No gate code touched.
- **Roadmap** (`docs/plans/4-0-0-milestone-roadmap.md`): a "Direction update (2026-10-12)"
  section; GA date removed throughout; three-leg dependency spine; Theme 3/4 and exit criteria
  re-anchored; mission-status API labelled open-core producer.
- **Executive overview** (`docs/plans/4-x-executive-overview.md`): done-when-done framing; the
  three-leg gate; Team Kitty = consumer.
- **Domain plans**: `api-dashboard` (API = open-core producer; ADR Accepted; Team Kitty =
  consumer; backend GA-gating); `doctrine-charter` (Addendum 2026-10-12: charter extraction
  GA-gating, own-repo, API-as-consumer boundary); `packs-extraction` (§1/§3.1/§3.2/§4: charter
  → own repo, GA-gating; both tiers' source home = open-packs; no-bundle invariant intact).
- **Generated guard artifact (not a content edit):** `docs/development/docs-retrieval-index.yaml`
  regenerated from frontmatter+headings (required by the docs-freshness gate).

Formatting/generated-file churn is isolated to the regenerated docs-retrieval-index.

## Tests run

```
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q   # 96 passed in 171.90s
.venv/bin/python -m scripts.docs.check_docs_freshness --ci --link-check none      # exit 0 — 0 errors, 1 warning (pre-existing)
.venv/bin/python -m scripts.docs.check_spelling --pass typo                       # 0 findings across 689 files
.venv/bin/python -m scripts.docs.inventory_lockfile --write <tmp> && diff         # no drift
PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write                  # regenerated; re-run freshness → 0 errors
```

- The terminology guard was run **by name** (never the bare `tests/architectural/` dir);
  `make test-full` was never run.
- `check_docs_freshness` was run with `--link-check none` (external-link HEAD requests are not
  reliable from the build sandbox; link liveness is orthogonal to these content edits). Its one
  remaining `HELP-DRIFT` **warning** (`spec-kitty spec-commit` recorded help vs live help, over
  "topic branch" vs "feature branch") is **pre-existing and out of scope** — it is not in any
  file this PR touches and reproduces on `origin/main`. (It also indicates a latent
  Terminology-Canon slip in live CLI help; flagged for a separate product change, not fixed
  here.)

Self-review:
- Diff scope is governance docs + the two ADRs + the regenerated docs-index only; no `src/`,
  no gate, no test logic. Inventory and docs-index regenerated and re-checked.
- Charter vs `AGENTS.md` reconciled (same model stated in both; charter phrased as authority).
- No `ceremony` / `status-writing` / lane-consolidation phrase / bare `spec-kitty merge`
  introduced (terminology guard green, both forbidden-term cases passing).
- Future items (Java service dir, charter's own repo, open-packs internal move) are marked as
  direction/intent, not shipped state.
- An independent adversarial review was run against the aggregate diff while this PR was a
  draft; findings folded (see the mission's `traces/`).

## Blast radius

Discovery: `git diff --stat origin/main`
Files:
- `.kittify/charter/charter.md`
- `AGENTS.md` (`CLAUDE.md` is a symlink to it)
- `docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md`
- `docs/adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md`
- `docs/plans/4-0-0-milestone-roadmap.md`
- `docs/plans/4-x-executive-overview.md`
- `docs/plans/domains/api-dashboard-domain-plan.md`
- `docs/plans/domains/doctrine-charter-domain-plan.md`
- `docs/plans/domains/packs-extraction-domain-plan.md`
- `docs/development/docs-retrieval-index.yaml` (regenerated guard artifact)
- `kitty-specs/governance-realign-oct-direction/` (mission artifacts + the three tracer files)

## Deferred

Follow-up tracks that need their own epics/ADRs (intentionally NOT authored here — each rides
with its own epic being filed separately; docs point at "a dedicated epic/ADR (to be filed)"):
- **Charter repository extraction** — the mechanics of moving the charter into its own repo.
- **Docsite → "doc-kitty"** — the documentation-site extraction track.
- **QA test-absorption** — the test-ownership/absorption track.

Also out of scope, flagged for the operator:
- The GitHub **milestone object's due date** and any **issue re-milestoning** — a separate
  tracker pass owns these; this PR changes prose only.
- `docs/context/team-kitty.md` — a detailed hosted-model context doc not in this mission's file
  set; it likely needs a follow-up reconciliation pass to the "Multiplayer Mode" consumer
  framing.
- The pre-existing `spec-commit` `HELP-DRIFT` / live-help "feature branch" Terminology-Canon
  slip (product-help change, not governance docs).
