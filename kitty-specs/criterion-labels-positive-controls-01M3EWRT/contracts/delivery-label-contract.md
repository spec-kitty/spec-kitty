# Contract: per-criterion delivery labels (software-dev spec template)

**Canonical definition**: tactic `acceptance-criteria-non-vacuity`
(`spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity`). This contract fixes only the
*shape* the tooling depends on; it does not redefine the labels.

## Functional Requirements table

```
| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
```

- `Delivery` ∈ `[build]` · `[ratchet]` · `[folded]` (a `[folded]` row names the item that satisfies it).
- `No-op passable?` ∈ `no` · `yes — <named positive control>`.
- Both columns are **trailing** and **optional**; legacy five-column tables parse and gate identically.

## Success criteria

`- **SC-###**: <measurable outcome> — [build|ratchet|folded] · no-op passable: yes|no`

## Invariants (pinned by tests)

| Invariant | Guard |
|-----------|-------|
| A labelled row is declared by `parse_requirement_ids_from_spec_md` and yields the same coverage through `plan_mapping` as its unlabelled twin | `tests/specify_cli/test_requirement_mapping.py::TestDeliveryLabelledRequirementRows` |
| A label inside/before the id cell undeclares the row (never place it there) | same class, same fixture |
| The template scaffold stays non-substantive; its filled example (`FR-EXAMPLE`) declares no id | `tests/specify_cli/missions/test_substantive_gate_formats.py` |
| No gate enforces the labels (guidance only) | spec C-002 |
