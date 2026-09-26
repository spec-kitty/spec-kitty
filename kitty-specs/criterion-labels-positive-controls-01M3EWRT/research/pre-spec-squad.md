# Pre-spec research squad — #5061 (synthesis)

Lenses (profile-loaded): architect-alphonso (arch alignment), doctrine-daphne (doctrine integrity),
python-pedro (integration points, live parser probes), planner-priti (foldable issues).

## Convergent findings
1. Label shape: labels MUST be separate trailing FR-table columns (`Delivery`, `No-op passable?`).
   Inline/leading labels in the ID cell silently undeclare the FR (`requirement_mapping.py:55-99`,
   first-ID-per-line break is load-bearing, #3394). Inline labels in the Title cell make an unfilled
   scaffold row pass `_substantive.py` (placeholder patterns); inline bullet labels make a real
   bullet-form FR fail `_extract_fr_bullet_description` (blocks setup-plan). SC bullets are outside
   both parsers → inline trailing suffix is safe.
2. No test runs the live spec-template scaffold through the substantive gate → add one (negative:
   scaffold not substantive; positive: labelled filled row substantive).
3. Label definitions live in ONE place. `build` collides with the core glossary term (checkout/worktree);
   glossary pack is generated (two edit points) → define in the tactic (canonical) + template legend
   pointing to it; no bare glossary term.
4. `.kittify/overrides/missions/software-dev/{templates/spec-template.md, command-templates/review.md}`
   shadow the pack in THIS repo (tier-1 override). Render acceptance test must render from
   `packs/built-in`, not the override. Override drift is out of scope → file a follow-up gap.
5. Regen gate: `spec-kitty doctrine regenerate-graph`; freshness/manifest tests in tests/doctrine/drg,
   tests/architectural/test_doctrine_regenerate_graph_roundtrip.py, test_pack_manifest_no_author_edit.py.

## Divergence + adjudication (host tactic)
- architect: extend `atdd-adversarial-acceptance` (refusal assertions live there).
- daphne: extend `acceptance-test-first` (already review-scoped in action.graph.yaml, though only
  via calibrator side-effect; atdd-adversarial reaches review only 2 hops via DIRECTIVE_034).
- Adjudication (from source): host = `acceptance-test-first` + author review scope explicitly in
  `actions/review/index.yaml`; `atdd-adversarial-acceptance` "Convert to acceptance scenarios" step gets
  one sentence + step reference back (no duplicated content). Both lenses satisfied: refusal-authoring
  site points to the rule; the rule lives in the review-scoped tactic.

## Fold verdict (planner-priti)
No folds. #5068 adjacent (same epic #5107, different mechanic), #4858/#3264 adjacent closed, #4891 out
of scope. No open PR touches target files. No duplicate mission.
