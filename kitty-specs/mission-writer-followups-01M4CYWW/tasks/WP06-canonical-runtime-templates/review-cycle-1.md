---
affected_files: []
cycle_number: 1
mission_slug: mission-writer-followups-01M4CYWW
reproduction_command:
reviewed_at: '2026-10-08T18:47:18Z'
reviewer_agent: claude-reviewer-runtime
wp_id: WP06
---

# WP06 review feedback (cycle 1)

Reviewed `stream/runtime` 25f7f1b7f..9651145e2. Most of the WP is sound: B1 query mode reads the frozen copy,
the built-in tier uses `builtin_missions_root()` with a named fail-closed error, the ledger is 22, the
software-dev/plan pack templates equal the old src content (bar comments), and the documentation/research
pack bytes are unchanged. 382 targeted tests pass. Two blocking items remain.

## Blocking

1. **Formatter gate is red.** `ruff format --check .` (the whole-repo CI gate) fails on the new
   `tests/runtime/test_pack_runtime_template_parity.py`: there is an extra blank line before `def _baseline()`
   (line 62). Fix: `uv run --frozen ruff format --force-exclude tests/runtime/test_pack_runtime_template_parity.py`.

2. **FR-020: `_ensure_feature_metadata` still has an unlocked `write_meta`, and the comment that justifies it is wrong.**
   `src/specify_cli/mission_loader/command.py` writes a brand-new `meta.json` with no lock, commenting
   "there is no Mission to lock on yet". That is not true: `mission_write_lock(feature_dir)` resolves a key with
   no `meta.json` (`_lock_name_for_dir` falls back to `feature_dir.name`). The `exists()` check followed by an
   unlocked read and write is a check-then-act gap: a writer that creates `meta.json` between the check and
   `write_meta` is overwritten. FR-020 names the mission loader, and WP15's Rule 4 will flag this sink with
   no allowlist allowed.
   Fix: put the check, the read and the write inside one `mission_write_lock(feature_dir)` region. For example,
   use `locked_update_meta` when the file exists, and otherwise call `load_meta_or_empty` and `write_meta`
   under the same lock. Remove the incorrect comment. Add a test that shows the first write runs under
   the lock, for example with a spy on `mission_write_lock`.

## Should fix while you are here (non-blocking)

- `packs/built-in/missions/software-dev/mission-runtime.yaml`: the src content brought back a comment pointing at
  `src/charter/offering/missions/built_in_step_contracts/tasks.step-contract.yaml`, which does not exist. The real
  path is `packs/built-in/...`. It also changed the accept description from "Validate mission completeness" to
  "Validate feature completeness", which breaks the Terminology Canon. Software-dev resolves from the built-in tier, and the drift
  check for in-flight runs skips the vanished src path, so editing comments or descriptions changes neither routing
  nor in-flight runs. Restore both. The parity test does not compare descriptions.
- NFR-006 strength: in the bare tmp repo, the `route` column for software-dev and plan only repeats `agent_profile`.
  I checked against a real charter-bearing repo (this worktree): software-dev discovery and accept are legacy,
  the other steps are composition, and plan is all composition. The charter part of the route never reads
  `mission-runtime.yaml`, so the per-step `agent_profile`/`contract_ref` pin covers everything the template
  contributes. A mutation that adds `agent-profile: researcher-robbie` to discovery in a copied pack root, through
  `SPEC_KITTY_PACKS_ROOT`, fails `test_resolved_plan_equals_baseline[software-dev]`. A case that runs on a fixture
  repo with a charter action sequence would make the `route` column meaningful. This is optional.
