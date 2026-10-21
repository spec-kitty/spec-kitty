# WP07 review cycle 1: changes requested (one MEDIUM)

Everything else passes: red-first proven (30 red at 92911581), stop-at-denied walk, the partition
invariant, --include-deactivated (exit 2 without --cascade; clears only nodes the walk activates),
preset keep / --force clear (additive JSON; tests/acceptance/charter_pack_cutover/test_presets.py
green), reach_only first-creation, interview passes no deny_change, FR-014 static guard (only
ACTIVATE / CASCADE_INCLUDE_DEACTIVATED / PRESET_FORCE / DEACTIVATE are passed), gates, ruff/format/mypy
(3 mypy errors are pre-existing at the base), complexity. The one-line-per-node format is accepted;
the dead-symbol allowlist removal for cascade::ReferencedArtifact is accepted (gate-forced, now has a
src importer; recorded in tooling-friction.md).

**Issue 1 [MEDIUM] src/specify_cli/cli/commands/charter/activate.py:277 (`_deactivated_urns`, called at :399 and :482) - NFR-003 latency regression, not noise.**
`_deactivated_urns` builds a whole `PackContext.from_config(repo_root)` only to read
`deactivated_urns`. Warm in-process, that call costs ~0.44 s on this repository, while
`pack_context.load_denied(repo_root)` costs ~5 ms here (it short-circuits on `ledger_may_hold_deny`
when no deny list exists; that is exactly why NFR-003 put the short-circuit there). Measured
`charter activate --cascade all directive 024-locality-of-change --no-compile` in clean clones,
three alternating pairs: head slower by 0.9 s, 0.9 s and 1.4 s each time (cProfile: `_deactivated_urns`
1.68 s cumulative; it accounts for the whole `_render_cascade_activation` delta). #6506 is
pre-existing, but this WP must not add to it.
Required fix: compute the URNs through `load_denied(repo_root, org_roots=org_roots)` (union of each
`DenySet.urns`). `org_roots` is already in scope at both call sites. Alternatively reuse a context
you already hold. Keep the post-direct-activation read order (the docstring's reason). Re-time
base vs head and record the numbers in traces/.

## LOWs (fold in this cycle if cheap, otherwise carry to closeout/WP15)

- [LOW] src/charter/activation/cascade.py:431-438 - when a denied node is out of scope it is reported only as
  "Skipped (out of scope)" (data-model §7, correct), but it still stops the walk, so its children
  print as "Unreached (behind a deactivated artifact)" with no deactivated artifact named anywhere,
  and the hint "--include-deactivated ... clear their exclusions" clears nothing for it. Either annotate
  that out-of-scope line (e.g. "(deactivated)") or have WP15 document the case. Not required here.
- [LOW] activate.py:299 - the "Reinstated" line comes from the pre-read deny set, not from `deny_delta`
  as T038.2 says. It is equivalent today; note it in design-decisions.md or switch.
- [LOW] tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py:131 -
  `test_mission_type_seeding_keeps_denied_cli` passed at the red commit. It is a regression pin, not an
  acceptance test (no seeding writer names c-tac; the orchestrator is taking this to the operator).
  Say "pin" in its docstring.
- [LOW] tests/charter/test_cascade_stop_at_denied.py:148 - the partition test checks disjointness and
  coverage only. Add an oracle: `activated` ⊆ reachable in (graph − denied), and `unreached` ∩ that set = ∅.
- [LOW] data-model §7 still shows block headings; WP15 documents the shipped one-line format.
