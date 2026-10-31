# Discovery Findings — charter write round-trip latency (#6506)

All figures below were measured **before any code change**, on this checkout of `main` at
`dfe9efb0e8`, against a scratch git project holding a copy of this repository's own
`.kittify/` (13 MB, `charter.yaml` 165,004 bytes / 1,937 lines, `catalog.references` 264
entries). Reproduction:

```bash
mkdir -p /tmp/sk6506-repro && cd /tmp/sk6506-repro && git init -q .
cp -r <clone>/.kittify . && cp -r <clone>/packs .
time spec-kitty charter deactivate tactic analysis-extract-before-interpret
time spec-kitty charter activate   tactic analysis-extract-before-interpret
time spec-kitty charter list
```

## Decision 1 — The dominant cost is the compiled-charter write path, not the compiler

Observed warm wall times: `deactivate` 17.3 s, `activate` 17.9 s, `charter list` 2.6 s.

Instrumented attribution of a full `deactivate` run (19.1 s under instrumentation;
inclusive times, so rows nest):

| Cost centre | Time | Share |
|---|---|---|
| `recompile_catalog` | 15.0 s | 78 % |
| └ `write_compiled_charter` | 10.2 s | 53 % |
| └ └ `prepare_charter_yaml_section` ×2 | 8.6 s | 45 % |
| └ └ └ `render_yaml_document` ×2 | 7.6 s | 40 % |
| └ └ └ └ `_yaml_value_events` (96 calls) | 4.3 s | 23 % |
| └ └ └ └ `_render_mapping_document` (3 calls) | 4.3 s | 23 % |
| └ `compile_charter` | 2.8 s | 15 % |
| └ └ `_build_references` | 1.9 s | 10 % |
| └ `_preserved_generated_at` (one extra full load, for one scalar) | 1.2 s | 6 % |

**Decision.** Target the write path. `compile_charter` is the second-largest term but it is
the single compiler authority (charter C-001/C-004) and out of scope per C-004.

## Decision 2 — The writer re-parses and re-emits the whole document about ten times per section write

Unit costs measured directly on the real document:

| Operation | Cost |
|---|---|
| one round-trip `load` of `charter.yaml` | 290 ms |
| one `dump` of the parsed document | 315 ms |
| `scan` of the text | 144 ms |
| `yaml_documents_equal(original, changed)` (whole document) | 1.20 s |
| `_yaml_value_events(whole document)` | 593 ms |
| `render_yaml_document` unchanged (early return) | 261 ms |
| `render_yaml_document` changed, one section | 4.67 s |
| `render_yaml_document` changed, two sections back to back | 9.10 s |

Step-level breakdown of one changed `render_yaml_document`:

| Step | Cost |
|---|---|
| `load(before)` | 293 ms |
| **whole-document `yaml_documents_equal` precheck** (always fails when something changed) | 1 204 ms |
| `compose(text)` | 205 ms |
| `_mapping_spans(text)` | 152 ms |
| `_render_owned_entries` (deepcopy + full dump) | 366 ms |
| `compose(rendered)` | 218 ms |
| `load(rendered)` | 249 ms |
| `_mapping_spans(rendered)` | 155 ms |
| per-changed-key `yaml_documents_equal` | ~500 ms |
| full splice | ~20 ms |
| **final `load` + whole-document `yaml_documents_equal` verify** | ~1 450 ms |

So ~2.4 s of the 4.67 s is two `yaml_documents_equal` calls over the entire document, and
each of those costs ~1.2 s because the fallback **dumps the whole value and re-parses it into
an event tuple** to compare it. The two sections (`catalog`, `metadata`) are written by
separate `update_charter_yaml_section` calls, so this whole cycle runs twice with no sharing.

## Decision 3 — Make the equality cheap rather than remove the checks

The two whole-document comparisons are load-bearing:

- the precheck is what makes a no-op write return the original bytes (no mtime churn);
- the final verify is the "Cannot preserve YAML aliases or section boundaries" guard.

Removing either would weaken a real invariant. Instead, `yaml_documents_equal` is reimplemented
as: try `==`; on failure, walk both values structurally (mappings by key set, sequences by
index, `is`-identical subtrees as equal) and only fall back to the existing
dump-and-reparse event comparison for the *leaves* that are still materially different. The
expensive path then costs one small value, not the whole document. Prototype measurement:
`yaml_documents_equal(original, changed)` 1 189 ms → **0.8 ms**, same verdict.

