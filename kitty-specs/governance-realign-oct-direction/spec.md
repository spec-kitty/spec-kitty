# Mission Specification: Realign governance docs to the October direction

**Mission Branch**: `governance-realign-oct-direction`
**Created**: 2026-10-12
**Status**: Draft
**Mission type**: documentation (governance realignment)
**Input**: Operator brief (2026-10-12) ratifying six strategic decisions for the 4.x line.

> **Confidentiality.** The ratified decisions originate in internal strategy
> material that is not reproduced here. This spec and every artifact it governs
> express the decisions as repo-public governance, grounded in the existing
> tracker epics, ADRs and roadmap. No confidential deck/memo is quoted,
> attributed or reconstructed.

## Intent Summary

- **Primary actor:** a maintainer or agent reading the project's governance surface
  (charter, `AGENTS.md`/`CLAUDE.md`, the 4.0.0 roadmap, the executive overview, the
  domain plans and the two implicated ADRs) to learn the current direction of the 4.x
  line.
- **Trigger:** the operator ratified six decisions on 2026-10-12 that change the GA
  posture, the GA gate's contents, the charter-extraction target, the framing of the
  mission-status read API, the support posture for Team Kitty, and the source home of the
  pack tiers.
- **Desired outcome:** the governance documents state exactly those six decisions, no
  more, and no longer state the superseded framings. The charter and `AGENTS.md` do not
  disagree; where they would, the charter wins and the two are reconciled.
- **Invariant:** docs mirror shipped behaviour; anything stated as future direction is
  marked as direction/intent, not as shipped state. No product code, reducer, gate or
  test logic changes. The no-bundle packaging invariant and every architectural gate stay
  exactly as they are.
- **Domain terms:** Mission, GA gate, release candidate (RC), open-core, producer surface,
  consumer surface, Multiplayer Mode, adapter seam, pack tier, external contract package.

## The ratified decisions (operator, 2026-10-12)

1. **4.0.0 GA is no longer date-gated.** GA ships "done when done"; release candidates
   keep shipping to early adopters off `main` meanwhile; red-CI-no-release (Standing
   Order 9) still holds per RC. The 2026-10-16 target is removed from the GA framing in
   the docs. (The GitHub milestone object's due date is handled outside this mission.)
2. **The GA gate expands beyond local integrity** to also gate on (a) charter modular
   extraction and (b) the mission-status API backend. The roadmap's
   "local-integrity-only" framing is reframed around this.
3. **Charter modular extraction → its own repository.** The charter (`src/charter/offering/`,
   or `src/charter/`) becomes an independently-released unit consumed via its public
   surface, like `spec-kitty-events` / `spec-kitty-tracker`. #645 (move the ~129
   `specify_cli → charter` imports onto the stable API) is its precondition and is now
   GA-gating. Grounded in #3101, ADR `2026-08-02-1` (charter-wheel-assessment), ADR
   `2026-04-25-1` (shared-package-boundary).
4. **The mission/run-status read API is Build Kitty / open-core (producer side),** not a
   Team Kitty surface. It is the stable entry point to ledger + event data the free CLI
   exposes. Its Java implementation (`services/mission-status-api/`) starts in-repo as a
   modular component and is extracted as needed as an open-core surface, never into a Team
   Kitty repo. `contracts/mission-status/` and the conformance fixtures stay canonical
   beside the Python reducer. ADR `2026-10-01-2` moves Proposed → Accepted.
5. **Team Kitty = "Multiplayer Mode," the consumer side.** UI/multiplayer surfaces
   (mission-ui, pack composer) consume the open-core API across its
   contract boundary. The "do not build toward Team Kitty" standing rule is scoped-lifted:
   it no longer blocks (a) consumer-side UI/multiplayer built on the mission-status API, or
   (b) the event-dispatch / produce-drain adapter seam (`status/adapters.py`). Everything
   else hosted (zeitgeist auth, the hosted backend, the SaaS surface) stays frozen unless
   the operator asks. ADR `2026-10-06-1` gains a dated amendment recording the scoped lift.
