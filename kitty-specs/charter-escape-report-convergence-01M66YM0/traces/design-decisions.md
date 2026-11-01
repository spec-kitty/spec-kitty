# Design decisions — charter-escape-report-convergence-01M66YM0 (#6733)

- **[2026-10-30][planning] One containment authority, three reporters.** `find_body_path_escapes` / `find_asset_path_escapes` (and the registry-aware wrappers in `charter.activation.drg_activation`) own "is this path contained"; each surface owns only where the finding goes. Cost: each reporter repeats a three-line call + message append. Benefit: a change to the rule moves all three surfaces at once, and no surface can quietly disagree.

- **[2026-10-30][implement] Status collects escapes before `merge_three_layers`, mirroring the doctor.** Ordering is load-bearing: a merge that refuses (`OrgDRGConflictError`) or crashes would otherwise take the escape findings with it, which is exactly how "more breakage" turns into "fewer findings" — the defect the merge/conflict split in this collector already fixed once.

- **[2026-10-30][implement] A failed check reports itself, never an empty list.** Each helper wraps only its own predicate call and appends `org-layer <kind> check failed: <exc>`; the distinction between "checked, clean" and "could not check" is the whole point of the `errors` channel. A bare `except: pass` here would recreate the original defect one layer down.

- **[2026-10-30][implement] No new `org_layer` key (NFR-003).** Verified by `test_status_json_schema_is_unchanged`, which pins the key set. Rationale recorded in the collector docstring: a payload slot nothing renders is inert schema, and status already prints every `errors` entry.

- **[2026-10-30][implement] Validator: `body_path_escape`, `artifact_type="drg"`, `artifact_id=<node>`, `file=<drg/fragment.yaml>`, message = the predicate's.** Structured like the asset leg so `charter org validate`'s renderer needs no change; `charter org validate` exits non-zero through its existing "any error" path.

- **[2026-10-30][implement] The predicate is fed the *loaded* fragment, verbatim.** `find_body_path_escapes` judges `authored_nodes` only, and that distinction lives on the loader's instance (a re-validated copy would lose it and start judging discovered nodes, whose `body_path` is relative to their own file). Pinned by `test_a_discovered_artifact_body_path_is_not_judged_here`, which also asserts the discovered node really carries the escaping string so the test cannot pass for the wrong reason.

- **[2026-10-30][implement] The corpus scaffolds packs with `charter org init`.** Hand-built or fixture-copied packs carry unrelated faults (`org-charter.yaml` schema drift, no `pack.yaml`), which would make the validator adapter's "contained ⇒ ok" cell measure something other than containment. The canonical scaffolding command keeps each case's only fault the one it declares.

- **[2026-10-30][closeout] Commit slices: test-before-fix per surface, then corpus, docs, artefacts.** The compaction is a snapshot chain over a fixed tree (`git rev-parse HEAD^{tree}` identical before and after, `7` additive commits, no merge commits), and the ATDD boundary is preserved inside it: each `test(...)` commit is the red half and each `fix(...)` commit the green half, in that order.
