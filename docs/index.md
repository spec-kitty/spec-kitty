---
title: Spec Kitty 3.2 Documentation
description: Current Spec Kitty 3.2 documentation for new adopters, upgrade operators, harness users, and CLI integrators.
doc_status: active
updated: '2026-10-08'
related:
- docs/changelog/index.md
- docs/changelog/release-goals.md
- docs/migrations/from-charter-2x.md
- docs/migrations/index.md
- docs/migrations/upgrade-to-0-12-0.md
---

<section class="sk-docs-hero" aria-labelledby="sk-docs-title">
  <p class="sk-eyebrow">Spec Kitty</p>
  <h1 id="sk-docs-title">Spec Kitty documentation</h1>
  <p class="sk-docs-lead">Spec Kitty is for developers and teams who use AI coding agents (Claude Code, Cursor, Gemini CLI, and others) and want those agents to build the right thing, in the right order, without losing the plot halfway through. It gives your agent a clear spec, a plan, and a checklist to work from — instead of a loose prompt and a hope.</p>
  <nav class="sk-docs-actions" aria-label="Primary documentation paths">
    <a class="sk-btn sk-btn-primary" href="guides/tutorials/getting-started.md">Get started</a>
    <a class="sk-btn" href="migrations/index.md">Upgrade a project</a>
    <a class="sk-btn" href="api/index.md">Open the API reference</a>
  </nav>
</section>

New here? [Get started](guides/tutorials/getting-started.md) walks you through installing Spec Kitty and running your first mission end to end — about 30 minutes, no prior Spec Kitty knowledge required.

Just need the install steps? [Install Spec Kitty](guides/how-to/installation/install-spec-kitty.md) covers macOS, Linux, and Windows — the `pipx`, `uv`, and `pip` paths, adding Spec Kitty to a repository you already have, and what to do when your distribution blocks a system-wide `pip install`.

Set up and wondering what to type? The [slash command reference](api/slash-commands.md) covers the `/spec-kitty.*` commands your AI agent gains — specify, plan, tasks, implement, review, accept, merge — with each one's syntax, prerequisites, and the files it writes.

Already using Spec Kitty? Head to [Migrations](migrations/index.md) if you're upgrading, [Guides](guides/index.md) for task-oriented how-tos, or the [API and CLI reference](api/index.md) for exact command behavior.

## What's new and roadmap

- [Changelog](changelog/index.md) — release history (canonical `CHANGELOG.md`).
- [Release goals](changelog/release-goals.md) — declared intent of each release line (3.2.x, 3.3.x); each line's execution roadmap is linked from there and from [Plans](plans/index.md).

## Browse by topic

