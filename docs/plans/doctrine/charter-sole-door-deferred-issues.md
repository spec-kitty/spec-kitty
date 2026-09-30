---
title: 'Charter as Sole Door: Deferred Issues Record'
description: Citable record of the six GitHub issues confirmed adjacent-but-separate from the charter-sole-door-bypass-closure mission, deferred as their own follow-ons.
doc_status: active
updated: '2026-08-03'
related:
- docs/plans/index.md
- docs/archive/plans/3-2-x-open-core-delivery-plan.md
---

# Charter as Sole Door: Deferred Issues Record

Mission `charter-sole-door-bypass-closure-01KZ3WAA` ("Charter as Sole Door: Close Bypass Access Paths")
closes every in-scope charter/doctrine bypass call site (direct `AgentProfileRepository`/`DoctrineService`
construction, the `._inner` reach-around, the template/command resolver axis, and hardcoded missions-root
paths) and extends activation gating to all 9 charter-activatable `ArtifactKind` members plus the
`mission-type` token. A pre-spec research squad confirmed five adjacent GitHub issues are
**not domain-matched** to this mission's diff and must stay deferred as their own tracked follow-ons —
see [`spec.md` §C-003](../../../kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/spec.md) for the full,
authoritative context (this document is a citable summary, not a re-derivation). A cycle-2 WP10 review
found a sixth adjacent issue, #3101, that belongs in the same tracker-hygiene sweep even though it is not
one of FR-011/SC-006's five named issues.

Per FR-011 / SC-006, each of the five squad-confirmed issues below carries an `issue-matrix.json` row
(mission `charter-sole-door-bypass-closure-01KZ3WAA`, `verdict: "deferred-with-followup"`) and a GitHub
comment on the issue itself naming this mission, so the deferral is discoverable by opening the issue
directly and not only by reading this mission's PR description. #3101 carries the same row shape and the
same kind of tracker comment, as a WP10 hygiene addition rather than an FR-011/SC-006 obligation.

## The six deferred issues

| Issue | Why it stays out of scope |
|-------|----------------------------|
| [#2986](https://github.com/Priivacy-ai/spec-kitty/issues/2986) | The runtime→doctrine import-ratchet's own function-local-import blind spot — 61 sites across 30 files, a different pair of layers than this mission's charter-factory bypass closure. |
| [#3036](https://github.com/Priivacy-ai/spec-kitty/issues/3036) | A doctrine-content-shippability gate contradiction — a different domain (packaging/shippability, not access-path enforcement). |
| [#3039](https://github.com/Priivacy-ai/spec-kitty/issues/3039) | A test-file reorganisation unrelated to access-path enforcement. |
| [#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091) | Relocate `src/doctrine/missions/` to `packs/built-in/` — a packaging/relocation track. This mission's missions-root path consolidation (FR-004) explicitly does not claim convergence with `doctrine.pack_paths.built_in_dir`; that convergence remains #3091's to deliver. |
| [#3022](https://github.com/Priivacy-ai/spec-kitty/issues/3022) | Extract built-in packs into `spec-kitty-packs-open` — a packaging/distribution track, downstream of #3091. |
| [#3101](https://github.com/Priivacy-ai/spec-kitty/issues/3101) | Split `src/doctrine/` (and assess `src/charter/`) into a separate installable wheel/package — the kernel→doctrine→charter wheel-cutover track, already assessed and sequenced as a deferred follow-on by `docs/adr/3.x/2026-08-02-1-charter-wheel-assessment.md`. Added to this record in WP10's cycle-2 review; not one of FR-011/SC-006's five named issues. |

## Verification

- `kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/issue-matrix.json` (coordination branch
  `kitty/mission-charter-sole-door-bypass-closure-01KZ3WAA`) carries one `deferred-with-followup` row per
  issue above (six rows total), with `wp: "WP10"`; the five FR-011/SC-006 issues share the same one-line
  reason shape, and #3101's row cites the ADR-sequenced wheel-cutover track instead.
- Each issue above received a GitHub comment naming this mission and the reason it stays deferred (WP10,
  subtask T043 for the five FR-011/SC-006 issues; a follow-up landing-pass comment for #3101); the comment
  text and the issues' still-open state are recorded in WP10's Activity Log in
  `kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/tasks/WP10-deferred-issue-tracker-hygiene.md`.
- None of the six issues is touched by this mission's diff (SC-006 for the five it names; the same
  no-diff-overlap fact holds for #3101 by inspection).
