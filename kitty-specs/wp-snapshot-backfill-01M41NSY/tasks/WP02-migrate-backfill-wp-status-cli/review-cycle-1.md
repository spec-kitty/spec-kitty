---
affected_files: []
cycle_number: 1
mission_slug: wp-snapshot-backfill-01M41NSY
reproduction_command:
reviewed_at: '2026-10-03T21:22:31Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review — REJECT (mission wp-snapshot-backfill-01M41NSY, #5579)

Reviewer: reviewer-renata. Diff reviewed: `git diff 62f6e9431b..HEAD`
(06f431c2c1 red, 41177a9cd7 impl). The implementation is sound and the three
flagged concerns are adjudicated in your favour. Rejected only for test
evidence on new branches, and one post-red assertion narrowing.

## Adjudication of the flagged concerns

(a) `__all__` edit — HONEST, not green-washing. `test_no_dead_symbols` never
rescues an `__all__` member via intra-module use (being in `__all__` is itself a
cross-module export claim), but it does rescue a non-`__all__` public name used
inside its own module. `apply_wp_status_backfill`'s only caller is
`apply_wp_status_backfill_repo` in the same module, so dropping it from
`__all__` makes the declaration truthful rather than silencing a finding; no
allowlist entry was added (charter SO #5 honoured) and the symbol keeps 19
direct call sites in `tests/unit/migration/test_wp_status_backfill.py` (a
non-`__all__` name is still importable). The out-of-map touch of WP01's file is
covered by ownership-map leeway: same lane, WP01 already landed, no overlap.

(b) Selector — NO violation. You do use the canonical resolver
(`context/mission_resolver.resolve_mission`: mission_id -> mid8 -> slug) and you
re-raise `AmbiguousHandleError` as a structured `MISSION_AMBIGUOUS` error, so
there is no ambiguity fallback. Not using
`cli/selector_resolution.resolve_mission_handle` is the right call: it
`sys.exit`s 2 in human mode, which contradicts T007's own contract ("unknown
handle -> exit 1") and would desync this command's exit codes from its
documented envelope and its sibling. The exact-dir-name fallback fires only
after `MissionNotFoundError`, only for a directory name no identity index can
hold (legacy mission without `mission_id`) — acceptable. It must, however, be
pinned by a test (R3): as shipped, the deviation is indistinguishable from a bug
to the next reader.

(c) Dry-run lock file — NOT a defect. WP01's engine takes the same per-mission
status lock as `backfill_runtime_state`, before planning. In a real checkout the
file lands in `<git-common-dir>/spec-kitty-locks/<slug>.status.lock`, i.e. inside
`.git/`, outside the working tree and version control entirely: my real-corpus
`--dry-run --json` created 542 of them and `git status` stayed clean. FR-005's
"writes nothing" means Mission state, which your byte-identity assertions prove.

## Required before re-review

R1 (must) `tests/cli/test_migrate_backfill_wp_status.py:117-125` — the impl
commit narrowed `_tree_bytes` from the whole tmp root to `kitty-specs/` only.
That is a post-red assertion weakening: a dry-run that wrote a stray file
anywhere outside `kitty-specs/` (e.g. into `.kittify/`) is no longer caught.
Restore the whole-root walk and exclude only the lock, e.g. skip
`p.name.endswith(".status.lock")`, keeping the rest of the tree under the
"dry-run writes nothing" guarantee (directive 041 — delete the assertion, not
the test).

R2 (must) `src/specify_cli/cli/commands/migrate/backfill_wp_status.py:189-190`
— the `AmbiguousHandleError -> MISSION_AMBIGUOUS` branch is uncovered (95%
coverage, missing lines 96, 190, 193, 315, 317, 377-379). It is the "structured
ambiguity error, no silent fallback" guarantee of the identity model, and the
impl commit's `_ID_TWO`/`_SLUG_TWO` fixture fix (correct in itself) removed the
only colliding-mid8 setup that would have exercised it. Add a test: two missions
sharing a mid8, `--mission <mid8>` exits 1, nothing written, and in `--json` the
envelope carries `error_code == "MISSION_AMBIGUOUS"`.

R3 (must) same file `:191-197` — pin the legacy fallback adjudicated above: a
mission directory whose `meta.json` carries no `mission_id`, selected by its
exact directory name, is repaired; plus the negative, a near-miss handle still
exits 1 with `MISSION_NOT_FOUND` and writes nothing.

R4 (should) same file `:377-379` — the `ValueError -> MISSION_SELECTOR_REJECTED`
path (containment refusal from `_mission_dirs`) is uncovered; one test over an
escaping selector pins exit 1 plus the envelope.

R5 (nit) `tests/cli/test_migrate_backfill_wp_status.py:120-122` — "git-ignored"
is wrong. The path is right for the fixture (a non-git tree degrades to
`<root>/.kittify/spec-kitty-locks/`), but in a real checkout the lock lands in
`<git-common-dir>/spec-kitty-locks/` — inside `.git/`, not ignored but outside
version control. Reword while you are in the file.

## Verified green

Red-first holds: at 06f431c2c1 the new file is 44 failed / 0 passed; at HEAD
45 passed. Help text carries `--mission`, `--dry-run`, `--evidence-manifest`,
`--json`, no `--feature` (only the negative assertion), an example, and the
"complete on the first live run" statement. Unused-manifest warning covers both
`not in scope` and `nothing to seed`. JSON payload keys pinned and the command
is in `test_json_contract_enumeration` PARSEABLE. Exit codes 0/1 documented and
tested (including outside a project, per-mission error, dry-run with a broken
mission). Manifest validation is fail-closed before any write (12 invalid-shape
cases x 2 output modes, byte-identity before/after). Payload shape mirrors the
sibling `backfill-runtime-state`; failure envelope matches the
`{success,error_code,error}` convention. Repeated literals hoisted in both
modules.

Commands: `pytest tests/cli/test_migrate_backfill_wp_status.py
tests/cli/test_migrate_group_flags_4964.py tests/unit/migration/` -> 293 passed;
`pytest tests/architectural/test_json_contract_enumeration.py
test_safety_registry_completeness.py test_no_dead_symbols.py` -> 170 passed;
`ruff check` + `ruff format --check --force-exclude` + `mypy --strict` over the
4 changed files -> clean; `ruff check --select C901` -> clean (<=15);
real-corpus `--dry-run --json` -> exit 0, 545 scanned / 44 would-seed / 284
events / 13 finished / 6 snapshot-only / 0 errors, `git status` clean.
