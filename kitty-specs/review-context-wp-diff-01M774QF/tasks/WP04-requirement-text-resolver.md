---
work_package_id: "WP04"
title: "Requirement-text resolver for cited IDs"
dependencies: []
requirement_refs: ["FR-010", "FR-011", "NFR-003"]
subtasks: ["T018", "T019", "T020", "T021"]
owned_files: ["src/specify_cli/requirement_mapping/text.py", "tests/specify_cli/test_requirement_mapping_text.py"]
authoritative_surface: "src/specify_cli/requirement_mapping/"
execution_mode: "code_change"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: ""
create_intent:
  - "src/specify_cli/requirement_mapping/text.py"
  - "tests/specify_cli/test_requirement_mapping_text.py"
---

# WP04: Requirement-text resolver for cited IDs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

**Implementation command**:

```bash
spec-kitty agent action implement WP04 --agent claude --mission review-context-wp-diff-01M774QF
```

## Objective

Add one pure function, `resolve_requirement_texts(spec_text, refs, *, mission_type)`, in a NEW module
`src/specify_cli/requirement_mapping/text.py`. It turns the requirement IDs a work package cites into
their declared text from the Mission's `spec.md`. It never drops a citation: an undeclared ID, a citation
of another Mission and an ambiguous declaration each get an explicit resolution. It is built only on the
canonical declaration parser (`_declaration_occurrences` / `duplicate_declared_ids`), never on a new one.

## Context

- **Why (User Story 3, FR-010, FR-011, NFR-003).** Review prompts list bare IDs today, so reviewers re-read
  `spec.md` and `plan.md` over and over (104 reads in one benchmark, the largest group of review
  commands). After this Mission the prompt's `CITED REQUIREMENTS:` block
  (`contracts/review-context-block.md`) shows each cited ID with its declared text:

  ```
  CITED REQUIREMENTS:
    FR-003 — <title>: <statement>
    NFR-001 — <text>
  ? C-009 — not declared in this Mission's spec
  ? other-mission#FR-002 — cites another Mission (not resolved here)
  ```

  This WP produces the data (a tuple of `CitedRequirement`); it does NOT render that block. WP05 (IC-05)
  owns `review/context_block.py::render_review_context(range, cited)`, reads the WP's `requirement_refs`
  from frontmatter, reads `spec.md` through the placement seam, and calls this function. Keep the output
  shape exactly as `data-model.md` defines it so WP05 can consume it unchanged.
- **Data model** (`data-model.md`, `CitedRequirement`):

  | Field | Type | Notes |
  |---|---|---|
  | `ref` | `str` | As cited (canonical form). |
  | `resolution` | `Resolution` | `DECLARED` · `NOT_DECLARED` · `OTHER_MISSION` · `AMBIGUOUS` |
  | `text` | `str \| None` | Declared text, at most 600 characters plus a marker. `None` unless `DECLARED`. |

- **Plan IC-04 (key design decisions).**
  - Built on `_declaration_occurrences` (`src/specify_cli/requirement_mapping/__init__.py:133`). A probe on
    this Mission's own spec found all 34 IDs with usable line numbers.
  - A table row becomes `ID — Title: statement`, with escaped `\|` handled. A heading, list item or bold
    lead becomes its block's first paragraph, with the SC trailer (`— [build] · …`) stripped.
  - AMBIGUOUS uses only `duplicate_declared_ids` semantics (`__init__.py:175`), so a bullet that merely
    restates an ID is not ambiguous.
  - A cross-Mission `slug#ID` is labelled, and an undeclared ID is marked.
- **Research R6 / issue #3481.** The repository already has two definitions of "declares". A third parser
  is explicitly rejected. Reuse `_declaration_occurrences` (for the declaring line and its shape) and
  `duplicate_declared_ids` (for ambiguity). The ID grammar (`grammar.parse`, `grammar.canonical`,
  `grammar.tokenize_refs`, research kinds `DR`/`AR`/`QR`, the `slug#` qualifier) is already shared.
