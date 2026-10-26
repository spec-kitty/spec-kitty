# Research: reach-only membership fails open on an unreadable synthesis manifest (#6454)

Base: `origin/main` at `e28ddabf`. Reader: the implementer and reviewer of the follow-up
software-dev Mission.

## Root cause (confirmed, live)

`src/charter/activation/synthesizer/reach_only.py::_manifest_slugs` loads the synthesis
manifest (`.kittify/charter/synthesis-manifest.yaml`, `MANIFEST_PATH`) and catches
`OSError`, `ValueError` (this includes pydantic `ValidationError`) and `YAMLError`, returning
`frozenset()`. An absent manifest (`FileNotFoundError`) and an unreadable one therefore look
the same. `reach_only_ids` intersects the overlay's nodes with that empty set, so it returns
an empty set and nothing is subtracted from the roots.

Live reproduction (scratch script driving the existing `test_reach_only_delivery` fixture):

```
intact  reach_only_ids= ['how-we-apply-directive-024']
corrupt reach_only_ids= []
directive OFF, corrupt manifest, delivered reach-only tactic: True
```

The tactic of an inactive directive is delivered through the real
`_load_action_governance_bundle` path, with no warning.

## Blast radius (every caller)

| Caller | Use | Effect of the fail-open |
|--------|-----|-------------------------|
| `action_governance_bundle.py` (`selected_tactics -= reach_only_ids(repo_root, "tactic")`) | root subtraction, tactics | tactic of an inactive directive becomes a root and is delivered |
| `compiler.py::_direct_root_urns` (tactic and styleguide) | reference-graph roots | synthesized tactic or styleguide is a compiled reference root |
| `reach_only._eligible` (styleguide append) | which created styleguides may be appended | fewer styleguides appended; activation surface only, not delivery |
| `reach_only._first_time_slugs` / `append_synthesized_activations` (via `_manifest_slugs`) | "created before this run" | reads the manifest the same synthesis run just wrote; the created-artifacts record already keeps an operator's removal sticky |

Indirect consumers (`synthesize.py`, `resynthesize.py`) only reach the append path.

## Decisions

1. **Membership source order.** The manifest stays the primary source. When it exists but
   cannot be read, the created-artifacts record (`CREATED_ARTIFACTS_PATH`, plus the legacy
   `synthesized-tactics.yaml` for tactics, both read by `_read_record`) supplies membership
   (operator ruling 1). Rationale: the record lists every id synthesis ever created per kind,
   a superset of the manifest's live entries, and membership still needs the synthesis-shaped
   overlay edge, so a superset cannot turn a hand-authored artifact reach-only.
2. **Neither readable → fail closed, "no roots".** Every overlay node of the kind that is the
   target of a synthesis-shaped edge (`is_synthesized_source_edge`) counts as reach-only; it
   is then delivered only through its directive's suggests edge, while that directive is in
   force. Org-required ids stay roots (existing subtraction). No consumer-side graph filtering
   (operator ruling 2). An absent record counts as unreadable for this purpose: it carries no
   membership.
3. **Absent manifest unchanged.** An absent manifest means "never synthesized" (or a
   deliberately removed manifest); `test_reach_only_ids_empty_without_a_manifest` (a present
   manifest with no entries) and the no-overlay cases keep returning the empty set.
4. **Warning channel.** A module `logging` logger at WARNING, the same channel the bundle
   (`_LOGGER.warning` in `action_governance_bundle.py`) uses; the CLI logging bootstrap
   (`specify_cli/cli/logging_bootstrap.py`) routes WARNING records to the operator's
   terminal. Warn on the record fallback as well as on fail-closed, and only when the overlay
   has a synthesis-shaped edge of the kind (nothing to decide otherwise, so no noise).
5. **Append path keeps its lenient read.** `_first_time_slugs` and
   `append_synthesized_activations` keep "unreadable manifest reads as empty": they run right
   after the synthesis run rewrote the manifest, they decide activation-list appends (not
   delivery), and the record keeps removals sticky. Widening them is out of scope (#6455 /
   #6456 are the sibling synthesis fixes).

## Red-first tests (to land before the fix)

Through `reach_only_ids` and the consumer paths (`_load_action_governance_bundle` for
tactics; `compiler._direct_root_urns` for styleguides):

- unreadable manifest + readable record: tactic of an inactive directive is not delivered;
  `reach_only_ids` names it; an edgeless recorded tactic stays a root; a warning is logged.
- unreadable manifest + unreadable (or absent) record: fail-closed set = every synthesis-edge
  target; a warning names both files; org-required id stays a root.
- styleguide counterpart of both cases via `_direct_root_urns`.
- absent manifest: unchanged (empty set, no warning).

## Open questions

None blocking. The operator triage comment mentions "a named error" for the both-unreadable
case; the later operator ruling given for this delivery chooses the "no roots" fail-closed
set plus a warning instead, which keeps action context rendering. Recorded here so the
reviewer sees the choice.
