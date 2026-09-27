---
description: Discover documentation needs, audience, iteration mode, and goals for a documentation mission
---
# /spec-kitty.discover - Discover Documentation Needs

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/spec.md`). Never refer to a folder by name alone.

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
- Branch: Should show your mission branch (e.g. `kitty/mission-<slug>-<mid8>` or a legacy `NNN-mission-name` form), NOT `main`

**If you see the main branch or the wrong directory path:**

⛔ **STOP - You are in the wrong location!**

This command creates or fills `spec.md` in your mission directory. You must be in the repository root checkout.

## What This Step Produces

If no mission exists yet, create one now with the mission type declared explicitly:

```bash
spec-kitty specify <mission-slug> --mission-type documentation --json
```

This scaffolds `kitty-specs/<mission-slug>/spec.md` from the documentation-domain spec template. The deliverable of this step is that file, **filled in** — not a blank scaffold.

## Goal

Produce a documentation specification that frames the documentation needs, names the target audience, declares the iteration mode, and states the goals — **before** any audit, architecture design, or content generation begins.

## What to Do

1. **State the documentation needs explicitly.** What questions must the documentation answer? What user tasks must it enable? Vague needs ("better docs") produce vague deliverables — write concrete, restateable needs a reader could repeat back without re-reading the spec.

2. **Name the target audience** by role and skill level — beginner end-users, working developers, integrators, operators, contributors. Each audience implies a different Divio type mix (tutorials serve beginners, how-tos serve task-driven users, reference serves working developers, explanations serve architects and decision-makers). A spec that conflates audiences produces docs that serve none of them well. Flag any entry that mixes audiences.

3. **Declare the iteration mode** up front and record it in `spec.md`:
   - `initial` — greenfield documentation suite, nothing exists yet.
   - `gap_filling` — audit-first; fill missing cells in an existing coverage matrix.
   - `mission_specific` — cover one feature or component, not the whole product surface.

   The mode drives every downstream decision. Do not change it silently mid-mission — a mode change is a re-scoping decision that needs an explicit note.

4. **State the documentation goals** in stakeholder-relevant terms — onboarding speed, support-ticket reduction, API discoverability, contributor ramp-up. Tie goals to a business or user outcome, not a page count.

5. **Surface format and tooling constraints early**: required generators (JSDoc / Sphinx / rustdoc), publishing platform (MkDocs, Docusaurus, Sphinx HTML), accessibility requirements (WCAG level), localization needs. A constraint invisible at discover time becomes a design surprise later — write it down now.

6. **Capture content constraints**: scope (which modules/features are in/out), depth (overview vs. exhaustive), and freshness (one-shot vs. living-documentation cadence).

7. **State what is explicitly in scope and out of scope** for this iteration. A documentation mission rarely covers an entire product surface in one pass; the scope sentence in `spec.md` is the contract for every later step.

8. **Record uncertainty as an explicit assumption**, not buried narrative prose. Assumptions are addressable later; narrative is not.

9. **Write success criteria** that are measurable (e.g., "every public function in module `foo` has a reference entry"), technology-agnostic at the outcome level (describe the user-visible outcome, not the generator invocation), and user-focused (passing means a target reader can accomplish the named task, not that a build succeeded).

## Success Criteria

- The documentation needs are stated in user-task or stakeholder-outcome terms — a reader can restate the goal without re-reading `spec.md`.
- The target audience is named and scoped; mixed-audience entries are explicitly flagged.
- Iteration mode is declared (`initial` | `gap_filling` | `mission_specific`) and matches the work the rest of the mission will do.
- Success criteria in `spec.md` are verifiable against the produced artifacts, not against process metadata.
- No `[NEEDS CLARIFICATION: ...]` markers remain unresolved in `spec.md`.

## Handoff

This step produces the documentation spec only. It does **not** audit existing coverage (that's the `audit` step), choose generators or design the navigation hierarchy (that's `design`), produce documentation content (`generate`), or validate/publish the output (`validate`/`publish`). If you find yourself specifying Sphinx extensions or drafting a page tree here, that work belongs to a later step — hand it off cleanly.
