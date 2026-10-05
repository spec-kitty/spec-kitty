# Implementation Plan: In-Harness Feedback Survey

**Branch**: `feat/in-harness-feedback-survey` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/in-harness-feedback-survey-01M3PK9W/spec.md`

## Summary

Offer a short, optional **Feedback Survey** — a 1–5 rating, "What would you change?", an optional email, and a "Send feedback?" consent step — at three completion points (planning complete, mission end, Op close) and on demand. The survey is presented in the harness's own question UI: agents learn about an offer through a post-command block that mirrors the existing startup upgrade check (`--agent-check` → native ask → `--agent-submit`), while humans in a real terminal get an inline prompt gated by the existing `is_interactive()` authority. A confirmed submission is handed to a detached child process that makes one bounded HTTPS attempt and exits silently. Preferences and the weekly throttle live in one hardened per-user file; the default endpoint comes from the existing `DistributionProfile` seam, so the upstream build ships dormant and downstream distributions supply their own endpoint.

## Technical Context

**Language/Version**: Python 3.11+ (mypy `--strict`, ruff, complexity ceiling 15)
**Primary Dependencies**: typer + rich (CLI and terminal form), httpx (already a dependency; used only inside the detached sender), platformdirs (per-user config dir, already a dependency); kernel primitives `kernel.atomic.atomic_write`, `kernel.no_follow`, `kernel.guarded_read.read_guarded`, `kernel.locks.machine_file_lock`; `specify_cli.core.env.is_interactive`; `specify_cli.compat.planner.is_ci_env`; `specify_cli.distribution.profile.DistributionProfile`
**Storage**: One JSON file, `feedback.json`, in the per-user config directory (`platformdirs.user_config_dir("spec-kitty")`), mode 0600, symlink-refusing, atomically replaced, guarded by a machine-wide lock. No project-repository storage; no local copy of answers.
**Testing**: pytest, ATDD-first (one failing acceptance test per user story committed before implementation); unit tests for eligibility, preferences, payload, endpoint resolution; integration tests driving the real `spec-kitty feedback` command and the three trigger commands through their production entry points with a local loopback test endpoint; renderer tests proving the agent block reaches every configured agent surface. Targeted test surfaces only (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: Linux, macOS, Windows 10+ (detached child: `start_new_session` on POSIX, `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows)
**Project Type**: single (existing `src/specify_cli` CLI package)
**Performance Goals**: eligibility check ≤ 100 ms with no network I/O (NFR-003); control returns ≤ 1 s after "Send feedback" (NFR-001); background attempt abandoned at 5 s
**Constraints**: nothing sent without per-submission consent; allowlisted anonymous payload; HTTPS required except loopback; never block, fail, or change exit status of a trigger command; trigger commands' existing `--json` output contracts unchanged; vendor-neutral upstream (no company identity in code, docs, or defaults)
**Scale/Scope**: ~1 new package (`src/specify_cli/feedback/`, 6–7 modules), 1 new CLI command, 1 additive field on `DistributionProfile`, 3 trigger hook points, 2 agent-surface mechanisms (pack prompts + Python helper), glossary + docs; no server-side work

