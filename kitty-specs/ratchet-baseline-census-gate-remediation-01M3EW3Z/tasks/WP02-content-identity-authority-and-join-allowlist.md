---
work_package_id: WP02
title: Content-identity matching authority + join allowlist
dependencies: []
requirement_refs:
- C-004
- FR-004
- FR-007
- NFR-001
- NFR-003
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - Matching authority
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_content_identity.py
create_intent:
- tests/architectural/_content_identity.py
- tests/architectural/test_content_identity.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/_content_identity.py
- tests/architectural/test_content_identity.py
- tests/architectural/test_built_in_location_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Content-identity matching authority + join allowlist

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load `spec-kitty charter context --action implement --json`. Binding here: DIRECTIVE_044 (single canonical authority: this WP creates **the** matcher, not an eighth one), DIRECTIVE_041/DIR-041 (content anchoring), DIRECTIVE_043 and Standing Order #5 (non-vacuity), Standing Order #4 (red-first), the charter `__all__` declaration convention (C-007) for the new module.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
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

1. A new test helper `tests/architectural/_content_identity.py` is the single matching authority for content-keyed allowlists (plan D-OP-9): resolve descriptors, partition findings as a **multiset** (one entry suppresses at most one finding, `rel_path` always part of the key), two drift mutators, and one render/parse pair for the text serialisation of a descriptor. WP03 and WP04 depend on it.
2. `_KNOWN_JOIN_ALLOWLIST` (6 `(Path, int)` entries in `test_built_in_location_authority.py`) becomes `_KNOWN_JOIN_SITES: tuple[ContentDescriptor, ...]` with **4** entries; the 2 dead entries (`src/kernel/paths.py:88`, `src/specify_cli/runtime/home.py:79`) are deleted (FR-004; NFR-003: per-site exemption total −2).
3. Stale entries fail (FR-007, hand-curated policy): `test_join_allowlist_entries_each_suppress_a_live_join` is RED on the planning base naming exactly the 2 dead entries, GREEN at the end.
4. Drift tolerance (NFR-001): `test_join_allowlist_survives_line_drift` is parametrized over **every distinct file the allowlist references** (3 after migration, derived, with the parameter count asserted equal to that derived set, never hard-coded) and proves the `(unexpected, suppressed)` identity sets are identical under both mutations.
5. `test_new_join_at_formerly_pinned_line_is_caught`: a new `root / "built-in"` join planted in memory into `src/kernel/paths.py` at the formerly pinned line is reported.

## Context & Constraints

