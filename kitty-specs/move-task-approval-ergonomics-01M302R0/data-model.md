# Data Model: move-task / approval-gate ergonomics (#3469)

## Entity: Issue Reference (discovered)

A `#NNNN` token detected in mission artifacts. Extended with a gating classification.

| Field | Type | Description |
|-------|------|-------------|
| `issue_number` | int | The referenced issue number. |
| `occurrences` | list[Occurrence] | All sites the number appears (file, line, surrounding text). **Aggregate**, not first-only (FR-015). |
| `classification` | `GatingClass` | Derived from the aggregate of all occurrences (see below). |

### Value Object: `GatingClass`

| Value | Gating? | Derivation signal |
|-------|---------|-------------------|
| `implementation_target` | **yes** (gating) | Default when no explicit non-gating signal applies to any occurrence, OR at least one occurrence is an implementation-target citation (impl-target wins). |
| `context_only` | no | Every occurrence carries an explicit context marker (`Follow-up:`, `baseline-red`, `see #`, `parent`, `epic`, …). |
| `pr_or_commit_ref` | no | A leading `PR `/`pull` token (hash form) or a `/pull/<n>` URL. |

**Invariants**:
- Default is `implementation_target` (fail-safe, FR-011). Demotion requires a positive explicit signal on *every* occurrence.
- Classification is a pure function of the aggregate occurrence set (FR-015) — deterministic, no I/O.
- Cross-repo issue references (`owner/repo#NN`, other-repo `/issues/<n>` URL) remain excluded from discovery entirely (pre-existing behavior, unchanged).

## Entity: Issue-Matrix Row (`issue-matrix.json`)

| Field | Type | Description |
|-------|------|-------------|
| `issue` | int | Issue number (row key). |
| `title` | str | Human title (scaffolded placeholder until filled). |
| `verdict` | `IssueMatrixVerdict` | The mission's relationship to the issue. |
| `evidence` / `evidence_ref` | str | Evidence text/link supporting the verdict. |

**Behavior**:
- A row is *required* (gating) iff its reference classifies `implementation_target` (FR-013 —
  classification governs row-requirement). Non-gating classifications are recorded as non-gating rows
  (or omitted from the gated set) and never block approval.
- A row is *resolved* iff its verdict is terminal for the current transition (FR-013 — verdict
  governs row-resolution).

## Value Object: `IssueMatrixVerdict` (StrEnum)

| Value | Gating at `approved`? | Terminal at `done`/merge? | Meaning |
|-------|----------------------|---------------------------|---------|
| `fixed` | resolves | yes | The mission fixed the issue. |
| `verified-already-fixed` | resolves | yes | Verified already fixed upstream. |
| `deferred-with-followup` | resolves | yes | Deferred; evidence must carry a `#NNN` or `Follow-up:` token. |
| `in-mission` | resolves at `approved` | **no** (rejected at `done`) | Work owned within this mission, must resolve before `done`. |
| **`not-applicable`** *(new)* | **non-gating** | **yes (terminal)** | Cited for context / a PR reference; the mission owes no work. |

**Contract**: additive — the four legacy values parse and validate unchanged (`IssueMatrixVerdict(value)`).
No migration. `not-applicable` is the only value that is both non-gating at `approved` and terminal
at `done`/merge.

## Relationships

```
IssueReference (discovered, classified)
      │  classification governs whether a matrix row is REQUIRED
      ▼
Issue-Matrix Row  ──carries──►  IssueMatrixVerdict (governs whether the row is RESOLVED)
      ▲
      └── consumed identically by: approval blocker · merge_gates · status/doctor  (one shared classifier)
```
