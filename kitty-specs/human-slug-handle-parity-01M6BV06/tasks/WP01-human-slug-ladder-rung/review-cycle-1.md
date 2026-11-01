---
affected_files: []
cycle_number: 1
mission_slug: human-slug-handle-parity-01M6BV06
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission human-slug-handle-parity-01M6BV06 --agent reviewer-renata
reviewed_at: '2026-11-01T16:33:05Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

Approved by reviewer-renata: approval:WP01

# Review record — WP01 (The identity resolver's human-slug rung)

Reviewer: reviewer-renata (pi/deepseek-v4.1-flash-1017). Verdict: **approved**.

## What I checked

- `_human_slug_for_index_entry` folds `strip_numeric_prefix(slug)` then strips `-<mid8>`
  only when it equals `ResolvedMission.mid8`. Field-only, no extra `meta.json` read
  (NFR-001). Empty-`mid8` guard present.
- The rung still funnels through `_resolve_or_raise`, so two Missions sharing a human
  slug raise `AmbiguousHandleError` with both candidates (FR-003). No second ambiguity
  check was introduced.
- Precedence untouched (NFR-002). Probe over real fixtures, eight shapes:
  `smoke-test` / `smoke-test-01M6BTQX` / `01M6BTQX` / full ULID all resolve; legacy
  `083-foo-bar` still answers to `foo-bar` and `083`; `058-smoke-01M6BTQX` answers to
  `058`, `smoke` and `01M6BTQX`; a directory literally named `smoke-test` still wins at
  the exact-directory rung over the composed sibling; `plain` vs `plain-feature` do not
  cross-resolve; `""`, `"-"`, `"--"` raise `MissionNotFoundError`.
- Negative control holds: a composed slug whose tail is not its own mid8 keeps the tail,
  so the human slug does not resolve (#FR-002). A mid8 token that is not at the tail is
  not stripped.
- Red-first is real: the three positive rows failed with `MissionNotFoundError` before
  the fold and pass after it; the two negative rows were written first and stayed green
  (they are controls, not the proof).
- Docstrings updated: module priority list, ladder priority list, and the rung comment
  now describe the mid8 fold and its guard. No stale "`foo-bar` only" wording left.

## Suites run

- `tests/context/test_mission_resolver.py` — 38 passed (32 pre-existing untouched rows).
- `tests/context/test_mission_resolver_exact_directory.py` +
  `tests/specify_cli/context/test_mission_resolver_port.py` — 92 passed together with the
  above, no pre-existing row edited.
- `tests/architectural/test_no_dead_symbols.py` — 37 passed (the private helper does not
  trip the dead-symbol gate).
- ruff + mypy on both changed files — clean.

## One finding, deferred (not the implementer's to fix here)

`specify_cli/lanes/branch_naming.py::_human_slug_for_mid8_branch` applies the same
"strip the mid8 only when it is the Mission's own" rule when composing branch names, so
the rule now has two implementations: one private per layer, each documented as the
twin of the other, each behaviourally pinned. Unifying them belongs in
`mission_runtime.identity` (the canonical handle surface, where `mid8_from_slug` and
`resolve_mid8` already live), which means touching the shared package and the branch
composition every mission uses — a materially larger blast radius than this defect fix,
with its own regression surface (`_mid8` raises `InvalidMissionIdentity` on a short
`mission_id`; `strip_numeric_prefix` lives above `mission_runtime` and cannot be
imported from it). Deferred to #4745 (folding the agent-layer Mission-resolution path
onto one seam), which already owns converging these paths. Recorded in the PR's
`## Deferred` section.
