# Tracer — design decisions

Mission: `nightly-census-and-timeout-headroom-01M3PM2S`

## DD-1: remove, don't convert, the toolguide references
The toolguide -> tactic/directive relationship is already authored as inbound edges by #5324
(`tactic:supply-chain-install-safety --suggests--> toolguide:*-supply-chain`, `DIRECTIVE_051 --suggests-->
tactic`). Adding reverse outbound edges would change charter cascade closure (tests/charter/test_cascade.py
documents it) for no governance gain, so the inline refs are deleted and no edge is added.

## DD-2: timeout cap formula
cap = ceil((max observed suite step + 0:30) x 1.5), never lowered. 0:30 is the measured ceiling of job
overhead (checkout/sync/upload/escalation) across the known job totals (+0:22 .. +0:30). Inputs: runs
36300726806, 36393904544, 36482214935, 36517786727, 36553997695.

Shard 2 (20:09) and out-of-matrix (45:01) maxima come from run 36553997695, where both jobs were cancelled
at their caps: they are censored lower bounds (recorded as `>=`). Out-of-matrix's completed runs trend upward
(21.5 -> 30.5 -> 36.5 -> >=45.0 min), so 69 min is a stopgap; the first post-merge nightly must confirm it.

## DD-3: no re-shard, no split, no conclusion-keyed escalation
Out of scope (C-002); left for the operator and listed as follow-ups in the PR body: split the out-of-matrix
leg; conclusion-keyed "budget overrun" escalation; `module-tests.yml` 40-min cap (charter shards at ~1.35x,
shared with the PR lane); doctrine guard rejecting artefact ids in styleguide/toolguide `references`
(the extractor's silent `continue` is how #5324 shipped inert refs); stale `reason` on the
`styleguide:common-docs --requires--> asset:common-docs-structural-lint` edge.

## DD-4: headroom evidence lives in the workflow (post-tasks squad, BLOCKING finding 6)
A test with committed per-leg maxima would restate values `_interpreter_shard_roster.py` (LAND-PAT-005)
says live in one place, and would be an SK-247-style stale duration list. Instead each re-derived cap
carries a structured `# headroom:` comment in `ci-nightly.yml`; the test parses only the workflow.