## Charter Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Charter rule | Assessment | Status |
|---|---|---|
| Single canonical authority | Reuses `is_interactive()` (prompt gating), `DistributionProfile` (packaged defaults), `kernel.locks`/`kernel.atomic`/`kernel.no_follow` (hardened state), and the upgrade-check agent-prompt pattern. No second prompt mechanism, lock, or config authority is introduced. | Pass |
| Architectural alignment / layer rules | New code lives in the top `specify_cli` layer and only imports downward (`kernel`, `specify_cli.core`, `specify_cli.distribution`). No `kernel`/`charter` changes. | Pass |
| Team Kitty is Zeitgeist — "sync" is dead | Feedback is a separate, anonymous channel: not a moment, not gated by login, never carries credentials; no sync identifiers revived (C-003). | Pass |
| Central CLI–SaaS API contract | Not applicable: the Feedback Endpoint is not the hosted SaaS and the receiving service is out of scope (C-004). Recorded so reviewers do not expect a `cli-saas-current-api.yaml` change. | Pass (N/A) |
| Credential handling (DIRECTIVE_050) | Sender builds its request from the allowlisted payload only; no auth headers; test asserts no token-bearing header is ever sent. | Pass |
| Pack tiers (built-in vs internal) | Survey guidance is consumer product behaviour and is injected by the command renderer in `src/`; nothing goes into `packs/internal/`. | Pass |
| User customization preservation | The renderer only appends to package-managed generated command files; no user-authored command or skill is touched. | Pass |
| Terminology canon | "Feedback Survey" / "Feedback Submission"; never "telemetry"; Mission, never feature; `--mission` only. Glossary entries added under `docs/context/`. | Pass |
| ATDD-first (C-011) | Each user story gets a red acceptance test committed before its implementation. | Pass (planned) |
| Sonar expectations | New modules are small and pure where possible; trigger hooks are one-line calls so `consolidate`/`finalize_tasks` complexity does not grow; every helper gets focused tests; loopback HTTP allowed only for local test endpoints with rationale. | Pass (planned) |
| Performance (< 2 s CLI) | Eligibility is local file + clock only; network happens only in the detached child after consent. | Pass |
| Cross-platform | Detached-child and lock behaviour specified per OS; tests parametrised for POSIX/Windows code paths. | Pass (planned) |
| No version numbers in scope | Plan carries no release/version targets. | Pass |
| Vendor neutrality (operator direction) | Upstream stock profile ships no endpoint; no company names in code, docs, fixtures, or defaults. | Pass |

No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/in-harness-feedback-survey-01M3PK9W/
├── spec.md
├── plan.md                         # this file
├── research.md                     # Phase 0
├── data-model.md                   # Phase 1
├── quickstart.md                   # Phase 1
├── contracts/
│   ├── feedback-submission.schema.json   # POST body sent to the Feedback Endpoint
│   ├── agent-check.schema.json           # `spec-kitty feedback --agent-check --json`
│   └── agent-submit.schema.json          # `spec-kitty feedback --agent-submit/--agent-choice --json`
├── traces/                         # mission tracer files (seeded at planning)
└── tasks.md                        # created by /spec-kitty.tasks, not by this command
```

### Source Code (repository root)

```
src/specify_cli/feedback/
├── __init__.py            # public surface (__all__)
├── models.py              # SurveyTrigger, SurveyAnswers, FeedbackSubmission, Offer/decision value types
├── preferences.py         # hardened feedback.json read/write under machine_file_lock
├── eligibility.py         # pure decide_offer(prefs, now, endpoint, interactive, ci, trigger)
├── endpoint.py            # effective endpoint: user override > DistributionProfile.feedback_endpoint > None
├── payload.py             # allowlisted payload builder + validation (rating, 2,000-char cap, email shape)
├── sender.py              # detached single-attempt HTTPS POST (5 s cap, silent)
├── terminal_form.py       # inline human form (typer/rich prompts) — only when is_interactive()
└── agent_block.py         # post-command agent guidance block + append helper for the renderer

src/specify_cli/cli/commands/feedback.py        # `spec-kitty feedback` (+ --status, --prompts, hidden agent flags)
src/specify_cli/distribution/profile.py         # + optional `feedback_endpoint: str | None = None`
src/specify_cli/skills/command_installer.py     # append agent block to the CLI-wrapper skill body (consolidate)
src/specify_cli/shims/generator.py              # append agent block to CLI-driven shims (consolidate, tasks-finalize)
packs/built-in/missions/mission-steps/software-dev/{tasks,tasks-finalize}/prompt.md  # agent block between markers
src/charter/offering/skills/spec-kitty/SKILL.md # Op-close guidance
src/specify_cli/cli/commands/consolidate.py     # mission-end hook (one call, after success)
src/specify_cli/cli/commands/agent/mission_finalize.py  # planning-complete hook (one call, after success)
src/specify_cli/cli/commands/profile_invocation.py      # Op-close hook (one call, after close, done|failed only)
src/specify_cli/cli/commands/dispatch.py        # Op-close guidance line in the capsule text

docs/context/                                   # glossary: Feedback Survey, Feedback Submission, Survey Trigger, Feedback Endpoint
docs/ (how-to + reference)                      # "Give feedback / control the Feedback Survey" + field reference
CHANGELOG.md