- **Post-plan squad P16** folded three details into IC-04: ambiguity semantics, the SC trailer, escaped
  pipes. Each has a test in T018.
- **Dependencies**: none. This WP can run in parallel with WP01–WP03. WP05 depends on it.

### Useful facts about the canonical parser (read before coding)

- `_declaration_occurrences(spec_content, *, mission_type)` returns `(id, line_no, shape, table_block)`
  for the first ID on each declaring line. `shape` is `"table"`, `"heading"` or `"other"` (list item or
  bold-led paragraph). Line numbers count over `grammar.blank_html_comments(spec_content)`, which keeps
  the line count, so index the **blanked** text's `splitlines()` with `line_no - 1`. Reading the blanked
  text also keeps commented-out content out of the resolved text.
- An ID's declaring site is its **first** occurrence. Later occurrences (a traceability table, a review
  bullet `- **FR-005 has a second leg**`, a detail heading `### FR-004 Detail: …`) restate or cite it.
- `duplicate_declared_ids` reports an ID only when a later occurrence has the same shape at the same site:
  another lead row of the SAME table, or another ID-naming heading when the first was a heading. A row in
  a later table, a bullet, or a detail heading under a table-declared ID is NOT a duplicate.
- `grammar.parse(token, mission_type=...)` returns a `RequirementId(kind, digits, suffix, mission)` or
  `None`. `.canonical` is the unqualified form; `str(rid)` is `slug#ID` when `rid.mission` is set.
  Research kinds parse only with `mission_type="research"`.
- Table header shapes in real specs: `| ID | Title | User Story | … |` (FR), `| ID | Title | Requirement | … |`
  (NFR), `| ID | Title | Constraint | … |` (C). So cell 1 is the title and cell 2 the statement.
- SC bullets in this Mission's spec look like
  `- **SC-002**: 100% of requirement IDs … label. — [build] · no-op passable: no`.

---

### Subtask T018: Red-first tests

**Purpose**: write the executable contract before the implementation, as a separate first commit, so the
reviewer can see the tests fail on the parent commit (ATDD-first, red-first discipline from the charter).

**Steps**:

1. Create `tests/specify_cli/test_requirement_mapping_text.py`. Follow the style of
   `tests/specify_cli/test_requirement_mapping.py`: `from __future__ import annotations`,
   `pytestmark = [pytest.mark.unit, pytest.mark.fast]`, small classes grouping cases, inline spec
   snippets built with `textwrap.dedent`.
2. Import only the public surface:
   `from specify_cli.requirement_mapping.text import CitedRequirement, Resolution, resolve_requirement_texts`.
