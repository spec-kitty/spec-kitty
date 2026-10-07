# Spec Kitty Development Guidelines

**Spec Kitty is building the operating system for Governed AI Delivery.** It helps individuals and teams reduce the time from agreed intent to a verified, useful result, with human-led decision-making and accountability at the centre of the work. Spec-Driven Development (SDD), inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit), is the method: an agreed specification comes before implementation, and the result is checked against it.

**The Spec Kitty CLI** (this repository) carries that method into a repository: it bootstraps the directory structure, templates, charter and agent integrations, then runs Missions from specification through review and consolidation. Every command template leads with a discovery interview; the CLI refuses to create specs or plans until the question set is answered.

**What to optimise for.** Judge a change by whether it shortens the path from agreed intent to a verified, useful result for the person using Spec Kitty, without weakening what that path requires: a clear purpose, verification proportionate to the risk of the work, and evidence that the result did its job.

---

## ⚠️ CRITICAL: Load the Project Charter First

**Every LLM agent working in this repository MUST read the project charter at [`.kittify/charter/charter.md`](.kittify/charter/charter.md) at the start of a session, before planning or making changes.**

The charter is the binding governance document. It carries rules that are NOT repeated in this file, including:

- **Governing principles** — single canonical authority, architectural alignment, DDD + tiered rigour, ATDD-first, terminology adherence.
- **Quality & Tech-Debt Standing Orders** — the eight binding practices (adversarial squad cadence, campsite cleaning, mission tracer files, test-remediation/red-first discipline, architectural gate discipline, canonical sources, git/workflow discipline, mission hygiene).
- **Agent operating discipline and collaboration strategy** — model routing, profile-loaded delegation, draft-PR-first, the operator merges.
- **Governance by workflow action** — which rules bind specify/plan/implement/review/merge.

For action-scoped detail, load the doctrine context via `spec-kitty charter context --action <name>` rather than improvising. If the charter and this file ever disagree, the charter wins — flag the drift instead of picking silently.

---

## ⚠️ CRITICAL: Template Source Location

**Edit SOURCE files, NOT agent copies!**

| What | Location | Action |
|------|----------|--------|
| **SOURCE templates** | `packs/built-in/missions/mission-steps/` | ✅ EDIT THESE |
| **Agent copies** | `.claude/`, `.amazonq/`, `.augment/`, etc. | ❌ DO NOT EDIT |

Agent directories are **generated copies** deployed to consumer projects via `spec-kitty upgrade`. Template flow:
```
packs/built-in/missions/mission-steps/{mission_type}/{step_id}/prompt.md  (SOURCE)
    ↓ spec-kitty upgrade
.claude/commands/, .amazonq/prompts/, ... (12 agent dirs + .agents/skills/)  (GENERATED)
```

---

## ⚠️ CRITICAL: Pack Tiers — `built-in` (consumer) vs `internal` (in-house)

**`packs/built-in/` SHIPS TO CONSUMERS; `packs/internal/` NEVER DOES.** Put doctrine in the right tier.

| Pack | Audience | Ships? | Put here |
|------|----------|--------|----------|
| `packs/built-in/` | every downstream Spec Kitty user | ✅ in the PyPI wheel | product doctrine that should govern **all consumers** |
| `packs/internal/` | the Spec Kitty core team | ❌ excluded from wheel/sdist | **in-house / maintainer / dogfooding** doctrine (how *we* land PRs, triage the tracker, calibrate P0, keep main honest) |

**Before adding doctrine, ask: "does this govern consumers, or only how the core team works?"** In-house guidance placed in `built-in` gets force-shipped to everyone — a real defect. The wheel include is narrowed to `packs/built-in/` and guarded by `tests/cross_cutting/packaging/test_packaging_safety.py`. Internal-pack shape differs: a single `drg/fragment.yaml` (not sharded `*.graph.yaml`) + `org-charter.yaml`, loaded via `.kittify/config.yaml` → `charter_packs.org.packs` (legacy fallback `doctrine.org.packs`). Editing either pack trips the pack-manifest regen gate — run `spec-kitty doctrine regenerate-graph` after. See ADR `docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md` and `packs/internal/README.md`.

---

## ⚠️ CRITICAL: Use Canonical Sources, Never Improvise

**Always use the canonical templates, skills, commands, and code surfaces rather than improvising or using older artefacts as examples.**

- Spec/plan/tasks templates come from `packs/built-in/missions/<type>/templates/` (resolved through the charter/doctrine chain) — never copy structure from an older mission in `kitty-specs/`.
- Workflows run through the documented `spec-kitty` CLI commands and the published skills — do not hand-roll equivalents or reconstruct paths the resolver should provide.
- When a canonical command, template, or code surface appears missing or broken, **trace the source and file an upstream gap** — do not silently work around it with an improvised substitute.

**Why:** older missions and ad-hoc artefacts drift from the canonical structure; copying them propagates the drift. The doctrine templates are the single source of truth.

---

## ⚠️ CRITICAL: Team Kitty is not actively supported — do not build toward it

**Team Kitty**, the hosted collaboration product, is no longer actively supported. Team Kitty / SaaS work was frozen on 2026-10-01 ([4.0.0 direction amendment](docs/changelog/4.0.0.md)), and nothing hosted gates a release. Do not propose or extend hosted features, and do not point users or agent harnesses to them, unless the operator explicitly asks for hosted work.

What still ships, and how it is fenced ([ADR `2026-10-06-1`](docs/adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)):

- **Hosted interaction is off by default, behind two gates** ([ADR `2026-09-26-3`](docs/adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md)). Moments, Live Work and the relay commands need the drain posture (`src/specify_cli/core/hosted_posture.py`): `hosted.drain` in the repository's `.kittify/config.yaml` and `[hosted] drain` in the personal `config.toml` must both be true, and no environment variable can turn it on. Authentication and the SaaS-backed tracker calls need a configured endpoint instead (`SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url`, `src/specify_cli/auth/server_target.py`). Neither ships configured.
- **The hosted CLI entries are hidden from listings.** `auth`, `issue-search`, `live-work`, `moments`, `routes` and `zeitgeist` (`_HOSTED_SURFACE_NAMES`, `src/specify_cli/cli/commands/__init__.py`) are missing from `--help`, completion and the CLI reference unless drain is on. They still run when invoked by name. `tracker` stays visible for its local providers (`beads`, `fp`).
- **The `spk-team-*` skills are retired.** Do not add skill or command-template guidance that sends agents to Team Kitty.

When work does touch the dormant hosted code, keep its model straight. The live transport is **Zeitgeist**, a volatile per-team relay: on every lane transition, with drain on, the CLI publishes one **moment** to the team's relay (`status/emit.py` → `status/adapters.py` → `status/zeitgeist_bridge.py` → `zeitgeist_client/`), bounded to one request with no queue and no retry. The old "sync" transport (daemon, offline queue, per-project consent, `api/v1/sync/*` ingress) was deleted on both sides in August 2026. Every remaining "sync" identifier (`SPEC_KITTY_ENABLE_SAAS_SYNC`, `SPEC_KITTY_SYNC_*`, `sync_active()`, `OWNED_SYNC_UNSUPPORTED`) is residue that does **not** gate the moment path; never design against or "re-enable" sync. The full model is in [`docs/context/team-kitty.md`](docs/context/team-kitty.md).

---

## ⚠️ CRITICAL: Git Workflow — Branches, PRs, and Merges

This repository uses **`main` as the integration branch**. Open a topic branch, target it with a pull request, and let repository review and branch-protection settings enforce the merge gate. GitHub Actions are live here: the reinstated lean, modular CI (`#3995`) runs on public `main` — a path router (`ci-router.yml`) feeding the single `gate_selection.py` authority, a per-module test matrix (`module-tests.yml` / `ci-modules.yml`), coverage/xunit aggregation with a diff-cover ≥90% gate (`ci-aggregate.yml`), a packs lane (`packs.yml`), a nightly full/performance/interpreter run (`ci-nightly.yml`), and a fork-safe SonarCloud workflow (`sonar.yml`). These replaced the archived EXPERIMENTAL Blacksmith producer.

- **Never push to `main`.** Create a topic branch from the current `main`, open a PR targeting `main`, and let the repository merge controls handle publication.
- `spec-kitty consolidate` consolidates lanes into your **local** `main` only; it never publishes to the remote. Qualify local vs origin when naming the branch (see the `primary`/`merge` footgun note under Terminology Canon).
- If your GitHub CLI installation cannot use issue or pull-request commands in a restricted environment, use the GitHub web interface or an authenticated GitHub API client.

### Convergence ports