Equivalence evidence: over a corpus of 120 shipped pack YAML documents (each compared with an
identical copy and with a copy missing one top-level key) the prototype produced **0**
divergences from the previous implementation. NFR-003 turns that corpus into a committed test.

## Decision 4 — One write cycle, not two

`write_compiled_charter` calls `update_charter_yaml_section` for `catalog` and then again for
`metadata`. Each call independently observes, loads, renders, prepares and applies. Merging
them into one prepared write halves the cycle and, more importantly, makes the cost of a
compiled-charter refresh independent of how many derived sections the compiler owns.

`_preserved_generated_at` is the same problem one level down: it loads the whole document a
third time to read one scalar and compare one section. Deriving it from the document the
merged writer already loaded removes that load and removes a read/write race between the two
loads (today the file could change between them; `apply_yaml_write`'s receipt only covers the
inputs observed at *prepare* time).

## Decision 5 — The 2 s charter budget is not reachable at this repository's scale, and the mission says so with numbers

`.kittify/charter/charter.md` (Performance and Scale) sets `< 2 seconds` for CLI operations
"for typical projects". On this repository's own `.kittify/`:

- `charter list`, a **pure read** that writes nothing and compiles nothing, takes 2.6 s;
- `charter activate`/`deactivate` additionally pay `compile_charter` (2.8 s) and the compiled
  charter rewrite.

So the read floor alone already exceeds the 2 s budget. Reaching 2 s for a writing command
would require re-architecting the compiler (incremental catalog update instead of a full
recompile), which C-004 excludes and which is a separate mission. The issue's own acceptance
criteria allow the alternative: *"Bring both under the 2 s budget, or record a justified
budget for repositories of this size."* This mission takes that branch and records the budget
as an ADR with the measured floor, the post-fix write cost and their ratio.

## Decision 6 — The regression test must be a count, and the timing test must be a ratio

The repository already decided this class of question twice:

- ADR `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md`: absolute wall-clock
  budgets on shared runners false-red; assert the ratio of a command median to a floor sampled
  interleaved in the same run, with every limit in `tests/_perf_helpers.py` only
  (`tests/architectural/test_perf_limit_authority.py` enforces that).
- CHANGELOG #3787: a single-shot absolute ceiling on the `next` path was retired after being
  ratcheted up four times, replaced by a content-hash cache and an off-PR measure.

The existing `tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py` follows the
first: it is a *ratio* test at fixture scale and explicitly disclaims an absolute budget,
naming "#6506" as the repository-scale gap.

**Decision.** Deliver both:
1. a **structural count** test (exact, load-independent, runs on every PR): count whole-document
   parses through the writer's public entry point and pin the maximum at 2 per section write;
2. a **repository-scale ratio** timing test using `tests/_perf_helpers.py`, asserting the
   command median over a floor sampled in the same run, per ADR `2026-10-05-2`. No absolute
   seconds anywhere.

## Open questions for plan/specify

1. Where exactly does the merged multi-section prepare live — extend
   `update_charter_yaml_section`, or add a sibling `prepare_charter_yaml_sections`? The
   constraint is INV-9 (one writer) plus the existing `remove=`/section-validation contract.
2. Is `_preserved_generated_at` derivable from the merged writer's loaded document without
   widening `write_compiled_charter`'s signature in a way that changes its callers?
3. What is the committed budget constant for the repository-scale ratio test, and does it need
   a new `tests/_perf_helpers.py` limit (which would also need the authority test updated)?
4. Which ADR number/date to use for the recorded budget, and whether `docs_index` +
   `freshen_adr_inventory` need re-running (they do for a new ADR).

## Evidence retained

Raw profiles: `/tmp/deact.prof` (cProfile, 74.6 s instrumented, 159 M calls) and the
wall-clock attribution harnesses `/tmp/instr.py`, `/tmp/instr2.py` used to produce the tables
above. They are throwaway diagnostics, not committed: the committed tests (FR-004, FR-005)
reproduce the two quantities that matter — round trips per write, and command-over-floor ratio.
