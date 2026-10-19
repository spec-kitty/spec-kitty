# Data Model: ROI ledger

One markdown file per work package: `roi-ledger/WP0N.md`.

## File section (one per reviewed test file)

```markdown
## tests/charter/<path>.py

Kept: <n> · Deleted: <n> · Merged: <n> · Rewritten: <n>

| Test | Verdict | Rubric class | Covering test / merge target | Note |
|------|---------|--------------|------------------------------|------|
| test_foo | delete | private-helper | tests/charter_offering/test_x.py::test_bar | public path hits same branches |
```

Rules:

- `Verdict` ∈ {keep, delete, merge, rewrite}. Only non-keep rows are required. Kept tests are counted in the header line.
- `Rubric class` ∈ {change-detector, tautology, mock-only, retired-path, private-helper, duplicate}.
- `delete` requires a covering test node id, or `none — low ROI` plus a reason (feeds FR-006).
- `merge` names the surviving test, which must be in the same WP's file set.

## Cluster section (WPs that own a duplicate cluster)

```markdown
## Cluster N: <file A> ↔ <file B>
Verdict: merged | A deleted | B deleted | distinct
Reason: <one or two sentences>
```

## Coverage note

A trailer listing any `src/charter` lines that lost coverage as a result of the WP's removals, with the reason.
