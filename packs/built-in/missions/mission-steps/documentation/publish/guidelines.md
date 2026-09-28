# Publish Action — Governance Guidelines

These guidelines govern the release-readiness and handoff standards for the **publish** phase of a documentation mission. The deliverable is `release.md` — the canonical publication-handoff artifact recording what shipped, where it shipped, and what the post-publish living-documentation expectations are. Publish is the boundary between "content produced" and "content read by users".

---

## Core Authorship Focus

- Publish only what `audit-report.md` has marked **ready-to-publish**. The validate verdict is the gate; bypassing it is a process failure.
- Confirm release readiness explicitly: build succeeds in the publication target environment, link checks pass, generator output is current, search index is rebuilt.
- Coordinate **deployment handoff** with the operator who owns the publication target — docs site, package registry, internal portal. A handoff without an acknowledged owner is not a handoff.
- Author `release.md` as the **publication-handoff artifact**: it cites the published URLs, the generator versions, the source revision, the validate verdict, and the post-publish maintenance expectations.

---

## Release-Readiness Checks

- **Build verification** — the documentation builds cleanly in the target environment with the recorded generator and theme versions. A green local build that fails in CI is a release blocker.
- **Link integrity at the publication target** — internal links resolve under the deployed URL structure (which may differ from local). External links return non-error status codes.
- **Search and navigation** — the site index, search backend, and top-level navigation reflect the new content; stale TOC entries are removed.
- **Asset hygiene** — images, code samples, downloadable artifacts are present at their referenced paths under the deployed root.
- **Versioning** — for versioned doc sites, the new content lands under the right version label and the latest pointer (if any) updates correctly.

---

## release.md as Publication-Handoff

- `release.md` is the **canonical handoff artifact**. It is written for the operator who will receive support questions and for the next mission that will iterate on these docs.
- The artifact records: what shipped (page paths, area), where it shipped (URLs), the validate verdict reference, the source revision, the generator versions, and any caveats from the validate report that were accepted rather than fixed.
- The artifact records the **living-documentation cadence**: which pages need re-validation when the underlying surface changes, who owns the re-validation, and how the next gap-filling iteration is triggered.
- Future missions read `release.md` to know the prior baseline; an empty or boilerplate file makes the next iteration start from zero.

---

## Post-Publish Living-Documentation Sync

- Reference content tied to a code surface is subject to **DIRECTIVE_037** (Living Documentation Sync), the single owner of the same-change documentation-update rule; when the update cannot land in the same change, queue it as an explicit gap for the next cycle.
- How-tos and tutorials enter a **periodic-revalidation contract**: the cadence is recorded in `release.md`. Stale tutorials are worse than missing tutorials.
- Explanations are revisited when the underlying architecture changes; the design ADRs from this mission are the source for "what changed" comparisons.
- Surface any unresolved drift to the next iteration's discover and audit phases. The post-publish state is the next mission's input.

---

## What This Phase Does NOT Cover

The publish action releases validated content and records the handoff. It does **not**:

- Reopen scope, audience, mode, audit findings, or design decisions.
- Author new content (that is the generate action's job, and a re-publish requires re-validation first).
- Re-run quality gates (that is the validate action's job).
- Plan the next documentation mission (that is the next discover's job, informed by this `release.md`).

A publish step that introduces edits beyond release-mechanics fixes is leaking generate work. If new content is needed, the validate verdict was wrong; cycle back.

---

## Quality Gates

- `audit-report.md` verdict is `ready-to-publish` and the cited evidence is current.
- `release.md` exists, names the published URLs, the source revision, and the living-documentation cadence.
- Build, link, and search checks pass in the publication target environment.
- Living-documentation expectations are explicit, owned, and aligned with the discover spec for the next iteration.