- Port commits from the pre-fork line with `git cherry-pick -x` so authorship and provenance are preserved.
- Before applying a commit, classify it with `git show --stat <sha> -- <retired paths>`.
- If every touched path is retired, record the commit as `DROP` in the convergence map and do not port it.
- For a mixed commit, drop the retired hunks and cite the omitted hunks under `Dropped hunks:`.
- Every convergence PR carries `Retired-surface scan: 0 hits`, computed over added diff lines with the canonical regex in [planning `PROGRAM.md` §5](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-planning/blob/main/PROGRAM.md#5-the-pr-protocol).
- Never add `# noqa: TID251` for a retired module.
- Never resolve a kept-file conflict with `theirs` without re-running `tests/architectural/test_no_retired_subsystems.py`.

**Test policy (§6):** run every test you write or change plus your blast radius, and record commands + counts in the PR. Baseline is `make test-fast`; add the test files of every module your diff touches, and the full test directory of each owning subsystem. Do **not** run `make test-full` or any whole-repo suite — the CI agent owns that. **Superseded by `NO_FULL_HEAVY_SUITES_IN_MISSION` (internal doctrine pack, 2026-09-27):** the line below about running `tests/architectural/` "in full" for cross-cutting changes no longer applies to mission work (implement/review/fold/closeout) — even a cross-cutting change targets the SPECIFIC gate files it implicates, never the bare directory, unless the operator explicitly asks for a full run; CI's cross-cutting lane (`ci-aggregate.yml`) still runs the full suite. See "Test policy — what you must run for a change" below for the calibrated blast-radius rule.

---

## Terminology Canon

- Canonical product term is **Mission** (plural: **Missions**).
- `Feature` / `Features` are prohibited in canonical, operator, and user-facing language for active systems.
- Do not introduce or preserve `feature*` aliases (API/query params, routes, fields, flags, env vars, command names, or docs) when the domain object is a Mission.
- Historical archived artifacts may retain legacy wording only as immutable snapshots, explicitly marked legacy.
- **Overloaded terms `primary` and `merge` — footgun.** `primary` carries four senses (PRIMARY partition / Primary Branch / repository-root checkout / Target Ref) and `merge` three operations (lane consolidation / branch integration / publish to origin). The load-bearing trap is reading a **PRIMARY-partition** verdict as a **Primary-Branch (`main`)** instruction — and treating `spec-kitty consolidate` (local lane consolidation) as a **publish to origin**. Always name the sense; the canonical definitions and "Do NOT use when" guards live in the glossary: [`docs/context/orchestration.md`](docs/context/orchestration.md) (`#primary-partition`, `#primary-branch`, `#target-ref--commit-target`, `#lane-consolidation`, `#branch-integration--git-merge`, `#publish-to-originmain`) and [`docs/context/execution.md`](docs/context/execution.md#repository-root-checkout).
- **Overloaded term `routing` — footgun (cf. #2653, the `primary`/`merge` disambiguation this entry extends).** "Routing" names at least six distinct, governed decisions — placement (kind + topology → surface), branch-target (which branch a change commits to), commit (coord-worktree materialization inside `commit_for_mission`), dispatch/profile (`invocation/router.py`), model/task (`src/charter/offering/model_task_routing/`), and scope routing — plus infrastructural senses named explicitly out of scope (event routing, HTTP request routing, significance routing bands). The sync-fan-out sense (`sync/routing.py`) was retired with the sync transport (issue #115) and is no longer a live governed decision. Never write bare "routing"; name the sense. Full disambiguation with "do NOT use when" guards: [`docs/context/orchestration.md#routing`](docs/context/orchestration.md#routing). Placement-sense explanation: [`docs/architecture/artifact-placement-seam.md`](docs/architecture/artifact-placement-seam.md).

---

## Supported AI Agents

17 agents total: 13 slash-command, 4 Agent Skills. Update all command-layer agents when changing slash commands, migrations, or templates.

### Slash-Command Agents (13)

| Agent | Directory | Subdirectory | Format |
|-------|-----------|--------------|--------|
| Claude Code | `.claude/` | `commands/` | Markdown |
| GitHub Copilot | `.github/` | `prompts/` | Markdown |
| Google Gemini | `.gemini/` | `commands/` | TOML |
| Cursor | `.cursor/` | `commands/` | Markdown |
| Qwen Code | `.qwen/` | `commands/` | TOML |
| OpenCode | `.opencode/` | `command/` | Markdown |
| Windsurf | `.windsurf/` | `workflows/` | Markdown |
| Kilocode | `.kilocode/` | `workflows/` | Markdown |
| Augment Code | `.augment/` | `commands/` | Markdown |
| Amazon Q | `.amazonq/` | `prompts/` | Markdown |
| Kiro | `.kiro/` | `prompts/` | Markdown |
| Google Antigravity | `.agent/` | `workflows/` | Markdown |
| LLxprt Code | `.llxprt/` | `commands/` | TOML |

**Argument placeholders:** Markdown agents use `$ARGUMENTS`; TOML agents use `{{args}}`; `{SCRIPT}` is replaced with the actual script path; `__AGENT__` is replaced with the agent name.

### Agent Skills Agents (4)

| Agent | Skills Root | Command Surface | Key |
|-------|-------------|-----------------|-----|
| Codex CLI | `.agents/skills/` | `$spec-kitty.<command>` | `codex` |
| Mistral Vibe | `.agents/skills/` via `.vibe/config.toml` | `/spec-kitty.<command>` | `vibe` |
| Pi | `.agents/skills/` | `/skill:spec-kitty.<command>` | `pi` |
| Letta Code | `.agents/skills/` | Agent Skills | `letta` |

Codex, Vibe, Pi, and Letta share `.agents/skills/spec-kitty.<command>/SKILL.md`. Manifest: `.kittify/command-skills-manifest.json`.

**Agent key mappings** (key differs from directory for some): `copilot` → `.github/prompts`, `auggie` → `.augment/commands`, `q` → `.amazonq/prompts`. Use `AGENT_DIR_TO_KEY` in [`src/specify_cli/agent_utils/directories.py`](src/specify_cli/agent_utils/directories.py) for conversions.

**Canonical source**: `src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py` → `AGENT_DIRS`

**When modifying**: Migrations → use `get_agent_dirs_for_project()`. Template changes propagate via migration. Test at least `.claude`, `.codex`, `.opencode`.

**Skills modules** (mission 083): `src/specify_cli/skills/` — `command_renderer.py`, `command_installer.py`, `manifest_store.py`.

---

## Agent Management

**CRITICAL: `.kittify/config.yaml` is the single source of truth for agent configuration.**

```bash
spec-kitty agent config list/add/remove/status/sync
```

**DO:** Use CLI commands. Let migrations respect config. **DON'T:** Manually delete agent dirs without updating config. Modify `config.yaml` directly.

### Writing Migrations

Always use the config-aware helper:
```python
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

agent_dirs = get_agent_dirs_for_project(project_path)
for agent_root, subdir in agent_dirs:
    agent_dir = project_path / agent_root / subdir
    if not agent_dir.exists():
        continue  # respect deletions — never mkdir
    # process agent...
```

**DON'T:** Hardcode `AGENT_DIRS`. Create missing dirs. Assume all 12 agents are present. Process agents not in `config.yaml`.

**Key functions:**
- `get_agent_dirs_for_project(project_path)` — (dir, subdir) tuples for configured agents
- `load_agent_config(repo_root)` / `save_agent_config(repo_root, config)` — config I/O

**See also:** ADR #6, `tests/agent/test_agent_config_migration.py`, `tests/specify_cli/cli/commands/test_agent_config.py`

### Adding New Agent Support

1. **Add to `AI_CHOICES`** in `src/specify_cli/__init__.py` and `agent_folder_map`.
2. **Update CLI help text** — `--ai` param description, docstrings, error messages.
3. **Update `README.md`** Supported AI Agents section.
4. **No release-script update needed.** Release automation is centralized and does not require a per-agent entry; follow `RELEASE_CHECKLIST.md`.
5. **Add to `AGENT_DIRS`** in `src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py`.
6. **CLI tool check** (only for agents with required CLI tools, not IDE-based ones):
   ```python
   tracker.add("windsurf", "Windsurf IDE (optional)")
   check_tool_for_tracker("windsurf", "https://windsurf.com/", tracker)
   ```

**Agent categories:**
- *CLI-based* (require CLI tool): Claude Code (`claude`), Gemini (`gemini`), Cursor (`cursor-agent`), Qwen (`qwen`), opencode (`opencode`), Amazon Q (`q`)
- *IDE-based* (no CLI check needed): GitHub Copilot (VS Code), Windsurf (Windsurf IDE)

**Testing new agent:**
1. Run package creation script locally
2. `spec-kitty init --ai <agent>` and verify directory structure and files
3. Confirm generated commands work with the agent

**Common pitfalls:** Wrong argument placeholder format; directory naming deviates from agent convention; missing help text updates; unnecessary CLI checks for IDE-based agents.

---

## Project Structure

```
docs/adr/         # ADRs (governance decision records)
docs/architecture/ # Technical specs and C4 arch docs
src/kernel/       # Foundation primitives (clock, paths, atomic, git_topology) — root layer
src/charter/      # Governance authority; absorbed former src/doctrine/ at src/charter/offering/
src/glossary/     # Glossary semantic-integrity pipeline + DRG glossary bridge
src/mission_runtime/ # Artifact-placement seam (PlacementSeam, resolver port, identity, lifecycle_phase)
src/runtime/      # Canonical mission control loop — runtime/next/_internal_runtime/
src/specify_cli/  # Top adapter/application layer: CLI, status, consolidation, lanes, workspace, tracker clients
tests/            # Test suite
kitty-specs/      # Mission specs (dogfooding)
docs/             # User documentation
```

New architectural designs → `docs/architecture/` following `docs/architecture/README.md` template.

### Modularity SSOT (canonical)

The **single source of truth for the module set and its import direction is the enforced pair**,
not any prose map:

- **Inventory** — `pyproject.toml` `[tool.hatch.build.targets.wheel].packages` (enforced by
  `tests/architectural/test_pyproject_shape.py`).
- **Direction** — the `landscape` fixture in `tests/architectural/conftest.py` +
  `tests/architectural/test_layer_rules.py` (pytestarch `LayerRule`s + the shrink-only
  `mission_runtime` and `runtime` outbound ledgers). The enforced chain is
  `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.

Every other module map (this file, `docs/architecture/00_landscape`, `04_implementation_mapping`,
the demoted `05_ownership_map.md`) is a **derived view**; on conflict the enforced pair wins. The
former self-declared authority `docs/architecture/05_ownership_manifest.yaml` was deleted (mission
`post-convergence-governance-01M1TMPH`). `src/specify_cli/zeitgeist_client/` and `saas_client/` are
**clients** of the upstream authoritative repos `spec-kitty/zeitgeist` + `spec-kitty/saas`
(consumer code; API authored upstream) — see ADR
`docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`.

## Commands

```bash
make test-fast    # fast tier of the typical blast-radius directories (target <2 min)
make test-full    # everything, parallel + serial passes
ruff check .
ruff format --check .  # formatter gate — same whole-repo check CI runs (`make format-check` is the target form)
```

Both make targets set `PWHEADLESS=1` themselves and need the synced dev environment (`make dev-setup`: the `test` extras plus `pytest-xdist`, declared in the `dev` group so a plain `uv sync` has it too).

### Test policy — what you must run for a change

- **`make test-fast`** is the shared baseline for ordinary changes. It runs the fast tier (`(fast or unit)`, with every slow tier deselected by marker) over the subsystem directories a blast radius typically covers: `tests/unit tests/status tests/cli tests/specify_cli/runtime`.
- **Run targeted module tests as well.** The fast tier is a baseline, not a substitute for the tests that directly cover the files and behavior you changed.
- **`make test-full`** runs everything in three passes: one `-n auto --dist loadfile` parallel pass over `tests/` with the parallel-unsafe `stress`/`timing` families deselected by marker, then two dedicated `-n0` serial passes — `-m "stress and not windows_ci"`, then `-m timing`. Use it for release-level changes or when a narrow blast radius cannot establish safety. The former fixed-port sync pass no longer exists.

**Computing your blast radius — run this in addition to `make test-fast`:**

1. For every source module your diff touches, run its own test file(s). The test tree mirrors the source tree (`src/specify_cli/status/store.py` → `tests/status/`), and when the mirror is not obvious, find the tests that exercise the module: `grep -rl "<module_name>" tests/ --include="*.py"`.
2. Plus the full test directory of each owning subsystem: touching `src/charter/offering/**` ⇒ both `tests/charter/` and `tests/doctrine/` — the doctrine test tree did not move when the package absorbed `src/doctrine/` into `src/charter/offering/`, so both directories still cover that code and both count as "each owning subsystem."
3. Cross-cutting changes (pytest.ini, pyproject.toml, conftest, markers, packaging) additionally touch `tests/architectural/` — but per `NO_FULL_HEAVY_SUITES_IN_MISSION`, run the SPECIFIC architectural gate file(s) the change implicates during mission work, not the bare directory as a whole; the full `tests/architectural/` sweep is CI's cross-cutting lane.

Record the exact commands and passed/failed counts under the PR's *Tests run* section. A failure you did not cause and cannot explain is not yours to chase — classify it via the baseline-red gotcha below and note it in the PR.

### Why the targets look the way they do

Do not hand-roll a broad pytest invocation — `make test-fast` and `make test-full`
already encode the rules below. The rationale, so a change to either target keeps
holding them:

- **Always `--dist loadfile`, never bare `--dist load`.** `loadfile` keeps every
  test in a file on a single worker, preserving file-scoped fixture and
  collection semantics; `load` scatters a file's tests across workers and breaks
  them.
- **Per-worker HOME isolation (WP04)** means a parallel run never touches the
  real `~/.spec-kitty` — each `pytest-xdist` worker (and the serial master) gets
  its own isolated home / XDG / AppData directories.
- **Parallel-unsafe families run in their own `-n0` pass.** `stress` /
  `timing` tests are corrupted by co-scheduled workers — so `make test-full`
  gives each family a dedicated serial pass.

Full rationale, the volume env gates, and the stability ratchet:
[docs/development/testing/testing-parallel.md](docs/development/testing/testing-parallel.md).

When a test goes red on CI unrelated to your diff, follow the flakiness policy —
**tune budget gates, fix correctness flakes at the root, never retry-to-green:**
[docs/development/testing/testing-flakiness.md](docs/development/testing/testing-flakiness.md).

**⚠️ Test-run baseline-red gotcha (attribute before you fix — applies to every agent, incl.
dispatched subagents).** A local or backgrounded `pytest` run over anything broad will show
red that is **NOT your change**. Before treating a failure as yours, classify it:
1. **Pre-existing known-P0 reds** honestly red the nightly (ADR `2026-07-17-1`); e.g. #2736,
   #2772, #1834. Their reproductions carry `p0_repro(issue=N)` and run only in the nightly
   `p0-repro` lane, so a normal local or per-PR run does not show them. Do **not** "fix" them;
   check the tracker, or run with `SPEC_KITTY_RUN_P0_REPRO=1` on the merge-base to confirm.
2. **CI-environment failures** — auth (`logged_out_on_connected_teamspace`) and the
   gate opt-out (`SPEC_KITTY_SKIP_PRE_REVIEW_GATE`; the pre-review gate no longer
   reads the sync-disable vocabulary, #3980). These pass locally; they are config,
   not your diff.
3. **Stale-install false reds** — code that shells out to `spec-kitty` (e.g. the
   `merge-driver-*` commands) only fires after `pip install -e .`; a stale install reports
   false reds until you reinstall.
4. **Stale-venv false reds** — a `ModuleNotFoundError` (or other import failure) for a
   package that *is* declared and pinned (`pyproject.toml` / `uv.lock`) usually means the
   local `.venv` was never (re)synced to that pin, not a real regression. Re-run
   `uv sync --frozen --all-extras` and retry before recording the failure as pre-existing or
   unrelated — a stale venv is indistinguishable from real breakage in raw pytest output
   (#648: a PR's `## Tests run` excluded a whole test file over exactly
   this; a clean `uv sync --frozen --all-extras` reproduced 1621/1621 passing, no exclusion
   needed).
Only failures that are red on your branch **and** green on the base are yours to fold. Never
green-wash category 1, and never misattribute categories 2–4 to your own work. Full policy:
[docs/development/testing/testing-flakiness.md](docs/development/testing/testing-flakiness.md#test-run-baseline-red-gotcha).

## Code Style

Python 3.11+. Follow standard conventions. Any changes to `__init__.py` require a version bump in `pyproject.toml` and a `CHANGELOG.md` entry.

**New code MUST pass `ruff` and `mypy` with zero issues and zero warnings. Do NOT disable, suppress, or relax checks (no blanket `# noqa`, `# type: ignore`, or per-file ignore additions) to achieve this — fix the code instead.** Narrowly-scoped, individually-justified suppressions are allowed only when the check is genuinely wrong about correct code, and must carry an inline rationale.

**Formatting is a separate gate from linting (#3952).** `ruff check .` passing says nothing about format: CI (`ci-quality.yml`, `ci-router.yml`) runs `ruff format --check .` over the whole repo, and `tests/architectural/test_ruff_format_enforcement.py` enforces the same command in `make test-full` (#473/#558), so an unformatted file goes red regardless of whether anyone ran the check locally. Run `make format-check` (or `uv run --frozen ruff format --check .`) before pushing; `uv run --frozen ruff format <files>` fixes what it flags. **Per-file invocations need `--force-exclude`** (#5301): `[tool.ruff.format].exclude` (the #473 formatter-debt ratchet) is honored only during directory discovery — an explicitly-passed path is checked/formatted regardless, producing false "would reformat" hits (and whole-file reformats) on ratchet-listed files. Check your diff with `make format-check-files FILES=<paths>` or `uv run --frozen ruff format --check --force-exclude <files>`.

**Pre-push: run the terminology guard when touching `src/charter/offering/` or user-facing prose.** The heavyweight GitHub-hosted test matrix was retired in The Convergence (PR #3881; see [`docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`](docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md)) and the lean modular GitHub CI was reinstated in `#3995`; a forbidden-term regression can still pass a local `src/charter/offering/`-or-prose run and only surface at CI. Before pushing such changes, run `pytest tests/architectural/test_no_legacy_terminology.py` (≈0.1 s); it gates exactly two retired terms — canonical `status commit`, never `ceremony` or `status-writing`. It does **not** check `Mission` vs `feature` — that half of the Terminology Canon is review-enforced, not gated. The full `tests/architectural/` suite is the complete safety net.

## Sonar Expectations (SonarCloud reinstated)

**SonarCloud is back in CI on two complementary surfaces.** The convergence-era workflow deletion (the `sonarcloud` job died with the 4,118-line `ci-quality.yml` in commit `e8cc2f444`, 2026-08-27) had left no coverage or new-code-quality gate in GitHub CI; the gap is now closed twice over. The per-change **`sonar-pr` job in `ci-aggregate.yml`** (until #4334, the `sonarcloud` job in `ci-quality.yml`) ([#3993](https://github.com/spec-kitty/spec-kitty/issues/3993), owner ruling 2026-09-06: it "was not meant to be permanently removed. It should be reinstated.") runs on pull-request-triggered runs **only** — never on pushes to `main`, so `main`'s standing SonarCloud branch analysis stays owned by the nightly — and **consumes the `CI Modules` shard coverage rather than re-running any tests** (#4334), uploading to SonarCloud keyed to the `SONAR_TOKEN` repository secret (both SonarSource actions SHA-pinned to the same commits `sonar.yml` vets, DIR-051), and reports the Sonar quality-gate status — **reported, not required**: the job is `continue-on-error` and deliberately excluded from `ci-aggregate.yml`'s terminal `aggregate-gate` job, whose `needs:` set-equality assertion makes a silent widening onto the merge path impossible. `sonar.projectVersion` tracks `pyproject.toml` via `scripts/ci/sonar_project_version.py` (restored by the same PR, unit-tested in `tests/ci/test_sonar_project_version.py`), and project/organization/coverage paths come from `sonar-project.properties`. The separate net-new **`sonar.yml`** workflow ([#3995](https://github.com/spec-kitty/spec-kitty/issues/3995)) runs a nightly/manual-dispatch informational scan that aggregates the `ci-modules.yml` shard coverage artefacts — fork-safe (skips green when `SONAR_TOKEN` is absent), and never per-PR-blocking. Per-PR coverage is additionally enforced by the `ci-aggregate.yml` diff-cover ≥90% gate. Read the reported numbers locally with the read-only, token-free REST helper `scripts/ci/sonarcloud_branch_review.sh` (unit-tested in `tests/ci/test_sonarcloud_branch_review.py`).

Treat these as code-shaping constraints, not post-hoc cleanup:

- **Complexity ceiling is 15.** Ruff `C901` and Sonar `S3776` are aligned (`[tool.ruff.lint.mccabe].max-complexity = 15`). When touching a function near that limit, keep it at `<=15` by extracting small helpers, flattening nested conditionals, or separating lookup/build/emit phases. Do **not** leave a function at 16+ and assume "tests passing" is enough.
- **Repeated non-trivial literals become constants.** If a string/path/message/help text appears `>=3` times in the same module, hoist it to a named module constant instead of duplicating it. This is the default response to Sonar `S1192`.
- **Do not leave empty or effect-free exception handlers.** If an `except` block does nothing meaningful, either remove it and let the exception propagate, or add the concrete recovery/logging/translation logic Sonar expects.
- **Every new branch/helper needs tests in the same PR.** Sonar's project gate is dominated by new-code coverage; extracting helpers without adding focused tests simply moves the failure. When you add or refactor logic, add narrow tests that execute the new branches/helpers directly.
- **Prefer testable extractions.** Sonar generally rewards pure/helper extraction plus focused tests. If a function is large, extract deterministic subroutines with stable inputs/outputs, then test those paths instead of only relying on a broad integration test.
- **Prefer real fixes over suppression.** Do not add `# noqa`, `# type: ignore`, or Sonar suppression comments to silence maintainability findings unless the tool is materially wrong about correct code. If suppression is unavoidable, keep it narrow and explain why the code is safe.
- **Loopback/local-only HTTP is a special case.** Do not "fix" localhost/127.0.0.1 control-plane URLs by forcing HTTPS when the transport is intentionally loopback-only. Keep the safe loopback semantics, add/keep regression tests, and record the rationale in the PR if Sonar raises a hotspot. Code change and hotspot review are separate actions.
- **PR description must call out remaining Sonar UI work.** If the code is correct but Sonar still needs hotspot review or UI-side rationale application, say so explicitly in the PR body so a later agent does not waste time trying to "fix" it in code.

## Recent Changes

- **068**: `src/specify_cli/post_merge/` (AST-based stale-assertion analyzer), `agent tests` CLI subgroup, `agent/release.py prep` subcommand, FR-019 safe_commit fix in `_run_lane_based_merge`, FR-021 `scan_recovery_state` + `implement --base`
- **047**: Added typer, rich, ruamel.yaml, requests, pytest, mypy (the SQLite OfflineQueue sibling table shipped here was retired with the sync transport in the convergence)
- **023**: Documentation sprint / agent management cleanup

---

## PyPI Release

Follow [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for PyPI and GitHub releases. Publication is owner+controller-executed only after the required checks pass. Contributors do not push release tags as part of an ordinary change; that restriction applies until the [#830 release phase](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty/issues/830). `release.yml` is not present in this EXPERIMENTAL checkout.

---

## Execution Workspace Strategy (2.x)

- **Coord/primary partition** (canonical, operator-confirmed): coord = lifecycle surfaces
  (status, notes, trace, issue-matrix, `move-task`); primary = stable planning (spec/plan/WP
  outlines). Missions with no coordination topology (`SINGLE_BRANCH` / `LANES`) route
  everything to primary. Planning commands may be invoked from the repo root — no worktree is
  required to run `/spec-kitty.specify` / `/spec-kitty.plan` / `/spec-kitty.tasks`.
- `spec-kitty implement WP##` creates/reuses the execution workspace via
  `resolve_workspace_for_wp` (`src/specify_cli/workspace/context.py`).
  `lanes` / `lanes_with_coord` missions resolve
  `.worktrees/<slug>-lane-<id>` from `lanes.json`; a missing manifest fails
  closed with `MissingLanesError` (`src/specify_cli/lanes/persistence.py`).
  There is no `-WP##` fallback.
- **`single_branch` has no lanes** ([topology glossary](docs/context/topology.md)). Its
  `lanes.json` is a one-lane repo-root manifest (`lane-planning`). Its WPs run
  sequentially in the *write checkout* (the repository root checkout, or a
  validated owned checkout), stamped `execution_mode: direct_repo`. There is no lane
  worktree and no dependency merge. `implement` refuses with
  `WRITE_CHECKOUT_WRONG_BRANCH`, `WRITE_CHECKOUT_OCCUPIED` (another WP is
  `in_progress` in the same write checkout, for a mission whose write branch is
  the branch checked out there; a status copy on any other branch does not
  count, except that a mission whose write branch cannot be determined -- no
  usable `target_branch`, `meta.json` and `lanes.json` disagreeing, or a
  detached HEAD -- still counts on every branch, #5550) or `WRITE_CHECKOUT_DIRTY` (a resume is exempt), all in
  `src/specify_cli/lanes/implement_support.py`.
- **Create-time topology.** On a non-primary branch the create default is `lanes`.
  `single_branch` comes only from `--topology single_branch` or `--owned-checkout`.
  Caveat: in a repository with no `origin/HEAD` (for example no remote), primary-branch
  detection falls back to the current branch (`resolve_primary_branch`, `src/specify_cli/core/git_ops.py`),
  so a create on that branch resolves to `coord`, not `lanes`. That behaviour is pre-existing.
  When a `single_branch` mission targets a *protected target* (the primary branch or a
  configured protected branch), `agent mission create` mints and checks out
  `kitty/mission-<slug>-<mid8>` in the write checkout and records it in `meta.json`;
  `--commit-to-target` (accepted only with `single_branch`) opts out: it is persisted in `meta.json` and `ProtectionPolicy.resolve_for_mission` then lets that mission's own writes reach its own `target_branch` (no env var; other missions, non-mission commits and mixed code+mission-dir `safe_commit` commits stay refused; a non-boolean value refuses). `consolidate` lands the mission branch onto the target.
- **Unmigrated `single_branch` missions with code lanes fail closed** with
  `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` (`src/mission_runtime/context.py`). Remedy: the
  re-stamp migration, or `spec-kitty migrate backfill-topology --restamp-single-branch`.
  `spec-kitty doctor topology` reports it, plus `LANES_MANIFEST_UNREADABLE`.
- **Lane work tips.** When the recorder hook is installed (migration `4_0_0rc5_install_lane_tip_recorder`), a POSIX `post-commit` / `post-rewrite` hook, plus spec-kitty's own
  record points (lane allocation in `implement`, `for_review` transitions, crash recovery, auto-rebase), write `refs/spec-kitty/lane-tip/<branch>` (`src/specify_cli/lanes/lane_tip.py`).
  A destroyed lane with unabsorbed work is refused with `DESTROYED_LANE`
  (`src/specify_cli/lanes/worktree_allocator.py`), naming the SHA and the restore
  command `git branch <b> refs/spec-kitty/lane-tip/<b>`. `LANE_WORK_TIP_UNKNOWN` (`LaneWorkTipUnknownError`) fires when a lane's branch was deleted before any work tip was recorded, or after its `refs/spec-kitty/lane-tip/<branch>` ref was deleted: nothing is left to classify the lane by, so the guard fails closed. Its message says to look for stranded commits (`git reflog <branch>` or `git fsck --lost-found`); if you find one, record it with `git update-ref refs/spec-kitty/lane-tip/<branch> <sha>` and re-run `implement`; if you are sure no work was ever committed, run `spec-kitty context cleanup` to clear the stale workspace record and retry. Abandoning a destroyed lane (`DESTROYED_LANE`) is two steps today: `git update-ref -d refs/spec-kitty/lane-tip/<branch>`, then `spec-kitty context cleanup`. Squash-absorption detection needs git >= 2.38 (`git merge-tree --write-tree`); on older git the guard fails closed and refuses even a genuinely squash-merged lane.
  The recorder hooks are installed into your repository's hooks directory (`.git/hooks`, or a `core.hooksPath` set at repository-local scope that points outside the working tree) and are skipped, with a warning, when `core.hooksPath` comes from global or system git config, is `/dev/null`, missing, or points inside the working tree; then tips are recorded only at spec-kitty's own record points. With the recorder inactive (skipped, or a foreign `post-commit` hook), a destroyed lane whose tip still equals its creation base is refused with `LANE_WORK_TIP_UNKNOWN` instead of being treated as empty (`lane_tip_recorder_active`, `src/specify_cli/policy/lane_tip_recorder.py`).

**Planning artifacts** (land on the primary partition):
- `/spec-kitty.specify` → `kitty-specs/<mission>/`
- `/spec-kitty.plan` → planning artifacts
- `/spec-kitty.tasks` → `tasks.md` + `tasks/*.md`
- `spec-kitty agent mission finalize-tasks` → validates deps, writes lane metadata

**Implementation:** `spec-kitty implement WP##` is the only supported way to prepare a workspace. Agent commands must consume the resolved workspace path, not reconstruct it.

**When modifying workspace/orchestration behavior:**
1. Update runtime resolver logic first.
2. Update agent wrappers to use the resolver.
3. Update templates, skills, and docs together.

**Testing:** Unit coverage for workspace resolution + integration coverage for `agent action implement/review`.

**Status source of truth:** the resolved status surface (coord branch for coord/lanes-with-coord
topologies; primary otherwise), not the open worktree.

**References:** [execution-lanes.md](docs/architecture/execution-lanes.md), [git-worktrees.md](docs/architecture/git-worktrees.md)

---

## Consolidation & Preflight Patterns (0.11.0+)

Consolidation progress saved in `.kittify/runtime/merge/<mission_id>/state.json` for resumable operations.

**ConsolidationState fields** (`src/specify_cli/consolidation/state.py`):

| Field | Type | Description |
|-------|------|-------------|
| `feature_slug` | `str` | Feature identifier |
| `target_branch` | `str` | Branch being consolidated into |
| `wp_order` | `list[str]` | Ordered WP IDs |
| `completed_wps` | `list[str]` | Successfully consolidated WPs |
| `current_wp` | `str\|None` | WP currently being consolidated |
| `has_pending_conflicts` | `bool` | Unresolved git conflicts |
| `strategy` | `str` | "merge", "squash", or "rebase" |
| `started_at` / `updated_at` | `str` | ISO timestamps |

Properties: `remaining_wps`, `progress_percent`. Import from `specify_cli.consolidation`: `ConsolidationState`, `save_state`, `load_state`, `clear_state`, `has_active_consolidation`.

**Pre-flight validation (corrected, #3131/C-005):** there is no consolidation-domain `PreflightResult`/`run_preflight()`/`WPStatus` — that shape does not exist in `src/specify_cli/consolidation/`. It was removed in the #2057 merge-god-module decomposition; the only `PreflightResult` class in the codebase belongs to the unrelated sync daemon-ownership preflight. `src/specify_cli/consolidation/preflight.py` DOES exist, but exposes a different API: git-state, target-branch, and review-artifact preflights consumed by the consolidation executor and the dry-run forecast — not a WP-worktree-cleanliness checker. Retention conflicts (below) are surfaced through the merge-gates render path (operator-visible warnings/notices printed during a real consolidation) and the `--dry-run` forecast payload (which threads the raw tri-state flags into `resolve_merge_retention` and reports the resolved retain/delete decision + a `retention` provenance object), not through a `PreflightResult`.

**Post-consolidation retention policy (#3131):** a mission's `meta.json` can carry `retain_branches: bool` / `retain_worktrees: bool` (flat fields, absent by default — non-retaining missions are never default-written). `spec-kitty consolidate` resolves effective cleanup via `resolve_merge_retention()` (`core/paths.py`), precedence **explicit CLI flag > meta.json retention > default (delete/remove)**, fail-closed toward retention on any ambiguity (corrupt `meta.json` aborts; a present-but-non-boolean value retains + warns, never truthiness-coerced). Resolution happens once, off the PRIMARY partition, in the unlocked `_run_lane_based_consolidation` (`consolidation/executor.py`) — both a fresh and a `--resume`d consolidation honor it identically. Mapping to the long-standing cleanup flags: `retain_branches` resolves to an effective `--keep-branch`; `retain_worktrees` resolves to an effective `--keep-worktree`. The coordination branch/worktree/marker are torn down (or retained) as ONE coupled decision — `teardown_coordination = delete_branch AND remove_worktree` — so partial lane-level retention can never half-tear the coord triple; `consolidate --abort`'s coordination teardown honors the same coupled decision. The internal merge scratch worktree (`cleanup_merge_workspace`, `.kittify/runtime/merge/<id>/workspace`) is NOT a retained resource and always cleans up unconditionally. Mint retention at creation with `spec-kitty agent mission create --retain-branches --retain-worktrees`.

**Common commands:**
```bash
spec-kitty consolidate --resume          # resume interrupted
spec-kitty consolidate --abort           # start fresh
spec-kitty consolidate --dry-run         # conflict forecast
spec-kitty consolidate --mission 017-my-mission
```

**Implementation files:** `consolidation/state.py`, `consolidation/preflight.py`, `consolidation/approved_bound.py`, `consolidation/approved_attestation.py`, `consolidation/executor.py`, `consolidation/run_state.py`, `consolidation/entry_preflight.py`, `consolidation/resume_recovery.py`, `consolidation/phase_*.py`, `consolidation/coord_strand.py`, `consolidation/rollback.py`, `consolidation/mission_number/`, `consolidation/forecast.py`, `consolidation/resolve.py`, `consolidation/retention.py`, `consolidation/bookkeeping_projection.py`, `cli/commands/consolidate.py`, `core/paths.py` (`resolve_merge_retention`, `read_retention_from_meta`), `core/mission_creation.py` (create-time mint)

**Evidence gates check origin freshness (#5780, #5758, #5759).** `consolidate`, `accept`, `orchestrator-api accept-mission` / `consolidate-mission` and `agent action review` refresh the remote's view of the branches they trust (`specify_cli.git.origin_freshness`, through `git/origin_gate.py::run_origin_gate`; remote contact itself belongs to `kernel.git.remote`) before any mutation. Status evidence behind or diverged refuses `ORIGIN_STATUS_STALE`, an approved lane behind refuses `ORIGIN_LANE_STALE` (before the approval-stamp check, refuse-only), an unreachable remote refuses `ORIGIN_UNREACHABLE`, and review fast-forwards a behind lane or refuses `ORIGIN_LANE_DIVERGED`. No remote, or a never-pushed branch, passes silently. Opt out with `--origin-check warn` or `SPEC_KITTY_ORIGIN_CHECK=warn` (default `enforce`); never name this "sync". `consolidate --dry-run` is a recorded non-gate. Gates: `tests/architectural/test_remote_contact_owner.py` and `test_evidence_gates_check_origin.py`, both with empty allowlists. ADR `docs/adr/4.x/2026-10-06-3-evidence-gates-check-origin-freshness.md` (amends ADR 2026-06-05-1 Decisions 1 and 2).

**Forward ref advance is compare-and-swap (terminus-merge-integrity / #4996).** The forward consolidation advance `advance_branch_ref` (`git/ref_advance.py`) now performs a 3-arg `git update-ref <ref> <new_sha> <expected_old_sha>` and **fails closed** (raises) when the ref moved since it was read — it never falls back to a 2-arg write and never silently retries. This matches the compare-and-swap discipline `restore_branch_ref` (rollback) always had; the two are no longer opposite (the pre-fix `advance_branch_ref` was a non-CAS 2-arg write, the #4996 smoking gun). The coord teardown additionally re-checks the coordination tip via a compare-and-swap gate (`coordination/teardown.py::ProjectionTeardownGate`) before destroying the coordination triple, so a commit that landed after the projection window is never silently torn down. That earlier window refuses with `PROJECTION_TEARDOWN_ABORTED` and exit 1. A later window has its own code (#5570 / #5613): when the gate passed and the coordination branch (or the mission branch of a mission without coordination topology) then moved before its compare-and-swap delete, the branch is kept and `consolidate` raises `run_state.CoordMovedAfterLanding` — the message ends with `Error code: COORD_MOVED_AFTER_LANDING.` and the exit code is 75 (`consolidation/_constants.py`). `orchestrator-api consolidate-mission` keeps its `PREFLIGHT_FAILED` envelope and reports the code in `data["teardown_error_code"]`.

**The DEFAULT squash merge now runs a content axis (terminus-integrity-followups / #5013).** The reconciliation gate no longer early-returns PASS under the default `squash` strategy before the content checks. `MergeOutcomeVerifier.verify` runs a squash-sound **blob-attribution axis** (`_unattributable_content_squash`): every non-bookkeeping content path of the squashed diff `B..T` is attributed against the union of approved lanes' **first-parent authored blobs** (`ApprovedWpCommitSet.authored_blobs` — the *final* blob per `(lane, path)`, content identity rather than the lane-tip SHAs/patch-ids squash destroys); an unattributable path FAILs the gate and CAS-reverts the target. It is fail-closed: an empty authored set while approved WPs resolved commits, an unresolved window base, or any git-probe error REFUSE rather than passing vacuously (`consolidation/git_probes.py::blob_id_at`/`changed_paths_in_range` raise `GitProbeError`). `consolidate --resume` honors the persisted `ConsolidationState.strategy` and anchors the claim to a read-persisted-first `pre_mutation_coord_sha` + `pre_interrupt_lane_tips` (never the poisoned resume-start checkpoint), preserving an already-consolidated lane's commit by SHA; the per-lane tip is a CAS expectation (`state.lane_tip_cas_ok`) that tolerates the behind-HEAD window but REFUSEs true divergence. Honest residual remains `xfail`: the 3-way merge-resolution content case (a target blob equal to neither parent). (#4997 — the resume behind-own-HEAD staged-deletion window — was closed by PR #5031: a `--resume` now recovers a *provably pure* behind-own-HEAD primary in place and the MERGE-strategy no-op is adjudicated like the squash no-op. Since #5571 / #5613 the same in-place recovery covers the coordination worktree, a mission worktree and a lane worktree, each proven against its own `pre_mutation_refs` entry (`pre_mutation_coord_sha` for the coordination worktree); a worktree with no recorded tip is never reset.)

**Approved content must be present on the target (#5571 / #5613).** A strategy-independent presence axis (`MergeOutcomeVerifier._approved_content_divergence`, `reconciliation.unmet_approved_content`) FAILs with `APPROVED_CONTENT_MISSING` and rolls back when an approved code lane's own NET change to a path is not on the target, the target left that path alone since the lane was cut, and no later approved lane built atop it superseded the path. Typical cause: an operator committed the staged deletions of a lagging checkout, then resumed. It deliberately does not judge a path the target also changed (the blob-attribution and closed-world axes own that), and a git-probe error REFUSEs. The resume-only preflight leg (`entry_preflight._assert_mission_checkouts_clean`) refuses a dirty mission-branch worktree only when a lane remains to be consolidated or the worktree actually lags; a leftover `index.lock` no longer gets "Commit" advice; a lag plus an operator edit in a non-root worktree gets patch-based advice (`preflight.lag_with_edit_guidance`: `git diff --binary` to a patch in the common git dir, `reset --hard HEAD`, resume, `git apply`). Residuals: the repository root checkout with a lag plus an edit keeps the stock "Commit, stash, or revert" remedy; a corrupt `state.json` falls back to the generic dirty-checkout advice.

**Mixed lanes are attributed per WP (mixed-lane-authorship-soundness / #5046).**
- **Problem.** A lane that mixes an approved WP with a WP in `excluded_canceled_wp_ids` was previously trusted as a whole, so the canceled WP's committed content shipped at exit 0.
- **Stamp.** Every persisted lifecycle transition of a lane-mapped WP now carries `policy_metadata["lane_head"]`. It is stamped best-effort in `status/transition_pipeline.prepare_transition` through a probe (`status/lane_head.py`) that the two status shells inject; the pipeline itself stays git-free.
- **Resolver.** `consolidation/wp_attribution.py` rebuilds each WP's work windows from those stamps and derives the canceled WP's unsuperseded per-path content, comparing against its pre-state.
- **Verdict.** The strategy-independent `_canceled_content_divergence` step returns:
  - **FAIL** (`Divergence.canceled_content`) when that content is on the target;
  - **REFUSE** when attribution is missing or contradictory, when the canceled change was merged with an independent change, or (closed world, FR-013, ADR `2026-09-29-1`) when a lane content commit lies outside every WP's window.
  - **FAIL** (`Divergence.canceled_reachable_via_dependency`, code `CANCELED_REACHABLE_VIA_DEPENDENCY`, #5569 / #5613) when a fully-canceled dependency lane's content that an approved lane carries is live on the target; it is rendered alongside the strategy axis's own clause and is never attest-liftable. Commits of that lane which every carrier lane fully superseded stay in the claim, so they no longer over-refuse under `--strategy merge`.
- **Migration events.** Events whose actor starts with `migration:` (`wp_attribution.MIGRATION_ACTOR_PREFIX`) never open or close a window (FR-011).
- **Override.** `consolidate --attest-canceled-superseded <WP> --attest-reason "..."` (`consolidation/canceled_attestation.py`) records a forced `canceled -> canceled` operator transition with `policy_metadata.attestation`; it lifts the attribution-evidence REFUSEs, exempts lane commits up to its own `lane_head` stamp from the closed world (later stragglers still REFUSE), and never lifts a FAIL or an unreadable log/history (FR-012). For a fully-canceled dependency lane (#5613) an unstamped canceled WP (no `lane_head`) REFUSEs at claim time, and the attestation lifts ONLY that refusal, per attested WP, gated on `OVERRIDABLE_REASONS`; it takes no commit out of the subtracted set. The closed world only counts commits after the lane's own base (first-claim stamp, dependency-lane tips, target tip).
- **Unchanged.** Existing claim fields are byte-identical.
- **Rollback.** Every gate REFUSE now CAS-restores the target, like FAIL.
- **Residuals.** Four are pinned as strict `xfail` in `tests/consolidation/test_canceled_content_residuals.py` (#5330), including one gap of the closed-world anchors (a pre-claim out-of-workflow commit); a fully-canceled dependency lane's content is now subtracted from the dependency-tip exemption and REFUSEs when its branch is unreadable (#5569), less the commits every carrier lane fully superseded (#5613); two former ones now REFUSE. An approved WP that touches a canceled WP's file supersedes the whole path (path-level, not hunk-level).

**Approved claim is bounded by the approval stamp (#5668).** The claim no longer treats the whole live lane as approved authorship. The approval stamp is `policy_metadata.lane_head` on a work package's latest non-migration `approved` transition (or an approved-reviewed attestation); the `approved -> done` restamp is never read, and the stamp shipped with 4.0.0rc5, so earlier approvals carry none. `consolidation/approved_bound.py::check_lane` examines the commits reachable from the lane tip and from none of the lane's approval stamps, not from the claim base and not from an anchor, over the full commit range, never the first-parent spine. Nothing is exempt on a lane that also holds a canceled WP (#5720, operator ruling): `check_lane` reads no event of a canceled WP, so no commit of that WP, no status move of it while it stays canceled and no attestation covers a commit (forcing it into `approved` is a forced approval, see the residual below), and a mixed lane where a canceled WP committed after the approval needs the approved WP approved again, also when that work was reverted (three exemption designs, covered point, work windows and attribution-assigned commits, each let a commit land unreviewed; ADR below). `approved_bound_refusal` and the repeat-attestation check read the same rule. Merge commits and commits that touch only bookkeeping paths (the gate's own `_is_bookkeeping`) are dropped; anything left refuses. Three codes: `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING` (an approved WP with no stamp; the lane tip never stands in for it) and `APPROVAL_STAMP_NOT_ON_LANE` (a rewritten lane). Each refusal prints one short line per refused lane or work package and then one recovery block (`approved_bound.render_refusals`): commands carry the Mission slug and run as printed, `LANE_MOVED_AFTER_APPROVAL` names the late commits and says to see one with `git show <sha>`, `APPROVAL_STAMP_MISSING` offers one combined `--attest-approved-reviewed` command for every unstamped WP beside the move-back command per WP, and the approval stamp is defined once in the text. Rework, review and approve again; a fix committed to a lane after approval, including one folded in after a late review, needs the WP approved again. `move-task` and `agent status emit` print a one-line warning on stderr when an approval was persisted with no stamp on a WP of a code lane (`approved_bound.unstamped_approval_warning`; the status pipeline itself stays git-free). The claim base is the TARGET branch's tip as it was before the run mutated anything (persisted on a resume; the coordination base when that does not resolve); anchors are the dependency-lane tips of lanes that are not fully canceled, the target's pre-consolidation tip and every bounded lane's approval stamps. Because every bounded lane's approval stamps are anchors, a commit that another lane's approval stamp reaches is not refused on its own lane: if lane B merges lane A after a post-approval commit on lane A and the WP on lane B is approved again, lane A no longer refuses. A dependency-lane tip anchor exempts that commit only on the lane that depends on lane A; lane A itself is still checked against its own stamps. This is deliberate (content inside an approval stamp was in a reviewed tip), and a fresh run can give a different verdict than the first implementation of this rule did. No live branch is a reference: a post-approval commit already merged into the mission branch (for example after an interrupted run, then a resume) would pass, and so would one reachable from the live target through a planning-lane dependency, so planning lanes are not anchors. An unforced `in_review -> done` is read as an approval; the run's own `approved -> done` and any forced `done` are not. A lane with no commit beyond the claim base is not checked, so a `done` WP with no `approved` event on an empty lane is not refused (deliberately narrower than spec FR-005). It runs at claim time inside `reconciliation.build_approved_wp_set` (`_approved_bound_verdict`, after the mixed-lane resolution, before the snapshot, so nothing is rolled back); at the gate through `phase_gate._lane_recheck_verdict` and `reconciliation.lane_tips_moved_refusal`, which compares live lane tips with the tips validated at claim time and anchors only on SHAs captured before mutation, then rolls back through the one rollback authority; and in `orchestrator-api consolidate-mission` (`_refuse_post_approval_lane_content`, which calls the public entry `reconciliation.approved_bound_refusal` before its first lane is consolidated) as `PREFLIGHT_FAILED` with `data.preflight_error_code` (contract 1.10.0; that path has no gate re-check because it has no rollback door); it has no attestation flag, and for `APPROVAL_STAMP_MISSING` only its message says attestation is done with `spec-kitty consolidate` (CLI only). The gate re-check mostly renames a failure: a commit added to a lane DURING a run was already failed as un-attributable and rolled back, so it swaps the generic text for the named refusal, commit, WP and remedy. The case it closes is a mission with no coordination branch, where a late commit on one lane that writes another lane's approved content (same path, identical blob) passed the old gate with exit 0 and the banner. A commit added to a lane after that lane was already consolidated is also refused although it never landed. `consolidate --attest-approved-reviewed <WP> --attest-reason "<why>"` (`consolidation/approved_attestation.py`) records a forced operator self-transition with `policy_metadata.attestation = "approved_reviewed"`; the lane head at that moment becomes the bound. It is accepted only for a WP in the approved claim whose newest approval is not a stamped review approval (an earlier attestation falls under the repeat rule below), never lifts a post-approval-commit refusal (no attestation does, the canceled-superseded one included, see the next sentence), and a repeat is accepted (and re-recorded) only while the lane has not moved past the earlier one, otherwise refused with nothing recorded. A canceled-superseded attestation (`--attest-canceled-superseded`, ADR `2026-09-29-1` FR-012) still exempts lane commits up to its own `lane_head` from the mixed-lane closed world, but it covers no commit of this bound (the bound does not read it, #5720, nor any other event of a canceled WP): it says the canceled work is absent, not that new content was reviewed, so a commit made after an approved WP's approval needs that WP approved again even when the attestation is supplied. When a mixed-lane or canceled-dependency refusal stops the claim, the claim builder appends the bound's refusals to the same text after `This Mission also has:` (`reconciliation._compound_refusal`), so the operator sees both problems in the first run (a canceled-dependency refusal is shown with the bound only; a mixed-lane refusal on the same Mission shows on the next run, because the mixed lanes are not resolved once the dependency resolution refuses; when the only problem is a canceled WP's commit made after the approval the bound's refusal stands alone; only claim-time refusals are compounded, those of earlier or later phases are still one per run); the first refusal is unchanged, every canceled WP that refuses is named (one per line), and both fixes are needed in either order. An unmaterializable status surface, a missing approved lane branch, an unreadable canceled dependency lane and an unreadable event log refuse alone. `orchestrator-api consolidate-mission` adds `data.preflight_error_codes`, every distinct code of the text. It is not a review: an attestation is never read as the approving review, so it cannot satisfy the independent-review check; it is a forced transition and counts as one, so it can itself bring a WP to the forced-transition count at which the hollow-review warning prints. This reverses the claim builder's old rule that approved commit SHAs come from lane-branch git tips (never status rows) and the premise of ADR `2026-09-29-1` Decision 1 that only mixed lanes need a bound; the closed-world check itself still applies only to mixed lanes and keeps precedence there. ADR `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`. Residuals, each open: a commit between two approvals on one lane; content inside a merge commit (strict `xfail`; the merge skip stays because `git show` lists a lane auto-rebase's own conflict resolution as changed paths); a commit made during review (the stamp is the lane head when the approval was recorded); `orchestrator-api consolidate-mission` has only the up-front check, so a commit hand-merged into the mission branch with the lane reset to its stamp, or one landing between that check and its lane consolidation, is not caught there (`consolidate` fails both); a forced transition into `approved` of any WP of the lane restamps the lane at its current tip, so a commit made after the earlier approval then lands with no refusal and no warning: the approved WP itself (`approved -> approved --force`), a canceled WP (`move-task WP02 --to approved --force` un-cancels it and stamps the tip) or a sibling never reviewed (`in_progress -> approved --force`), and a forced `done` of such a WP followed by `--attest-approved-reviewed <WP>` does the same (the hollow-review warning prints then); the bound is as strong as the review model, these are recorded, forced operator acts, tracked in #5721; an approval recorded while the lane branch is missing has no stamp and can then be attested (two recorded operator acts); planning lanes and `single_branch` missions, which are not stamped and not bounded; the width of the gate's bookkeeping definition (`.kittify/` and any `kitty-specs/<slug>/` segment); `--dry-run` does not report the new refusals; on a resume, a repeat attestation after the target already advanced measures from the live target tip (the claim check still refuses afterwards).

**Refusals and failures roll back through one authority (slice 10 / #5338 #5318 #5332 #5296).** A claim that fails its integrity check (`reconciliation.claim_integrity_refusal`, the same predicate the gate uses) now exits before the first mutation. Every run persists one pre-mutation snapshot (`ConsolidationState.pre_mutation_refs`; never recaptured on `--resume`) and records per-phase post tips (`post_mutation_refs`, the CAS expected value) only for the target/mission/coordination branches whose tip changed during that phase — never after a CAS refusal (`RefAdvanceError`/`RefRestoreError`), but always after a `RefResyncError` (our CAS won, only the checkout resync failed). Lane branches (`snapshot_lane_branches`) are report-only: snapshotted, never recorded, never restored. A reconciliation-gate FAIL/REFUSE, a squash-projection refusal and `consolidate --abort` all call `consolidation/rollback.py::rollback_to_snapshot`, which restores each run-movable branch only while it is still at this run's recorded post tip, brings the checkout of a coordination branch it leaves in place back to that branch's tip (`git/ref_advance.py::resync_checkouts_to_tip`, toolchain residue only; a non-residue edit refuses the resync, which is reported with a remedy: commit or stash it, then re-run; #5638), reports a moved branch with no recorded tip (interrupted phase) or a vanished target/mission/coordination branch as NOT restored (the record is kept), reports a vanished lane branch with a `git branch <b> <sha>` recreate hint without blocking, resyncs checkouts via `git/ref_advance.py::_resync_checkouts`, and never rolls back a landing an earlier attempt verified (`state.reconciliation_passed_for_tip`). Residuals: a foreign commit landing on a run-movable branch inside the same phase after our own advance is recorded as ours; a same-mission `--abort` racing a live run relies on the existing lock owner-token scheme. `--abort` restores before clearing the record, under the consolidation lock only when a snapshot exists. The caller set is AST-pinned (`tests/consolidation/test_single_rollback_authority.py`). Planning-lane claims on the target checkout waive code-lane ancestry instead of merging code lanes there. ADR `2026-09-19-1` (Amendment 2026-09-29, follow-ups 2026-09-30 and 2026-10-05) records the design. Since #5385 every exit between the first mutation and the gate (non-zero `typer.Exit`, any exception, an interrupt) goes through one `try` in `_run_lane_based_consolidation_locked` that calls `rollback_to_snapshot` and re-raises the original error (`Exit(0)` passes; a failed or interrupted rollback prints "Rollback could not complete" and the original error still propagates); the executor's revert-based helpers are retired and the AST pin forbids them. Since #5666 the gate's own FAIL/REFUSE target restore (`_rollback_target_after_failed_reconciliation`) is retired: the gate's `Exit(1)` lands in that door, which keeps a commit another actor landed on top of the landing (reported NOT restored), and the AST pin forbids any `restore_branch_ref` in the executor family outside `rollback.py`. Since #5686 the record is the only anchor: `begin_attempt` marks every run-movable branch unsettled (`unsettled_refs`; only a restored / already-at-snapshot / kept-by-operator outcome or, for the target, a reconciliation PASS settles it, never an orderly exit), every in-span `advance_branch_ref` first persists an intent chain (`advance_intents`, adopted as this run's post tip only when its base is the tip the record expected), a phase records a post tip only when its entry tip was the expected one (FR-011), and a re-run or `--resume` facing a tip on an unsettled branch it cannot explain refuses with `UNEXPLAINED_BRANCH_MOVE` (exit 1, before the attestations and the coord-strand heal, record unchanged; while the target sits at a PASS anchor only the target and coordination rows are exempt, never the mission branch; the anchor is the tip read before `verify()`, refused if the target moved meanwhile, and persisted only after the squash projection proof), where `consolidate --abort --release-branch <b> --release-reason "..."` keeps that branch at its bound live tip (`KEPT_BY_OPERATOR`) and lets the record clear (misuse: `RELEASE_BRANCH_INVALID`, exit 2); ADR follow-up 2026-10-05 lists the residuals. Remaining second restore path: `repair_coord_strand`; resume recovery also still performs a raw `git reset --hard HEAD`, now on four checkout roles (repository root checkout, coordination worktree, mission worktree, lane worktree; #5613). Before any branch moves, consolidate also refuses a mission whose pending done bookkeeping the workflow mutation policy would refuse (e.g. a LANES mission recorded for protected `main`) with `PROTECTED_BRANCH_REFUSED`, via `BookkeepingTransaction.preflight_refusal` (recorded target, `--dry-run` reports it too); `orchestrator-api consolidate-mission` (`_execute_lane_merge`, both its code-lane and planning-only paths) runs the same preflight first, and a refused `--resume` (a merge record exists) points at `consolidate --abort` instead of claiming no branch moved. Residuals: a `BookkeepingPolicyRefused` can still escape unrendered from `_record_operator_attestations` and post-gate phases; the orchestrator-api path has no rollback door; legacy missions are not probed; lane auto-rebase merge commits, the resume-start heal floor, a failed-resync checkout reading dirty and the protected `single_branch` checkout switch survive a rollback (#3536, #5371, #5372 out of scope); lane-branch deletes still use `git branch -D`; the projection-window race (`ProjectionTeardownAbort`) has no rendered refusal on `consolidate` and keeps exit 1.

---

## Status Model Patterns (034+, 060 cleanup)

Append-only event log (`status.events.jsonl`) is the **sole authority** for WP lane state. Frontmatter `lane` is retired (migration-only). Phase 2 is the only active model as of 3.0.

> **Reducer duality — two reducers ship (`#4990` closed 2026-09-25 for the rejection-after-approval case; residual wall-clock ordering bug tracked by `#4941`).** "Deterministic event → snapshot" holds ONLY for the **Lamport** reduction wrapper (`status.reducer.materialize` / `reduce_shared_state`, `status/reducer.py:371`), which honors ADR [`2026-02-09-3`](docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md) (Lamport-primary, causal ordering). A **second** reducer also ships — the wall-clock LWW `reduce_parsed` (`spec_kitty_events.diary`, sorts `(at, event_id)`) — and the merge/terminus reconciliation gate deliberately sources its own approved/canceled WP-membership claim through the **Lamport** wrapper (`consolidation/reconciliation.py::build_approved_wp_set`) so a wall-clock-later approval cannot green-wash a committed rejection *in the gate's claim*. The general LWW split-brain (a later wall-clock event overriding a causally-earlier one in `reduce_parsed`) is **not** fixed by the terminus-merge-integrity mission — the rejection-after-approval case was closed via `#4990` (spec_kitty_events 10.4.0), and the remaining wall-clock ordering bug is tracked as the open sibling **#4941** (a `spec_kitty_events` change, out of scope / C-002). Do not read "sole authority / deterministic reducer" as a claim that only one reducer ships or that #4941 is resolved.

**Event format:**
```json
{"actor":"claude","at":"2026-02-08T12:00:00+00:00","event_id":"01HXYZ...","evidence":null,"execution_mode":"worktree","feature_slug":"034-feature","force":false,"from_lane":"planned","reason":null,"review_ref":null,"to_lane":"claimed","wp_id":"WP01"}
```

**Key functions:**

| Function | Module | Purpose |
|----------|--------|---------|
| `emit_status_transition()` | `status.emit` | Flat/primary shell over the status-owned `transition_pipeline` (validation runs once there); the transactional shell lives in `coordination/status_transition.py` |
| `reduce()` | `status.reducer` | Causal (Lamport) event → snapshot — the deterministic reducer honoring ADR `2026-02-09-3`. NOT the wall-clock LWW `reduce_parsed` sibling (`#4990` closed the rejection-after-approval case; residual ordering bug tracked by `#4941`). |
| `append_event()` / `read_events()` | `status.store` | JSONL I/O with corruption detection |
| `validate_transition()` | `status.transitions` | Check (from, to) against matrix + guards |
| `resolve_lane_alias()` | `status.transitions` | `doing` → `in_progress` at input boundaries |

**9-lane state machine:**
```
planned → claimed → in_progress → for_review → in_review → approved → done
```
`blocked` reachable from all non-terminal. `canceled` reachable from all. Alias: `doing` → `in_progress` (never persisted). Terminal: `done`, `canceled` (force required to leave).

**Coordination status-write guard (#5572 / #5613):** before it opens a coordination status write, `BookkeepingTransaction` calls `coordination/status_surface_guard.py::committed_events_missing_from_worktree`. The write refuses with `COORD_STATUS_SURFACE_DIVERGED` when the worktree's `status.events.jsonl` lost events its HEAD has committed (the rollback authority now resyncs that worktree itself, #5638, so the guard is the backstop), and with `COORD_STATUS_SURFACE_UNREADABLE` when the committed log is malformed, repeats an event id or cannot be read. Extra uncommitted lines in the worktree log are tolerated. Nothing is written in either case.

**Dependency gating:** WPs with `dependencies` frontmatter cannot be claimed/implemented until every dependency is `approved` or `done`. Computed by `dependency_readiness_for_wp()` (`src/specify_cli/core/dependency_graph.py`). `approved` satisfies the gate — gating on `done` only would deadlock same-mission chains. Re-invoking `implement` on an `in_progress` WP is a no-op resume (not re-gated).

**Quick status check (recommended for agents):**
```bash
spec-kitty agent tasks status
spec-kitty agent tasks status --feature 012-documentation-mission
```

**Package:** `src/specify_cli/status/` — `models.py`, `transitions.py`, `reducer.py`, `store.py`, `emit.py`, `lane_reader.py`, `bootstrap.py`, `validate.py`, `doctor.py`, `aggregate.py`, `lifecycle.py`, `lifecycle_events.py`, `tail_reader.py`, `views.py`, `preflight.py`, `work_package_lifecycle.py`, `zeitgeist_bridge.py` (status→Zeitgeist ephemeral-status seam), plus `wp_*` view/metadata helpers and migration utilities (`migrate_lifecycle_envelope.py`).

**Common operations:**
```python
from specify_cli.status.emit import emit_status_transition
event = emit_status_transition(
    feature_dir=feature_dir, feature_slug="034-feature",
    wp_id="WP01", to_lane="claimed", actor="claude",
)

from specify_cli.status.reducer import materialize
snapshot = materialize(feature_dir)
```

**Docs:** [docs/architecture/status-model.md](docs/architecture/status-model.md), [data-model.md](kitty-specs/034-feature-status-state-model-remediation/data-model.md)

---

## Mission Identity Model (083+)

Every mission carries a ULID-based `mission_id` in `meta.json`. `mission_number` is display-only, assigned at consolidation time. Fixes `NNN-` prefix collision on selectors, branches, and dashboards.

| Field | Type | Role | When assigned |
|-------|------|------|---------------|
| `mission_id` | ULID (26 chars) | Canonical machine identity (immutable) | At `mission create` |
| `mid8` | First 8 chars | Branch/worktree disambiguator | Derived |
| `mission_slug` | kebab slug | Human handle | At `mission create` |
| `mission_number` | `int\|None` | Display-only, `null` pre-merge | At consolidation via `max+1` |
| `friendly_name` | string | Human display | At `mission create` |

`mission_id` is the only runtime identity. `mission_number` is never used for lookup, locking, or routing.

**Naming:** Lane branch/worktree are keyed on the recorded Mission slug + lane id only (the mid8 appears when the slug embeds it): Branch `kitty/mission-<slug-body>-lane-<id>` (a stale `NNN-` is dropped from the slug body only when the slug embeds a mid8) | Worktree `.worktrees/<slug>-lane-<id>` (full recorded slug, verbatim). Mission/coordination branches keep `kitty/mission-<human-slug>-<mid8>`. See ADR `docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md`.

**Selector disambiguation:** Resolves `mission_id` → `mid8` → `mission_slug`. Ambiguous handles → structured error, **no silent fallback** (WP07 — reintroducing fallback is a regression).

**Migration** (pre-083 projects):
```bash
spec-kitty doctor identity --json        # audit
spec-kitty migrate backfill-identity     # mint mission_id for legacy missions
spec-kitty doctor identity --json        # confirm
```

Full runbook: [docs/migrations/mission-id-canonical-identity.md](docs/migrations/mission-id-canonical-identity.md)

---

## Shared Package Boundary (2026-04-25)

- **Runtime:** `src/runtime/next/_internal_runtime/` (canonical). The `src/specify_cli/next/` deprecation shim was **removed in commit `93dcbd75481c` (2026-07-03, "feat(unshim)!: delete 5 legacy shim namespaces …")**, two months before the convergence, and remains absent at 3.2.7rc1 — do not anchor new code there. `spec-kitty-runtime` PyPI package is retired.
- **Events / Tracker:** Consume only via `spec_kitty_events.*` / `spec_kitty_tracker.*` public imports. Vendored copies are removed. In the EXPERIMENTAL programme, these packages resolve from exact git-rev pins per [planning `PROGRAM.md` §2](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-planning/blob/main/PROGRAM.md) and the [internal-distribution ADR](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-planning/blob/main/decisions/ADR-INTERNAL-PYTHON-PACKAGE-DISTRIBUTION-2026-08-27.md); PyPI ranges return with [#830 Phase 3](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty/issues/830).
- **Dev editable/path overrides:** never committed in `pyproject.toml [tool.uv.sources]`. See [docs/development/how-to/local-overrides.md](docs/development/how-to/local-overrides.md).

Enforced by `tests/architectural/test_shared_package_boundary.py`, `test_pyproject_shape.py`, and the `clean-install-verification` CI job.

ADR: [`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`](docs/adr/3.x/2026-04-25-1-shared-package-boundary.md). Runbook: [`docs/migrations/shared-package-boundary-cutover.md`](docs/migrations/shared-package-boundary-cutover.md).

---

## Charter Activation and Doctrine Integrity Model

Governing ADR: [`docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md`](docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md)

### Activation Engine (`charter.activation.activation_engine`)

Plan/commit seam: `plan_activation()` validates (non-mutating); `commit_plan()` writes config only after plan succeeds. Never mutates config on validation failure (NFR-003). `CharterPackConfigError` → fail-closed. (Companion seam: `plan_deactivation()` / `promote_activations()`.)

```python
plan = plan_activation(kind="directive", artifact_id="010-...", pack_context=ctx)
commit_plan(plan, project_root=Path("."))
```

### Charter Cascade (`charter.activation.cascade`)

Follows DRG `requires`/`suggests` edges (not hardcoded per-kind logic).

```bash
charter activate mission-type research --cascade all
charter activate mission-type research --cascade agent-profile,tactic
charter deactivate mission-type research --cascade all
```

Without `--cascade`: warns about skipped artifacts with a suggested recovery command. **Shared-reference safety (C-005):** cascade deactivation skips artifacts still referenced by another active artifact.

### Canonical Kind Vocabulary

`ArtifactKind.from_operator_token` (`charter.offering.artifact_kinds`) normalizes operator-facing tokens at input boundaries (`charter.activation.kind_vocabulary` only re-exports the token set + error type):

| Token | Canonical kind |
|-------|----------------|
| `agent-profile` | `agent_profile` |
| `mission-step-contract` | `mission_step_contract` |
| `glossary-pack` | `glossary_pack` |
| `skill` | `skill` (a pack skill; see [Pack skills](#pack-skills)) |
| `directive` / `tactic` / `styleguide` / `toolguide` / `paradigm` / `procedure` | (same) |
| `mission-type` | raises `MissionTypeNotAnArtifactKind` |

`template` and `asset` are `ArtifactKind` members that are **not** charter-activatable — they resolve specially (`ArtifactKind.activatable == False`). `anti_pattern` **is** charter-activatable (`ArtifactKind.activatable == True`; it is in `CHARTER_ACTIVATABLE_KINDS` and the activation surfaces accept it end to end — issue #5409, 2026-09-30 ruling), but it is excluded from the hand-authorable operator-token set `CHARTER_KIND_TOKENS` (via `_NON_AUGMENTATION_ELIGIBLE_KINDS`) because an anti-pattern node is a re-kinded node inside another kind's graph fragment, never a standalone artifact file. The single authority is the `ArtifactKind` enum. It carries the `plural` and `activatable` facts and three more: `org_requirable` (an org pack may declare a `required_<plural>` list for the kind), `selection_overlayable` (that org list also unions into the charter's `selected_<plural>` field; true for 8 kinds, a strict subset of the org-requirable ones: `glossary_pack`, `asset` and `skill` are requirable but not overlayable) and `effective_when_absent` (`"all"` or `"required"`: what is in force while the kind's activation key is absent; `"required"` only for `skill`). Every activation kind-vocabulary set and singular↔plural map derives from it (no hand-copied mirrors — gated by `tests/architectural/test_charter_kind_vocabulary_single_authority.py`). The FR-005 docstring in `src/charter/offering/artifact_kinds.py` is the canonical statement.

### Pack skills

A **pack skill** is a thin, parameterized entry point a team shares through a pack (ArtifactKind `skill`, URN `skill:<id>`; ADR [`2026-09-27-1`](docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md)). Not to be confused with a shipped doctrine skill or a command skill (see [Pack skill](docs/context/execution.md#pack-skill)).

- **Activate:** `spec-kitty charter activate skill <id>` (and `deactivate`). **Declare:** `<id>.skill.yaml` plus a body file (prompt form) in an org pack's `skills/` or in `.kittify/doctrine/skills/`.
- **Project:** rendered as `<skill_namespace>-<id>/SKILL.md` into the primary project skill root of each configured tool, never a user-global root; ownership lives in `.kittify/skills-manifest.json`. `spec-kitty doctor skills` reports drift, staleness and orphaned copies.
- **Namespace:** a non-built-in skill needs a `skill_namespace` (org: `org-charter.yaml`; project: `charter_packs.project.skill_namespace` in `.kittify/config.yaml`). Grammar for the namespace and for skill ids: lowercase ASCII, starts with a letter, `[a-z0-9]` segments joined by single `-`; namespace at most 32 characters, id at most 64. `spk-`, `spec-kitty-` and `spec-kitty.` are reserved.
- **Default in force:** when `activated_skills` is absent, the effective set is the org packs' `required_skills` plus built-in defaults (empty today), not every available skill. Neither default-pack seeding (`spec-kitty upgrade`) nor the charter interview writes the key; the first `activate skill <id>` writes it, starting from that in-force set.

### `specializes_from` DRG Lineage

Profile lineage is a DRG edge (C-009 binding constraint), not a per-profile field. Declare in org-pack DRG YAML:
```yaml
edges:
  - source: "agent_profile:my-analyst"
    target: "agent_profile:researcher-ryan"
    relation: specializes_from
```

**Endpoint form matters.** An endpoint is either a **DRG URN** — `<kind>:<id>`, where `<kind>` is a `NodeKind` member such as `agent_profile`, `directive` or `styleguide` — or a **bare id** that the fragment's own `nodes:` block declares. Anything else is refused at merge time with an `unresolved_edge_endpoint` conflict naming the token. (Before mission `doctrine-silence-guards-01KYFV7Q` this snippet read `urn:profile:…`, a shape that exists nowhere in the vocabulary; the bridge dropped it in silence, so the documented declaration was inert. See `src/charter/offering/drg/merge.py:_resolve_edge_endpoint`.)

- Distinct from `delegates_to` (runtime work handoff).
- Resolved via `AgentProfileRepository.resolve_profile` DRG traversal. Retired per-profile field form rejected at load time.
- `enhances` = field-merge (preserves action sequence + step I/O); `overrides` = full replacement. Silently dropping steps or stripping step I/O is rejected.

### Profile Load Diagnostics

`AgentProfileRepository.skipped_profiles` exposes load failures without filesystem rescans. Included in `spec-kitty doctor doctrine --json`. A pack with invalid profiles is NOT reported healthy even if DRG counts are valid (FR-010).

### Upstream Deferred-Item References

These issues predate the 2026-09-07 org move that made this repository `spec-kitty/spec-kitty`; they were filed against the pre-move upstream line and are closed references, not open work items here:

- [#1622](https://github.com/spec-kitty/spec-kitty/issues/1622) (upstream): `coordination.status_service` dead-symbol debt
- [#1623](https://github.com/spec-kitty/spec-kitty/issues/1623) (upstream): `doctor.py` god-module split (FR-012)
- [#1624](https://github.com/spec-kitty/spec-kitty/issues/1624) (upstream): `_tag_source` provenance sidecar typing (FR-013)

---

## Branches and CI

GitHub branch protection and review requirements enforce the repository workflow. `spec-kitty consolidate` still consolidates into **local** `main` only — do NOT use `spec-kitty consolidate --push` or `git push origin main`; publish via a topic branch and a PR targeting `main`.

Live GitHub Actions are part of that workflow. The reinstated lean modular CI (`ci-router.yml` → `module-tests.yml` / `ci-modules.yml` → `ci-aggregate.yml`, plus `packs.yml`, `ci-nightly.yml`, and `sonar.yml`) is the sole/primary public producer, replacing the archived EXPERIMENTAL Blacksmith producer (`#3995`). `ci-quality.yml` and `protect-main.yml` are [#830 Phase-1](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty/issues/830) infrastructure; `ci-quality.yml` carried a per-PR `sonarcloud` job ([#3993](https://github.com/spec-kitty/spec-kitty/issues/3993)) until mission `sonar-per-pr-coverage-reuse` ([#4334](https://github.com/spec-kitty/spec-kitty/issues/4334)) retired it: it re-ran the fast tier under `pytest --cov` to build a coverage report the `CI Modules` shards had already produced for the same commit. The per-change report is now the **`sonar-pr` job in `ci-aggregate.yml`**, which consumes that measurement instead of re-measuring. It keeps the same posture — **reported, not required**: `continue-on-error`, and excluded from the terminal `aggregate-gate` job by a `needs:` set-equality assertion. `ci-windows.yml`, `docs-pages.yml`, and `check-spec-kitty-events-alignment.yml` are also live.

---

## Docker Mode Policy (`spec-kitty-saas`)

The SaaS repository serves the hosted Team Kitty product, which is not actively supported (see the Team Kitty section above). This policy applies only when the operator explicitly asks for work there. When work touches `/spec-kitty-saas`, use two explicit Docker modes:

- **`dev-live`** (implementation/debug loops): `make docker-app-up-live`, `make docker-app-down-live`
- **`prod-like`** (pre-merge gate): `make docker-app-up`, `make docker-auth-check` (required before merge), `make docker-app-down`

Default to `dev-live` while editing Python, templates, or assets. Always run and pass `prod-like` auth preflight before merge. If tracker connectors are missing in UI, verify waffle flag `tracker_connectors` is enabled for the team.

Runbook: `spec-kitty-saas/docs/docker-development-modes.md` in the sibling SaaS repo.

---

## Documentation Mission Patterns (0.11.0+)

**Modes:** `initial` (from scratch), `gap_filling` (audit + fill gaps), `mission_specific` (one feature/component; legacy input alias `feature_specific`).

**Divio types:** Tutorial (learning), How-To (task), Reference (API, often auto-generated), Explanation (architecture/why).

**Generators:** JSDoc (JS/TS, `npx`), Sphinx (Python, `sphinx-build`), rustdoc (Rust, `cargo`).

**Workflow:**
```bash
/spec-kitty.specify  # prompts for iteration_mode, divio_types, target_audience, generators
/spec-kitty.plan && /spec-kitty.tasks
/spec-kitty.implement  # creates Divio templates, configures generators, generates API docs
/spec-kitty.review && /spec-kitty.accept
```

**Gap-filling:** Auto-detects framework, classifies docs by Divio type, builds coverage matrix, prioritizes: HIGH (missing tutorials/reference for core), MEDIUM (how-tos for advanced), LOW (explanations). Output: `gap-analysis.md`.

**Troubleshooting:**
```bash
pip install sphinx sphinx-rtd-theme    # Python generator
npm install --save-dev jsdoc docdash   # JavaScript generator
```
Low-confidence classification: add `---\ntype: tutorial\n---` frontmatter. Unpopulated templates: replace all `[TODO: ...]` placeholders.

**Implementation:** `src/specify_cli/missions/documentation/mission.yaml`, `doc_generators.py`, `gap_analysis.py`, `doc_state.py`. User guide: [docs/architecture/documentation-mission.md](docs/architecture/documentation-mission.md).

---

## GitHub CLI Authentication

If `gh` fails with "Missing required token scopes" on org repos, `GITHUB_TOKEN` may have limited scopes. Unset it to use keyring auth (gho_* token with full `repo` scope):

```bash
unset GITHUB_TOKEN && gh auth status  # verify keyring token is active
unset GITHUB_TOKEN && gh issue comment <issue> --body "..."
```

## Other Notes

Never claim frontend works without Playwright proof. API responses don't guarantee UI works; frontend can fail silently (404 caught, shows fallback). The bundled dashboard and its Playwright guard (`tests/ui/test_dashboard_wp_modal.py`) were removed in #5530; any future UI, including the replacement built on the Mission Status Read API, carries its own browser-driven suite following [`docs/development/testing/ui-e2e.md`](docs/development/testing/ui-e2e.md) (`PWHEADLESS=1 .venv/bin/python -m pytest <suite> -q` — **not** a bare `uv run`, which re-syncs the environment and destroys a hand-built `.venv`).

---

## Skill Routing

When user's request matches a skill, invoke via Skill tool. When in doubt, invoke.

- Product ideas/brainstorming → `/office-hours`
- Strategy/scope → `/plan-ceo-review`
- Architecture → `/plan-eng-review`
- Design system/plan review → `/design-consultation` or `/plan-design-review`
- Full review pipeline → `/autoplan`
- Bugs/errors → `/investigate`
- QA/testing → `/qa` or `/qa-only`
- Code review/diff → `/review`
- Visual polish → `/design-review`
- Ship/deploy/PR → `/ship` or `/land-and-deploy`
- Save/resume context → `/context-save` / `/context-restore`

<!-- spec-kitty:orientation -->
**Spec Kitty v3.2.7rc1** — project: spec-kitty (healthy)

Two usage patterns:
- **Full mission** (spec → plan → tasks → implement → review → consolidate):
  trigger: "spec out", "create a mission", "write a spec", "plan this"
  → run `/spec-kitty.specify`
- **Lightweight dispatch** (ad-hoc fix, question, or advice — no mission created):
  trigger: "hey spec kitty", "use spec kitty to", "spec kitty <anything>"
  → **ALWAYS run `spec-kitty dispatch "<request verbatim>"` — do NOT answer directly.**
  If you know the right profile, pass it to skip routing:
  `spec-kitty dispatch "<request verbatim>" --profile <profile-id>`
  Reason: `spec-kitty dispatch` loads governance context, routes the request,
  and opens the Op. Skipping it produces ungoverned, untracked responses.
  After finishing the work, close the Op with the command printed in the capsule
  (`spec-kitty profile-invocation complete --invocation-id <id> --outcome <done|failed|abandoned>`).
<!-- /spec-kitty:orientation -->
