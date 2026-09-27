# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-22 — Decision: adopt Option A (fix production + deterministic
  red-first regression test) per operator instruction, recorded verbatim in
  spec.md Clarifications CL-001. Alternatives considered: (a) quarantine the
  test as `type:flake` with a bounded retry, rejected because the charter's
  test-remediation discipline (Standing Order 4) forbids retry-to-green when
  the underlying defect is real or unruled-out; (b) make the test
  deterministic without touching production code, rejected because the issue
  itself instructs "if production-side, fix the race — do not just
  quarantine it." Rationale: the causal theory, even unproven, points at a
  real code smell (shared mutable module state + `functools.cache`'s
  non-serializing cache-miss execution) worth closing regardless of natural
  reproduction rate.
- 2026-09-22 — Decision: cite `src/charter/offering/missions/` (not
  `src/doctrine/missions/`) and
  `src/charter/offering/templates/mission-tracer-files/` (not
  `src/doctrine/templates/mission-tracer-files/`) throughout this mission's
  artifacts. Alternatives considered: keep the readiness brief's original
  path names for consistency with the GitHub issue's wording. Rationale: the
  `src/doctrine/` paths do not exist on this checkout (verified with `ls`);
  citing them would violate the charter's "canonical sources, never
  improvise" principle and the spec-content rule requiring every named path
  to actually exist.
- 2026-09-23 — Decision (WP01, T002 OBL-1 construction): both fix sites'
  distinct-key race uses TWO DISTINCT tmp_path projects, never one project
  racing two mission types. Alternatives considered: the plan's own
  illustrative (non-normative) sketch names `distinct_key_race=
  ("software-dev", "documentation")`, which reads as "one project, two
  mission types." Rationale: `_inject_projected_fields` nests a PRIMARY_SITE
  call inside every SECOND_SITE population (each mission-type file load
  resolves its own step set), and SECOND_SITE's key is
  `(mission_types_dirs, pack_context)` — fixed `mission_types_dirs`, so two
  calls sharing ONE project also share ONE SECOND_SITE key. Post-6b that
  is a SAME-key race at SECOND_SITE even while PRIMARY_SITE's two
  mission-type-id keys stay distinct — pausing one thread mid-load (holding
  SECOND_SITE's lock for the whole call under 6b's design) while the OTHER
  thread blocks trying to acquire that SAME lock is exactly the ARB-002
  deadlock shape the plan's binding constraints forbid. Two distinct
  projects make BOTH sites' keys distinct between the two threads
  simultaneously, closing the risk by construction rather than by
  discipline.
- 2026-09-23 — Decision (WP01, T002 OBL-2 SECOND_SITE counting seam): count
  `scan_mission_types_dir(mission_types_dirs[0], ...)` invocations rather
  than inventing a placeholder name for the not-yet-extracted walk unit.
  Alternatives considered: the WP prompt's own suggested fallback ("instrument
  the inline walk body's entry today ... note that T004 will make the
  counted symbol exist by name"), which would need editing the test's
  counting target once T004 lands. Rationale: `scan_mission_types_dir` is
  called exactly once per population for the built-in-equivalent layer
  (`mission_types_dirs` is always a 1-tuple), both in the inline pre-fix
  body and in T004's extracted `_resolve_layered_mission_types_uncached` --
  this seam is untouched by that refactor, so the test needed no edit
  between the red and green commits, avoiding a second reason (beyond 6a/6b
  themselves) for the assertion to change shape mid-mission.
- 2026-09-23 — Decision (WP01, T002 OBL-2 interleave-window widening): add a
  short (10ms), self-releasing `time.sleep()` inside the racing threads'
  loader wrapper, on top of the `threading.Barrier` the WP prompt specifies.
  Alternatives considered: Barrier alone (as literally specified — "no long
  pause needed"). Rationale: measured empirically to be genuinely flaky at
  Base without it (both threads' walks are fast enough, and the OS page
  cache warm enough after the first test run, that one thread can
  occasionally complete its whole population before the interpreter
  schedules the other) — observed ~33% pass-when-should-be-red at SECOND_SITE
  across repeated runs. The added sleep is not the long, test-controlled,
  event-gated pause OBL-1 uses: it self-releases after a fixed short
  duration and nothing waits on the other thread's action, so it carries
  none of ARB-002's deadlock risk (confirmed: still green in the "6a
  reverted, 6b kept" revert cell, where 6b's lock is present and could, in
  principle, serialize the racers around it).
