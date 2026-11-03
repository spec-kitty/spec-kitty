# Discovery findings — analysis freshness vs claim-time runtime fields (#7106)

Branch/ref used for every probe: `main` @ `d18c4f1d58` (clone
`/home/exedev/work/sk-7106`, `uv` venv, real CLI via
`python -m specify_cli`).

## Evidence: the defect still reproduces on current `main`

End-to-end, in a throwaway git repo (`init` → `agent mission create --topology
lanes` → two WPs → `finalize-tasks` → `record-analysis --report-only` → two
`agent action implement` claims):

```
$ spec-kitty agent action implement WP01 --agent alice   # rc=0
$ spec-kitty agent action implement WP02 --agent alice   # rc=1
Error: analysis_report_required: ...
  Reason: stale_analysis_report
  Stale inputs:
    - material:kitty-specs/fx-01M6G9HP/meta.json
    - material:kitty-specs/fx-01M6G9HP/tasks/WP01-m1.md
```

The claim commit `chore: WP01 claimed for implementation` is exactly the diff the
issue reports:

```
 kitty-specs/<slug>/meta.json        | 4 +++-   # +vcs, +vcs_locked_at
 kitty-specs/<slug>/tasks/WP01-m1.md | 3 +++    # +base_branch, +base_commit, +created_at
```

So the issue is **not** superseded: #1764 normalised `tasks.md` status churn and
#2493 normalised pipe-table status cells, but the claim writes to
`tasks/WP##-*.md` (frontmatter) and `meta.json`, which neither fix covers.

`git log -S` on the relevant symbols shows the runtime-state eviction (#2816 /
wp-runtime-state-eviction) moved the claim *triple* (`shell_pid`, `agent`) into the
event log, but left the workspace-provenance triple (`base_branch`,
`base_commit`, `created_at`) written into the WP prompt by
`lanes/implement_support.create_lane_workspace`, and the `vcs`/`vcs_locked_at`
lock written into `meta.json` by `implement_support.ensure_vcs_locked`. Both
writes still land inside the analysis closure.

## Evidence: where the fingerprint is built

- `src/specify_cli/analysis_inputs.py::collect_material_inputs` — the material
  closure. `meta.json` is hashed whole (`_artifact_hash_entry`); every
  `tasks/WP*.md` is hashed as `sha256(json(metadata - MUTABLE_FIELDS) + body)`.
- `src/specify_cli/migration/strip_frontmatter.py::MUTABLE_FIELDS` — the exclusion
  list, whose `STATIC_FIELDS` sibling *includes* `base_branch`, `base_commit`,
  `created_at`; those keys are therefore fingerprinted today.
- `src/specify_cli/analysis_report.py::check_analysis_report_current` — the gate.
  It only consults the material closure when the recorded report carries
  `material_manifest_version` (i.e. it was recorded through
  `record_report_transaction`, the `record-analysis --report-only` path the issue
  uses).
- `src/specify_cli/cli/commands/agent/workflow.py::_require_current_analysis_report`
  — the refusing entry point (`agent action implement`).

## Decisions

