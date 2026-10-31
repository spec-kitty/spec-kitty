# Review round 1 — WP01 (#6891)

**Reviewer**: independent adversarial review (separate model, `glm-5.3`, review role) plus a
self-review pass. **Verdict on the first submission: HOLD** (1 blocker, 3 minors, 2 nits).

## Blocker (fixed)

- **The truthful line could swallow a real warning.** `command_installer.verify()` records an
  unrecorded dotted leftover that is *not* the exact legacy rendering under `report.legacy`
  without clearing `ok` (a kept, edited leftover is a warning, never a failure). The new branch
  returned before `_print_command_skill_guidance`, so `doctor skills` printed the truthful line
  **instead of** the `Legacy dotted command skills (no longer managed): … remove it when you no
  longer need your edits` warning — and its "no agent surface were examined" clause was factually
  wrong, because `_verify_legacy_folders` had examined on-disk folders and found something.
  Reproduced both sides before fixing:
  - pre-fix: `all manifest entries healthy (0 file(s))` **plus** the leftover warning;
  - first submission: truthful line only, warning gone (the defect this Mission exists to prevent).
  **Fix**: keep the truthful line and print the guidance after it, and stop claiming what was not
  examined — the line now says `0 manifest entries were examined` (always true in this branch) and
  leaves the surfaces gap to the detail line. Regression test
  `test_legacy_kept_leftover_warning_survives_the_truthful_line` pins both halves (truthful line
  present, leftover named, health claim absent).

## Minors (fixed)

- **Wording asserted the config file exists.** With `.kittify/config.yaml` absent (project root
  found, config not written) the detail line said the file "states no agents.available list";
  `load_agent_config` logs `Config file not found`. Reworded to `does not state an
  agents.available list`, true whether or not the file exists; test
  `test_missing_config_file_does_not_claim_the_file_states_anything` pins both the positive and the
  forbidden phrasing.
- **`--fix` edge coverage.** Added `--json --fix` (frozen envelope, no repair, no write) and
  `doctor tool-surfaces --fix` (truthful line, no `Repaired`, tree byte-identical) tests for the
  legacy shape; the tool-surface one grants checkout ownership so it exercises the summary rather
  than #2613's refusal.
- **Evidence files lived only on the PR branch.** `research/red-first-run.txt`,
  `research/half-fix-revert.txt`, `research/keysets.txt`, `research/doc-mentions.txt` are committed
  on `issue-6891-legacy-doctor-empty-audit-truthful` (the PR branch), not on the lane branch; the
  reviewer re-derived the half-fix proof and the key sets independently in the meantime. Recorded
  in the PR's Blast radius so an auditor knows where they are.

## Nits (one fixed, one accepted)

- **Fixed**: `_print_tool_surface_human(..., stated_agent_list=...)` is now a required keyword, so
  a future caller cannot silently get the old behaviour by omission; the one existing caller in
  `test_doctor_skills.py` passes it explicitly.
- **Accepted as-is**: the no-install-advice test greps the substring `install`. It is shallow but
  non-vacuous, and a benign future wording containing the word would be a legitimate prompt to
  re-read the line (C-002).

## Findings the review cleared

Correctness of the tool-surface predicate (zero tools ⇒ zero surfaces ⇒ any finding flips `ok`);
`ok` computed after the FINAL fused gate; both `--json` envelopes frozen (the reason key is
human-only); exit codes 0/1/2 unchanged, including `AgentConfigError` → `config_error` exit 2 in
`_tool_config_or_exit`; no added `load_agent_config` call (3 / 1, matching
`research/load-counts.txt`); `--fix` cannot claim a repair and the truthful line survives it;
half-fix independence verified independently by the reviewer; no interference with PR #6894
(stated-empty stays out of the predicate, `explicit_agent_list` is the only reader).

## Re-review evidence after the fixes

```
uv run --frozen python -m pytest tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py -q   # 15 passed
uv run --frozen python -m pytest tests/specify_cli/cli/commands/test_doctor_skills.py tests/specify_cli/cli/commands/test_doctor_slash_commands.py \
  tests/specify_cli/cli/commands/test_doctor_tool_surfaces_config_error.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py \
  tests/specify_cli/cli/commands/test_tool_surfaces_fail_closed.py tests/specify_cli/cli/commands/test_doctor_shim_reexports.py -q          # 118 passed
uv run --frozen ruff check src/specify_cli/cli/commands/_command_surface_doctor.py tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py  # All checks passed
```

Behavior on the blocker fixture after the fix (real CLI):

```
$ spec-kitty doctor skills        # legacy + user-edited dotted leftover, exit 0
Command Skills: no stated agent list (every agent is available) — nothing to check (0 manifest entries were examined)
  ! .kittify/config.yaml does not state an agents.available list, so the CLI cannot tell which surfaces to verify
  ! Legacy dotted command skills (no longer managed): .agents/skills/spec-kitty.plan/SKILL.md — remove it when you no longer need your edits
```
