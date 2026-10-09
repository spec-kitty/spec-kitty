# WP01 review — changes requested

Audience: software-engineer (implementer and orchestrator). Reviewer: pi / reviewer-renata, independent of implementer-ivan.

Reviewed and rejected HEAD: `8ec3b0c28025909f00bf8eca6a84ed7cbbb5b59a` (implementation source includes final `b428a130856b83f1de369688a157eaaa00b085ea`). No production or test edits by reviewer.

## HIGH / R1 — qualified explicit declarations are lost on bare-id collision

Location: `src/specify_cli/doctrine/pack_validator.py:836–851, 889–890`.

`_org_local_registry` correctly preserves last-assignment precedence for bare-id binding, but that lossy map is incorrectly reused as the full declared existence universe via `set(local.values())`. Different node kinds may share an id. Both qualified identities must remain known regardless of which one bare binding selects. This violates FR-005, FR-006 and C-002 and blocks valid packs through both existing public commands.

Reproduced through real `load_org_pack` and `validate_pack`, with no validator/resolver/catalog mock and no artifact files:

```yaml
nodes:
  - {id: SHARED, kind: directives}
  - {id: SHARED, kind: assets}
edges:
  - {source: 'directive:SHARED', target: 'asset:SHARED', relation: requires}
```

Both declarations survive in `fragment.authored_nodes`. The bare map contains only `SHARED -> asset:SHARED`. `validate_pack` incorrectly returns `ok=False` with exactly one `drg_dangling_edge`, role source, token `directive:SHARED`. Both `doctrine pack validate --json` and `charter org validate` exit 1 with that same finding. Reversing declaration order instead falsely reports the target `asset:SHARED`. A distinct-id twin passes. A bare `SHARED` edge to `asset:SHARED` passes, confirming that preserving last-winner bare binding is compatible with fixing the qualified universe.

Required correction: derive the declared existence set from ALL normalized `fragment.authored_nodes`, independent of the bare-id winner map; retain current bare-id last-assignment policy and schema-trust/provenance fences. Add focused tests through real validation for same-id/different-kind qualified source and target in both node orders, plus bare precedence controls. Do not alter resolver policy or require backing files for explicit declarations.

Focused reviewer diagnostic (external script/fixtures, no tracked tests mutated): `PYTHONPATH="$PWD/src" .venv/bin/python ../pack-fragment-validation-run/review-shared-id-probe.py`. Successful diagnostic: 4 direct validation cases (2 false-positive reproductions, 2 valid controls), 2 public-command checks reproducing false failures. Initial diagnostic invocation had a reviewer-only loader-signature error before validation; corrected to the existing three-argument loader signature, not counted as product evidence.

## Anti-pattern checklist (early blocking review)

1. Dead code: N/A — full audit deferred after concrete blocker.
2. Synthetic-fixture test: N/A — full test audit deferred; this finding uses actual production paths.
3. Silent empty return: N/A — full audit deferred.
4. FR coverage: FAIL — FR-005/FR-006 qualified explicit-declaration behavior demonstrably fails for shared ids; current controls do not constrain this case.
5. Frozen surface: N/A — no reviewer source/test changes; full implementation-history audit deferred.
6. Locked decision: FAIL — C-002 requires the known set to include authored declarations, not only bare-map winners.
7. Shared-file ownership: N/A — one WP; no implementation edits by reviewer.
8. Production fragility: N/A — full audit deferred.

This is an early rejection, not a completed approval audit. Expensive suites and approval-only helper/coverage/static verification are deliberately deferred. Prior implementation counts are not independent reviewer results. #5971 was already reported/claimed and narrowly fixed in this Mission; no missing-report finding is raised.
