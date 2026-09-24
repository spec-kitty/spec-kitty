# Spec Kitty Development Guidelines

**Spec Kitty** is a toolkit for Spec-Driven Development (SDD) — clear, actionable specifications ahead of implementation, inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit). **Spec Kitty CLI** bootstraps projects with the framework: directory structures, templates, and AI agent integrations. Every command template leads with a discovery interview; the CLI refuses to create specs or plans until the question set is answered.

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

**Before adding doctrine, ask: "does this govern consumers, or only how the core team works?"** In-house guidance placed in `built-in` gets force-shipped to everyone — a real defect. The wheel include is narrowed to `packs/built-in/` and guarded by `tests/cross_cutting/packaging/test_packaging_safety.py`. Internal-pack shape differs: a single `drg/fragment.yaml` (not sharded `*.graph.yaml`) + `org-charter.yaml`, loaded via `.kittify/config.yaml` → `doctrine.org.packs`. Editing either pack trips the pack-manifest regen gate — run `spec-kitty doctrine regenerate-graph` after. See ADR `docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md` and `packs/internal/README.md`.

---

## ⚠️ CRITICAL: Use Canonical Sources, Never Improvise

**Always use the canonical templates, skills, commands, and code surfaces rather than improvising or using older artefacts as examples.**

- Spec/plan/tasks templates come from `packs/built-in/missions/<type>/templates/` (resolved through the charter/doctrine chain) — never copy structure from an older mission in `kitty-specs/`.
- Workflows run through the documented `spec-kitty` CLI commands and the published skills — do not hand-roll equivalents or reconstruct paths the resolver should provide.
- When a canonical command, template, or code surface appears missing or broken, **trace the source and file an upstream gap** — do not silently work around it with an improvised substitute.

**Why:** older missions and ad-hoc artefacts drift from the canonical structure; copying them propagates the drift. The doctrine templates are the single source of truth.

---

## ⚠️ CRITICAL: Team Kitty is Zeitgeist — "sync" is dead

The hosted product is **Team Kitty**; the live transport is **Zeitgeist**, a volatile per-team relay the SaaS provisions and polls. On every lane transition the CLI publishes one **moment** straight to the team's relay (`status/emit.py` → `status/adapters.py` → `status/zeitgeist_bridge.py` → `zeitgeist_client/`), bounded to one request with no queue and no retry, gated only by team membership and repository admission on the SaaS side. The old "sync" transport (daemon, offline queue, per-project consent, `api/v1/sync/*` ingress) was deleted on both sides in August 2026; every remaining "sync" identifier (`SPEC_KITTY_ENABLE_SAAS_SYNC`, `SPEC_KITTY_SYNC_*`, `sync_active()`, `OWNED_SYNC_UNSUPPORTED`) is residue that does **not** gate the moment path. Read [`docs/context/team-kitty.md`](docs/context/team-kitty.md) before touching anything hosted, and never design against or "re-enable" sync.

---

## ⚠️ CRITICAL: Git Workflow — Branches, PRs, and Merges

This repository uses **`main` as the integration branch**. Open a topic branch, target it with a pull request, and let repository review and branch-protection settings enforce the merge gate. GitHub Actions are live here: the reinstated lean, modular CI (`#3995`) runs on public `main` — a path router (`ci-router.yml`) feeding the single `gate_selection.py` authority, a per-module test matrix (`module-tests.yml` / `ci-modules.yml`), coverage/xunit aggregation with a diff-cover ≥90% gate (`ci-aggregate.yml`), a packs lane (`packs.yml`), a nightly full/performance/interpreter run (`ci-nightly.yml`), and a fork-safe SonarCloud workflow (`sonar.yml`). These replaced the archived EXPERIMENTAL Blacksmith producer.

- **Never push to `main`.** Create a topic branch from the current `main`, open a PR targeting `main`, and let the repository merge controls handle publication.
- `spec-kitty merge` consolidates lanes into your **local** `main` only; it never publishes to the remote. Qualify local vs origin when naming the branch (see the `primary`/`merge` footgun note under Terminology Canon).
- If your GitHub CLI installation cannot use issue or pull-request commands in a restricted environment, use the GitHub web interface or an authenticated GitHub API client.

### Convergence ports