3. Write these cases (one test each; use `pytest.mark.parametrize` where shapes repeat):
   - **Table rows**: FR, NFR and C rows each resolve `DECLARED` with text `"FR-001 — <Title>: <Statement>"`.
     Assert the exact string, including the em dash and the colon.
   - **Escaped pipe**: a cell containing `a \| b` yields `a | b` in the text and does not split the cell.
   - **SC bold-lead bullet**: `- **SC-001**: Something holds. — [build] · no-op passable: no` resolves to
     text `"SC-001 — Something holds."` (or the exact format you settle in T019; pin it). The trailer
     `— [build] · no-op passable: no` is stripped. Add a `[ratchet]` variant with a longer trailer
     (`— [ratchet] · no-op passable: yes — paired with …`) to prove the whole trailer goes.
   - **Heading-led declaration**: `### FR-007: Title` followed by a paragraph resolves to the heading text
     plus the first paragraph; a second paragraph after a blank line is not included.
   - **List-item continuation**: a bullet whose statement wraps onto an indented continuation line keeps
     the continuation, stops at the next bullet or blank line.
   - **Letter-suffixed ID**: `FR-003a` declared in a table resolves; citing `FR-003A` (upper suffix)
     resolves to the same row (`grammar.parse` lowers the suffix); `FR-003` and `FR-003a` stay distinct.
   - **Research-mission kinds**: with `mission_type="research"`, `DR-001`, `AR-001`, `QR-001` table rows
     resolve `DECLARED`. With the default mission type, a cited `DR-001` is `NOT_DECLARED` (never dropped).
   - **Cross-mission citation**: `other-mission#FR-002` resolves `OTHER_MISSION`, `text is None`, `ref` is
     `"other-mission#FR-002"`, even when this spec also declares `FR-002`.
   - **Undeclared**: `C-009` absent from the spec resolves `NOT_DECLARED`, `text is None`.
   - **Malformed token**: a token `grammar.parse` rejects (for example `FR-` or `<NON_STRING:3>`) appears
     as `NOT_DECLARED` with `ref` equal to the token as written. Never dropped.
   - **AMBIGUOUS** (duplicate_declared_ids semantics, exactly):
     - two lead rows of the SAME table declaring `FR-004` → `AMBIGUOUS`, `text is None`;
     - two ID-naming headings `### FR-005` (first declaration by heading) → `AMBIGUOUS`.
   - **Not ambiguous** (each resolves `DECLARED` from the first occurrence):
     - a bullet `- **FR-001 has a second leg**` after the table row;
     - a later traceability table whose lead column repeats `FR-001`;
     - a table-declared ID followed later by a detail heading `### FR-001 Detail: …`.
     Add one assertion per case that `duplicate_declared_ids(spec)` agrees (empty for these, non-empty for
     the AMBIGUOUS cases), so the test proves the resolver follows that function rather than its own rule.
     Note: a table row plus a later heading is NOT a duplicate under `duplicate_declared_ids` (different
     shape at a different site), so it must not be tested as AMBIGUOUS.
   - **Truncation (NFR-003)**: a statement whose rendered text exceeds 600 characters yields text of
     exactly 600 characters followed by the truncation marker; a text of exactly 600 characters gets no
     marker. Pin the marker constant (`TEXT_LIMIT`, `TRUNCATION_MARKER`) by import.
   - **Budget (NFR-003), measured in bytes**: build a spec declaring 20 IDs (FR-001..FR-020), each with a
     statement far over 600 characters that includes non-ASCII characters (an em dash, accented letters), so
     every result is truncated at the maximum length. Render the lines the way the contract prints them,
     `rendered_lines = [f"  {c.text}" for c in results]` (the text already carries the `ID — ` prefix), and
     assert `len("\n".join(rendered_lines).encode()) <= 12 * 1024`. Also assert every result is `DECLARED`
     and ends with `TRUNCATION_MARKER`, so the cell really exercises maximum-length citations.
   - **Order**: output order equals citation order (`["NFR-001", "FR-002", "C-001"]` comes back in that
     order, not sorted). A repeated citation appears once, at its first position (pin this).
   - **Whitespace**: internal runs of whitespace and line breaks collapse to single spaces; markdown bold
     markers around the ID (`**FR-001**`) never appear in the text.
   - **HTML comments**: an ID declared only inside `<!-- … -->` is `NOT_DECLARED`.
   - **Realistic fixture**: read this Mission's own spec,
     `Path(__file__).resolve().parents[2] / "kitty-specs/review-context-wp-diff-01M774QF/spec.md"`.
     Cite every ID in `parse_requirement_ids_from_spec_md(spec)["all"]` (34 at the time of writing; assert
     equality with that function, not a literal, plus `>= 34`). Every one resolves `DECLARED` with
     non-empty text that starts with its ID; spot-check `FR-010` contains `"Cited requirement text"` and
     `SC-002` does not contain `"no-op passable"`.
4. Run the file and confirm it fails on import (the module does not exist yet). Commit this file alone:
   `test(WP04): red-first tests for requirement-text resolver`.

