# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-22 — Mission seeded from a readiness pass, not a fresh
  investigation: the spec starts from a hypothesis (YAML-singleton +
  functools.cache cache-miss race) rather than a confirmed root cause,
  because 0/300 cold-subprocess reruns and 0/2000 Barrier-synchronized
  trials failed to reproduce the race naturally. Approach is: research the
  hypothesis first (FR-001), then fix concurrency-safety in the cache
  population path (FR-002), then add a red-first, by-construction
  regression test (FR-004/FR-005) — in that order, not fix-then-hope-a-test-
  catches-it.
- 2026-09-23 — WP01 implementation (T001-T006): started with a spike
  (throwaway scripts, never committed) to empirically confirm the pause
  point BEFORE writing any test assertion, per the plan's own binding
  constraint. The spike immediately reproduced the corruption at both
  sites on the first attempt (a dropped `charter` step at PRIMARY_SITE, an
  `IndexError` from a garbled parse at SECOND_SITE) using a class-level
  hook on `ruamel.yaml.main.YAML.get_constructor_parser` plus a
  thread-local "current path" pin set by wrapping `_load_step_yaml`/
  `_load_layered_mission_type_file` — validating research.md's traced
  mechanism directly rather than by inference. From there the red-first
  test pair (OBL-1/OBL-2/OBL-3) went in first, confirmed red/red/green at
  Base, then 6a (thread-local accessor) and 6b (single-flight lock,
  requiring the SECOND_SITE public/private split the plan specifies) went
  in together, turning everything green. One approach change mid-flight:
  OBL-2's initial construction (both racing threads each calling the
  existing `_run_create` test helper) turned out to have a real bug —
  `_run_create` enters/exits a process-global `unittest.mock.patch` via
  `_patched_mission_creation_context`, and two threads concurrently
  entering/exiting mock.patch on the SAME targets corrupts whichever OTHER
  test happens to run next in the same pytest process (not the test being
  written itself). Fixed by mirroring OBL-4's own proven-safe shape:
  enter the patch ONCE, outside the thread spawn, both threads calling
  `create_mission_core` directly inside that one active context.
