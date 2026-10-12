# Implementation Plan: Realign governance docs to the October direction

**Mission**: `governance-realign-oct-direction`
**Created**: 2026-10-12
**Spec**: [spec.md](spec.md)

## Approach

A documentation/governance realignment, delivered on the single topic branch
`governance-realign-oct-direction` as a draft PR. This is not a lane-based code mission:
there are no code lanes, no worktrees, and no consolidation of lane branches — the canonical
loop is run as governance artifacts (this plan, the spec, the tasks and the three tracer
files) over one branch, because the whole change is prose on a single branch. (Flagged in
the PR: the loop was run as artifacts, not as lane worktrees, for exactly this reason.)

### Canonical-source-unification note

Two governance surfaces can disagree: the charter (`.kittify/charter/charter.md`) and
`AGENTS.md` (`CLAUDE.md` is a symlink to it). The charter wins on conflict. Every edit that
touches a concept stated in both is made in both, with the charter phrased as the authority
and `AGENTS.md` mirroring it.

### Divio / freshness discipline

- One Divio quadrant per doc — preserved; no new `type:` is added to a doc that lacks one.
- Every touched doc gets `updated: 2026-10-12` (ADR `2026-10-01-2` gains the field, matching
  the sibling ADR convention). The charter gets a dated one-line header note.
- The page-inventory lockfile tracks only `path/tag/divio_type/owning_workstream/current_target/notes`;
  none of those change, so no inventory drift is expected. Regenerate-and-diff confirms it.

## Architecture of the change (what maps where)

| Decision | charter.md | AGENTS.md | roadmap | exec-overview | api-dashboard | doctrine-charter | packs-extraction | ADR 2026-10-01-2 | ADR 2026-10-06-1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 GA not date-gated | posture | — | remove date, done-when-done, RCs | remove date | — | — | — | — | — |
| 2 GA gate expands | release line | — | reframe local-integrity-only | gates / moved-out | API gates GA | charter ext gates GA | — | — | — |
| 3 charter → own repo | shared-pkg note | Modularity SSOT + Shared Package Boundary | charter ships alone / #645 GA | §3.6 / wheel | §3.1 own repo | — | — | — |
| 4 API = open-core producer | — | — | label producer surface | reflect | API=producer | — | — | Proposed→Accepted + amendment | — |
| 5 Team Kitty = consumer | Team Kitty posture | Team Kitty section rewrite | Theme 4 / adapter seam | reflect | TK=consumer | cross-ref | — | — | amendment (scoped lift) |
| 6 open-packs source home | Pack Tiers | Pack Tiers | — | — | — | — | §3.1/§3.2 internal+built-in | — | — |

## Risks

- **R1 — introducing a forbidden term.** The terminology guard forbids `ceremony` /
  `status-writing`, the lane-consolidation phrases, and bare `spec-kitty merge` in scanned
  `docs/`. Mitigation: write with canonical terms; run the guard before push.
- **R2 — scope creep into frozen hosted work.** Decision 5 is a precise carve-out.
  Mitigation: encode only (a) consumer UI/multiplayer on the API and (b) the produce/drain
  adapter seam; keep zeitgeist auth, hosted backend and the SaaS surface frozen.
- **R3 — stating direction as shipped state.** Mitigation: mark the Java service, the
  charter repo and the open-packs internal move as direction/intent; keep the ADR's
  shipped-state description (in-repo-now) accurate.
- **R4 — inventory/freshness drift.** Mitigation: regenerate the lockfile and diff; run the
  freshness `--ci` gate.

## Validation strategy

- `pytest tests/architectural/test_no_legacy_terminology.py` (terminology guard).
- `uv run python -m scripts.docs.check_docs_freshness --ci` (freshness/leakage/inventory).
- `python -m scripts.docs.check_spelling` (typo pass over the touched docs).
- Independent adversarial review of the aggregate diff before the draft PR (reviewer ≠
  implementer).

## Delivery

Compact, logically-sliced, rebased-onto-`main` history. Draft PR targeting `main` using
the repo PR template; `Refs` the epics/ADRs (#5528, #645, #3101, the two ADRs); no
`Closes #…`. The operator merges.