**D1 — Exclusion, not relocation.** Of the issue's two options ("exclude the
runtime fields from the fingerprint" vs "record the claim's runtime fields outside
the fingerprinted files"), the first is chosen. Relocating workspace provenance out
of the WP prompt would touch `create_lane_workspace`, `WorkspaceContext`,
`review/baseline.py` and the claim-commit path — a bounded, tested surface far wider
than the defect. The fingerprint side has one caller and a normalisation precedent
(`_normalize_tasks_md`, #1764/#2493).

**D2 — Reuse the declared field sets, mint no new list.** The issue's general fix is
"fingerprint a declared set of planning fields". Two such declarations already
exist and are guarded:

- `src/specify_cli/dossier/hasher.py::WP_STATIC_PROJECTION_FIELDS` — the authored
  WP contract; `tests/dossier/test_canonical_hash.py` proves every `WPMetadata`
  field is consciously classified into static / runtime / descriptive. It already
  contains every field the issue names as the positive control (`subtasks`,
  `dependencies`, `requirement_refs`, `owned_files`), and excludes
  `base_branch`/`base_commit`/`created_at`/`planning_base_branch`/
  `merge_target_branch`/`branch_strategy`.
- `src/kernel/vcs_lock.py::VCS_LOCK_META_FIELDS` — the single VCS-lock field-set,
  "no inline-literal duplicates elsewhere (NFR-002)".

**D3 — Projection, never a strict re-parse.** Keep reading the prompt with
`FrontmatterManager` (tolerant) and project the raw mapping onto the declared
planning fields. Switching to `WPMetadata` (`extra="forbid"`) inside the closure
would make legacy prompts carrying retired keys raise `Invalid WP definition` — a
new false refusal class in the gate.

**D4 — `meta.json` keeps every non-VCS key.** Only `VCS_LOCK_META_FIELDS` are
dropped from the `meta.json` hash; `target_branch`, `topology`, `mission_id`,
`status_phase` and friends keep staling the report.

## Open questions (resolved during planning)

- Does the report recorded *without* `--report-only` change behaviour? No: without a
  material manifest the gate never consults this closure (C-003 keeps that).
- Does a narrowed WP projection weaken addition/removal detection? No: the closure's
  key set (`material:<path>`) already covers a WP file appearing or disappearing.
- Blast radius of the reuse: `dossier.hasher` is imported lazily inside the WP-file
  branch of `_entry`, so the analysis closure gains no import-time dependency on the
  dossier package.

## Design revision after the independent planning review (2026-11-03)

An independent reviewer (`openai-codex/gpt-6.1-sol`, read-only squad pass)
attacked the first design — an allow-list projection onto
`dossier.hasher.WP_STATIC_PROJECTION_FIELDS` — and raised three findings that
changed it. Recorded here because the reviewed plan no longer describes what
shipped (DIRECTIVE_010: deviations are documented, not silent).

**R1 — the closure still followed `tasks/<wp>/` runtime artifacts (blocking).**
`collect_material_inputs` recursed into every descendant of `tasks/`, and
`tasks/<wp>/` is where a review cycle writes `review-cycle-N.md`,
`review-feedback-N.md` and `baseline-tests.json`. So a rejected work package
could never be re-claimed: the rework's own bookkeeping staled the report. The
issue names this symptom ("every rework re-claim"). Fix: planning content under
`tasks/` is flat, so the closure includes the directory sentinel plus every
non-directory entry and never follows a per-WP sub-directory.

**R2 — an allow-list silently stops watching authored fields (blocking, policy).**
The projection would have newly ignored 17 keys the gate watches today —
`status`, `agent_profile`, `model`, `role`, `reviewer*`, the descriptive
`mission_*`/`feature_slug`/`wp_code` set, and the WP's landing instructions
(`planning_base_branch`, `merge_target_branch`, `branch_strategy`) — plus every
unknown legacy/custom key. That is a widening of what the readiness gate ignores,
i.e. a governance decision for the maintainer, not a repair. The dossier's
classification is the *content-hash* contract, not the *analysis-gate* contract.
Rejected in favour of the issue's first option: exclude exactly the declared
runtime/claim keys.

**R3 — `vcs` should be normalised, not dropped (blocking-ish).**
Dropping the whole lock would also hide an unexpected backend value. Fix: absent
`vcs` and `git` are the same state (git is the only supported backend), any other
value is fingerprinted as written, and only the lock timestamp is dropped.

**Consequence for the plan's D-1/D-2** (the shipped design):

- WP prompt: exclude `MUTABLE_FIELDS` + the newly declared
  `frontmatter.WP_CLAIM_PROVENANCE_FIELDS` (`base_branch`, `base_commit`,
  `created_at`). `create_lane_workspace` now builds its provenance dict from that
  same tuple (`dict(zip(..., strict=True))`), so the exclusion and the writer
  cannot drift. Every other key — including `planning_base_branch`,
  `merge_target_branch`, `branch_strategy`, `status`, `agent_profile`, `model`,
  `role` and any unknown legacy key — stays watched.
- `meta.json`: `vcs` normalised (absent == `git`), lock timestamp dropped, every
  other key watched.
- `tasks/`: flat planning surface only; per-WP runtime directories excluded.

Residual, accepted: a *future* runtime writer of a new WP-prompt key would stale
the report again (the allow-list would have closed that class by construction).
That recurrence is visible and loud — the gate names the file — whereas silently
ignoring an authored planning field is not. The recurrence path is bounded by
`WP_CLAIM_PROVENANCE_FIELDS`: extending the claim's stamp means extending that
tuple, which the writer consumes.