- Port commits from the pre-fork line with `git cherry-pick -x` so authorship and provenance are preserved.
- Before applying a commit, classify it with `git show --stat <sha> -- <retired paths>`.
- If every touched path is retired, record the commit as `DROP` in the convergence map and do not port it.
- For a mixed commit, drop the retired hunks and cite the omitted hunks under `Dropped hunks:`.
- Every convergence PR carries `Retired-surface scan: 0 hits`, computed over added diff lines with the canonical regex in [planning `PROGRAM.md` §5](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-planning/blob/main/PROGRAM.md#5-the-pr-protocol).
- Never add `# noqa: TID251` for a retired module.
- Never resolve a kept-file conflict with `theirs` without re-running `tests/architectural/test_no_retired_subsystems.py`.

**Test policy (§6):** run every test you write or change plus your blast radius, and record commands + counts in the PR. Baseline is `make test-fast`; add the test files of every module your diff touches, and the full test directory of each owning subsystem. Run `tests/architectural/` in full only for cross-cutting changes (pytest.ini, pyproject.toml, conftest, markers, packaging) — see "Test policy — what you must run for a change" below for the calibrated blast-radius rule. Do **not** run `make test-full` or any whole-repo suite — the CI agent owns that.

---

## Terminology Canon

- Canonical product term is **Mission** (plural: **Missions**).
- `Feature` / `Features` are prohibited in canonical, operator, and user-facing language for active systems.
- Do not introduce or preserve `feature*` aliases (API/query params, routes, fields, flags, env vars, command names, or docs) when the domain object is a Mission.
- Historical archived artifacts may retain legacy wording only as immutable snapshots, explicitly marked legacy.
- **Overloaded terms `primary` and `merge` — footgun.** `primary` carries four senses (PRIMARY partition / Primary Branch / repository-root checkout / Target Ref) and `merge` three operations (lane consolidation / branch integration / publish to origin). The load-bearing trap is reading a **PRIMARY-partition** verdict as a **Primary-Branch (`main`)** instruction — and treating `spec-kitty merge` (local lane consolidation) as a **publish to origin**. Always name the sense; the canonical definitions and "Do NOT use when" guards live in the glossary: [`docs/context/orchestration.md`](docs/context/orchestration.md) (`#primary-partition`, `#primary-branch`, `#target-ref--commit-target`, `#lane-consolidation`, `#branch-integration--git-merge`, `#publish-to-originmain`) and [`docs/context/execution.md`](docs/context/execution.md#repository-root-checkout).
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
src/specify_cli/  # Top adapter/application layer: CLI, status, merge, lanes, workspace, tracker clients
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
3. Cross-cutting changes (pytest.ini, pyproject.toml, conftest, markers, packaging) additionally touch `tests/architectural/`.

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
1. **Pre-existing known-P0 reds** honestly red main (ADR `2026-07-17-1`); e.g. #2736, #2772,
   #1834. Do **not** "fix" them — leave them red. Confirm by running the same test on the
   merge-base / `upstream/main` (via `PYTHONPATH=<worktree>/src`), or check the tracker.
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

**Formatting is a separate gate from linting (#3952).** `ruff check .` passing says nothing about format: CI (`ci-quality.yml`, `ci-router.yml`) runs `ruff format --check .` over the whole repo, and `tests/architectural/test_ruff_format_enforcement.py` enforces the same command in `make test-full` (#473/#558), so an unformatted file goes red regardless of whether anyone ran the check locally. Run `make format-check` (or `uv run --frozen ruff format --check .`) before pushing; `uv run --frozen ruff format <files>` fixes what it flags.

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
  `resolve_workspace_for_wp` (`src/specify_cli/workspace/context.py`),
  resolving `.worktrees/<feature>-lane-<id>` from `lanes.json`. There is no
  `-WP##` fallback: flat / `SINGLE_BRANCH` / `LANES` missions all still
  require `lanes.json`; a missing manifest fails closed with
  `MissingLanesError` (`src/specify_cli/lanes/persistence.py`).

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

## Merge & Preflight Patterns (0.11.0+)

Merge progress saved in `.kittify/merge-state.json` for resumable operations.

**MergeState fields** (`src/specify_cli/merge/state.py`):

| Field | Type | Description |
|-------|------|-------------|
| `feature_slug` | `str` | Feature identifier |
| `target_branch` | `str` | Branch being merged into |
| `wp_order` | `list[str]` | Ordered WP IDs |
| `completed_wps` | `list[str]` | Successfully merged WPs |
| `current_wp` | `str\|None` | WP currently being merged |
| `has_pending_conflicts` | `bool` | Unresolved git conflicts |
| `strategy` | `str` | "merge", "squash", or "rebase" |
| `started_at` / `updated_at` | `str` | ISO timestamps |

Properties: `remaining_wps`, `progress_percent`. Import from `specify_cli.merge`: `MergeState`, `save_state`, `load_state`, `clear_state`, `has_active_merge`.

**Pre-flight validation (corrected, #3131/C-005):** there is no merge-domain `PreflightResult`/`run_preflight()`/`WPStatus` — that shape does not exist in `src/specify_cli/merge/`. It was removed in the #2057 merge-god-module decomposition; the only `PreflightResult` class in the codebase belongs to the unrelated sync daemon-ownership preflight. `src/specify_cli/merge/preflight.py` DOES exist, but exposes a different API: git-state, target-branch, and review-artifact preflights consumed by the merge executor and the dry-run forecast — not a WP-worktree-cleanliness checker. Retention conflicts (below) are surfaced through the merge-gates render path (operator-visible warnings/notices printed during a real merge) and the `--dry-run` forecast payload (which threads the raw tri-state flags into `resolve_merge_retention` and reports the resolved retain/delete decision + a `retention` provenance object), not through a `PreflightResult`.

**Post-merge retention policy (#3131):** a mission's `meta.json` can carry `retain_branches: bool` / `retain_worktrees: bool` (flat fields, absent by default — non-retaining missions are never default-written). `spec-kitty merge` resolves effective cleanup via `resolve_merge_retention()` (`core/paths.py`), precedence **explicit CLI flag > meta.json retention > default (delete/remove)**, fail-closed toward retention on any ambiguity (corrupt `meta.json` aborts; a present-but-non-boolean value retains + warns, never truthiness-coerced). Resolution happens once, off the PRIMARY partition, in the unlocked `_run_lane_based_merge` (`merge/executor.py`) — both a fresh and a `--resume`d merge honor it identically. Mapping to the long-standing cleanup flags: `retain_branches` resolves to an effective `--keep-branch`; `retain_worktrees` resolves to an effective `--keep-worktree`. The coordination branch/worktree/marker are torn down (or retained) as ONE coupled decision — `teardown_coordination = delete_branch AND remove_worktree` — so partial lane-level retention can never half-tear the coord triple; `merge --abort`'s coordination teardown honors the same coupled decision. The internal merge scratch worktree (`cleanup_merge_workspace`, `.kittify/runtime/merge/<id>/workspace`) is NOT a retained resource and always cleans up unconditionally. Mint retention at creation with `spec-kitty agent mission create --retain-branches --retain-worktrees`.

**Common commands:**
```bash
spec-kitty merge --resume          # resume interrupted
spec-kitty merge --abort           # start fresh
spec-kitty merge --dry-run         # conflict forecast
spec-kitty merge --feature 017-my-feature
```

**Implementation files:** `merge/state.py`, `merge/preflight.py`, `merge/executor.py`, `merge/forecast.py`, `merge/resolve.py`, `merge/retention.py`, `merge/bookkeeping_projection.py`, `cli/commands/merge.py`, `core/paths.py` (`resolve_merge_retention`, `read_retention_from_meta`), `core/mission_creation.py` (create-time mint)

**Forward ref advance is compare-and-swap (terminus-merge-integrity / #4996).** The forward merge advance `advance_branch_ref` (`git/ref_advance.py`) now performs a 3-arg `git update-ref <ref> <new_sha> <expected_old_sha>` and **fails closed** (raises) when the ref moved since it was read — it never falls back to a 2-arg write and never silently retries. This matches the compare-and-swap discipline `restore_branch_ref` (rollback) always had; the two are no longer opposite (the pre-fix `advance_branch_ref` was a non-CAS 2-arg write, the #4996 smoking gun). The coord teardown additionally re-checks the coordination tip via a compare-and-swap gate (`coordination/teardown.py::ProjectionTeardownGate`) before destroying the coordination triple, so a commit that landed after the projection window is never silently torn down.

**The DEFAULT squash merge now runs a content axis (terminus-integrity-followups / #5013).** The reconciliation gate no longer early-returns PASS under the default `squash` strategy before the content checks. `MergeOutcomeVerifier.verify` runs a squash-sound **blob-attribution axis** (`_unattributable_content_squash`): every non-bookkeeping content path of the squashed diff `B..T` is attributed against the union of approved lanes' **first-parent authored blobs** (`ApprovedWpCommitSet.authored_blobs` — the *final* blob per `(lane, path)`, content identity rather than the lane-tip SHAs/patch-ids squash destroys); an unattributable path FAILs the gate and CAS-reverts the target. It is fail-closed: an empty authored set while approved WPs resolved commits, an unresolved window base, or any git-probe error REFUSE rather than passing vacuously (`git/git_probes.py::blob_id_at`/`changed_paths_in_range` raise `GitProbeError`). `merge --resume` honors the persisted `MergeState.strategy` and anchors the claim to a read-persisted-first `pre_mutation_coord_sha` + `pre_interrupt_lane_tips` (never the poisoned resume-start checkpoint), preserving an already-merged lane's commit by SHA; the per-lane tip is a CAS expectation (`state.lane_tip_cas_ok`) that tolerates the behind-HEAD window but REFUSEs true divergence. Honest residuals remain `xfail`: #4997 (resume SHA-preservation over the staged-deletion / `LOCAL_CHANGES` behind-HEAD window) and the 3-way merge-resolution content case (a target blob equal to neither parent).

---

## Status Model Patterns (034+, 060 cleanup)

Append-only event log (`status.events.jsonl`) is the **sole authority** for WP lane state. Frontmatter `lane` is retired (migration-only). Phase 2 is the only active model as of 3.0.

> **Reducer duality — two reducers ship (`#4990` named-open).** "Deterministic event → snapshot" holds ONLY for the **Lamport** reduction wrapper (`status.reducer.materialize` / `reduce_shared_state`, `status/reducer.py:371`), which honors ADR [`2026-02-09-3`](docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md) (Lamport-primary, causal ordering). A **second** reducer also ships — the wall-clock LWW `reduce_parsed` (`spec_kitty_events.diary`, sorts `(at, event_id)`) — and the merge/terminus reconciliation gate deliberately sources its own approved/canceled WP-membership claim through the **Lamport** wrapper (`merge/reconciliation.py::build_approved_wp_set`) so a wall-clock-later approval cannot green-wash a committed rejection *in the gate's claim*. The general LWW split-brain (a later wall-clock event overriding a causally-earlier one in `reduce_parsed`) is **not** fixed by the terminus-merge-integrity mission — it is tracked as the open sibling **#4990** (a `spec_kitty_events` change, out of scope / C-002). Do not read "sole authority / deterministic reducer" as a claim that only one reducer ships or that #4990 is resolved.

**Event format:**
```json
{"actor":"claude","at":"2026-02-08T12:00:00+00:00","event_id":"01HXYZ...","evidence":null,"execution_mode":"worktree","feature_slug":"034-feature","force":false,"from_lane":"planned","reason":null,"review_ref":null,"to_lane":"claimed","wp_id":"WP01"}
```

**Key functions:**

| Function | Module | Purpose |
|----------|--------|---------|
| `emit_status_transition()` | `status.emit` | Flat/primary shell over the status-owned `transition_pipeline` (validation runs once there); the transactional shell lives in `coordination/status_transition.py` |
| `reduce()` | `status.reducer` | Causal (Lamport) event → snapshot — the deterministic reducer honoring ADR `2026-02-09-3`. NOT the wall-clock LWW `reduce_parsed` sibling (`#4990` named-open). |
| `append_event()` / `read_events()` | `status.store` | JSONL I/O with corruption detection |
| `validate_transition()` | `status.transitions` | Check (from, to) against matrix + guards |
| `resolve_lane_alias()` | `status.transitions` | `doing` → `in_progress` at input boundaries |

**9-lane state machine:**
```
planned → claimed → in_progress → for_review → in_review → approved → done
```
`blocked` reachable from all non-terminal. `canceled` reachable from all. Alias: `doing` → `in_progress` (never persisted). Terminal: `done`, `canceled` (force required to leave).

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

Every mission carries a ULID-based `mission_id` in `meta.json`. `mission_number` is display-only, assigned at merge time. Fixes `NNN-` prefix collision on selectors, branches, and dashboards.

| Field | Type | Role | When assigned |
|-------|------|------|---------------|
| `mission_id` | ULID (26 chars) | Canonical machine identity (immutable) | At `mission create` |
| `mid8` | First 8 chars | Branch/worktree disambiguator | Derived |
| `mission_slug` | kebab slug | Human handle | At `mission create` |
| `mission_number` | `int\|None` | Display-only, `null` pre-merge | At merge via `max+1` |
| `friendly_name` | string | Human display | At `mission create` |

`mission_id` is the only runtime identity. `mission_number` is never used for lookup, locking, or routing.

**Naming:** Branch: `kitty/mission-<slug>-<mid8>-lane-<id>` | Worktree: `.worktrees/<slug>-<mid8>-lane-<id>`

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
| `directive` / `tactic` / `styleguide` / `toolguide` / `paradigm` / `procedure` | (same) |
| `mission-type` | raises `MissionTypeNotAnArtifactKind` |

`template`, `asset`, and `anti_pattern` are `ArtifactKind` members that are **not** charter-activatable — they resolve specially and are excluded via `_NON_AUGMENTATION_ELIGIBLE_KINDS` (`src/charter/offering/artifact_kinds.py`). The tokens above (plus `mission-type`) are the charter-activatable vocabulary (`CHARTER_KIND_TOKENS`).

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

GitHub branch protection and review requirements enforce the repository workflow. `spec-kitty merge` still consolidates into **local** `main` only — do NOT use `spec-kitty merge --push` or `git push origin main`; publish via a topic branch and a PR targeting `main`.

Live GitHub Actions are part of that workflow. The reinstated lean modular CI (`ci-router.yml` → `module-tests.yml` / `ci-modules.yml` → `ci-aggregate.yml`, plus `packs.yml`, `ci-nightly.yml`, and `sonar.yml`) is the sole/primary public producer, replacing the archived EXPERIMENTAL Blacksmith producer (`#3995`). `ci-quality.yml` and `protect-main.yml` are [#830 Phase-1](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty/issues/830) infrastructure; `ci-quality.yml` carried a per-PR `sonarcloud` job ([#3993](https://github.com/spec-kitty/spec-kitty/issues/3993)) until mission `sonar-per-pr-coverage-reuse` ([#4334](https://github.com/spec-kitty/spec-kitty/issues/4334)) retired it: it re-ran the fast tier under `pytest --cov` to build a coverage report the `CI Modules` shards had already produced for the same commit. The per-change report is now the **`sonar-pr` job in `ci-aggregate.yml`**, which consumes that measurement instead of re-measuring. It keeps the same posture — **reported, not required**: `continue-on-error`, and excluded from the terminal `aggregate-gate` job by a `needs:` set-equality assertion. `ci-windows.yml`, `docs-pages.yml`, and `check-spec-kitty-events-alignment.yml` are also live.

---

## Docker Mode Policy (`spec-kitty-saas`)

When work touches `/spec-kitty-saas`, use two explicit Docker modes:

- **`dev-live`** (implementation/debug loops): `make docker-app-up-live`, `make docker-app-down-live`
- **`prod-like`** (pre-merge gate): `make docker-app-up`, `make docker-auth-check` (required before merge), `make docker-app-down`

Default to `dev-live` while editing Python, templates, or assets. Always run and pass `prod-like` auth preflight before merge. If tracker connectors are missing in UI, verify waffle flag `tracker_connectors` is enabled for the team.

Runbook: `spec-kitty-saas/docs/docker-development-modes.md` in the sibling SaaS repo.

---

## Documentation Mission Patterns (0.11.0+)

**Modes:** `initial` (from scratch), `gap_filling` (audit + fill gaps), `feature_specific` (one feature/component).

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

Never claim frontend works without Playwright proof. API responses don't guarantee UI works; frontend can fail silently (404 caught, shows fallback). This is enforced, not aspirational: the runnable regression guard lives at [`tests/ui/test_dashboard_wp_modal.py`](tests/ui/test_dashboard_wp_modal.py) (`PWHEADLESS=1 .venv/bin/python -m pytest tests/ui/ -q` — **not** a bare `uv run`, which re-syncs the environment and destroys a hand-built `.venv`). The suite is documented in [`docs/development/testing/ui-e2e.md`](docs/development/testing/ui-e2e.md) — extend it instead of asserting UI behavior from API responses alone.

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
- **Full mission** (spec → plan → tasks → implement → review → merge):
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
