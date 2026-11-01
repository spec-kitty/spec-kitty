---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: frontmatter-contract-completion-6931-01M6BVXW
mission_id: 01M6BVXWKTRSD7WMYEY3SM65HC
generated_at: '2026-11-01T15:51:31.008691+00:00'
analyzer_agent: python-pedro
input_artifacts:
  spec.md:
    path: kitty-specs/frontmatter-contract-completion-6931-01M6BVXW/spec.md
    sha256: 66263d4c6df5d54d1a8965f88bcfa589c315fbda706c966983b004078c35851d
  plan.md:
    path: kitty-specs/frontmatter-contract-completion-6931-01M6BVXW/plan.md
    sha256: c2a3a6f977a0b9bdec41b922586437bf2525ddc217556f42f366d86e4dd133cf
  tasks.md:
    path: kitty-specs/frontmatter-contract-completion-6931-01M6BVXW/tasks.md
    sha256: b8c69cee31d3225443fec5d5e6b5ba1de584a0448a45e4beab76ac019816fc34
  charter:
    path: /home/exedev/work/sk-6931/.kittify/charter/charter.md
    sha256: 1bf06fd2403c9f4cef7dfc2d36208df2530aeb89910c96368816240f3cbdf87d
---
# Analysis Report — frontmatter-contract-completion-6931-01M6BVXW

Cross-artifact check of `spec.md`, `plan.md`, `tasks.md` and the five WP prompts
against issue #6931 and ADR 2026-10-31-1 D-7. Performed before implementation.

## Coverage

| Spec requirement | WP | Verdict |
| --- | --- | --- |
| FR-001 one contract module | WP01 | covered |
| FR-002 vocabularies mirrored | WP01 (+ parity test) | covered |
| FR-003 `kind` on every published page | WP04 | covered |
| FR-004 Divio `type` folded into `kind` | WP03 (readers) + WP04 (corpus) | covered — split deliberately so readers move first |
| FR-005 `doc_status` normalisation | WP04 | covered |
| FR-006 `updated` instant | WP04 | covered |
| FR-007 validator gate | WP02 | covered |
| FR-008 body-immutability proof | WP04 | covered |
| FR-009 reader port | WP03 | covered |
| FR-010 `docs query` still answers | WP03 | covered |
| FR-011 deferral recorded | WP05 | covered |
| NFR-001..005 | WP02, WP04 | covered |
| C-001..006 | all | covered; C-006 is asserted by the PR body, not by code |
| SC-001..006 | WP02..WP05 | covered |

No unmapped functional requirement. No WP cites a requirement the spec does not
define.

## Consistency findings

1. **Deliverable 4 of the issue cannot be executed as written.** "Delete
   `description_length_check.py` … once `dockitty-validate-frontmatter` covers them
   (D-6)" is conditioned on a tool absent from `main`. Spec FR-011 turns that into a
   recorded deferral rather than a blind deletion; WP05 owns the record. This is a
   scope reading, not a scope reduction: the issue's own wording gates the deletion.
2. **Done-when 1 is unrunnable, not merely red.** It invokes a binary and a config
   path that do not exist (`dockitty-validate-frontmatter --astro-config
   site/astro.config.mjs`). No local gate can make it green. SC-006 records the
   substitution: the local gate checks the *same contract*, and the doc-kitty gate
   stays named as not run. C-006 forbids presenting the local gate as that gate.
3. **Done-when 2 ("the body-hash test from S-4b still passes") has no referent.**
   #6929 is unstarted, so the test does not exist. WP04 delivers an independent
   immutability proof (baseline + transformer property), which also satisfies
   #6929's intent for the files this mission rewrites.
4. **D-7 vs D-8 conflict on two pages.** `point_in_time → durable` (D-7) would
   publish two `plans/engineering-notes/` pages that D-8 marks `draft` and
   unpublished. Resolution recorded in the contract: the D-8 subtree rule wins for
   `plans/engineering-notes/`, `plans/investigations/`, `plans/research/`. Flagged
   for the maintainer in the PR body as a judgement call affecting 2 files.
5. **`kind: Persona` is not available for the 20+ persona pages** without authoring
   `role`/`goals`/`responsibilities`, which doc-kitty's gate makes mandatory for that
   kind. Classifying them `Persona` would ship a red gate; they take `Explanation`.
   Recorded in `## Deferred`.
6. **Ownership partition.** WP03 owns the three reader modules and the two generated
   artifacts; WP04 owns the corpus subtrees; WP05 owns the changelog, the gate page
   and `description_length_check.py`. The migration writes files in WP03's and WP05's
   trees too (the corpus is migrated whole); that is disclosed here rather than
   sharded, because a partial corpus migration cannot be green.

## Ambiguities resolved by reading, not by guessing

- Which pages are "published sections": the existing resolver's answer (670 pages,
  `archive/`/`reports/`/`convergence/` out). No new list.
- Whether `type` may stay as a Divio value: no — upstream doc-kitty reads `type` as
  the section (ADR-0009), so a Divio value becomes a wrong section name; the 198
  values fold into `kind` and the readers move to `kind`.
- Whether unknown `kind`/`doc_status` fail: no — upstream warns, so this gate warns.

## Verdict

Ready for implementation. No blocking ambiguity that requires a maintainer decision
before coding; the two decision-shaped items (finding 4, finding 5) are recorded for
the PR body.