**Files**: `tests/specify_cli/test_requirement_mapping_text.py` (new, ~250–350 lines).

**Validation**: `uv run --frozen pytest tests/specify_cli/test_requirement_mapping_text.py -q` fails with
`ModuleNotFoundError` before T019, and the commit holds only this file.

---

### Subtask T019: Implement `resolve_requirement_texts` on the canonical parser

**Purpose**: resolve each cited ID to its declared text, reading the declaring line found by
`_declaration_occurrences`. No new declaration grammar.

**Steps**:

1. Create `src/specify_cli/requirement_mapping/text.py` with a module docstring that names #3481 and says
   the module adds no declaration parser: it reads the declaring site `_declaration_occurrences` reports.
2. Imports: `from specify_cli.requirement_mapping import _declaration_occurrences, duplicate_declared_ids`
   and `from specify_cli.requirement_mapping import grammar`. The parent `__init__` does not import
   `text`, so there is no cycle. Do NOT edit `__init__.py` (not an owned file, and a change there would
   need a version bump per the code-style rules).
3. Public signature:

   ```python
   def resolve_requirement_texts(
       spec_text: str,
       refs: Iterable[str],
       *,
       mission_type: str = "software-dev",
   ) -> tuple[CitedRequirement, ...]:
   ```

   `refs` are raw tokens (as `grammar.tokenize_refs` returns them). Compute the occurrence list, the
   duplicate map and the blanked lines once, then resolve each ref in citation order.
4. Per-ref resolution (`_resolve_one`):
   - `grammar.parse(token, mission_type=mission_type)` is `None` → `NOT_DECLARED`, `ref=token`.
   - `rid.mission is not None` → `OTHER_MISSION`, `ref=str(rid)`.
   - `rid.canonical in duplicates` → `AMBIGUOUS`, `ref=rid.canonical`.
   - no occurrence for `rid.canonical` → `NOT_DECLARED`.
   - otherwise → `DECLARED`, text from the **first** occurrence's line and shape.
   - De-duplicate by the resolved `ref`, keeping the first position.
5. Text extraction by shape:
   - **table** (`_table_row_text`): take the line, use `grammar.DECLARED_TABLE_ROW` (or the research
     variant from `grammar.declared_shape_patterns(mission_type)[0]`) to find where the ID cell ends, split
     the remaining text on unescaped pipes (`re.split(r"(?<!\\)\|", rest)`), unescape `\|` to `|`, strip
     each cell, drop empty trailing cells. Two or more cells → `f"{id} — {cells[0]}: {cells[1]}"`; one
     cell → `f"{id} — {cells[0]}"`. Reusing the shape pattern from `grammar` is not a new parser; it is the
     same compiled pattern `_declaration_occurrences` matched.
   - **heading** / **other** (`_block_text`): take the declaring line plus following lines until a blank
     line, a heading, a table line or another list item. Remove the leading heading hashes or list
     marker, the bold/strike markup around the lead ID and a `:` or `—` separator after it, then strip the
     SC trailer with one module regex, for example
     `_SC_TRAILER = re.compile(r"\s+—\s+\[[a-z-]+\](?:\s*·.*)?$")`. Result: `f"{id} — {statement}"`
     (or just `id` when the statement is empty; pin the exact behaviour in T018).
6. Normalize whitespace (`" ".join(text.split())`), then truncate (`_truncate`): over `TEXT_LIMIT` (600)
   characters → `text[:TEXT_LIMIT] + TRUNCATION_MARKER`. Pick a short, explicit marker such as
   `" … [truncated]"` and export it as a module constant so WP05 and the tests share it. Count the limit
   on the text including the `ID — ` prefix, so the 12 KB bound for 20 IDs in NFR-003 holds.

**Files**: `src/specify_cli/requirement_mapping/text.py` (new, ~150–200 lines).

**Validation**: T018 tests go green; `git diff` shows no change outside the two owned files.

