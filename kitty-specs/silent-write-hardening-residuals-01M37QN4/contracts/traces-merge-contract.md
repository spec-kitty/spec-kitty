# Contract — traces merge-driver hardening (Finding C)

**Surface**: `cli/commands/merge_driver.py` — `_TRACE_FENCE_MARKER`, `_split_trace_blocks`, `_trace_block_key`, `_drop_stale_theirs_trace_blocks`. **Out of scope (C-002)**: `union_trace_texts` whole-block dedup and the overall fence/section contract.

## Guarantees

1. **Tilde fences recognized.** Fence detection matches `~~~` equivalently to ```` ``` ````. A heading-like line inside a `~~~`-fenced block is not treated as a section boundary.
2. **Non-colliding base-comparison key.** In the 3-way base-aware stale-drop, each block's base-comparison key is the `<!-- section:ID -->` id when present, else `(first_line, occurrence_ordinal)`. Two sections sharing a heading get distinct keys; a section whose body changed keeps its key (so `theirs_unchanged`/`ours_diverged` still fires).
3. **No data loss (NFR-004).** Merged output loses 0 sections and preserves within-section content byte-for-byte. Over-inclusion is acceptable; loss is not.
4. **Whole-block dedup untouched.** `union_trace_texts`'s byte-identical full-block dedup is unchanged; the base-comparison key is a separate, body-insensitive key (no full-block hash there).

## Acceptance (red-first)

- **AC-C1**: a traces block fenced with `~~~` containing a heading-like line is not split at that line. Fails against the backtick-only regex, passes after. (SC-003)
- **AC-C2**: two distinct sections with an identical heading are keyed distinctly; neither is dropped or mis-attributed in the stale-drop. Fails against the `setdefault(block[0])` collision, passes after. (SC-003)
- **AC-C3**: an unchanged-theirs / diverged-ours single-heading section is still correctly stale-dropped (3-way base-awareness intact — no regression from the key change).
- **AC-C4**: byte-identical whole-block dedup in `union_trace_texts` is unchanged (existing #4894 section-union test stays green).
