# Tracer: Design Decisions

## D1 — Helper form: `git rev-parse --verify`
The two prior helpers agree on valid refs but diverge on AMBIGUOUS refs (bare
`rev-parse` returns a multi-line multi-SHA string; `--verify` fails to None).
`--verify` is the single-object-safe form and closes divergence #3. (Plan-phase
detail; see spec Assumptions.)

## D2 — Keep merge-env routing
`_make_merge_env` PATH-prepend is inert for `rev-parse` (no merge driver
invoked), but the FR-008b ratchet requires every `lanes/merge.py` subprocess to
route through it. Canonical helper stays merge-env-compatible.

## D3 — Canonical home: `core/vcs/git.py`
Next to `git_rev_list_count`; the canonical git-wrapper module. Route the
classifier-tip callers through it; leave the general-purpose / coord-doctor uses
and the distinct `implement_support._rev_parse` (unknown-sentinel) alone (C-001).

## D4 — #4152 item1 vs item2 conflict → implement item2, decline item1
item1's warning needs the guard item2 removes; and it would fire on the intended
#4135 path. Recorded decline in spec issue-matrix.

## Append during implement

## D5 — PREMISE CORRECTION (post-tasks adversarial squad, empirically verified)
The original #4857 "ambiguous divergence" between bare `rev-parse` and `--verify` is
FALSE on git 2.43.0: both resolve a branch+tag name collision to the TAG and exit 0; the
env difference is inert. The two helpers are behaviourally identical. The REAL defect both
share: bare-name resolution → a tag colliding with the target-branch name misresolves the
pin to the tag. Operator ruling (2026-09-25): fix it — canonical helper resolves
`refs/heads/{branch}` (matches merge/preflight.py:240 + _coordination_doctor.py:587,636).
RED-first test = branch@C1 + tag@C1≠C2 → helper returns C1 (branch), bare returned C2 (tag).

## D6 — typer.Exit uses `.exit_code`, not `.code`
#4152 item3: `typer.Exit` has NO `.code` attr (verified). Current test
`getattr(exc,"code",1) or 1` is ALWAYS 1 (blind). Fix:
`exit_code = exc.exit_code if isinstance(exc, typer.Exit) else exc.code`.

## D7 — keep `_raw_frontmatter_has_field` import
#4152 item2: the guard is dead only at :1069; the import is STILL used at
mission_finalize.py:1515-1516. KEEP the import.

## D8 — `--full-history` is a conservative upper bound
#4593: without `--simplify-merges`, source-relevant merge commits are counted too, so the
count can exceed real source commits. Acceptable (message-only, fail-open). Test asserts
inclusion, not naive exact equality.
