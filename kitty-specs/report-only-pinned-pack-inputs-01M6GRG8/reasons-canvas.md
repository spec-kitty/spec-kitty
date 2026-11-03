# REASONS Canvas — report-only-pinned-pack-inputs-01M6GRG8

## Requirements

One sentence: `record-analysis --report-only` must record in a clone that ran the documented
`make sync-packs`, without weakening the refusal for material inputs that really have no committed
state (#7128).

- **Problem**: the report transaction's "material input with no committed state" rule
  (`report_transaction.py:317`) counts the gitignored, pin-fetched `packs/<name>/` tree as dirty, so
  the stricter transactional recording mode refuses with `DIRTY_ANALYSIS_INPUT` in exactly the
  configuration it exists for.
- **Acceptance criteria**: see `spec.md` FR-001..FR-006 and SC-001..SC-004. Must (Safeguards): a
  pack tree that no longer matches its committed pin still refuses; the pin file is itself
  committed authority (dirty/absent pin grants nothing); untracked ignored material input outside a
  verified pack tree still refuses. Should (Norms): a refusal names the offending paths. May
  (Approach options): registering the pin file as a material input — deferred, out of scope.
- **Definition of done**: a red-first end-to-end CLI test that fails on `main` and passes with the
  fix; the existing `ignored_input` and `DIRTY_ANALYSIS_INPUT` cases pass unedited; the per-PR
  changelog fragment; docs updated where the flag's behaviour is described.

## Entities

One sentence: the domain concepts are the pin, the fetched tree it content-addresses, the material
input set, and the report qualification the transaction establishes.

- **Pack pin** (`packs/<name>.source.yaml`): tracked lockfile recording `repository`, `commit`,
  `subtree`, `tree_digest` and `snapshot_sha256`; owned by `charter.offering.packs.pack_pin`.
- **Fetched pack tree** (`packs/<name>/`): gitignored directory placed by `make sync-packs`; its
  committed state is the pin, not a blob in this repository.
- **Material input**: a path whose content the analysis report hashes
  (`specify_cli.analysis_inputs.collect_material_inputs`).
- **Report transaction / qualification**: the preflight-verify-commit sequence in
  `record_report_transaction` that makes a retained report trustworthy (`report_is_qualified`).
- **Dirty material input**: a material input whose committed state the transaction cannot establish
  — index/worktree dirt on a material path, or a material path present but untracked.

## Approach

One sentence: add one exemption — a pin-verified pack tree — computed from committed authority, and
scope it by repo-relative prefix.

- **Chosen**: for each registry pack root, exempt paths under it only when its sibling pin file is
  tracked and clean and `verify_pack_pin(pin, root)` passes with `pin.subtree` naming that same
  root. Reuses the existing pin parser and digest authority (C-002), stays offline (NFR-001), fails
  closed on every doubt (NFR-002).
- **Rejected**: excluding gitignored paths wholesale — it would admit operator-authored ignored
  material input and defeat the existing `ignored_input` refusal. Rejected: parsing the pin from
  `HEAD` with a second parser (duplicate authority). Rejected: hard-coding `packs/internal` (the
  registry, not a literal, names the org pack).

## Structure

One sentence: one new predicate at the analysis-input seam, one filter in the preflight.

- `specify_cli/analysis_inputs.py`: the predicate that returns the repo-relative roots of
  pin-verified pack trees (single place that knows the pin↔tree convention).
- `specify_cli/git/report_transaction.py`: the untracked-material rule subtracts those roots; every
  other rule in the preflight is untouched.

## Operations

One sentence: the preflight gains a read-only, offline verification and no new write.

- On the `--report-only` preflight only, when an untracked material path exists, hash any candidate
  pack tree against its committed pin (measured 8 ms for the 67-file tree here), then either
  exempt it or keep the strict refusal.

## Norms

One sentence: the change is additive to a fail-closed preflight and may not relax any other rule.

- No gate, test, allowlist or assertion is weakened (C-001).
- Smallest viable diff; no refactor of the transaction or of the fetch machinery (C-003).
- Charter vocabulary: pack, pin, material input, qualification (C-004).

## Safeguards

One sentence: four negative controls guard the positive one.

1. A byte changed inside the pack tree → refuse, naming the file.
2. Pin file dirty or absent → refuse, naming the pin.
3. Unpinned ignored material input present → refuse (the pre-existing `ignored_input` case).
4. Pin `subtree` naming a different root → no exemption for that root.
