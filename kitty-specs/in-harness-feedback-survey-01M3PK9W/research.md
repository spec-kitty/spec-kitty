# Research: In-Harness Feedback Survey

**Mission**: `in-harness-feedback-survey-01M3PK9W` | **Date**: 2026-09-30

Each entry records the decision, why it was chosen, and what was considered instead. Sources are files in this repository at the planning base (`feat/in-harness-feedback-survey`).

## R-01 — How the survey reaches agent harnesses

- **Decision**: Reuse the startup-upgrade-check pattern. A short agent-facing block tells the agent to run `spec-kitty feedback --agent-check --trigger <t> --agent <key> --json`. On `action == "prompt"` the agent asks with its native question UI and then records the result with `--agent-submit` (answers plus explicit consent) or `--agent-choice skip|never`. The block is added only to trigger-bearing commands; how it reaches each surface was refined at tasks time (R-10). For Op close, the dispatch capsule (`cli/commands/dispatch.py`) gains one guidance line after its existing "close it with" line.
- **Rationale**: Spec constraint C-002. The upgrade check (`src/specify_cli/agent_upgrade_prompt.py`, `cli/commands/upgrade.py::_agent_check_payload`/`_record_agent_choice`) is a proven agent ↔ CLI handshake that already reaches all 17 agents. The trigger commands `consolidate` and `tasks-finalize` are thin CLI-driven shims (`src/specify_cli/shims/generator.py`: "No workflow logic is embedded in command files"), so guidance must come from generator code or pack sources, never hand edits to generated copies.
- **Alternatives considered**: (a) Embed a `feedback_survey` offer object in each trigger command's JSON. Rejected: it alters output contracts, and `profile-invocation complete --json` is explicitly "contract-frozen" (`cli/commands/profile_invocation.py`). (b) A new standalone skill the agent must remember to call. Rejected: nothing would prompt the agent at the right moment.

## R-02 — Inline prompt for humans in a terminal

