# Data Model: Issue-matrix reference over-matching

## Occurrence (changed)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `source_file` | `str` | (required) | basename of the artefact |
| `line_text` | `str` | (required) | stripped line |
| `ref_offset` | `int \| None` | `None` | column of the citation in `line_text` |
| `in_gating_scope` | `bool` | `True` | artefact is `spec.md` or under `tasks/` (new) |

Invariant: `in_gating_scope=False` only demotes. A closing keyword leading into the citation
still gives `implementation_target`.

## GatingClass (unchanged)

`implementation_target` (gating), `context_only` (non-gating; "cited"), `pr_or_commit_ref`
(non-gating).

## Classification order (one function, `classify_occurrence`)

1. A non-negated closing keyword leads into the citation, giving `implementation_target`.
2. A PR token / pull URL on the line, or a backticked SHA next to the citation, gives `pr_or_commit_ref`.
3. The occurrence is out of the gating scope, giving `context_only`.
4. A line marker (`follow-up:`, `baseline-red`) gives `context_only`.
5. A positional label (`see`, `parent`, `epic`) leads in, giving `context_only`.
6. Otherwise `implementation_target`.
