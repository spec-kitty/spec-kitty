"""Regression snapshot tests for the twelve non-migrated agents.

This package contains byte-identity regression tests that lock in the
post-mission-083 command-file output for the twelve agents whose command
delivery mechanism was NOT changed by mission 083-agent-skills-codex-vibe.

The non-migrated agents are the keys of ``AGENT_COMMAND_CONFIG``:
claude, gemini, copilot, cursor, qwen, opencode, windsurf, kilocode,
auggie, q, kiro, antigravity, llxprt.

Command-skill agents such as Codex, Vibe, Pi, and Letta are excluded
because they use the Agent Skills pipeline (``.agents/skills/``) instead
of per-agent command files.  Representative renderer snapshots live under
``tests/specify_cli/skills/__snapshots__/``.

Baseline capture
----------------
The baseline under ``_twelve_agent_baseline/`` was captured at mission 083
completion (post-WP01–WP06 merge), **NOT** from a pre-mission checkout.

Pre-vs-post byte-identity is infeasible for this mission because WP02 edited
seven source templates (removing stray ``$ARGUMENTS`` references outside
User-Input blocks), which changes the rendered output for **all** agents,
including these twelve.

Instead, this baseline locks in the post-mission state.  Any future
unintended drift in command-file output for the twelve non-migrated agents
will be caught immediately.

Regenerating the baseline
--------------------------
When a template change is intentional, regenerate with::

    PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/regression/ -v

The regeneration script writes updated files under
``tests/specify_cli/regression/_twelve_agent_baseline/<agent>/<command>.<ext>``
and commits them alongside the template change so reviewers can see the
exact before/after diff.

Do **NOT** regenerate the baseline to silence a failing test without
understanding why the output changed — the baseline is the regression guard.
"""