- **Decision**: After a trigger command succeeds, call one hook that offers the terminal form only when `specify_cli.core.env.is_interactive()` is true, `--json` was not requested, and `specify_cli.compat.planner.is_ci_env()` is false. The first question is the rating itself ("How would you rate your experience? (1-5, Enter to skip, 'never' to stop asking)"), and it auto-skips after 30 s without input.
- **Rationale**: `is_interactive()` is the documented single authority for prompt gating (fixes the #2876 "prompt blocks forever in an agent harness" defect class). The timeout covers the residual case of an agent running inside a pseudo-terminal. Putting the timeout on the rating (rather than a separate "Share quick feedback?" gate) keeps the flow at four interactions (NFR-008; analysis finding I1).
- **Alternatives considered**: Detect specific agents via environment variables (`CODEX_CLI`, and so on). Rejected: brittle, incomplete, and would create a second authority.

## R-03 — Fire-and-forget delivery

- **Decision**: After consent, spawn a detached child (`sys.executable -m specify_cli.feedback.sender`) with the serialized payload on stdin and stdout/stderr sent to the null device. POSIX uses `start_new_session=True`; Windows uses `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`. The parent does not wait. The child makes one `httpx` POST with a 5 s total timeout, ignores every outcome, and exits 0.
- **Rationale**: Meets NFR-001 (control returns ≤ 1 s) while still giving slow endpoints a real chance (5 s). Passing the payload on stdin keeps answers out of argv (visible in process listings) and off disk (FR-014: no local copy). `httpx` is already a dependency.
- **Alternatives considered**: An in-process send with a 1 s cap. Rejected: most real endpoints would never receive anything, making the feature pointless. A persistent queue or retry. Rejected by spec (FR-014, fire-and-forget).

## R-04 — Preferences and throttle storage

- **Decision**: One `feedback.json` in `platformdirs.user_config_dir("spec-kitty")`, holding `schema_version`, `last_shown_at`, `automatic_prompts` (on/off), and `endpoint_override`. Reads go through `kernel.guarded_read.read_guarded` + `kernel.no_follow`, writes through `kernel.atomic.atomic_write` with mode 0600, and read-modify-write happens under a non-blocking `kernel.locks.machine_file_lock`.
- **Rationale**: A config directory (not a cache directory) means clearing caches does not silently re-arm prompts or lose "don't ask again". Reusing kernel primitives honours the "one canonical lock" gate in `kernel/locks.py` and avoids copying `compat/cache.py`'s private hardening helpers. Non-blocking lock acquisition means contention yields "no offer", never a stall.
- **Alternatives considered**: Split settings (config dir) from throttle (cache dir), exactly like the upgrade nag. Rejected by operator decision. Extending `upgrade.yaml`/`NagCache`. Rejected: mixing two subsystems' state in one file.

## R-05 — Default endpoint per distribution

- **Decision**: Add an optional `feedback_endpoint: str | None = None` field to `specify_cli.distribution.profile.DistributionProfile`. The stock profile and the degraded sentinel both leave it `None`. Downstream distributions set it through their existing `spec_kitty.distribution_profile` entry point. Precedence: `SPEC_KITTY_FEEDBACK_URL` > `feedback.json:endpoint_override` > profile default > none.
- **Rationale**: `DistributionProfile` is already the packager-facing seam for per-distribution knobs (package name, upgrade provider, index URLs). Leaving the stock value empty keeps upstream vendor-neutral and dormant, as decided.
- **Alternatives considered**: A hard-coded upstream URL. Rejected: operator decision (dormant upstream) and vendor neutrality. A packaged data file. Rejected: a second distribution-configuration authority.

## R-06 — Transport security

- **Decision**: Accept only `https://` endpoints, except loopback hosts (`127.0.0.1`, `::1`, `localhost`) which may use `http://` for local testing. Anything else resolves to "no endpoint".
- **Rationale**: NFR-006. Follows the repository's Sonar guidance that intentionally loopback-only HTTP is legitimate and must not be "fixed" by forcing HTTPS.
- **Alternatives considered**: Allowing any scheme with a warning. Rejected: warnings are noise and violate the silent-by-default posture.

## R-07 — What counts as "shown"

- **Decision**: `last_shown_at` is written when an automatic offer is made, before the first question, in the same locked transaction that checked eligibility. Non-interactive runs never reach the offer, so they never write it. The on-demand command does not update `last_shown_at`.
- **Rationale**: This makes the weekly guarantee (NFR-005) hold across concurrent processes and abandoned forms. It also matches the spec assumptions (skip, abandon, and answer all count as shown; manual use does not consume the window).
- **Alternatives considered**: Writing at completion. Rejected: abandoned forms would not count, and two processes could both offer.

## R-08 — Harness identification in the payload

- **Decision**: The `harness` field is `cli` for the inline terminal form and the on-demand command run by a human. For agent submissions it is the agent key passed via `--agent` (validated against the known agent keys in `specify_cli.agent_utils.directories`; unknown values become `other`).
- **Rationale**: This gives maintainers a useful signal without fingerprinting. The value comes from an allowlist, never free text.
- **Alternatives considered**: Inferring from environment variables. Rejected: incomplete and a second detection authority.

## R-09 — Op-close outcome filter and mission-end definition

- **Decision**: Op close offers only for outcomes `done` and `failed` (not `abandoned`). Mission end means `spec-kitty consolidate` finished successfully, and the offer comes after its state and cleanup are complete. Planning complete means `finalize-tasks` succeeded.
- **Rationale**: These are the spec assumptions. An abandoned Op is usually a mis-dispatch, not an experience worth rating. Offering only after success keeps FR-015 (outcome recorded first).

## R-10 — How the agent block reaches each surface (refined at tasks time)

- **Decision**: One canonical block in `specify_cli.feedback.agent_block`, delivered two ways. Prompt-backed commands (`tasks`, `tasks-finalize`) carry an exact copy between markers in their pack source prompts (`packs/built-in/missions/mission-steps/software-dev/*/prompt.md`), with a drift test against the Python definition. CLI-driven commands get it appended by the Python helper in the CLI-wrapper skill body (`skills/command_installer.py`, `consolidate`) and the shim generator (`shims/generator.py`, `consolidate` and `tasks-finalize`).
- **Rationale**: `spec-kitty next` builds prompts in `src/runtime/next/prompt_builder.py`, and `runtime` may not import `specify_cli` (enforced chain `kernel <- charter <- {runtime, …} <- specify_cli`). Putting the block in the pack source reaches the skills installer, the slash-command asset generator, and the runtime at once. The shim generator did not carry the upgrade block, so it needs its own call.
- **Alternatives considered**: Appending only in `command_renderer`/`asset_generator` (the plan's first draft). Rejected: misses the runtime path and the CLI-driven shims.

## R-11 — Unattended agent runs (analysis finding U1)

- **Decision**: The CLI cannot distinguish an attended agent session from a headless one, so `agent_check` does not try. The agent block instructs agents to run the check only when a human is in the loop, and this is documented as a known limitation.
- **Rationale**: Agents set `SPEC_KITTY_NON_INTERACTIVE` routinely, so honouring it in `agent_check` would suppress every agent-side survey. CI is still detected and suppressed by the CLI.

## Open items

None. All planning questions are resolved (decision moments recorded; `decision verify` clean).