6. **`packs/internal/` + `packs/built-in/` source home moves to `spec-kitty-open-packs`.**
   This is a SOURCE-LOCATION move only. The no-bundle invariant is unchanged: internal
   packs stay excluded from the wheel/sdist, built-in content stays present in the consumer
   install. This is not a reversal of ADR `2026-08-16-3`. Grounded in #3504 / #3022.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A maintainer learns the current GA posture (Priority: P1)

A maintainer opens the 4.0.0 roadmap and the executive overview to decide what still
blocks GA. After the change they read that GA is "done when done" (not date-gated), that
the gate now also includes charter modular extraction and the mission-status API backend,
and that RCs keep shipping to early adopters off `main` under red-CI-no-release.

**Independent Test**: the roadmap and overview contain no `2026-10-16` / "16 October" GA
target; the GA gate section names charter extraction and the mission-status API backend.

### User Story 2 — An agent reads the Team Kitty standing rule (Priority: P1)

An agent reads the `AGENTS.md` Team Kitty section before proposing UI/multiplayer work.
After the change it reads the scoped producer-API-vs-consumer-UI model: consumer-side
UI/multiplayer on the mission-status API and the produce/drain adapter seam are no longer
blocked; the hosted backend surfaces stay frozen unless the operator asks.

**Independent Test**: the `AGENTS.md` Team Kitty section states the scoped lift and names
the two carve-outs and the still-frozen surfaces; the charter does not contradict it.

### User Story 3 — A reader reconciles the two implicated ADRs (Priority: P1)

A reader opens ADR `2026-10-01-2` and finds it Accepted, with a dated amendment recording
the open-core producer framing and the in-repo-now / extract-when-frozen decision; and
opens ADR `2026-10-06-1` and finds its original content intact plus a dated amendment
recording the scoped lift.

**Independent Test**: ADR `2026-10-01-2` frontmatter `status: Accepted`; both ADRs carry a
2026-10-12 amendment; `2026-10-06-1`'s original Decision block is unchanged.

## Acceptance Criteria

- AC1 — The six decisions are encoded in the in-scope files, exactly, no more.
- AC2 — No product code, reducer, gate, or test logic changes. The only test touched/run
  is the terminology guard (freshness/spelling guards are run, not edited).
- AC3 — The terminology guard passes; the docs freshness `--ci` check passes; the spelling
  check passes.
- AC4 — Every touched doc carries an `updated: 2026-10-12` freshness date (or, for the
  charter, a dated one-line header note per its convention); Divio type discipline is
  respected (no new quadrant mixing).
- AC5 — The charter and `AGENTS.md` agree; conflicts are reconciled in the charter's favour
  and the reconciliation is noted.
- AC6 — No confidential source material is quoted, cited, attributed or reconstructed.
- AC7 — Delivery is a DRAFT PR targeting `main`; the operator merges. No push to `main`.

## Out of scope / non-goals

- No GitHub issue move/re-milestone; no GitHub milestone object edit. Issue numbers are
  referenced in prose only.
- No authoring of the NEW-track ADRs (charter-repo-extraction, docsite→doc-kitty, QA
  test-absorption) — each rides with its own epic, filed separately. Docs point at "a
  dedicated epic/ADR (to be filed)".
- No change to packaging code or gates; no revival of frozen hosted work beyond the exact
  scoped carve-out in decision 5.
- `docs/context/team-kitty.md` is not in scope for this mission (flag as a follow-up
  reconciliation pass).

## Ambiguities flagged (resolve in review / PR)

- A1 — The mission names the Java service path as `services/mission-status-api/`. The
  current tree ships `contracts/mission-status/` and the Python reducer; the Java service
  directory is future/direction. Docs mark it as direction, not shipped state.
- A2 — "Build Kitty" and "Multiplayer Mode" are framing names from the brief; they are
  introduced in governance prose as the producer/consumer split of the open-core API, not
  as shipped product names.