- **Mission**: `ratchet-baseline-census-gate-remediation-01M3EW3Z` (#5085). Read `spec.md` (FR-004, FR-007, NFR-001, NFR-003, C-004, Key Entities), `plan.md` rev 2 (D-OP-8, D-OP-9, Coordination points), `research.md` §B1, §B2, §B5, `data-model.md` ("ContentDescriptor entry"), `research/postplan-paula.md` Q1 (the seven existing hand-rolled matchers; Counter semantics; render/parse), `research/postspec-renata.md` (FR-007 / NFR-001 HIGH items).
- **Substrate (reuse, never fork)**: `tests/architectural/_ratchet_keys.py` exports `ContentDescriptor(rel_path, qualname, token_substring, occurrence, rationale)` (L95-121), `CompositeKey = tuple[str, str, str]` (L127), `DescriptorResolutionError` (L130), `resolve_descriptor(source, descriptor) -> CompositeKey` (L223-234, exactly-one rule), `composite_key(source, lineno) -> (qualname, token_line)` and `code_tokens_by_line` (re-exported from `specify_cli.contracts.anchoring`). Note the descriptor field is `rationale` (data-model.md's "reason" is the same field). Do **not** edit `_ratchet_keys.py`: WP07 owns its docstring; a pointer sentence to `_content_identity` is routed through WP07 or WP13, not you.
- **Why a multiset**: `composite_key` strips strings. `src/charter/activation/neutrality/lint.py` lines 379 and 380 in `_default_scan_roots` both tokenize to `roots . extend ( _iter_mission_scan_roots ( repo_root / / / ) )`. A set match would let the single allowlisted entry also bless a future join at 380 (Renata HIGH). Use `collections.Counter`.
- **Stale rule (FR-007, D-OP-8)**: an entry is stale if (a) it fails `resolve_descriptor`'s exactly-one rule, or (b) its resolved key suppresses no live finding. (b) is stronger than `descriptor_still_live`. The stale test also asserts `checked == len(allowlist) >= 4`, so it cannot pass over an empty list.
- **Resolve lazily**, inside a `functools.cache`d accessor, never at import time (the `test_trio_seam_only.py:528-530` import-time pattern turns a stale entry into a collection error that takes out the whole module).
- **Out of scope** (D-OP-9): adopting `_content_identity` in the other matchers (`_sole_door_scan.resolve_exclusion_keys` L587-602, `test_trio_seam_only.py` L528-564, `test_single_mission_surface_resolver.py` L389-403, `test_no_read_side_bypass.py` L796/L946, `test_no_write_side_rederivation.py`, `untrusted_path_audit/audit.py` `check_undercount`/`check_overcount` L507/L530). They change semantics (set → multiset, 2-tuple → 3-tuple) and need their own red-first; list them in the module docstring as known non-adopters (follow-up FR-019(d), filed by WP13). The census `diff_against_allowlist` adopts it in WP04.
- **Formatting**: none of your three files is in `pyproject.toml` `[tool.ruff.format].exclude`; all must pass `ruff format --check`.
- **C-005**: no `src/` edits. **C-006**: commit in your lane; never push or merge.
- **WP01 interaction**: WP01 lands interim per-site exemption rows for the 6 join tuples in the ban file. After your migration those rows have no finding and only warn; do not edit the ban file (WP13 removes the rows).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

Commit plan: **commit 1 = T007 alone (RED)**; commit 2 = T008; commit 3 = T009 + T010; T011 is validation.

### Subtask T007 – Red-first acceptance tests for the join gate (commit 1, RED)

- **Purpose**: C-001. Prove, on the planning base, that the line-keyed join allowlist carries dead entries and does not survive line drift, through the gate's own detection path.
- **Steps**:
  1. In `test_built_in_location_authority.py`, extract a pure seam from `test_no_builtin_path_joins_outside_pack_paths_authority` (L377-408), behaviour-preserving: `_join_partition(sources: Mapping[Path, str]) -> tuple[set[...], set[...]]` returning `(unexpected, suppressed)` for the current `(rel, lineno) in _KNOWN_JOIN_ALLOWLIST` matching, using `_find_builtin_joins(ast.parse(source))` (L342-370). The gate test calls the seam; nothing else changes. This extraction is test code and may ride in the RED commit; it must not change matching.
  2. Add `test_join_allowlist_entries_each_suppress_a_live_join`: for every allowlist entry, assert it suppresses a live finding; the message names each stale entry. On base this is RED naming `src/kernel/paths.py` (88) and `src/specify_cli/runtime/home.py` (79).
  3. Add `test_join_allowlist_survives_line_drift`, parametrized over the distinct files referenced by the allowlist, with an extra test asserting the parameter set equals the derived file set. For each file: prepend one blank line to that file's source in memory, recompute `(unexpected, suppressed)` through the seam, and assert both sets are identical to the unmutated run (not merely "still green"). On base this is RED for every file (line keys shift). In this commit use an inline blank-line mutation; T009 switches it to the shared mutators and adds the probe mutation.
  4. Run the two tests, capture the RED failure text, record it: `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category approach --actor <you> --entry "WP02 RED: ..."`. Commit these tests alone.
- **Files**: `tests/architectural/test_built_in_location_authority.py`.
- **Validation**: the pre-existing gate test and the two negative-bite tests (L411, L450) stay green in this commit; only the two new tests are red.

### Subtask T008 – Create `_content_identity.py` and its unit tests (commit 2)

- **Purpose**: The one matching authority (D-OP-9) that WP02, WP03 and WP04 consume.
- **Steps**:
  1. Create `tests/architectural/_content_identity.py` with `from __future__ import annotations`, a module docstring and `__all__`. It depends only on `tests.architectural._ratchet_keys` and the stdlib. API (research §B1, Paula Q3):
     ```python
     def resolve_allowlist(
         descriptors: Iterable[ContentDescriptor], source_for: Callable[[str], str]
     ) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
         """Resolved multiset + [(descriptor, reason)] for each DescriptorResolutionError."""

     def partition_findings(
         findings: Iterable[tuple[K, T]], allowed: Counter[K]
     ) -> tuple[list[T], Counter[K]]:
         """(unexpected, unused). MULTISET: one allowed key suppresses at most one finding."""

     def with_blank_line_at_top(source: str) -> str: ...

     def with_probe_above_statement(source: str, lineno: int) -> str:
         """Insert "# drift-probe\\n<indent>pass\\n" above the innermost ast.stmt containing
         lineno, at that statement's col_offset (safe inside multi-line expressions)."""

     def render_descriptor_line(descriptor: ContentDescriptor) -> str: ...
     def parse_descriptor_line(line: str, rationale: str) -> ContentDescriptor: ...
     ```
     `partition_findings` is generic in the key type `K` (a `TypeVar` bound to `Hashable`) so WP04's `CensusKey` (count-1 keys) reuses it. `unexpected` preserves finding order; `unused` is `allowed` minus what was consumed.
  2. `render_descriptor_line` / `parse_descriptor_line` implement the text form `<repo-rel path>::<qualname>::<token_substring>[::<occurrence>]` (research §B4). Parse with `split("::", 3)`; token substrings may contain `:` (e.g. `if sys . platform == :`) but never `::`. Reject (raise `ValueError` naming the line) anything that does not have 3 or 4 fields, an empty field, or a non-int occurrence. `parse(render(d))` round-trips. WP03 uses this pair for the os-detect, lock-ban and clock loaders (Paula LOW: one serialiser, not three).
  3. Docstring: state that this module is **the** partition/resolve authority for content-keyed allowlists; explain multiset semantics with the `neutrality/lint.py` 379/380 example; state the two stale policies are caller policies (hand-curated fails, census warns — D-OP-8); list the known non-adopters named in "Context & Constraints" with their paths; state why unit tests live in `tests/architectural/test_content_identity.py` rather than `tests/unit/test_descriptor_resolver.py` (architectural-marker collection next to its consumers; the resolver's own tests stay where they are).
  4. Create `tests/architectural/test_content_identity.py` (`pytestmark = [pytest.mark.architectural]`, matching sibling modules) with focused tests for every branch: multiset partition (two identical findings, one allowed → one unexpected); cross-file keys never cross-bless (same qualname/token in two `rel_path`s); `unused` reports an entry that matched nothing; `resolve_allowlist` reports 0-candidate and >1-candidate descriptors as errors instead of raising; `with_blank_line_at_top` shifts lines by 1 and keeps `composite_key` equal; `with_probe_above_statement` inside a multi-line call and inside a nested function keeps the source parseable and the composite key of the site unchanged; render/parse round-trip, `::`-free tokens containing `:`, and each rejection path (including a `path:12` line).
- **Files**: `tests/architectural/_content_identity.py`, `tests/architectural/test_content_identity.py` (both new).
- **Parallel?**: Can be written in parallel with T007, but commit after it.
- **Notes**: Keep each function ≤ complexity 15; `mypy --strict` must pass (generic `Counter[K]`, `TypeVar`s).

### Subtask T009 – Migrate `_KNOWN_JOIN_ALLOWLIST` to content identity (commit 3)

- **Purpose**: FR-004. Remove line identity and the 2 dead entries.
- **Steps**:
  1. Replace `_KNOWN_JOIN_ALLOWLIST: frozenset[tuple[Path, int]]` (L138-265) with `_KNOWN_JOIN_SITES: tuple[ContentDescriptor, ...]`. The four live entries (each verified to resolve uniquely on HEAD):

     | rel_path | qualname | token_substring | occurrence |
     |---|---|---|---|
     | `src/charter/activation/kind_vocabulary.py` | `_org_scan_dirs` | `legacy = flat /` | None |
     | `src/charter/activation/neutrality/lint.py` | `_default_scan_roots` | `_iter_mission_scan_roots ( repo_root / / /` | **0** (lines 379/380 are token-identical) |
     | `src/specify_cli/template/manager.py` | `copy_specify_base_from_local` | `missions_src = repo_root /` | None |
     | `src/specify_cli/template/manager.py` | `get_local_repo_root._is_template_root` | `return ( path /` | None |

  2. Collapse the FRESHENED / RE-PINNED comment archaeology (L143-262) into each descriptor's `rationale` (keep the substance: org-tier legacy nested-pack join; caller-supplied root scanned in tests; the tests that pin each behaviour). Delete the entries for `src/kernel/paths.py:88` and `src/specify_cli/runtime/home.py:79` (no live join; `kernel/paths.py:88` is `if is_windows():`).
  3. Add a `functools.cache`d accessor that calls `resolve_allowlist(_KNOWN_JOIN_SITES, source_for)` where `source_for` reads `_REPO_ROOT / rel`.
  4. Rewrite the seam from T007: findings are `((rel_posix, *composite_key(source, lineno)), lineno)` for each `lineno` in `_find_builtin_joins(tree)`; call `partition_findings(findings, allowed)`. The gate fails on `unexpected` (print `rel:lineno` plus the token line so the author can write a descriptor); `test_join_allowlist_entries_each_suppress_a_live_join` fails on resolution errors or a non-empty `unused`, and asserts `checked == len(_KNOWN_JOIN_SITES) >= 4`.
  5. Switch the drift test to `with_blank_line_at_top` and add mutation (ii): `with_probe_above_statement(source, lineno)` at every exempted site (re-resolving the site line from the descriptor on the unmutated source). Both mutations must leave `(unexpected, suppressed)` identical.
- **Files**: `tests/architectural/test_built_in_location_authority.py`.
- **Validation**: all tests in the file green; the drift parameter set is the 3 files `kind_vocabulary.py`, `neutrality/lint.py`, `template/manager.py`, derived from `_KNOWN_JOIN_SITES`.

### Subtask T010 – Non-widening proof and docstring rewrite (commit 3)

- **Purpose**: Renata LOW / FR-004 AS: a dead line pin must never re-bless a new violation, and the module docstring must stop documenting line identity.
- **Steps**:
  1. Add `test_new_join_at_formerly_pinned_line_is_caught`: read `src/kernel/paths.py`, insert `    _probe = Path("root") / "built-in"` immediately above line 88 **in memory** (line 88 is `if is_windows():` inside `get_kittify_home`, indent 4, so the plant lands at the formerly pinned line inside that function), run the seam over the real sources with that one file replaced, and assert the planted site is in `unexpected`.
  2. Add a multiset proof on real data: duplicate the allowlisted `neutrality/lint.py` join statement in memory (so two findings share its composite key) and assert exactly one is suppressed and one is unexpected.
  3. Rewrite the module docstring passage at L107-110 ("Each site below is allowlisted by exact ``(file, lineno)``…") and the "Known pre-existing exemption" section (L42 onward) to describe descriptor identity, multiset matching and fail-on-stale.
- **Files**: `tests/architectural/test_built_in_location_authority.py`.

### Subtask T011 – Validation, evidence, quality gates

- **Purpose**: Close the WP with reproducible evidence.
- **Steps**:
  1. Run the blast radius and quality gates below. Confirm the two RED tests from T007 are now GREEN.
  2. Record in the tracer (`--category design-decisions`): the 6 → 4 shrink with the two dead sites, the multiset rationale, and the list of known non-adopter matchers left for FR-019(d).
  3. Confirm the WP01 ban (if WP01 is already on your base) reports no line pin in this file: `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q` (rows for this file only warn).
- **Files**: none new.

## Test Strategy

Tests are required. New: `tests/architectural/test_content_identity.py`; extended: `tests/architectural/test_built_in_location_authority.py`.

```bash
.venv/bin/python -m pytest tests/architectural/test_content_identity.py tests/architectural/test_built_in_location_authority.py tests/doctrine/test_built_in_location_authority.py tests/unit/test_descriptor_resolver.py -q
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q   # new shared helper under tests/architectural/
make test-fast
uv run --frozen ruff check tests/architectural/_content_identity.py tests/architectural/test_content_identity.py tests/architectural/test_built_in_location_authority.py
uv run --frozen ruff format --check tests/architectural/_content_identity.py tests/architectural/test_content_identity.py tests/architectural/test_built_in_location_authority.py
uv run --frozen mypy tests/architectural/_content_identity.py tests/architectural/test_content_identity.py tests/architectural/test_built_in_location_authority.py
```

Pre-existing failure rule: classify any red that is also red on the planning base; if pre-existing, file (or find) a GitHub issue before continuing and cite it in the PR.

Campsite (FR-020): #2972 findings (S5778 / S5779 / S8997) only in `test_built_in_location_authority.py`; record before/after, zero is acceptable.

## Risks & Mitigations

- **Eighth matcher** (Paula HIGH): the docstring must claim authority and list non-adopters; do not copy partition logic into the gate.
- **Set semantics creeping back**: any `set(...)`/`in` over keys in the gate reopens the 379/380 widening hole; the multiset test in T010 guards it.
- **Import-time resolution**: resolving at import turns a stale entry into a collection error; resolve lazily behind `functools.cache`.
- **Probe mutation breaking syntax**: insert above the innermost `ast.stmt` containing the line, at its `col_offset`; the unit tests cover multi-line calls and nested functions.
- **Session fixture**: `src_source_tree` (`tests/architectural/conftest.py:58`) is a read-only session cache; never mutate it. Build mutated copies in local dicts.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`):

- The first lane commit contains only the two acceptance tests (plus the behaviour-preserving seam extraction) and is RED naming exactly the two dead entries and the drift failures.
- Stale detection requires "suppresses a live finding", not merely "resolves"; it asserts `checked == len(_KNOWN_JOIN_SITES) >= 4`.
- The drift test's parameter count is asserted equal to a set derived from the allowlist (no hard-coded 3); it uses both mutations and compares the full `(unexpected, suppressed)` sets.
- `partition_findings` is a Counter-based multiset and keys always include `rel_path`; the cross-file and duplicate-key unit tests exist.
- `test_new_join_at_formerly_pinned_line_is_caught` plants at `src/kernel/paths.py` old line 88 and asserts the gate reports it.
- `_content_identity.py` declares `__all__`, imports nothing but the stdlib and `_ratchet_keys`, and its docstring lists the non-adopters.
- No edit to `_ratchet_keys.py`, `_sole_door_scan.py`, the ban file, `pyproject.toml` or `src/`.
- ruff check, ruff format --check and mypy are clean on all three files.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
