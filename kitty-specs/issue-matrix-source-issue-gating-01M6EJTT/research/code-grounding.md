# Code grounding — issue-matrix source-issue gating (#7011)

Base: `main` @ `9aed3a8012` (fast-forwarded, tree clean at mission start).
Repro harness: a throwaway `kitty-specs/` fixture with one `spec.md`; no test files added yet.

## 1. Reproduction on the current base

`spec.md` containing exactly the header line reported in #7011:

```
**Input**: Issue #6926 (part of epic #6100, sdist packaging cleanup)
```

`discover_issue_references(feature_dir)` returns:

```
#6926   class=context_only           file=spec.md
#6100   class=context_only           file=spec.md
```

So the Mission's own target (`#6926`) scaffolds `verdict: not-applicable`,
`title: <auto-classified: context_only>`, `evidence_ref: <auto-classified: no action
required>` — the row the approval gate accepts as terminal. The reported defect is
present on the base.

Control, same base, from the merged `sdist-readme-anchor-01M6BRD9` mission this issue
was filed from: its `spec.md` line 6 is that header verbatim, and its `meta.json`
`source_description` is `Issue #6926: anchor the sdist README.md/CHANGELOG.md include…`.

## 2. Cause 1 — the citation label is matched anywhere on the line

`src/specify_cli/tasks/issue_reference_discovery.py`:

- `Occurrence` (line 76) carries only `source_file` and `line_text`. The position of
  the citation inside the line is **not** retained, so `classify_occurrence` cannot
  tell which number a label belongs to.
- `_CONTEXT_MARKER_PATTERN` (line 118-ish) contains
  `(?:parent|epic)\b[^#\n]{0,12}#`, searched over the whole line. Its own comment
  states the intended rule: "`parent`/`epic` sitting immediately … before the `#`
  ref". The `#` in the regex is *any* `#` on the line — here `epic #6100` — so the
  pattern demotes every number on that line, including the one that appears before
  the label and the one the label does not describe.
- `classify_occurrences` then aggregates: every occurrence is `context_only`, so the
  number's aggregate class is `context_only`.

Vanilla check of the same mechanism on a non-`epic` label, same file, in a live
`kitty-specs/*/spec.md`: `Parent epic #5001. See #5330, …` demotes `#5330` too, so the
defect is broader than the one reported line.

## 3. Cause 2 — nothing protects the Mission's source issue

Searching the tree for any notion of "the issue this Mission exists to fix" in the
classification path: there is none. `grep` for `source_description` under `src/`
matches only the `MissionMetaRequired` dataclass (`mission_metadata.py:109`); no
classification code reads it, and `meta.json` is never opened by
`issue_reference_discovery.py`.

Consequence: even with Cause 1 fixed, any prose shape that genuinely looks like a
citation (`follow-up:`, a marker the author wrote about the target) demotes the
source issue. The issue's "never" cannot rest on the prose heuristic alone.

## 4. Consumers that must agree (single authority)

All four derive gating from the one predicate `is_gating` / `gating_issue_numbers`
(FR-012, #3469), so the promotion belongs in that seam:

| Consumer | File | What it reads |
| --- | --- | --- |
| Scaffold | `src/specify_cli/tasks/issue_matrix.py` `_scaffold_entry_for` / `_scaffold_issue_matrix_locked` (calls `detect_issue_references` on `spec.md` alone) | `is_gating(ref)` |
| Approval blocker | `src/specify_cli/tasks/issue_matrix_approval.py` `_issue_matrix_evaluation` | `is_gating` over `discover_issue_references` |
| `status doctor` | `src/specify_cli/status/doctor.py:513-537` | `gating_issue_numbers` |
| Merge gate | `src/specify_cli/policy/merge_gates.py:401-403` | `is_gating` |

`detect_issue_references` is the single-file detector the scaffold still calls
directly; it has no mission directory, so the scaffold must apply the same promotion
the discovery path applies — one shared helper, two call sites, no second predicate.

## 5. Why the fix is not just "delete the `epic` arm"

`_CONTEXT_MARKER_PATTERN`'s `parent`/`epic`/`see` arms were added deliberately
(#3469) so genuinely-context citations do not force verdicts; the fail-open hole they
closed (ordinary English words) is pinned by
`tests/tasks/test_issue_reference_classification.py::test_ambiguous_english_word_on_implementation_line_still_gates`.
Deleting the arm would re-open that hole and force verdicts on every `epic #N`
citation. The fix has to keep the demotion and narrow *which* number it applies to.

## 6. Test surfaces that already exist and must stay green

- `tests/tasks/test_issue_reference_classification.py` — direct `Occurrence(...)`
  construction (no position) plus the observable `scaffold_issue_matrix` path.
- `tests/specify_cli/tasks/test_issue_matrix_structured.py:558` — constructs
  `Occurrence(source_file=..., line_text=...)`.
- `tests/policy/test_issue_matrix_cross_site_consistency.py`, `tests/status/*` — the
  cross-consumer agreement the fix must preserve.
- `tests/specify_cli/cli/commands/review/test_zero_reference_not_applicable.py` — the
  zero-reference "nothing to enforce" rule (#6653), which must not change.

## 7. Changelog shape

`docs/changelog/unreleased/README.md` documents the per-PR fragment convention
(`<pr>.fixed.md`), enforced by `check_changelog_style` since #6988; the root
`CHANGELOG.md` is not edited.
