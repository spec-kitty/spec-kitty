# Design decisions — Silent Destructive-Write Hardening

## D-1 One mission, three WPs
Chosen over three separate missions: shared failure family + one consistent
acceptance bar reviewed once; WPs share no source files (parallelizable).

## D-2 WP02 depth = shared registry (decision 01M3560PHPQM617TH5MZHWRF8J)
Reject "add DecisionPoint to the preserved set" (whack-a-field, cf #2376/#3066/#3541).
One registry both the durable reader and the repair consult closes the class.

## D-3 Do NOT route through asset_preservation guard
That guard is filesystem-path granularity (ownership over a Path). These are
content/row/line-level writes — category mismatch. Apply the principle, not the mechanism.

## D-4 Traces driver is not fail-closed
Keyless append-union prose; fail-closed would abort nearly every real merge.
Structural union is the right shape, distinct from the acceptance verdict-authority rule.
