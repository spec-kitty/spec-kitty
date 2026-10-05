---
work_package_id: WP04
title: ADR, org-pack how-to and changelog
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-011
- C-007
planning_base_branch: issue-replaceable-builtins-sanction
merge_target_branch: issue-replaceable-builtins-sanction
branch_strategy: Planning artifacts for this mission were generated on issue-replaceable-builtins-sanction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-replaceable-builtins-sanction unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
history: []
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-05-1-org-packs-ship-their-builtin-override-sanction.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-05-1-org-packs-ship-their-builtin-override-sanction.md
- docs/adr/4.x/index.md
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/changelog/CHANGELOG.md
- docs/development/docs-retrieval-index.yaml
role: implementer
tags: []
tracker_refs: []
---

# WP04: ADR, org-pack how-to and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP04 --agent claude`

## Objective

Document the pack-root built-in override sanction. Write an ADR that records the decision and its #2594 absorption path, add an org-pack author how-to section (with migration and troubleshooting), and add a user-facing `[Unreleased]` changelog entry. Then regenerate the docs retrieval index.

## Context

- **Read first:**
  - `spec.md`: the decision table, FRs, Assumptions and Out of Scope.
  - `research.md` D1–D8.
  - `contracts/*.md`.
  - `research/code-grounding.md`.
- **Audience:**
  - For the ADR: maintainers and the #2216/#2594 implementers.
  - For the how-to: org-pack authors and consumer operators (DIRECTIVE_047).
- **Style:**
  - Follow the structure of existing ADRs: frontmatter with `updated:` and Divio type. Use a recent `docs/adr/4.x/2026-10-04-*.md` file as the shape reference.
  - Terminology: "Mission"; "org pack" and "pack root". Avoid new "doctrine pack" prose (#3732).

### Subtask T015: ADR `docs/adr/4.x/2026-10-05-1-org-packs-ship-their-builtin-override-sanction.md`
- **Context:** the drift problem (#5767), the rc3 promotion, and the template convention that nothing reads.
- **Decision:** a pack-root `replaceable-builtins.yaml`, read in place by `doctor doctrine` through one loader in `charter.offering.drg.override_policy`. It is scoped to the contributing pack by registry name, unioned with the consumer allowlist (checked first), and revocable per URN or per pack. Include the decision table.
- **Alternatives:**
  - (b) a fetch-time copy;
  - (c) a per-node `replaces:`;
  - an `org-charter.yaml` key, rejected for the `extra="forbid"` forward-compatibility reason.
- **Consequences:**
  - pack validate and assemble support the file;
  - API-source limitation;
  - integrity is checked at fetch, not by doctor;
  - the legacy-template hint is transitional and is removed with #2594;
  - per-URN or per-pack revocation;
  - out of scope: #5769, #5770.
- **#2594 absorption:** the pack sanction becomes "the pack's declared overlay intent" and the revocation becomes "consumer narrowing of a delegated sanction", the consumer-side counterpart of `governed`/`locked`. Follow-up: make `OrgCharterPolicy` tolerant of unknown keys when the schema version is newer.
- Cross-link ADR `2026-05-16-1` and mission `doctrine-governance-fidelity-01KW42KY` (NFR-004 fail-closed; FR-012 project tier).
- Add the ADR to `docs/adr/4.x/index.md`, matching the existing entry format.

### Subtask T016: How-to `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`
- Add a section, for example "Step 3b: Sanction the built-ins your pack replaces". It covers:
  - the file location and grammar;
  - the rule that a directive needs a reason;
  - scoping (the sanction covers only your own pack's overrides);
  - validating with `spec-kitty doctrine pack validate`;
  - how assembly unions sanctions;
  - migration: move `templates/setup/replaceable-builtins.yaml` to the pack root.
- In Step 8 "Configure consumers", explain that consumers no longer copy the allowlist, how to see the sanctioned list (`doctor doctrine`), and how to revoke with `revoked_pack_sanctions`.
- Add a Troubleshooting entry: "Unsanctioned built-in override(s)", with the remedies in order: pack-root file, then the consumer entry.
- Bump the page's `updated:` frontmatter to 2026-10-05.

### Subtask T017: Changelog `docs/changelog/CHANGELOG.md` `[Unreleased]`
- Write a bold, impact-first lead with `(#5767)`, then the before and after.
- Before: every built-in promotion broke consumers whose hand-copied allowlist was stale, so `doctor doctrine` returned RC=1.
- After: org packs ship `replaceable-builtins.yaml` at the pack root, `doctor doctrine` honours it scoped to that pack, the output lists sanction sources, consumers can revoke, and pack validate and assemble support the file.
- Add a pack-author action line: move the template to the pack root (the *resolved* pack root, including any configured `subdir`).
- Add a behaviour-change line: a malformed consumer allowlist, or a `revoked_pack_sanctions` entry naming an unconfigured pack, now makes `doctor doctrine` unhealthy even when no org override exists.
- Put it in the right `[Unreleased]` subsection (Fixed, or Added if that is the convention; check the file).

### Subtask T018: Docs index and gates
- Run `python scripts/docs/docs_index.py --write` and commit `docs/development/docs-retrieval-index.yaml`.
- `python scripts/docs/check_docs_freshness.py --ci` reports `errors=0`.
- `pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_docs_structural_lint.py tests/docs/test_unreleased_section.py` passes, and `make docs-lint` passes. These cover the #5426 changelog-shape and spelling guard that CI runs on every change.

## Definition of Done
- T015–T018 are recorded with `mark-status`, and the gates above are green.
- The commit carries the `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` trailer.
- No AI model names anywhere.

## Risks
- **Docs describe behaviour that has not shipped yet.** Mirror the WP01/WP02 semantics exactly. The reviewer cross-checks the docs against the code after WP02 merges.
- **Changelog union conflicts at rebase.** Keep the entry self-contained.

## Reviewer Guidance
- Check accuracy against the code, especially the decision table and the revocation grammar.
- Check the audience and Divio type.
- Confirm the docs never suggest a whole-file copy.