---

### Subtask T020: Resolution kinds, `Resolution` enum, frozen `CitedRequirement`

**Purpose**: give WP05 a typed, immutable result it can render without re-deriving anything.

**Steps**:

1. In `text.py`:

   ```python
   class Resolution(StrEnum):
       DECLARED = "declared"
       NOT_DECLARED = "not_declared"
       OTHER_MISSION = "other_mission"
       AMBIGUOUS = "ambiguous"

   @dataclass(frozen=True)
   class CitedRequirement:
       ref: str
       resolution: Resolution
       text: str | None = None
   ```

   (`enum.StrEnum` is available on Python 3.11+.) Optionally enforce the invariant "`text` is `None`
   unless `DECLARED`" in `__post_init__` with a `ValueError`, and test it.
2. Keep every function at complexity ≤ 15 (ruff `C901`, Sonar `S3776`): split lookup (`_resolve_one`),
   build (`_table_row_text`, `_block_text`) and post-processing (`_strip_trailer`, `_truncate`) into small
   private helpers, each covered by the T018 tests.
3. Hoist any literal used three or more times (the em-dash separator `" — "`, the marker) to a module
   constant (Sonar `S1192`).
4. Full type annotations; no `Any`; no `# type: ignore`, no `# noqa`.

**Files**: same module as T019.

**Validation**: `uv run --frozen mypy --strict src/specify_cli/requirement_mapping/text.py` reports zero
issues; `uv run --frozen ruff check src/specify_cli/requirement_mapping/text.py` is clean, including C901.

---

### Subtask T021: Validation and gates

**Purpose**: prove the new module fits the existing requirement-mapping surface and the architectural
gates, and record the results for the review.

**Steps**:

1. Targeted tests (blast radius):

   ```bash
   uv run --frozen pytest tests/specify_cli/test_requirement_mapping*.py \
       tests/specify_cli/test_requirement_id_grammar.py \
       tests/runtime/test_requirement_grammar_parity.py -q
   uv run --frozen pytest tests/architectural/test_layer_rules.py -q
   uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py -q
   make test-fast
   ```

