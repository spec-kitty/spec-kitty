# Operator flags

Facts that could not be verified (kept on the page, not rewritten) and proposals that need an
operator ruling (profile additions or removals, template changes).

## Unverifiable facts

| # | WP | Page | Claim | What was found |
|---|---|---|---|---|
| U1 | WP02 | `team-kitty.md` | Zeitgeist runs "one container per team". | Hosted infrastructure; nothing in this repository or its history before #6164 states it. Kept. |
| U2 | WP02 | `team-kitty.md` | The removed code is preserved in `spec-kitty/event-router` (PR #45). | Stated in `CLAUDE.md` and the #6164 migration docstring; not checkable from this repository. Kept. |
| U3 | WP02 | ~~`execution.md` (Clarification Prompt)~~ **Resolved: corrected, corrections-log row 37.** | "Burst policy: cap to top 3 high-priority conflicts per prompt burst". | No such cap found in `src/glossary/` (`clarification.py`, `middleware.py`). Kept. |
| U4 | WP02 | ~~`execution.md` (GovernanceContext, InfraContext)~~ **Resolved: corrected, corrections-log row 38.** | Owned by a "Governance module" and an "Execution module". | No `GovernanceContext` or `InfraContext` type and no module of those names in `src/`; only the generated `.contextive/execution.yml` repeats them. Kept. |
| U5 | WP02/WP03 | ~~`identity.md`~~ **Resolved for `identity.md`: corrected, corrections-log row 35.** `identity-fields.md` remains for WP03 (W1). | `project_uuid` is "a SaaS-assigned identity" absent until a repository is bound. | `src/specify_cli/identity/project.py`: `ProjectIdentity.project_uuid` is generated locally (`generate_project_uuid`) and `spec-kitty init` writes it to `.kittify/config.yaml` `project.uuid` (`ensure_identity`). Possibly two different fields share the name. Left unchanged in `identity.md`; WP03 checks `identity-fields.md`. |
| U6 | WP02 | ~~`orchestration.md` (Decision)~~ **Resolved: pointer removed, corrections-log row 39.** | "See the SaaS domain glossary at `architecture/domain-glossary.md`." | No such file in this repository (living or archived); likely in the SaaS repository. Kept. |
| U7 | WP02 | `orchestration.md` (Routing) | Scope routing is one of the six live governed routing senses. | Its named owner (the hosted auth transport) was removed in #6164 and no other owner was found; whether the sense is still live needs a ruling. The owner was corrected, the count left at six. |
| U8 | WP02 (section-wide) | every glossary page | The `Applicable to` row (for example `` `1.x`, `2.x` `` on terms still used in 4.x). | `glossary-conventions.md` calls it "version scope" without saying whether it means "introduced in" or "still applies to"; 122 entries say `1.x`, `2.x`. Not changed; needs a convention ruling. WP03 found the same on 15 more pages and left them for the same ruling. |
| U9 | WP03 | `charter.md` (Ratchet Baseline) | "Org packs may declare additional ratchet metrics via governance policies, but cannot lower an existing shipped baseline." | No such mechanism found in `src/charter/` or `tests/architectural/`. Kept. |
| U10 | WP03 | `charter.md` (Cat-7 Grandfathered Orphan) | Cat-7 items are excluded from the ratchet failure count; "each cat-7 record must carry a deferral reason and a target WP". | The list is a frozenset of module names in `test_no_dead_modules.py`; no per-entry reason or WP field was found. Kept. |
| U11 | WP03 | `charter.md` (Catalog Miss) | Catalog misses are reported "by the `test_no_dead_symbols.py` gate when the referencing code reaches into the doctrine catalog". | `test_no_dead_symbols.py` checks unused symbols; no catalog-miss check found in it. Kept. |
| U12 | WP03 | `charter.md` (Three-layer DRG) vs code | The glossary expands DRG as "Doctrine Relationship Graph". | The code docstrings say "Doctrine Reference Graph" (eight places; one says Relationship). `charter-overview.md` now follows the code; `charter.md` keeps its wording pending a naming ruling. |
| U13 | WP03 | `governance-files.md` (Git Policy) | Recommends not committing `provenance/*`, `synthesis-manifest.yaml` and `.kittify/charter-packs/graph.yaml`. | This repository commits all three. The page now states the repository's practice, but whether the recommendation or the practice is right needs a ruling. Recommendation kept. |
| U14 | WP03 | identity-fields.md | Entries for mission 081 names keep `Status: canonical` though the names are not implemented and the 081 spec is Draft | Kept status (operator ruling needed); each entry now carries a "Code today" row |
| U15 | WP03 | `scripts/git-hooks/pre-commit-task-workflow.sh` | Exists; no doc names how it is installed | Page now describes what it does; installation not verified |
| U16 | WP03 | planning-and-tracking.md | Label and issue-type claims (priority:P0..P3, triage:*, usability, issue types) and the #1418 link (Priivacy-ai org) not verified against GitHub | Left as written; tracker state is outside the repository |
| U17 | WP03 | `charter.md`, `identity-fields.md`, `mission-types.md` | The documentation-curation audit flagged a mixed Divio type on these pages. | Judged false positives: the first two are glossary pages (term tables, kind Explanation); `mission-types.md` carries a short choose-a-type table and a verify block that serve its explanation. Not split. |

## Proposals for an operator ruling

| # | WP | Proposal | Why |
|---|---|---|---|
| P1 | WP01 | Add "Vocabulary" and "Questions this reader brings" sections to the persona template (`src/charter/offering/templates/architecture/stakeholder-persona-template.md`) and then to the ten profiles. | #7522 asks to check each profile's vocabulary and questions, but the template has no place for them; WP01 checked them inside Desiderata and Behavioral Cues instead of changing the canonical shape in ten copies. |
| P2 | WP01 | Decide whether `internal/spec-kitty-cli-runtime` and `internal/project-codebase` stay reader profiles. | 0 of 307 `audience:` values name either (gathered on this branch); they model system actors for architecture work, not readers. No change made (C-002). |
| P3 | WP01 | ~~Consider an end-user (operator running the CLI on their own project) reader profile distinct from the evaluators and `project-owner`.~~ **Accepted (operator ruling 2026-11-16): added as `external/practitioner` through the WP01 rework path, corrections-log rows 127 to 129. Retargeting the guides is #7523.** | `external/project-owner` is the reader of 61 pages under `docs/guides/` (gathered), including tutorials such as `tutorials/your-first-mission.md` and `tutorials/claude-code-workflow.md`, whose reader runs the CLI rather than setting project intent; no profile describes that reader. No change made (C-002). |
| P4 | WP03 | Decide whether the Spec Kit methodology essay, template-quality section and example articles in `spec-driven.md` are rewritten for Spec Kitty or moved to an explanation page. | The methodology essay, template-quality section and Nine Articles reproduce GitHub Spec Kit content, labelled now but not rewritten for Spec Kitty |
| P5 | WP03 | ~~Confirm the Mermaid metadata convention~~ **Answered (review cycle 1): the convention is doc-kitty's own `parseMeta` (leading, unindented `%% title:` / `%% description:`; doc-kitty injects `accTitle` / `accDescr`). Applied, corrections-log row 121.** | No longer a proposal. |

## Out-of-scope drift seen on the way

| # | Location | Finding | Evidence |
|---|---|---|---|
| O1 | `CLAUDE.md` (Team Kitty section) | Says "`spec-kitty charter sync` is unrelated (it syncs charter artifacts)". | Removed in #5828 (commit `0189965d78`); `spec-kitty charter --help` lists no `sync`. |
| O2 | DIRECTIVE_047, DIRECTIVE_042 and the `common-docs` styleguide (built-in pack, upstream) | All three describe `audience:` as a repo-relative `.md` path or path list. `common-docs` also still says each directory carries its own `index.md` (renamed to `README.md` by #6939). | The shipped schema is `[{profile, guidance_text}]` (#6929, `scripts/docs/audience_resolver.py`). Upstream fix in `spec-kitty-open-packs`. |
| O4 | `CLAUDE.md` (Terminology Canon, routing) | Lists scope routing among six governed routing decisions. | Its owner left with #6164 (see U7). |
| O5 | `src/specify_cli/.contextive/governance.yml`, `system-events.yml` | Stale against their source pages on `origin/main` (`scripts/generate_contextive_glossaries.py check`); nothing in CI runs the check. | WP02 regenerated only its own pages' files; these two are WP03's. |
| O6 | `CLAUDE.md` (Git Workflow) | Says `spec-kitty consolidate` "never publishes to the remote". | `spec-kitty consolidate --help` offers `--push`, which runs `git push origin <target branch>` (`src/specify_cli/consolidation/phase_finalize.py:50`); the default does not publish. |
| O7 | `src/specify_cli/tracker/local_service.py:73-80` (comments) | Cite `tracker/saas_client.py` and `egress.py` as live peers ("happens to hold the same text today", "Each transport passes its own identifier-set fragment"). | Both modules were deleted (#6164; the egress module on 2026-08-25, `522e462a6b`). Code comment drift; not edited. |
| O3 | `spec-kitty plan` (documentation missions) | Auto-writes `jsdoc`/`sphinx` generators and `iteration_mode: initial` into `meta.json` `documentation_state`, ignoring the spec. Corrected by hand. | `meta.json` diff in the design commit. |
| O8 | `src/specify_cli/identity/project.py` `derive_project_slug` docstring | Cites `zeitgeist_client/repo_identity.py`, a module removed in #6164 | Code comment drift; outside docs scope, not edited |
| O13 | `src/specify_cli/state/contract.py` (`dossier_parity_baseline` notes) | Says `dossier/drift_detector.py` was deleted in #274; the deleting commit `e7f777652b` cites issue #116. | `git show -s e7f777652b`; code comment, not edited |
| O9 | `src/specify_cli/invocation/executor.py` `complete_invocation` docstring | Says the completed record "is also submitted to the SaaS propagator"; the hosted surfaces were removed (#6164) | Code-comment drift; outside docs scope, not edited |
| O10 | Contextive check | No CI gate compares committed Contextive files with a fresh generation; this is how governance.yml and system-events.yml went stale (O5) | Docs now say so; a gate is a code change outside this docs Mission |
| O11 | `.kittify/traceability/contextive-map.yaml` header | Lists 11 slugs; 16 pages are glossary-shaped | Not edited (outside docs/context scope) |
| O12 | `.kittify/glossaries/planning-and-tracking.yaml` | The seed's `op` definition still names `ask` / `advise` / `do`; the page says the seed governs semantic-check resolution | Seed not edited (outside docs/context); page carries a Note |

## Notes for later work packages

| # | For | Note |
|---|---|---|
| W1 | ~~WP03 (`identity-fields.md`)~~ **Resolved: corrected in WP03, corrections-log row 58.** | The `project_uuid` entry says "Optional SaaS-assigned collaboration identity ... Never locally minted", and the page intro says it is "absent until a repository is explicitly bound". `src/specify_cli/identity/project.py` mints it locally at `spec-kitty init` (see corrections-log row 35). |
| W2 | ~~WP03 (`identity-fields.md`)~~ **Resolved: corrected in WP03, corrections-log row 59.** | `repository_label` is described as the field "called `project_slug` before mission 081", but no `repository_label` exists in `src/`, while `ProjectIdentity.project_slug` still does. `identity.md` links to that entry as a related term. |
| F1 | WP02 follow-up (page frozen after approval) | `execution.md` Clarification Prompt, Burst policy: the row could add that without a prompt function (the non-interactive path) every conflict is deferred and a `GlossaryClarificationRequested` event is emitted (`src/glossary/clarification.py`, `prompt_fn` docstring: "If None, all conflicts are deferred"). Reviewer advisory, cycle 2. |
| F2 | WP03 follow-up (page frozen after approval) | `planning-and-tracking.md:116`: the lead-in "Deferred (FR-011, tracked as [#1418])" still says #1418 tracks the deferral, while the paragraph under it says #1418 closed without adding the scope. Fix the lead-in in a follow-up; listed as a known follow-up in the PR body. |
| F3 | WP01 follow-up (pages frozen after approval) | `audience/README.md` and `audience/external/README.md`: the scopes of `external/project-owner` (getting-started pages and governance defaults) and `external/practitioner` (tutorials and task how-tos) overlap on getting-started pages. Settle which reader a getting-started page names, together with #7523. |
| F4 | WP02 follow-up (page frozen after approval) | `identity.md` External Audience Persona entry defines external readers as evaluators and decision-makers, which does not cover `external/practitioner` (someone who runs the CLI). Widen the definition in a follow-up. |
