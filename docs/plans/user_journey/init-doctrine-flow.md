---
title: Init and Project Charter — User Journey
description: 'How spec-kitty init sets up a project and how you author your project charter afterward with the charter commands; charter.yaml is the authoritative governance file.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/external/project-owner.md
---
# Init and Project Charter — User Journey

## What `spec-kitty init` does

`spec-kitty init` creates the project skeleton — the directory structure, agent
command files, and mission scaffolding. It does **not** generate governance, run
an interview, or copy example doctrine assets into your project. After init, the
next-steps output points you at the `charter` command to add governance when you
want it.

> **Changed in 3.2.6.** Earlier versions ran a governance interview automatically
> during `init` and seeded an example toolguide into every new project. Both were
> removed — governance is now authored on demand, and no example assets are
> scaffolded into your repo.

## Authoring your project charter

Your project charter defines the paradigms, directives, and tooling that every AI
agent in the project follows. You author it on demand:

1. **`spec-kitty charter interview`** — an optional guided Q&A that captures your
   project's governance choices. Your answers are saved so you can regenerate later.
2. **`spec-kitty charter generate`** — compiles your answers into
   `.kittify/charter/charter.yaml`, the single authoritative, git-tracked charter.

`charter.yaml` is the source of truth. `charter.md` is an optional companion you
write by hand to record the human rationale behind your choices — `charter
generate` never overwrites it.