tests/specify_cli/feedback/                     # unit: models, preferences, eligibility, endpoint, payload, sender, agent_block
tests/specify_cli/cli/commands/test_feedback.py # integration: on-demand, --status, --prompts, agent flags
tests/specify_cli/feedback/acceptance/          # ATDD: one file per user story, driven through production entry points
```

**Structure Decision**: A single new bounded context, `specify_cli.feedback`, holds all survey logic; the CLI command and the three trigger hooks are thin adapters that call into it. Existing modules receive only additive, one-call changes so their complexity and contracts stay flat.

## Key Design Decisions

(Full rationale and alternatives in [research.md](./research.md); decision moments recorded under `decisions/`.)

1. **Surfacing mirrors the upgrade check.** Trigger commands keep their JSON output unchanged. Agents get a short post-command "Feedback Survey Check" block on the trigger-bearing commands only, plus one guidance line in the dispatch capsule for Op close. The block tells the agent to run `spec-kitty feedback --agent-check --trigger <t> --agent <key> --json`, ask with the host-native UI if `action == "prompt"`, then record the result with `--agent-submit` or `--agent-choice`. The block has one canonical definition (`feedback/agent_block.py`) and reaches agents through two mechanisms (refined at tasks time, see research R-10):
   - **Prompt-backed commands** (`tasks`, `tasks-finalize`): an exact copy between markers in their pack source prompts under `packs/built-in/missions/mission-steps/software-dev/`, guarded by a drift test. This single edit reaches the skills installer, the slash-command asset generator, and the `spec-kitty next` runtime, which cannot import `specify_cli` under the layer rules.
   - **CLI-driven commands** (`consolidate`, `tasks-finalize` shims): appended by the Python helper in the CLI-wrapper skill body (`skills/command_installer.py`) and the shim generator (`shims/generator.py`).
2. **Humans in a terminal** see the form inline after the trigger command succeeds, only when `is_interactive()` is true, the command was not run with `--json`, and `is_ci_env()` is false. Agent harnesses normally run commands without a TTY on stdin (or set `SPEC_KITTY_NON_INTERACTIVE`), so `is_interactive()` keeps them off the inline path; this is the same authority `init`, `merge` preflight, `intake`, and `doctor` already rely on (#2876/#2912).
3. **"Shown" is recorded at offer time**, under `machine_file_lock`, before any question is asked. Two concurrent processes therefore cannot both offer (NFR-005), and an abandoned form still counts as shown.
4. **Fire-and-forget via a detached child.** After consent the parent writes the validated payload to the child's stdin (never argv, never disk), detaches, and returns immediately. The child makes one HTTPS POST with a 5 s total timeout and exits 0 whatever happens; its stdout/stderr go to the null device.
5. **Endpoint precedence:** `SPEC_KITTY_FEEDBACK_URL` env var > `feedback.json` `endpoint_override` > `DistributionProfile.feedback_endpoint` > none. The stock profile's value is `None`, so upstream ships dormant. A non-HTTPS, non-loopback URL resolves to none.
6. **Fail toward silence:** unreadable, corrupt, or foreign-owned preferences → no automatic offer; a future `last_shown_at` (clock moved backwards) → no automatic offer until the date passes. The on-demand command still works.
7. **Lean command surface:** `spec-kitty feedback` (form), `--status`, `--prompts on|off`, and hidden `--agent-check`, `--agent-submit`, `--agent-choice`, `--trigger`, `--agent`. No subcommands.

## Implementation Concern Map

> Concerns are not work packages; `/spec-kitty.tasks` decides the WP split.

### IC-01 — Hardened preferences store and offer eligibility

- **Purpose**: Own the per-user survey state and the single pure decision "may an automatic survey be offered now?".
- **Relevant requirements**: FR-011, FR-012, FR-013, FR-018, NFR-003, NFR-005, C-005, C-006
- **Affected surfaces**: `src/specify_cli/feedback/preferences.py`, `eligibility.py`, `models.py`
- **Sequencing/depends-on**: none
- **Risks**: lock contention must never block a trigger (non-blocking acquire; contention = no offer); corrupt-file and clock-skew paths need explicit tests; reuse kernel primitives rather than copying `NagCache` private helpers.

### IC-02 — Endpoint resolution and distribution seam

- **Purpose**: Resolve the effective Feedback Endpoint and keep the upstream build dormant and vendor-neutral.
- **Relevant requirements**: FR-016, FR-017, NFR-006, C-004
- **Affected surfaces**: `src/specify_cli/feedback/endpoint.py`, `src/specify_cli/distribution/profile.py` (additive field; stock and degraded profiles default to `None`)
- **Sequencing/depends-on**: none
- **Risks**: the degraded-profile path must also resolve to "no endpoint"; distribution-profile tests must keep passing with the new defaulted field.

### IC-03 — Submission payload and fire-and-forget sender

- **Purpose**: Build the allowlisted, versioned payload and deliver it in one silent, bounded, detached attempt.
- **Relevant requirements**: FR-003, FR-004, FR-014, FR-020, FR-021, NFR-001, NFR-002, NFR-004, NFR-006
- **Affected surfaces**: `src/specify_cli/feedback/payload.py`, `sender.py`, `contracts/feedback-submission.schema.json`
- **Sequencing/depends-on**: IC-02
- **Risks**: detached-process behaviour differs on Windows; tests must prove the parent returns within 1 s against a hanging endpoint and that no auth header or unlisted field is ever sent (same-fixture positive controls per the non-vacuity tactic).

### IC-04 — `spec-kitty feedback` command and terminal form

- **Purpose**: Provide the on-demand survey, settings transparency, the prompts switch, and the hidden agent protocol.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-008, FR-009, FR-012, FR-013, FR-019, FR-020, NFR-008, C-007
- **Affected surfaces**: `src/specify_cli/cli/commands/feedback.py`, `src/specify_cli/feedback/terminal_form.py`, CLI registration, `contracts/agent-check.schema.json`, `contracts/agent-submit.schema.json`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the terminal form must never prompt when `is_interactive()` is false; agent-submit must reject a submission without an explicit consent flag.

### IC-05 — Trigger wiring (agent block + inline hooks)

- **Purpose**: Offer the survey at planning complete, mission end, and Op close without changing any trigger's outcome or JSON contract.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-010, FR-015, FR-018, C-002, C-008
- **Affected surfaces**: `src/specify_cli/feedback/agent_block.py`, `src/specify_cli/feedback/hooks.py`; the `tasks` and `tasks-finalize` pack source prompts + `packs/built-in/pack-manifest.yaml`; `skills/command_installer.py` (CLI-wrapper body); `shims/generator.py` + the twelve-agent regression baselines; `consolidate.py`, `agent/mission_finalize.py`, `profile_invocation.py`, `dispatch.py`; `src/charter/offering/skills/spec-kitty/SKILL.md`
- **Sequencing/depends-on**: IC-04
- **Risks**: `consolidate` and `finalize_tasks` are near the complexity ceiling (`finalize_tasks` already carries a `C901` suppression). Hooks must be single calls placed after the success path, with a tidy-first extraction if needed. The runtime `spec-kitty next` prompt path for `tasks-finalize` must also carry the block (verify it renders through the same seam; if not, route it there rather than editing generated copies). `profile-invocation complete --json` output must stay byte-identical. An agent harness that runs commands inside a pseudo-terminal would pass `is_interactive()`; the inline form's first question (the rating, with an "Enter to skip, 'never' to stop asking" hint) therefore auto-skips after 30 seconds without input, so an unattended run can never stall and the flow stays within NFR-008's four interactions (timed input needs a Windows-specific implementation path and tests), and the generated agent block tells agents to run trigger commands with `SPEC_KITTY_NON_INTERACTIVE=1`.

### IC-06 — Terminology, documentation, and changelog

- **Purpose**: Make the feature discoverable and the consent informed, in canonical language.
- **Relevant requirements**: C-001, C-007, FR-019 (documentation half)
- **Affected surfaces**: `docs/context/` glossary entries; one how-to ("Give feedback and control the Feedback Survey") and one reference page (submission fields, endpoint precedence, environment variables); `CHANGELOG.md`
- **Sequencing/depends-on**: IC-04, IC-05
- **Risks**: docs must stay vendor-neutral and carry Divio type and `updated:` frontmatter; run `tests/architectural/test_no_legacy_terminology.py` before pushing.

## Post-Design Charter Re-check

Re-evaluated after writing `research.md`, `data-model.md`, and `contracts/`: no new authority introduced, no layer-direction change, no hosted-contract change, no credential flow, vendor-neutral defaults. **Pass.**
