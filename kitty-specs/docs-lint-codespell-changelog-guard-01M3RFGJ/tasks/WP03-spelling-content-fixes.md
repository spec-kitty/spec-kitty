---
work_package_id: WP03
title: Content fixes and the live-tree spelling gate
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-006
- FR-007
- SC-001
- C-006
planning_base_branch: issue-5426-docs-lint
merge_target_branch: issue-5426-docs-lint
branch_strategy: Planning artifacts for this mission were generated on issue-5426-docs-lint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5426-docs-lint unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-docs-lint-codespell-changelog-guard-01M3RFGJ
base_commit: 929d9daba4f40b49b1ca5c73a2daa0dfe8ae069d
created_at: '2026-09-30T08:26:51.054880+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Spelling
history:
- at: '2026-09-30T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- tests/docs/test_docs_spelling_live.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/docs/test_docs_spelling_live.py
- docs/guides/**
- docs/context/**
- docs/adr/3.x/2026-07-22-1-gate-binding-content-vs-relationship.md
- docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
- src/specify_cli/.contextive/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Content fixes and the live-tree spelling gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Load it through the CLI (`spec-kitty agent profile show python-pedro`); do not just adopt the persona name.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log and the Activity Log. Address every item.

---

## Objectives & Success Criteria

Make the real tree clean under all three spelling passes without weakening the dictionary (issue #5426: "the known real typos are fixed"). It is done when:

1. `tests/docs/test_docs_spelling_live.py` exists. It was **committed red first** (before any content fix) and is green at the end. It runs the production entry point for each pass on the real repo and asserts zero findings.
2. The 2 ADR typos are fixed. WP01 already fixed the 2 changelog typos.
3. Every UK-spelling hit in `docs/guides/` and `docs/context/` is either respelled in prose, or, if it is a quoted literal (CLI output, config key, status value, canonical identifier), wrapped in a code span. **Never** add a UK word to an ignore list.
4. The three glossary headings are renamed to US spelling with legacy anchors (operator decision `01M3RFQ90SJVVDQ7C4AV6W13FM`). In-page links move to the new slug, and "communication artefact" is kept as an alias.
5. The contextive YAML and the docs retrieval index are regenerated. `check_docs_freshness.py --ci` shows no new errors from this WP, and the terminology guard is green.

Requirements: FR-003, FR-006, FR-007, SC-001, C-006.

## Context & Constraints

- Read: `spec.md` (FR-006, FR-007 and the edge cases), `research.md` (R-3, R-7), `plan.md` (IC-03).
- WP02 has landed `python -m scripts.docs.check_spelling`. Use `--pass typo`, `--pass us` and `--pass unreleased` to get the live list; do not work from this prompt's snapshot alone.
- **Never modify** `kitty-specs/`, `kitty-ops/` or `docs/archive/` (archive-freeze gate), even though old missions link to `#organisation-tier`. The legacy anchor exists for exactly those links.
- Out-of-map edit, allowed and recorded: `docs/development/3-2-docs-retrieval-index.yaml` is owned by WP05, but WP03's heading renames change it. Regenerate it here (T020) and record a one-line rationale in the Activity Log. WP05 regenerates it again afterwards, and the dependency chain makes that sequential.
- Terminology canon: do not introduce "feature" wording.

## Branch Strategy

- **Planning base branch**: `issue-5426-docs-lint` · **Merge target branch**: `issue-5426-docs-lint`
- Run `spec-kitty implement WP03` and work in the lane workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T015 – Live-tree test, red first

- Create `tests/docs/test_docs_spelling_live.py` (`pytestmark = [pytest.mark.unit, pytest.mark.fast]`) with three tests: `test_typo_pass_clean`, `test_us_pass_clean` and `test_unreleased_us_pass_clean`. Each calls `scripts.docs.check_spelling.run_pass(...)` (or `main`) against the real repo root, asserts **zero findings AND a scanned floor**, and on failure prints the findings in the assertion message. The floors, measured on the base, are: typo ≥ 600 files; US ≥ the current `docs/guides` + `docs/context` `*.md` count minus a small margin (record the measured count); Unreleased section found and ≥ 200 lines. A pass that silently scans nothing must go red.
- Add one subprocess test, `python -m scripts.docs.check_spelling` (all passes) → returncode 0. This is the production path CI runs.
- **Commit this test alone first** and confirm it is red. At this point `--pass typo` reports `migrateable` and `re-using`, and `--pass us` reports about 60 hits. The Unreleased pass is already clean (0 hits); its floor assertion is its non-vacuity. Paste the red counts into the Activity Log.

### Subtask T016 – ADR typos

- `docs/adr/3.x/2026-07-22-1-gate-binding-content-vs-relationship.md:76`: `migrateable` → `migratable`.
- `docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md:109`: `re-using` → `reusing`.
- Touch nothing else in those ADRs. They are accepted records; this is a typo-only change.

### Subtask T017 – US prose fixes (guides + context)

The snapshot from grounding (re-derive with `--pass us`):

- **`docs/context/charter.md`** (6 `#organisation-tier` links, not 7):
  - lines 31, 318, 322, 423, 435, 447: catalogue → catalog, artefact(s) → artifact(s);
  - Organisation occurrences at 326, 415, 584, 596, 668, 704 (612 is T018).
- **`docs/context/execution.md`**: 231 (artefact → artifact). Line 237 is the link `[communication artefact](#communication-artefact)`; move both the text and the slug to `[communication artifact](#communication-artifact)`. Line 242 is T018.
- **`docs/context/identity.md:153`**: judgement → judgment.
- **`docs/context/orchestration.md`**: 412 artefact; 624 Modelled → Modeled; 629 behaviour.
- **`docs/context/planning-and-tracking.md:59`**: favour → favor.
- **`docs/context/testing-taxonomy.md`**: behaviour/behavioural/Behavioural (×9), serialised, sanitisation, characterisation (×2), normalise.
- **`docs/context/topology.md:45`**: generalises → generalizes.
- **`dialogue`** at `docs/context/spec-driven.md:113` and `docs/context/audience/internal/system-architect.md:42`: already exempt via `-L dialogue`, so no change.
- **`docs/guides/gstack-glossary-observations.md:97`**: recognise (line 90 is T018).
- **`docs/guides/how-to/recovery/recover-from-implementation-crash.md:84`**: summarises.
- **`docs/guides/how-to/installation/fork-packaging-hooks.md`**: 18, 28, 148 behaviour.
- **`docs/guides/how-to/governance/create-an-org-doctrine-pack.md`**: 44, 255, 340, 407 organisation(s); 354, 416 behaviour; 544 recognised.
- **`docs/guides/how-to/governance/extend-charter-for-unsupported-language.md`**: 24, 34, 63, 69 recognis*, all prose, including "Recognised" at 69.
- **`docs/guides/how-to/governance/troubleshoot-charter.md`**: 250, 253 recognised.
- **`docs/guides/how-to/collaboration/adhoc-specialist-session.md`**: 89, 102 artefact.

**Literal classification (do this per hit, before editing):**

- If the word sits inside quoted CLI/tool output, an error message, a config key, a status value or a canonical identifier, it is a literal. Wrap the literal in a code span (or keep it in an existing fence) and do not respell it. The brownfield scout found **no** true literals among the `recognis*` hits. `create-an-org-doctrine-pack.md:544` paraphrases in prose (the CLI message at `src/specify_cli/doctrine/snapshot.py:412` reads "has no recognised artifact directories"), so respell it. Re-check any hit that quotes output verbatim.
- Canonical UK-spelled identifiers (the paradigm id `behaviour-driven-development`, the glossary-pack surface `behaviour-driven development` from `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml:59`) go in code spans if they appear in scope.
- Everything else is prose: respell it.

Record the literal-vs-prose decision for each non-obvious hit in the Activity Log.

### Subtask T018 – Glossary heading renames with legacy anchors

For each heading, rename it to US spelling and insert an explicit anchor for the old slug **on the line directly above the heading**:

```markdown
<a id="organisation-tier"></a>

### Organization Tier
```

1. **`docs/context/charter.md:612`** "Organisation Tier" → "Organization Tier". Move the 6 in-page `#organisation-tier` links (lines 326, 415, 584, 596, 668, 704; `grep -n "organisation-tier" docs/context/charter.md`) to `#organization-tier`. The anchor keeps old external links working.
2. **`docs/context/execution.md:242`** "communication artefact" → "communication artifact", plus `<a id="communication-artefact"></a>`. This is a ratified term (DIRECTIVE_032 naming note; ADR `docs/adr/3.x/2026-06-03-3-effector-actor-model.md`). In the entry's table, add or extend the `**Alias**` row (the page's convention, see `execution.md:182`) with `communication artefact (UK spelling, legacy)`. The contextive generator hard-codes `aliases=[]` (`scripts/generate_contextive_glossaries.py:122`), so the alias lives in the docs only. Do not claim it reaches the YAML. Also respell the heading's own table rows (lines 231/237 were handled in T017).
3. **`docs/guides/gstack-glossary-observations.md:90`**: the level-2 heading `## Trail Behaviour` → `## Trail Behavior`, plus `<a id="trail-behaviour"></a>`.
4. Check for inbound links from other live docs with `grep -rn "organisation-tier\|communication-artefact\|trail-behaviour" docs/ src/ packs/ --include="*.md" --include="*.yml" --include="*.yaml" | grep -v "docs/archive"`. Point live references at the new slug; generated files are regenerated in T019/T020. Leave `kitty-specs/` untouched.
5. Add a test to `tests/docs/test_docs_spelling_live.py`: for each of the three pages, the legacy `<a id="…">` is present **and** the new US heading exists. Also assert that **zero** `](#organisation-tier)` and `](#communication-artefact)` links remain in `docs/context/`, and that the alias text `communication artefact` is present in the entry's `**Alias**` row. Note that the US pass cannot see hyphenated tokens at all (verified codespell blind spot); WP02 case 6 covers the anchor regex with a single-word id.

### Subtask T019 – Contextive regeneration

- Run `PYTHONPATH=. .venv/bin/python scripts/generate_contextive_glossaries.py generate`; it has `generate` / `check` subcommands and no write flag. **The base is already stale** (`governance.yml` and `orchestration.yml` drift, plus a missing `src/specify_cli/merge/.contextive.yml`). Stage and commit **only** `src/specify_cli/.contextive/execution.yml`, and only the renamed-term hunk, then `git checkout --` the rest. Record the pre-existing drift in the Activity Log for the PR body; do not commit it. Then run the contextive tests: `grep -rl "contextive" tests/ --include="*.py" | xargs .venv/bin/python -m pytest -q`.
- This `src/` edit triggers a run-all CI on the PR. Note that in the Activity Log for the PR body.

### Subtask T020 – Retrieval index, freshness, terminology

```bash
PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci      # errors=0 expected; record any pre-existing errors vs base
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_docs_index_freshness.py tests/docs/test_docs_spelling_live.py -q
```

- If `check_docs_freshness --ci` reports errors, compare against the WP's base commit (`git stash`, or run in a clean checkout of the base) and classify each one as yours or pre-existing. Per the charter, pre-existing failures are reported, not chased.
- Pages whose content you edited: if their frontmatter carries `updated:`, bump it to `2026-09-30` (docs-freshness SLA).

## Test Strategy

- Red-first proof: the T015 commit precedes the content commits, and its red output is in the Activity Log.
- Final: all tests in `tests/docs/test_docs_spelling_live.py` pass, and `python -m scripts.docs.check_spelling` exits 0.
- Targeted runs only. Do not run the whole `tests/docs/` or `tests/architectural/`, only the files named here, plus `make test-fast` if time allows.

## Risks & Mitigations

- **Respelling a literal breaks a doc that quotes CLI output.** Classify first, using `grep` in `src/`.
- **Renaming a heading silently breaks anchors.** The legacy `<a id>` covers it, and so does the T018 test.
- **Scope creep into repo-wide US spelling.** Only `docs/guides/` and `docs/context/` are in scope (C-004).

## Review Guidance

- Check the red→green commit order.
- Spot-check 10 respelled words for literal misclassification.
- Confirm there are no `kitty-specs/`, `kitty-ops/` or `docs/archive/` changes: `git diff --stat`.
- Confirm the ignore list in `pyproject.toml` did not grow in this WP.

## Activity Log

- 2026-09-30T08:10:00Z – system – Prompt created.
