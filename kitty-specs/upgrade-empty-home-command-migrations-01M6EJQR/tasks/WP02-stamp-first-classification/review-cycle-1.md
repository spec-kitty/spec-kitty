# WP02 review cycle 1 — stamp-first classification

Reviewer: reviewer-renata (self-review round) · 2026-11-02

## What the diff does

`_SafeGlobalizeCommandsBase` gains `_is_past_globalization_boundary()`, which reads
`.kittify/metadata.yaml` through `ProjectMetadata` and compares it with
`self.target_version`. `apply()` computes it once; `_classify()` takes `globalized` and,
when true, skips both machine-driven checks. `_global_command_file_present()` now asks
`runtime.agent_commands.get_global_command_dir()` (the canonical owner) for roots that
have an agent key, keeping the historical `Path.home()/agent_root/subdir` shape for the
legacy `.codex/prompts` root that has none.

## Checklist

| Item | Verdict | Evidence |
| --- | --- | --- |
| Fixes the failure WP01 recorded, without editing WP01's assertions | PASS | the two red tests pass unchanged; `git diff` on the test module shows only the review-round rename/reformat |
| Stamp read through the canonical owner | PASS | `ProjectMetadata.load`, same call shape as `compat.py` |
| Threshold not duplicated | PASS | `self.target_version`; `3.2.0a4` sibling asserted at its own boundary |
| Undatable project keeps legacy answer | PASS | missing / `unknown` / unparseable / numeric-float stamps all covered |
| User-customisation rule outranks the stamp | PASS | `_HOLD` stays first; asserted with a marker-less file on a dated project |
| Second source of truth removed | PASS | `get_global_command_dir` used; fallback limited to roots with no agent key, with a test |
| No behaviour change on the settled path | PASS | a `success` record still settles the migration; `detect()` is untouched |
| Type/lint clean | PASS | `ruff check`/`ruff format` clean; `mypy` on the module reports only the pre-existing single-file `BaseMigration`-is-`Any` error that `main` reports identically |
| No gate weakened | PASS | no skip/xfail; `tests/architectural/test_mutation_ownership_routing.py` (40 tests, names this migration's `apply`) green |

## Findings

None. Two notes for the record:

- **N1 (accepted trade-off)** — on a stamped project the migration now removes
  project-local generated copies even when that machine has no global tree yet. The CLI
  installs the global copies at the next command; stated in the module docstring and to
  be stated in the changelog fragment (WP03).
- **N2 (deferred by scope)** — `_global_command_file_present` remains a *machine*
  question for the legacy shape; that is the historical contract for undated projects and
  is out of this issue's scope (C-002).

## Verdict

APPROVE.
