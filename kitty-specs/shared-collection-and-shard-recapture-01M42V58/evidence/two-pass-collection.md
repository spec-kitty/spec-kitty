# Evidence: two-pass collection (planning check)

**Date**: 2026-10-04. **Checkout**: `issue-5559-shared-collection-and-shard-recapture`, code identical to the primary branch (`main`) at `b2c466d7d1`. **Interpreter**: the repository `.venv`.

Two consecutive `collect_universe()` calls in one process, each with its own fresh temporary `HOME`, compared as sorted `(nodeid, relpath, markers)` tuples.

| Measure | Pass 1 | Pass 2 |
|---|---|---|
| Wall time | 95.3 s (cold) | 21.6 s (warm) |
| Records | 54,723 | 54,723 |

- Differences between the passes: 0.
- Serialised size of one universe: about 10.7 MB of JSON.

**Conclusion**: no collected test id or marker set depends on the temporary home directory, so a stored universe can equal a fresh one (NFR-005 is satisfiable). The record size means the store holds one record and evicts older ones (research D-03).
