---
title: 'runtime_bridge compat-delegate classification'
description: 'Forwarding-vs-real-seam classification of the 45 runtime_bridge compat-delegate candidates driving the Lane-0 deshim chain (classify → repoint → delete).'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/mission-notes/index.md
---
# runtime_bridge Compat-Delegate Classification (WP02 — FR-003 / #2561)

> **Historical (mission closed).** The owning mission, `test-suite-friction-remediation-01KXDKBX`, has closed (see its `retrospective.yaml` under `kitty-specs/`). Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

**Status:** authoritative classification for the Lane-0 deshim chain
(WP02 classify → WP03/WP04 repoint → **WP18** delete). WP02 makes **zero src edits**; this artifact +
the per-name evidence in `tasks/WP02-runtime-bridge-delegate-deletion.md` history + the FR-016 row in
`tracer-design-decisions.md` are the classification of record.

## Scope

~416 `setattr(runtime_bridge…)` / `"runtime.next.runtime_bridge.<name>"` occurrences across **53 test
files** (WP03 ~241 in `tests/next` + WP04 ~168 elsewhere). Of the `runtime_bridge.py` public+private
surface, **45 pure-forwarding compat-delegate candidates** were audited = **37 native `def`/`class` "Thin
compat delegate" symbols + 8 plain self-alias re-export imports**.

## Verdict: 0 deletable pre-repoint

A grep-only pass first flagged 5 apparently-zero-reference names
(`_extract_wp_heading`, `_collect_requirement_refs_for_section`, `_iter_requirement_refs`,
`_requirement_inline_refs_suffix`, `_is_requirement_heading`). Deleting them turned
`tests/runtime/test_bridge_cores.py::test_untracked_parse_helpers_are_identity_reexports` **RED**
(`AttributeError`) — it asserts `getattr(rb, name) is getattr(cores, name)` for that exact tuple, required by
`test_bridge_compat_surface.py`'s FROZEN exact-baseline (`test_guard_b_identity_reexport_for_relocated_symbols`).
A dependency grep cannot see an identity-equality assertion driven by a name-list variable. Reverted; baseline
green (121 passed on the 3 owned compat-surface files; 628 passed / 1 skipped on full `tests/runtime` +
`test_no_dead_symbols.py`).

## Categories (drives WP03/WP04/WP18)

| Category | Count | Disposition | Owner |
|---|---|---|---|
| Canonical `__all__` surface (`get_or_start_run`, `build_operational_context_for_claim`) | 2 | **Permanently kept** | — |
| Native forwarding delegates still patched/imported via the OLD `runtime_bridge.<name>` path | 35 | **Repoint-then-delete** — WP03 repoints `tests/next`, WP04 the rest; WP18 deletes the façade delegate once grep=0 | WP03/WP04 → WP18 |
| Live production cross-seam `_rb.<name>` deps (`_retrospective_blocks_completion`, `_composition_dispatch_inputs`, `_has_generated_docs`) | 3 | **Call-site refactor + delete** — WP18 refactors the 3 call-sites to import the seam leaf directly, then deletes the façade delegate | WP18 |

> Category counts sum to 40 named dispositions here; the residual of the 45 audited candidates are the
> self-alias re-export imports folded into the "repoint-then-delete" set (they resolve via the same
> `runtime_bridge.<name>` path). Per-name evidence: WP02 `add-history` (see the WP02 task file history).

## The 3 production call-sites (for WP18)

- `_retrospective_blocks_completion` — defined `runtime_bridge_retrospective.py:381`; called
  `runtime_bridge_engine.py:249` as `_rb._retrospective_blocks_completion(policy)`.
- `_composition_dispatch_inputs` — defined `runtime_bridge_composition.py:299`; trace its `_rb.` /
  in-module call-site before deleting the façade delegate.
- `_has_generated_docs` — defined `runtime_bridge_composition.py:408`; consumed via a live
  `_rb._has_generated_docs` lookup (`runtime_bridge_composition.py:~414`).

## Ordering constraint (why WP18 exists)

WP03/WP04 depend on WP02, so WP02 cannot accept the reds its original prompt anticipated without breaking the
serial chain. Deletion was therefore re-sequenced OUT of WP02 into **WP18** (deps WP04), which runs the
repoint-THEN-delete residue: delete the repointed forwarders, refactor the 3 call-sites, and update the
frozen `test_bridge_compat_surface.py` baseline. NFR-001: WP01's dynamic-access-aware gate proves each
deletion dead.
