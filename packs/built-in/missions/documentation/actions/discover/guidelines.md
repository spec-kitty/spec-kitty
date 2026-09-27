# Discover Action — Governance Guidelines

These guidelines govern the quality and authorship standards for the **discover** phase of a documentation mission. The deliverable of this phase is a documentation specification that frames the documentation needs, identifies the target audience, declares the iteration mode, and states the goals — before any audit, architecture design, or content generation begins.

---

## Core Authorship Focus

- Identify the **documentation needs** explicitly. What questions must the documentation answer? What user tasks must it enable? Vague needs ("better docs") produce vague deliverables.
- Name the **target audience** by role and skill level — beginner end-users, working developers, integrators, operators, contributors. Each audience implies a different Divio type mix.
- Declare the **iteration mode** up front: `initial` (greenfield documentation suite), `gap_filling` (audit-first, fill missing cells), or `mission_specific` (one feature or component). The mode drives every downstream decision.
- State the **documentation goals** in stakeholder-relevant terms — onboarding speed, support-ticket reduction, API discoverability, contributor ramp-up. Goals tie the documentation to a business or user outcome, not a page count.

---

## Stakeholders and Constraints

- Identify the **readers** for each Divio type: tutorials serve beginners, how-tos serve task-driven users, reference serves working developers, explanations serve architects and decision-makers. A spec that conflates audiences produces docs that serve none of them well.
- Surface **format and tooling constraints** early: required generators (JSDoc / Sphinx / rustdoc), publishing platform (MkDocs, Docusaurus, Sphinx HTML), accessibility requirements (WCAG level), localization needs.
- Capture **content constraints** that bound the work: scope (which modules / features are in / out), depth (overview vs. exhaustive), and freshness (one-shot vs. living-documentation cadence).
- A constraint that is invisible at discover time becomes a design surprise later. Write them down.

---

## Scoping Discipline

- State **what is in scope** and **what is explicitly out of scope** for this iteration. A documentation mission rarely covers an entire product surface in one pass; the scope sentence is the contract.
- Document the iteration mode upfront and never silently change it mid-mission. Changing modes is a re-scoping decision that demands an explicit ADR-style note.
- Where uncertainty exists, capture it as an explicit assumption rather than burying it in narrative prose. Assumptions are addressable; narrative is not.

---

## Success Criteria Standards

Success criteria for a documentation mission must be:

1. **Measurable** — e.g., "every public function in module `foo` has a reference entry", "tutorial walks an unfamiliar user from install to first request in under fifteen minutes".
2. **Technology-agnostic at the outcome level** — the criterion describes the user-visible outcome, not the generator invocation.
3. **User-focused** — passing means a target reader can accomplish the named task, not that a build succeeded.

---

## What This Phase Does NOT Cover

The discover action produces the documentation spec — needs, audience, mode, goals, constraints, and success criteria. It does **not**:

- Audit existing coverage (that is the audit action's job).
- Choose generators or design the navigation hierarchy (that is the design action's job).
- Produce documentation content (that is the generate action's job).
- Validate or publish the output (those are the validate and publish actions' jobs).

If a discover deliverable starts specifying Sphinx extensions or page-tree shape, that work belongs to a later phase. Hand off cleanly.

---

## Quality Gates

- The documentation needs are stated in user-task or stakeholder-outcome terms — a reader can restate the goal without re-reading the spec.
- The target audience is named and scoped; mixed-audience entries are explicitly flagged.
- Iteration mode is declared and matches the work the rest of the mission will do.
- Success criteria are verifiable against the produced artifacts, not against process metadata.
