# Tasks: Realign governance docs to the October direction

**Mission**: `governance-realign-oct-direction`
**Created**: 2026-10-12

Single-branch documentation mission. Tasks are sequenced, not laned. Each task carries the
decisions it encodes (see [spec.md](spec.md)).

## T01 — Mission scaffolding + tracer files
- Seed `spec.md`, `plan.md`, `tasks.md` and the three tracer files (`traces/approach.md`,
  `traces/design-decisions.md`, `traces/tooling-friction.md`).
- **Validates:** Standing Order #3 (mission tracer files).

## T02 — ADRs (Divio-exempt tree)
- `docs/adr/4.x/2026-10-01-2-...md`: flip `status: Proposed` → `Accepted`; add
  `updated: '2026-10-12'`; update the prose status line; append a dated amendment
  (2026-10-12) recording the open-core producer framing + in-repo-now / extract-when-frozen;
  state `contracts/mission-status/` + conformance fixtures stay canonical beside the Python
  reducer; state it is not a Team Kitty surface. **Decisions 4 (also 2, 5 context).**
- `docs/adr/4.x/2026-10-06-1-...md`: keep all existing content; append a dated amendment
  (2026-10-12) recording the scoped lift (consumer UI/multiplayer on the API; produce/drain
  adapter seam) and what stays frozen; bump `updated`. **Decision 5.**

## T03 — Charter (authority, wins on conflict)
- Header: add a dated one-line `Updated:` note (2026-10-12).
- Release Versioning / Branch & Release Strategy: GA = done-when-done, not date-gated; GA
  gate = local integrity **plus** charter modular extraction **plus** the mission-status
  API backend; RCs keep shipping to early adopters off `main`; red-CI-no-release per RC.
  **Decisions 1, 2.**
- Team Kitty posture → scoped Multiplayer-Mode consumer model. **Decision 5.**
- Shared Package Boundaries: charter becomes an external contract package (direction).
  **Decision 3.**
- Doctrine Pack Tiers: name the `spec-kitty-open-packs` source home for both tiers; restate
  the packaging-exclusion invariant intact. **Decision 6.**

## T04 — AGENTS.md (mirror of the charter)
- Team Kitty section: rewrite to the scoped producer-API-vs-consumer-UI model. **Decision 5.**
- Pack Tiers section: name the open-packs source home; restate the exclusion invariant.
  **Decision 6.**
- Modularity SSOT + Shared Package Boundary: direction note that the enforced layer chain
  and the shared-package-boundary gates will gain charter as an external contract package;
  do not change any gate code. **Decision 3.**

## T05 — Roadmap (`4-0-0-milestone-roadmap.md`)
- Remove the 2026-10-16 GA target everywhere in the GA framing; done-when-done + RCs for
  early adopters; keep red-CI-no-release per RC. **Decision 1.**
- Reframe the local-integrity-only framing; GA gate now also = charter modular extraction +
  mission-status API backend. **Decision 2.**
- Charter ships alone / #645 is now GA-gating. **Decision 3.**
- Mission-status API labelled open-core producer surface. **Decision 4.**
- Theme 4 / adapter seam: scoped lift reflected (produce/drain seam no longer blocked).
  **Decision 5.**

## T06 — Executive overview (`4-x-executive-overview.md`)
- Remove the GA date; reflect the expanded gate, the open-core producer API, charter
  extraction GA-gating, and the Team Kitty = consumer framing. **Decisions 1, 2, 3, 4, 5.**

## T07 — Domain plans
- `api-dashboard-domain-plan.md`: API = open-core producer surface; ADR `2026-10-01-2` now
  Accepted; Team Kitty = consumer; API/charter now GA-gating. **Decisions 2, 3, 4, 5.**
- `doctrine-charter-domain-plan.md`: charter extraction now GA-gating; cross-ref the own-repo
  direction and the API-as-consumer boundary. **Decisions 2, 3, 5.**
- `packs-extraction-domain-plan.md`: §3.1/§3.2 — charter becomes an independently-released
  unit in its own repository; `packs/internal/` + `packs/built-in/` source home is
  `spec-kitty-open-packs`; the no-bundle invariant intact. **Decisions 3, 6.**

## T08 — Guards + freshness + inventory
- Run the terminology guard, the freshness `--ci` check, the spelling check.
- Regenerate the page-inventory lockfile and diff (expect no drift).
- **Validates:** AC3, AC4.

## T09 — Independent adversarial review + fold
- Reviewer ≠ implementer: an independent pass over the aggregate diff; fold real findings
  while the PR is still a draft.

## T10 — Compact history + draft PR body
- Logically-sliced commits; rebased onto `main`; draft PR body from the repo template with
  the PROPOSED-amendments framing, the confidentiality note, and the follow-up tracks.
