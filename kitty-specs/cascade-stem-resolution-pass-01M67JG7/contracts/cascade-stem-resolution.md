# Contract: the cascade's stem-resolution batch (#6777)

Pinned by `tests/charter/activation/test_cascade_stem_resolution_6777.py` (deterministic:
call counts and ordering, no wall clock) and by
`tests/charter/activation/test_stored_spelling_6527.py::test_the_cascade_case_runs_under_the_suite_wide_timeout`
(marker state).

## C-1 — One resolution pass per cascade run

For a single `charter activate <kind> <id> --cascade <scope>` invocation, every
DRG-URN → config-stem lookup the activation batch performs receives the **same**
`charter.activation.kind_vocabulary.ResolutionPass` instance, and that instance is not
`None`.

*Why*: `ResolutionPass` memoises layer scans and artifact id reads for one read-only pass.
A fresh pass per lookup re-walks and re-parses the whole doctrine catalog per target — on a
full `--cascade all` walk that was 121 lookups → 5309 id reads and 5028 artifact-file
parses (#6777).

*Fails if*: a lookup resolves with no pass, or two lookups carry different pass instances.

## C-2 — All reads precede the first write

Every lookup in the batch completes before the first `ActiveCharterManager.activate()` call
of that cascade run.

*Why*: `ResolutionPass`'s documented rule is that a pass never spans a write to the files
it reads; resolving up front satisfies it by construction rather than by argument. It also
means a failing read aborts before any activation is recorded, which is strictly safer than
the pre-#6777 mid-walk abort.

*Fails if*: any `resolve` event is observed after the first `activate` event.

## C-3 — Order and outcome are unchanged

Activation order stays `sorted(activated)` by kind, then each kind's DRG walk order; a
target whose activation raises `ValueError` still produces a `FAILED` entry (with its
message) and the loop continues; a successful one produces `CASCADED`. The cascade render
lines, the stored activation lists and the deny-list writes are unchanged.

*Fails if*: `test_stored_spelling_6527.py::test_writer_stores_stems_only[cascade]`'s
stored-list assertions move, or the processors' `_non_stems` check goes non-empty.

## C-4 — The case keeps one timeout authority and the slow tier

`test_writer_stores_stems_only` carries no per-test `timeout` mark (the 240 s
`pytest.ini` backstop applies), and its `cascade` case alone carries `slow`.

*Why*: #6776 added a 600 s per-test marker as an interim crutch; with the work removed the
override must not come back, and `slow` is the repository's documented tier for a >30 s
case. The module shards select `-m "not performance and not stress"`, so the marker moves
no coverage out of CI.

*Fails if*: any case of `test_writer_stores_stems_only` gains a `timeout` mark, or the
`slow` marker is removed from (or added beyond) the `cascade` case.
