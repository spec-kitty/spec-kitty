---
description: Generate research documents for the current mission
---
**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission_slug>/tasks/`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Location Pre-flight Check

**BEFORE PROCEEDING:** Verify you are working in the repository root checkout.

```bash
pwd
git branch --show-current
```

**Expected output:**
- `pwd`: Should end with your project root directory path
- Branch: Should show your mission branch (e.g. `kitty/mission-<slug>-<mid8>` or a legacy `NNN-feature-name` form), NOT `main`

**If you see the main branch or the wrong directory path:**

⛔ **STOP - You are in the wrong location!**

This command creates research artifacts in your mission directory. You must be in the repository root checkout.

**Correct the issue:**
1. Navigate to your repository root checkout: `cd /path/to/project/root`
2. Verify you're on the correct mission branch: `git branch --show-current`
3. Then run this research command again

---

## What This Command Creates

When you run `spec-kitty research`, the following files are generated in your mission directory:

**Generated files**:
- **research.md** – Decisions, rationale, and supporting evidence
- **data-model.md** – Entities, attributes, and relationships
- **research/evidence-log.csv** – Sources and findings audit trail
- **research/source-register.csv** – Reference tracking for all sources

**Location**: All files go in `kitty-specs/<mission_slug>/`

---

## Workflow Context

**Before this**: `/spec-kitty.plan` calls this as "Phase 0" research phase

**This command**:
- Scaffolds research artifacts
- Creates templates for capturing decisions and evidence
- Establishes audit trail for traceability

**After this**:
- Fill in research.md, data-model.md, and CSV logs with actual findings
- Continue with `/spec-kitty.plan` which uses your research to drive technical design

---

## Goal

Create `research.md`, `data-model.md`, and supporting CSV stubs based on the active mission so implementation planning can reference concrete decisions and evidence.

## What to do

1. You should already be in the correct repository root checkout (verified above with pre-flight check).
2. Run `spec-kitty research` to generate the mission-specific research artifacts. (Add `--force` only when it is acceptable to overwrite existing drafts.)
3. Open the generated files and fill in the required content:
   - `research.md` – capture decisions, rationale, and supporting evidence.
   - `data-model.md` – document entities, attributes, and relationships discovered during research.
   - `research/evidence-log.csv` & `research/source-register.csv` – log all sources and findings so downstream reviewers can audit the trail.
4. If your research generates additional templates (spreadsheets, notebooks, etc.), store them under `research/` and reference them inside `research.md`.
5. Summarize open questions or risks at the bottom of `research.md`. These should feed directly into `/spec-kitty.tasks` and future implementation prompts.

## Success Criteria

- `kitty-specs/<mission_slug>/research.md` explains every major decision with references to evidence.
- `kitty-specs/<mission_slug>/data-model.md` lists the entities and relationships needed for implementation.
- CSV logs exist (even if partially filled) so evidence gathering is traceable.
- Outstanding questions from the research phase are tracked and ready for follow-up during planning or execution.
