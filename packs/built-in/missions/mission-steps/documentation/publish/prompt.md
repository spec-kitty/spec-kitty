---
description: Publish validated documentation and record the release handoff
---
# /spec-kitty.publish - Publish Documentation

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/release.md`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`.

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

## What This Step Produces

- **`kitty-specs/<mission>/release.md`** — the canonical publication-handoff artifact recording what shipped, where it shipped, and the post-publish living-documentation expectations.

This step is the boundary between "content produced" and "content read by users."

## Goal

Publish only what `audit-report.md` marked `ready-to-publish`, and record a handoff a future author and a support-facing operator can both act on.

## What to Do

1. **Publish only what the `validate` verdict cleared.** `audit-report.md`'s verdict is the gate; bypassing it is a process failure, not a shortcut.

2. **Confirm release readiness explicitly**:
   - **Build verification** — the documentation builds cleanly in the target environment with the recorded generator and theme versions. A green local build that fails in CI is a release blocker.
   - **Link integrity at the publication target** — internal links resolve under the deployed URL structure (which may differ from local); external links return non-error status codes.
   - **Search and navigation** — the site index, search backend, and top-level navigation reflect the new content; remove stale table-of-contents entries.
   - **Asset hygiene** — images, code samples, downloadable artifacts are present at their referenced paths under the deployed root.
   - **Versioning** — for versioned doc sites, the new content lands under the right version label and the latest pointer (if any) updates correctly.

3. **Coordinate deployment handoff** with the operator who owns the publication target (docs site, package registry, internal portal). A handoff without an acknowledged owner is not a handoff.

4. **Author `release.md` as the publication-handoff artifact.** Record: what shipped (page paths, area), where it shipped (URLs), the `audit-report.md` verdict reference, the source revision, the generator versions, and any caveats accepted during validate rather than fixed. Write it for the operator who will field support questions and for the next mission that will iterate on these docs — an empty or boilerplate `release.md` makes the next iteration start from zero.

5. **Record the living-documentation cadence.** Reference content tied to a code surface is subject to DIRECTIVE_037 (Living Documentation Sync), the single owner of the same-change documentation-update rule; when the update cannot land in the same change, queue it as an explicit gap for the next cycle. How-tos and tutorials enter a periodic-revalidation contract — record the cadence; stale tutorials are worse than missing tutorials. Explanations are revisited when the underlying architecture changes.

6. **Surface unresolved drift to the next iteration.** Anything left open feeds the next mission's `discover` and `audit` steps as their starting input.

## Success Criteria

- `audit-report.md`'s verdict is `ready-to-publish` and the cited evidence is current.
- `release.md` exists, names the published URLs (or exact publication target), the source revision, and the living-documentation cadence.
- Build, link, and search checks pass in the publication target environment.
- Living-documentation expectations are explicit, owned, and aligned with the discover spec for the next iteration.

## Handoff

This step releases validated content and records the handoff only. It does **not** reopen scope, audience, mode, audit findings, or design decisions, author new content (`generate`'s job — a re-publish requires re-validation first), re-run quality gates (`validate`'s job), or plan the next documentation mission (the next iteration's `discover`, informed by this `release.md`). A publish step that introduces edits beyond release-mechanics fixes is leaking `generate` work — if new content is needed, the validate verdict was wrong; cycle back.
