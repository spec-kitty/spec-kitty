---
affected_files: []
cycle_number: 1
mission_slug: truthful-discovery-step-01M3KABP
reproduction_command:
reviewed_at: '2026-09-28T08:01:41Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review (reviewer-renata): changes requested

The prompt rewrite is correct and executable. Point by point:
- No STOP on main.
- `research.md` is create-or-extend.
- The research-only section is fenced.
- Success criteria are truthful.
- The plan Phase 0 says to extend.

The e2e test goes red against the old prompt. The provenance count went down (research prompt 4 -> 1). There is no `#NNNN` in pack prose, no version bump and no `kitty-specs/` path in the diff, and merge-tree is clean. Three things block approval.

## Required
1. **FR-013 phrase-invariant test is missing** (post-tasks squad fold, binding). Add a test that fails if any of these drifts from the prompt's ordering and invocation:
   - `src/charter/offering/skills/spk-mission-research/SKILL.md`
   - `src/charter/offering/skills/spk-start-command-map/references/command-map.md`
   - the `/spec-kitty.research` section of `docs/api/slash-commands.md`
   - `docs/context/spec-driven.md` (the plan "Research Kickoff" bullet)

   The test should assert each of the following:
   - Any `spec-kitty research` mention carries `--mission`.
   - Research is described as pre-spec/discovery and create-or-extend.
   - The scaffold is scoped to research-type missions after plan.
   - No surface says "only after /spec-kitty.plan" or "plan prompts to run `spec-kitty research`".
2. **Docs freshness gate regresses.** `PYTHONPATH=$PWD/src:$PWD python scripts/docs/check_docs_freshness.py --ci` shows `errors=1`: `DOCS-INDEX-DRIFT docs/changelog/CHANGELOG.md` (the new `### Fixed` anchors). The lane-a base shows `errors=0`. Run `PYTHONPATH=. uv run python scripts/docs/docs_index.py --write` and commit the regenerated index.
3. **NFR-004 is breached.** `test_discovery_prompt_is_fully_executable_for_software_dev` takes 47.5 s in isolation, over the 30 s budget. A profile shows that about 80% of the time is `main_callback` -> `ensure_global_agent_commands` / `render_command_template`. Each CliRunner invoke re-renders every agent's command assets, because `sys.argv` is pytest's, so the `next` fast path never triggers. The global asset bootstrap is outside this contract, so monkeypatch these to no-ops in an autouse fixture:
   - `specify_cli.runtime.agent_commands.ensure_global_agent_commands`
   - `specify_cli.runtime.agent_skills.ensure_global_agent_skills`
   - `specify_cli.runtime.bootstrap.ensure_runtime`

## Should fix
- **Name the step.** The WP says to name the step `discovery` where it could be confused with specify's discovery interview. The prompt says only "Capture discovery findings". Add one sentence, e.g.: "This is the mission's `discovery` step (not the `/spec-kitty.specify` discovery interview)".
- **Weak FR-002 assertion.** `assert "STOP" not in prompt_text.upper() or "⛔" not in prompt_text` passes if either token is absent. The "main branch" check is hard to read. Assert directly that the template body has no "STOP" location instruction, no "NOT main", and no "⛔".
- **Command extraction scope.** The post-tasks fold says to extract commands from the template body only (after header + governance) and to reuse `_COMMAND_PATTERN` from `tests/doctrine/test_builtin_cli_command_references.py`. The test scans the whole issued file with a local regex.
- **Docstrings and chdir.** The module docstring and comments say "no `--result success` shortcut" while the test (correctly) uses `--result success`. Reword them. In the research-type case, use `monkeypatch.chdir` instead of `os.chdir`/try.
- **Changelog wording.** The last sentence of the Fixed entry (the test-file mention) is maintainer-facing; drop it.

## Process note
The red-first commit 2f1cd5fc never carried `@pytest.mark.regression`. The final state has no marker, which is correct.

## Evidence
- The new test module: 6 passed (47.5 s + 1.35 s).
- tests/next, tests/doctrine, the provenance ratchet, legacy terminology and tests/specify_cli/skills: 4348 passed, 3 failed. The 3 failures are in the skills installer and also fail on lane-a, so they predate this WP.
- ruff check, ruff format and mypy on the new test file are clean.
