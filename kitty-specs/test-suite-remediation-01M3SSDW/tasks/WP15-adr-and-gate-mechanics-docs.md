---
work_package_id: WP15
title: ADR and gate-mechanics docs
dependencies:
- WP13
- WP14
requirement_refs:
- FR-009
- FR-011
- NFR-005
- C-001
- C-006
- C-008
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 31abd2300e73dafc0d287d1dd24e1b8a2c6f5d55
created_at: '2026-09-30T23:45:41.852530+00:00'
subtasks:
- T070
- T071
- T072
- T073
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-01-1-dead-symbol-allowlist-module-name-identity.md
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- docs/adr/4.x/*-dead-symbol-allowlist-module-name-identity.md
- docs/adr/4.x/index.md
- docs/development/reference/ci-gate-mechanics.md
- docs/development/how-to/add-architectural-gate-exemption.md
- docs/development/3-2-page-inventory.yaml
- docs/development/3-2-docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – ADR and gate-mechanics docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- **Governance: a major architectural change needs an ADR (charter).** Write **one** ADR in `docs/adr/4.x/`, the folder where new ADRs land (see `docs/adr/4.x/index.md`). Suggested title: *"Dead-symbol allowlist identity is `(module, name)`; body hashes are runtime-only."* The ADR must:
  - **partially supersede** D-1 of `relocation-hardened-dead-code-scanners-01KX958P` (persisted identity only), `frozen-baseline-toll-reduction-01M0A42D` FR-001/FR-002 (the refresh helper), and #3552 FR-006/FR-007 (the `source_module` guards);
  - **relate** to ADR `docs/adr/3.x/2026-09-14-1-census-floor-ratchet-adjudication.md`, the precedent for adjudicating toll ratchets per ratchet, which is also why no census gate is added (C-008).
- **Correct the stale guidance at its live source (C-006)**: `docs/development/reference/ci-gate-mechanics.md`, section "### Renaming a symbol whose body is allowlisted" (`~:186-192`). It tells readers to run the retired hash-refresh tool.
- **Register the ADR and regenerate the docs indexes**, so the docs-freshness gate stays green: the ADR index row, the page inventory lockfile and the docs retrieval index. This WP owns every `docs/` edit in the mission, so the regenerated indexes have one owner.
- **CHANGELOG is not edited** (the orchestrator writes it at closeout).
- **NFR-005**: the terminology guard is green, and new prose says **Mission**, never "feature".

## Context & Constraints

- Read first:
  - `research/dead-symbol-rekey.md` §4 (the ADR content list: context, decision, consequences, supersedes, non-goals, related) and §2 (the numbers);
  - `research.md` D-10–D-13;
  - `plan.md` IC-12 and the Charter Check row "Governance → major architectural change needs an ADR";
  - `contracts/dead-symbol-allowlist.md` §0 (the non-goals);
  - the **landed** code from WP11–WP14, so the ADR describes facts, not intentions.
- The **template** is `docs/architecture/adr-template.md`. For frontmatter and section style, use `docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md` as an **example of shape only**: `title`, `description`, `status: Accepted`, `date`, `updated`, then **Status / Date / Deciders / Technical Story**. Do not copy its content.
- **Naming**: `YYYY-MM-DD-N-descriptive-title-with-dashes.md`, where the date is the **landing date** and `N` is the per-date counter. `owned_files` uses a date-agnostic glob; `create_intent` names the expected default (`2026-10-01-1-…`). If you land on another date, use that date; the glob still covers it. The `create_intent` literal is only a planned default, so a non-matching literal is harmless (analysis F4).
- **Tooling** (run from the repository root, so `scripts` resolves as a package):
  - `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<adr>.md` adds the index row and refreshes the inventory lockfile (per `docs/adr/4.x/index.md`);
  - `PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write` regenerates `docs/development/3-2-docs-retrieval-index.yaml`, which picks up the new headings;
  - `PYTHONPATH=. .venv/bin/python scripts/docs/inventory_lockfile.py --write docs/development/3-2-page-inventory.yaml`;
  - `PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci`.
- `docs/adr/3.x/*` and archived `kitty-specs/*` are **immutable**. Do not edit ADR 2026-09-14-1 or the older missions' specs; the new ADR references them.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`. This WP depends on WP13 and WP14, the last WPs of the dead-symbol chain. Start with:

```bash
spec-kitty agent action implement WP15 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the named docs tests plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **No code changes.** Run `git diff --stat src/ tests/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Evidence.** Write the evidence record (the commands you ran and their outputs) into a scratchpad file outside the repository, never under `kitty-specs/`. Paste it into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include it verbatim in your final report.
4. **Terminology.** Say Mission, never feature. Qualify "primary", "merge" and "routing" when used (Terminology Canon). The canonical "status commit" term applies if the status layer is mentioned.
5. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-opus-5-5`.
6. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits.

### Additional mission-wide rules (analysis folds)

- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.

## Subtasks & Detailed Guidance

### Subtask T070 – Author the ADR

- **Purpose**: A durable record of why the persisted identity changed and what was deliberately given up, so nobody re-adds hashes or a refresh helper.
- **Files**: `docs/adr/4.x/<date>-1-dead-symbol-allowlist-module-name-identity.md` (new).
- **Content** (research §4, verified against the landed code):
  1. **Frontmatter**:
     - `title: 'ADR: dead-symbol allowlist identity is (module, name)'`;
     - `description` (one sentence, within the house description length; `scripts/docs/description_length_check.py` exists);
     - `status: Accepted`, `date`, `updated`;
     - a `type` / `audience` if the 4.x index frontmatter pattern requires one; mirror `docs/adr/4.x/index.md`'s keys.
  2. **Status / Date / Deciders / Technical Story**:
     - the deciders are the operator and the orchestrator rulings (decisions `DM-01M3SSRY`, `DM-01M3SVDP` and the plan rulings R2 and RK-4/RK-6);
     - the technical story is #5346 under #5353, and Mission `test-suite-remediation-01M3SSDW`.
  3. **Context**:
     - D-1 (persisted content-tier body hash for relocation tolerance) and the `01M0A42D` refresh helper;
     - the toll: 57 body-edit re-pins in 41 of 78 allowlist commits since 2026-08-18, 25 of which did nothing else, and 0 sampled re-pins that changed a rationale;
     - relocation-proofness forfeited in practice by the #3552 `source_module` guard, so a move already cost one edit per entry;
     - the formatter-induced re-pin `2641f6b181`.
  4. **Decision**:
     - identity is `(module, name)`, where `module` is the `__all__`-declaring module;
     - the data lives in `tests/architectural/dead_symbol_allowlist.yaml`, under a schema-enforcing loader (L1–L10);
     - the #470 widened list is folded in;
     - body hashes are **never persisted**: runtime-only for keyability (INVALID) and auto-exempt condition (1);
     - the stale verdicts are INVALID, GONE, REVIVED, SUPERSEDED and MOOT;
     - the refresh helper is retired;
     - the size-ratchet rows `allowlist_entries` and `widened_grandfathered_470` are added (Burn-down (a));
     - the category ids are the old constant names, lower-cased (`category_*`).
  5. **Consequences, positive**:
     - a body edit costs 0 edits (SC-003);
     - collision escalation and its 18 module_path-tier entries are gone;
     - intra-category duplicates are detectable (the `check_push_safety` ×2 case);
     - the gate file stops co-changing with `src/` for data reasons;
     - Burn-down (a) is honoured.
  6. **Consequences, negative and accepted**:
     - a move or rename costs one YAML edit (the same as before, now explicit and hinted: "probably moved to …");
     - `bite_b`, `bite_g`'s body-edit arm and `bite_j`'s relocation arm are retired or inverted (M1/M7/M8 replace them);
     - `SymbolKey.source_module` and its G1–G6 guards are deleted;
     - MOOT is stricter than before.
  7. **Supersedes (partially)**: D-1 of `relocation-hardened-dead-code-scanners-01KX958P` (persisted identity only); `frozen-baseline-toll-reduction-01M0A42D` FR-001/FR-002; #3552 FR-006/FR-007; and `01M0A42D` **FR-005**, whose "re-adding an inert `test_no_dead_symbols` key is rejected" re-entry guarantee is subsumed by the row↔leaf bijection (WP14 re-planted the planted-leaf test onto a never-enforced section) (F-14).
  8. **Non-goals**: the caller detectors; the #470 widened scope; removing auto-exempt condition (1), which is a follow-up; renaming `test_no_dead_symbols.py` (the C-007 canon); a census gate (C-008).
  9. **Related**: ADR 2026-09-14-1 (census and floor ratchet adjudication).
  10. **Evidence pointer**: the parity result (293 / 91, identical digest), phrased as a fact with the numbers. Do not link to `kitty-specs/…/evidence/` paths unless the orchestrator confirms they exist at closeout.
- **Edge cases**: Keep the prose factual and short. Every claim must be checkable against the code or git history cited.

### Subtask T071 – Rewrite the "Renaming a symbol…" section of `ci-gate-mechanics.md`

- **Files**: `docs/development/reference/ci-gate-mechanics.md`.
- **Anchor**: the section "### Renaming a symbol whose body is allowlisted" (`~:186-192`).
- **Steps**:
  1. Replace it with the new mechanics, for example under the heading "### Moving or renaming a symbol that is dead-symbol allowlisted":
     - **editing a body** costs nothing;
     - **renaming or moving** an allowlisted symbol makes the gate report the old entry `GONE`, with a "probably moved to `X`" hint, and the new location as an offender; update `module:` / `name:` in `tests/architectural/dead_symbol_allowlist.yaml`;
     - **adding an entry** needs a category, a rationale, an issue where the category requires one, and a raised `_baselines.yaml` leaf (the shrink-only cap);
     - **never** weaken the gate.

     Link the ADR.
  2. Bump the frontmatter `updated:` to the landing date if the freshness gate expects it.
  3. Do not touch other sections.
  4. **Canonical exemption how-to (F-13, DIRECTIVE_044)**: in `docs/development/how-to/add-architectural-gate-exemption.md`, §1 lists only "hand-curated" and "census" allowlist kinds.
     - Add the third kind, the dead-symbol YAML (`(module, name)` + category + rationale + issue where required + a `_baselines.yaml` leaf bump), as one row in §1 plus a short "2c. Dead-symbol gate: add a YAML entry" section.
     - Link the ADR and `ci-gate-mechanics.md`.
     - Bump `updated:` if the freshness gate expects it.
- **Parallel?**: Yes, alongside T070.

### Subtask T072 – Register the ADR

- **Steps**:
  1. `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<adr>.md`. This is the **first** ADR in `docs/adr/4.x/`, so check that the freshener inserts its row correctly into the **empty** index table (header plus separator only). This inserts the index row `| YYYY-MM-DD | [Title](file.md) |` into `docs/adr/4.x/index.md` and refreshes `docs/development/3-2-page-inventory.yaml`.
  2. `python -m scripts.docs.freshen_adr_inventory --check docs/adr/4.x/<adr>.md` must be clean.
  3. Review the diff of `docs/adr/4.x/index.md`: exactly one new row, and `updated:` bumped if the tool does that.

### Subtask T073 – Regenerate the docs indexes; run the named checks; hand off

- **Steps**:
  1. Regenerate:
     ```bash
     PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write
     PYTHONPATH=. .venv/bin/python scripts/docs/inventory_lockfile.py --write docs/development/3-2-page-inventory.yaml
     PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
     ```
     The freshness check must pass. If `inventory_lockfile.py --write` refuses a `docs/` target (its help text says "never docs/"), rely on `freshen_adr_inventory` for the lockfile, record the refusal, and re-run the freshness check.
  2. Named docs tests:
     ```bash
     uv run --frozen pytest tests/docs/test_freshen_adr_inventory.py tests/docs/test_inventory_lockfile.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index_freshness.py tests/architectural/test_no_legacy_terminology.py -n0 -q
     ```
  3. `git diff --stat` shows only the six owned paths.
  4. `make test-fast` once.
  5. **Evidence**: the commands and their outputs; the ADR path; the index row.

## Test Strategy

```bash
uv run --frozen pytest tests/docs/test_freshen_adr_inventory.py tests/docs/test_inventory_lockfile.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index_freshness.py tests/architectural/test_no_legacy_terminology.py -n0 -q
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
make test-fast
```

## Risks & Mitigations

- **Docs-index drift from another WP's docs edit.** No other WP touches `docs/`, and this WP runs last in the chain. If the base has moved, regenerate after rebasing.
- **ADR claims that drift from the landed code.** Write the ADR after reading WP11–WP14's diffs, and cite the numbers from the parity evidence.
- **The date in the filename.** Use the landing date; the glob ownership covers it.

## Definition of Done (C-011)

- **C-011 (docs-only WP; D1 reading)**: prose has no failing test of its own. The verifiable red→green is the docs gate: `scripts/docs/check_docs_freshness.py --ci` (and `tests/docs/test_freshen_adr_inventory.py`) are RED with the ADR file present but unregistered, and GREEN after T072/T073. Record both runs.

## Review Guidance

- The ADR states "partially supersedes D-1 of `relocation-hardened-dead-code-scanners-01KX958P`" and relates to ADR 2026-09-14-1 (quickstart FR-009 "ADR" check).
- The ADR is listed in `docs/adr/4.x/index.md`, and `check_docs_freshness.py --ci` passes.
- `ci-gate-mechanics.md` no longer mentions the hash-refresh tool.
- There are no `src/` or `tests/` changes and no CHANGELOG edit.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-opus-5-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T070 T071 T072 T073 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP15 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence record>"
```