2. **Dead-symbol / dead-module gates.** `resolve_requirement_texts` gets its first `src/` caller in WP05.
   The dead-symbol gate is widened beyond `__all__` (#470): it scans every public module-level name, so
   leaving names out of an `__all__` does NOT hide them. `CitedRequirement` and `Resolution` are used
   inside `text.py` and pass the intra-module rescue; `resolve_requirement_texts`, `TEXT_LIMIT`,
   `TRUNCATION_MARKER` and the module itself (`test_no_dead_modules`) may still go red until WP05 lands.
   - If they go red only for these names, do NOT add allowlist entries and do NOT add a fake caller.
     Record the red as "expected until WP05 wires `review/context_block.py`" in the review hand-off, with
     the exact failing names, so the WP05 reviewer confirms the gate is green after WP05.
   - If any other name goes red, it is yours: fix it.
3. Lint and format the owned files:

   ```bash
   uv run --frozen ruff check src/specify_cli/requirement_mapping/text.py tests/specify_cli/test_requirement_mapping_text.py
   uv run --frozen ruff format --check --force-exclude src/specify_cli/requirement_mapping/text.py tests/specify_cli/test_requirement_mapping_text.py
   uv run --frozen mypy --strict src/specify_cli/requirement_mapping/text.py
   ```

4. Record each command with passed/failed counts in the hand-off (and later the PR's *Tests run*). Classify
   any unrelated red with the baseline-red gotcha in `CLAUDE.md` before attributing it.

**Files**: none new.

**Validation**: all listed commands green, except the documented, WP05-pending dead-symbol/module names.

---

## Definition of Done

- C-010 (per work package): the lane's first commit is the failing T018 test file alone.
- `tests/specify_cli/test_requirement_mapping_text.py` exists, was committed alone first (red), and passes
  after T019/T020 (`spec-kitty agent tasks mark-status T018 --status done`).
- `src/specify_cli/requirement_mapping/text.py` exports `resolve_requirement_texts`, `CitedRequirement`,
  `Resolution`, `TEXT_LIMIT`, `TRUNCATION_MARKER`; it imports `_declaration_occurrences` and
  `duplicate_declared_ids` and contains no new declaration regex or line-shape classifier
  (`mark-status T019 --status done`).
- `CitedRequirement` is a frozen dataclass matching `data-model.md`; `Resolution` has exactly the four
  members; `text is None` for every non-`DECLARED` result (`mark-status T020 --status done`).
- Every cited ref comes back exactly once, in citation order; no citation is dropped (FR-011).
- Each declared text is at most 600 characters plus the marker, and 20 maximum-length citations render to at
  most 12 * 1024 bytes (`len("\n".join(rendered_lines).encode())`, NFR-003).
- All 34 IDs of this Mission's own spec resolve `DECLARED` with non-empty text.
- NFR-006: ruff, `ruff format --check --force-exclude` and `mypy --strict` are clean on both owned files; no
  suppression comments; every function at complexity ≤ 15.
- No `tracer-*.md` is edited from the lane; anything worth recording goes in the completion note for the
  orchestrator.
- T021 commands are recorded with counts; any dead-symbol/module red is limited to the WP05-pending names
  and recorded (`mark-status T021 --status done`).
- No file outside `owned_files` is changed.

## Risks

- **A third parser by the back door (#3481).** Writing a fresh "is this line a declaration" regex in
  `text.py` would recreate the drift #3481 tracks. Mitigation: the only source of "where is ID X declared,
  and in which shape" is `_declaration_occurrences`; ambiguity comes only from `duplicate_declared_ids`.
  Text extraction reads the line it is pointed at; it never decides what counts as declared.
- **Ambiguity over-reporting.** Treating any repeated ID as ambiguous would mark most SC and FR IDs that
  a later section restates. Mitigation: the "not ambiguous" tests, each cross-checked against
  `duplicate_declared_ids`.
- **Table header variance.** Not every spec has `ID | Title | Statement`. Mitigation: one-cell fallback;
  never index past the cells present; empty cells dropped.
- **Line-number drift from HTML comments.** Mitigation: index the `grammar.blank_html_comments` output,
  the same text `_declaration_occurrences` numbered.
- **Dead-symbol gate red before WP05.** Mitigation: documented in T021; no allowlist entry, WP05 closes it.
- **Fixture coupling to this Mission's spec.** If `spec.md` gains IDs later, the realistic-fixture test
  still holds because it compares with `parse_requirement_ids_from_spec_md`, not a literal list.

## Reviewer Guidance

- **No third declaration parser (#3481).** Confirm `text.py` gets declaring lines only from
  `_declaration_occurrences` and ambiguity only from `duplicate_declared_ids`. Any new regex in `text.py`
  should be limited to text clean-up (escaped pipes, SC trailer, markup), never to deciding what counts as
  declared.
- **Unresolved IDs are never dropped.** Check the tests for undeclared, malformed, cross-Mission and
  ambiguous refs: each appears in the output with its resolution and `text is None`.
- **Ambiguity semantics.** A same-table duplicate row and a repeated ID heading are `AMBIGUOUS`; a bullet,
  a traceability table or a detail heading restating an ID is not.
- **Red-first.** The first commit holds only the test file and fails on its parent.
- **Output contract.** Field names and resolution members match `data-model.md`, so WP05 can render
  `contracts/review-context-block.md`'s `CITED REQUIREMENTS` block without translation. Truncation is
  600 characters plus a marker (NFR-003).
- **Quality gates.** mypy strict, ruff, format with `--force-exclude`, complexity ≤ 15, no suppressions;
  the dead-symbol/module red, if any, is limited to WP05-pending names and recorded.