<div class="sk-card-grid">
  <a class="sk-doc-card" href="context/index.md">
    <span class="sk-card-kicker">Context</span>
    <strong>Context</strong>
    <span>Glossary narrative, audiences, and the Charter-era governance model.</span>
  </a>
  <a class="sk-doc-card" href="context/index.md">
    <span class="sk-card-kicker">Core Concepts</span>
    <strong>Core Concepts</strong>
    <span>Context, terminology, and the charter that governs your agent.</span>
  </a>
  <a class="sk-doc-card" href="architecture/doctrine-kinds.md">
    <span class="sk-card-kicker">Doctrine</span>
    <strong>Doctrine</strong>
    <span>The layered artifacts — directives, tactics, profiles — that shape agent behavior.</span>
  </a>
  <a class="sk-doc-card" href="architecture/index.md">
    <span class="sk-card-kicker">Architecture</span>
    <strong>Architecture</strong>
    <span>Unified, unversioned living design for the system.</span>
  </a>
  <a class="sk-doc-card" href="adr/index.md">
    <span class="sk-card-kicker">ADRs</span>
    <strong>Decision records</strong>
    <span>Architecture decision records by era (1.x, 2.x, 3.x).</span>
  </a>
  <a class="sk-doc-card" href="plans/index.md">
    <span class="sk-card-kicker">Plans</span>
    <strong>Plans</strong>
    <span>User journeys, investigations, and traces (distil-then-retire).</span>
  </a>
  <a class="sk-doc-card" href="api/index.md">
    <span class="sk-card-kicker">API</span>
    <strong>API and CLI reference</strong>
    <span>Exact CLI, file, schema, and environment behavior.</span>
  </a>
  <a class="sk-doc-card" href="api/index.md">
    <span class="sk-card-kicker">Reference</span>
    <strong>Reference</strong>
    <span>API, configuration, integrations, and security — exact behavior, no narrative.</span>
  </a>
  <a class="sk-doc-card" href="configuration/index.md">
    <span class="sk-card-kicker">Configuration</span>
    <strong>Configuration</strong>
    <span>Configuration files, flags, and environment variables.</span>
  </a>
  <a class="sk-doc-card" href="integrations/index.md">
    <span class="sk-card-kicker">Integrations</span>
    <strong>Integrations</strong>
    <span>AI harness and external-system integration.</span>
  </a>
  <a class="sk-doc-card" href="security/index.md">
    <span class="sk-card-kicker">Security</span>
    <strong>Security</strong>
    <span>Security posture, credentials, and secrets handling.</span>
  </a>
  <a class="sk-doc-card" href="guides/index.md">
    <span class="sk-card-kicker">Guides</span>
    <strong>Guides</strong>
    <span>Task-oriented guides and guided learning workflows.</span>
  </a>
  <a class="sk-doc-card" href="operations/index.md">
    <span class="sk-card-kicker">Operations</span>
    <strong>Operations</strong>
    <span>Operational and developer-workflow guides, including recovery.</span>
  </a>
  <a class="sk-doc-card" href="migrations/index.md">
    <span class="sk-card-kicker">Migrations</span>
    <strong>Migrations</strong>
    <span>Version migrations, upgrade paths, and shim rules.</span>
  </a>
  <a class="sk-doc-card" href="changelog/index.md">
    <span class="sk-card-kicker">Changelog</span>
    <strong>Changelog</strong>
    <span>Release history.</span>
  </a>
  <a class="sk-doc-card" href="changelog/release-goals.md">
    <span class="sk-card-kicker">Release Goals</span>
    <strong>Release goals</strong>
    <span>Declared intent of each release line.</span>
  </a>
  <a class="sk-doc-card" href="changelog/index.md">
    <span class="sk-card-kicker">Project Updates</span>
    <strong>Project Updates</strong>
    <span>Changelog, release goals, and mission run history.</span>
  </a>
</div>

## Section index

| Section | Landing page |
|---|---|
| Context | [context/index.md](context/index.md) |
| Core Concepts | [core-concepts/index.md](context/index.md) |
| Doctrine | [doctrine/index.md](architecture/doctrine-kinds.md) |
| Architecture | [architecture/index.md](architecture/index.md) |
| ADRs | [adr/index.md](adr/index.md) |
| Plans | [plans/index.md](plans/index.md) |
| API | [api/index.md](api/index.md) |
| Reference | [reference/index.md](api/index.md) |
| Configuration | [configuration/index.md](configuration/index.md) |
| Integrations | [integrations/index.md](integrations/index.md) |
| Security | [security/index.md](security/index.md) |
| Guides | [guides/index.md](guides/index.md) |
| Operations | [operations/index.md](operations/index.md) |
| Migrations | [migrations/index.md](migrations/index.md) |
| Changelog | [changelog/index.md](changelog/index.md) |
| Release Goals | [release-goals/index.md](changelog/release-goals.md) |
| Project Updates | [updates/index.md](changelog/index.md) |

## Migration and archive

Use [Migrations](migrations/index.md) when moving an existing project onto the current release. 1.x and 2.x docs are preserved as a historical archive and should not be used to start a new project.
