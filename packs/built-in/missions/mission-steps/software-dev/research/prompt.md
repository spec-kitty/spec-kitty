---
description: Capture discovery findings before specification
---
**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `<mission_dir>/tasks/`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

This is the mission's `discovery` step (not the `/spec-kitty.specify`
discovery interview). Capture discovery findings — the facts, decisions, and
open questions gathered before a spec exists — so `/spec-kitty.specify` and
`/spec-kitty.plan` can build on them instead of rediscovering the same
ground.

## Location

This step runs before a spec or plan exists, on whatever branch your mission's
planning artifacts land on — that may be `main` or any other checkout; there is
no branch this step must refuse to run on. If you need the deterministic branch
contract, run:

```bash
spec-kitty agent mission branch-context --json
```

This command reads the current checkout only and takes no `--mission` option.

## Where to record findings

Write directly into `<mission_dir>/research.md` (that is `kitty-specs/<mission_slug>/research.md`)
— **create it if it does not exist yet, or extend it if it does; never truncate
or replace existing content.** Put any supporting evidence (notebooks,
spreadsheets, longer excerpts) under `<mission_dir>/research/` and reference
each file from `research.md`.

## What to record

- **Decisions** you have reached and the reasoning behind each one.
- **Evidence** — sources, prior art, data — that backs each decision.
- **Open questions** that `/spec-kitty.specify` or `/spec-kitty.plan` still
  need to resolve.

Everything you write here is available to the specify and plan steps; nothing
here is regenerated or discarded by them. The plan step's Phase 0 extends this
same `research.md`, it does not replace it.

---

## Research-type missions only

The section below applies **only** to mission types whose pack ships
`research.md` / `data-model.md` templates (today: the `research` mission type).
For every other mission type — including `software-dev` — there is no such
scaffold: skip this section, the scaffold command creates nothing by default, and
recording findings by hand as described above is the whole step.

On a mission type that does ship those templates, once its plan is filled in
you can scaffold the remaining artifacts from the pack's templates instead of
authoring them by hand:

```bash
spec-kitty research --mission <handle>
```

This creates `research.md`, `data-model.md`, `research/evidence-log.csv`, and
`research/source-register.csv` from the mission type's shipped templates. It
never overwrites an existing, non-empty file unless you pass `--force`, and it
never creates an empty file when no template exists for the mission type.

---

## Success Criteria

- `<mission_dir>/research.md` exists (created or extended) and records at least
  one decision with its rationale, or explicitly states there are none yet.
- Any evidence you gathered is either inline in `research.md` or filed under
  `<mission_dir>/research/` and referenced from it.
- Open questions that specify or plan still need to resolve are listed.
