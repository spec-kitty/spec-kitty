<div align="center">
    <img src="https://github.com/spec-kitty/spec-kitty/raw/main/docs/assets/logo_small.webp" alt="Spec Kitty logo"/>
    <h1>Spec Kitty</h1>
    <p><strong>Spec-driven development for AI coding agents, multi-agent workflows, and governed software factories.</strong></p>
</div>

Spec Kitty is an open-source CLI for turning product intent into a repo-native AI coding workflow:

```text
spec -> plan -> tasks -> next -> review -> accept -> merge
```

Use it to build a governed software factory around Claude Code, Codex, Cursor, Gemini, GitHub Copilot, Windsurf, OpenCode, and other AI coding agents. Spec Kitty keeps specs, plans, work packages, acceptance criteria, review state, and merge decisions in your repository, then gives agents isolated git worktrees so implementation can happen in parallel without branch chaos.

[![PyPI version](https://img.shields.io/pypi/v/spec-kitty-cli?style=flat-square&logo=pypi)](https://pypi.org/project/spec-kitty-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/downloads/)

## Team Kitty 4.x prerelease

`main` carries the 4.x release-candidate line. To test RC2, install its exact version:

```bash
uv tool install 'spec-kitty-cli==4.0.0rc2'
```

This prerelease is for qualification; stable launch acceptance remains pending.
Normal stable installs continue to select the published stable release.

## Bright Software Factory, Not a Black Box

Spec Kitty is for teams building software factories: repeatable inputs, clear work-package boundaries, isolated execution, visible progress, and review gates. It can support dark software factories and autonomous coding experiments, but it is deliberately not a lights-out black box by default. Humans define intent, architecture, and acceptance criteria; agents implement inside traceable worktrees; reviewers accept, reject, or merge with an audit trail.

The goal is not more prompt text. The goal is a durable operating system for agentic coding where the repository remains the source of truth.

## Is It For You?

Use Spec Kitty when:

- AI coding sessions are losing requirements, decisions, or acceptance criteria.
- You want specs, plans, tasks, reviews, and merge state stored in Git.
- Multiple agents or developers need clear work-package boundaries.
- You are running parallel Claude Code, Codex, Cursor, Copilot, Gemini, or Windsurf work and need git worktree isolation.
- You are moving from vibe coding to a repeatable spec-driven development workflow.
- You want a local workflow first, with optional hosted tracker and sync integrations later.

It is probably overkill for one-off edits, tiny scripts, or teams that do not use Git.

## What It Provides

| Need | Spec Kitty provides |
| --- | --- |
| Start from intent | Guided `specify`, `plan`, and `tasks` workflows |
| Keep agents aligned | Repository-native mission artifacts under `kitty-specs/` |
| Split implementation | Work packages with lifecycle lanes such as `planned`, `in_progress`, `for_review`, `approved`, and `done` |
| Run agents in parallel | Isolated git worktrees under `.worktrees/` |
| Keep quality visible | Review, accept, merge, and retrospective gates |
| See progress | Optional local kanban dashboard with `spec-kitty dashboard` |
| Integrate agents | Slash commands or skills for Claude Code, Codex, Cursor, Gemini, Copilot, Windsurf, OpenCode, and more |
| Learn from missions | Every completed mission generates a retrospective by default. Tune via `.kittify/config.yaml#retrospective` or charter; see [how-to](docs/guides/how-to/governance/use-retrospective-learning.md). |

## Common Use Cases

- Replace ad hoc vibe coding with spec-driven development.
- Turn GitHub issues, product requirements, or bug reports into executable work packages.
- Coordinate multiple AI coding agents without losing context between sessions.
- Keep architecture decisions, constraints, and acceptance criteria close to the code.
- Build a governed software factory that can scale toward more autonomy without hiding review, test, or merge decisions.

## Governance layer

Spec Kitty keeps runtime governance in the repo instead of treating it as
agent-only prompt text. The trail model in [docs/architecture/trail-model.md](docs/architecture/trail-model.md)
describes how `spec-kitty dispatch "<request>"` maps operator intent to
runtime behavior, while
[docs/architecture/host-surface-parity.md](docs/architecture/host-surface-parity.md) tracks parity across
CLI, slash-command, and hosted surfaces.

The primary standalone governance command is:

- `spec-kitty dispatch "<request>"` - loads governance context, opens an Op record, and returns the context the agent must use before doing the work

## Quick Start

Install the CLI:

```bash
pipx install spec-kitty-cli
```

`pipx` is the preferred installer for the CLI because it keeps Spec Kitty in its
own virtual environment and avoids the `externally-managed-environment` errors
common on modern Linux distributions.

Other supported install methods:

```bash
uv tool install spec-kitty-cli
# or, inside an activated virtual environment
python -m pip install spec-kitty-cli
```

Create or initialize a project:

```bash
spec-kitty init my-project --ai claude
cd my-project
spec-kitty verify-setup
```

Replace `claude` with your agent key when needed. Common choices include `codex`, `cursor`, `gemini`, `copilot`, `opencode`, `qwen`, `windsurf`, `kiro`, `vibe`, `pi`, `letta`, and `llxprt`. See [Supported Agents](docs/api/supported-agents.md) for the current list.

Open your AI coding agent in the project and run the core workflow:

```text
/spec-kitty.charter
/spec-kitty.specify Build a small task list app.
/spec-kitty.plan
/spec-kitty.tasks
```

Then let the runtime choose the next action until the mission is ready:

```bash
spec-kitty next --agent claude --mission <mission-slug>
```

Review, accept, merge, and close the loop:

```text
/spec-kitty.review
/spec-kitty.accept
/spec-kitty.merge --push
```

After merge, run `/spec-kitty-mission-review`. The mission's
`retrospective.yaml` is authored during the runtime terminus (HiC prompt or
autonomous facilitator), not by `merge`. Once it exists, use
`spec-kitty retrospect summary` for the cross-mission view and
`spec-kitty agent retrospect synthesize --mission <mission-slug>` to apply any
staged proposals (dry-run by default — pass `--apply` to mutate).

For the full walkthrough, see [Your First Mission](docs/guides/tutorials/your-first-mission.md).

## Everyday Commands

| Command | Purpose |
| --- | --- |
| `spec-kitty init . --ai <agent>` | Add Spec Kitty to the current repo |
| `spec-kitty verify-setup` | Check local installation and project wiring |
| `spec-kitty dashboard` | Open the local mission dashboard |
| `spec-kitty next --agent <agent> --mission <slug>` | Ask Spec Kitty what the agent should do next |
| `spec-kitty upgrade` | Update an existing project after upgrading the CLI |
| `spec-kitty --help` | Show available commands |

## Documentation

Start here:

- [Getting Started](docs/guides/tutorials/getting-started.md)
- [Your First Mission](docs/guides/tutorials/your-first-mission.md)
- [Orchestrator Quickstart](docs/guides/tutorials/orchestrator-quickstart.md)
- [CLI Command Reference](docs/api/cli-commands.md)
- [Slash Commands](docs/api/slash-commands.md)
- [Supported Agents](docs/api/supported-agents.md)
- [Dashboard Guide](docs/guides/how-to/monitoring/use-dashboard.md)
- [Install and Upgrade](docs/guides/how-to/installation/install-and-upgrade.md)

Deeper topics:

- [Spec-Driven Development](docs/architecture/spec-driven-development.md)
- [Mission System](docs/architecture/mission-system.md)
- [Git Worktrees](docs/architecture/git-worktrees.md)
- [Multi-Agent Orchestration](docs/architecture/multi-agent-orchestration.md)
- [External Orchestrator Runbook](docs/guides/how-to/collaboration/run-external-orchestrator.md)
- [Hosted Sync Workspaces](docs/guides/how-to/collaboration/sync-workspaces.md)

Hosted auth, sync, and tracker flows remain opt-in. For setup details, see
[Hosted Sync Workspaces](docs/guides/how-to/collaboration/sync-workspaces.md), [Internal
Hosted-Readiness](docs/operations/internal-hosted-readiness.md), and
[Launch-Readiness Behavior](docs/architecture/launch-readiness-future.md).

## FAQ

### Is Spec Kitty for dark software factories?

Spec Kitty can be used as part of a dark software factory or autonomous coding pipeline, but its default model is governed and human-in-loop. It keeps specs, work packages, agent actions, review decisions, and merge state visible in the repository.

### Which AI coding agents does Spec Kitty support?

Spec Kitty supports common AI coding agents and coding harnesses including Claude Code, Codex, Cursor, Gemini, GitHub Copilot, OpenCode, Qwen, Windsurf, Kiro, Vibe, Pi, and Letta. See [Supported Agents](docs/api/supported-agents.md).

### How is Spec Kitty different from prompt templates or Spec Kit?

Spec Kitty is inspired by spec-driven development workflows, but adds repo-native mission state, work-package lanes, git worktree isolation, a local dashboard, governance commands, and an explicit `next -> review -> accept -> merge` runtime loop.

### Does Spec Kitty require a SaaS service?

No. Spec Kitty is local-first and stores its core artifacts in your repo. Hosted tracker and sync integrations are optional.

## Development

```bash
git clone https://github.com/spec-kitty/spec-kitty.git
cd spec-kitty
pip install -e ".[test]"
```

When testing templates from a source checkout:

```bash
export SPEC_KITTY_TEMPLATE_ROOT="$(pwd)"
spec-kitty init my-project --ai claude
```

See the [Contributing guide](docs/development/contributing.md) for contribution guidelines.

## Ecosystem & Specification Tools

- [MySpec](https://myspec.dev) — Spec discovery engine compiling interactive developer interviews into structured 4-file bundles (`constitution.md`, `requirements.md`, `solution.md`, `tasks.md`) with MCP server support.

## Support

- Open a [GitHub issue](https://github.com/spec-kitty/spec-kitty/issues/new) for bugs, feature requests, or questions.
- See the [changelog](docs/changelog/CHANGELOG.md) for release notes.
- See [CONTRIBUTORS.md](CONTRIBUTORS.md) and the [GitHub contributors graph](https://github.com/spec-kitty/spec-kitty/graphs/contributors) for contributor credits.

## License

Spec Kitty is released under the [MIT License](LICENSE).
