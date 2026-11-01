# Research: synthesize consumes generator-shape proposals (#6385)

**Mission**: `retrospect-synthesize-generator-proposals-01M68ZKX`
**Grounded on**: `origin/main` = `dfe9efb0e8` (2026-10-31), clean tree, `main` fast-forwarded.
**Issue**: spec-kitty/spec-kitty#6385 (claimed: assignee `Ivan-Melck`, `status:claimed`,
`taken-by-human`), batch-14 triage split: application/reporting here, generation in #3947.

## D1 — The defect is live on current `main`, in both halves

Static re-verification of every line the issue cites, on `dfe9efb0e8`:

| Citation | Current `main` | Finding |
|---|---|---|
| `retrospective/generator.py` `_build_findings` | `proposals: list[GenProposal] = []` (L1188), `if generate_proposals: proposals.sort(...)` (L1362-1363) | `grep -rn "proposals.append\|proposals.extend" src/specify_cli/retrospective/` → **no hits**; `_classify_risk` (L615) has **no caller**. `create` can never emit a proposal. |
| `retrospective/policy.py` | `generate_proposals` default `True` (L169) | The flag is threaded into `_build_findings` and gates only a sort of an always-empty list. |
| `cli/commands/agent_retrospect.py` synthesize | `if _fabricated_empty or generator_record is not None: all_proposals = []` (L652-654) | The whole generator-shape record is dropped before `apply_proposals`. |
| same, warning | L601-607, warning only `if generator_record.proposals:` | A record with findings and zero proposals prints **nothing** and exits 0 — the issue's silent empty batch. |
| `reader.py` `read_gen_record` (L331) | dataclass schema, no `payload` key (`_PROPOSAL_KEYS`, L~85) | The generator shape has nowhere to say *what* to apply; `suggested_action` is free text. |
| `retrospective/schema.py` `Proposal` (L334) | `kind` + discriminated `ProposalPayload`, `ProposalId` = ULID pattern | The only shape `apply_proposals` can plan. `GenProposal.id` is `^p-[0-9]{3,}$`, so it is not a legal `ProposalId`. |

Not superseded: `git log -S "proposal application is not available for generator-shape" -- src/specify_cli/cli/commands/agent_retrospect.py`
returns only `c6c13c73db` (`#1246`), which *introduced* the warning; no later commit removes it.
The changelog has no entry for generator-shape proposal application. #1239 / #3533 (reader
disagreement) and #3537 / #3551 (diagnosis, docs) are closed and untouched by this gap; #3947
(open, `status:ready`) owns generation and is coordinated by a comment added from this Mission.

## D2 — Scope split is the triage's, not an arbitrary narrowing

The batch-14 triage comment on the issue is explicit: "generation overlaps already-linked #3947;
the application/honest-no-op half is additional scope. Please coordinate generation in #3947
versus application/reporting here before implementation, without duplicate generation work."
So `_build_findings` stays untouched (constraint C-001) and the Mission builds the seam #3947
fills. A comment recording exactly that seam was posted to #3947 before implementation.

## D3 — Decision: a structured `payload` on generator-shape proposals, not verb parsing

The issue lists two directions and calls verb-parsing `suggested_action` "fragile", adding "a
structured field would be safer". Decision:

- `GenProposal` gains an **optional** `payload` mapping, validated by the **existing**
  `ProposalPayload` discriminated union (`TypeAdapter(ProposalPayload)`) — one payload schema, not
  two (C-002, NFR-002).
- A proposal is translatable only when its `payload` is present and valid; the verb in
  `suggested_action` must agree with `payload.kind` when the verb names a typed kind, otherwise it
  is untranslatable with that reason (a disagreement is a record bug worth naming, not a silent
  guess).
- Translation produces the *same* `Proposal` type `apply_proposals` already consumes, so there is
  no new apply path, no new writer, and no change to `charter_pack_synthesizer`.
- State mapping: `auto_applicable: true` → `accepted` (the record declares it may be applied
  without further approval, which is what `auto_applicable` means in the generator contract);
  otherwise `pending`. `flag_not_helpful` proposals are auto-included by `apply_proposals` as
  today (Q2-A), so the one low-risk kind still applies without an accepted state.
- Proposal ids: `ProposalId` is a ULID pattern and `GenProposal.id` (`p-001`) is not, so a
  translated id is derived deterministically — the source `mission_id` ULID with its last three
  Crockford characters replaced by a digest of the generator proposal id. Stable across runs
  (re-running synthesize cannot double-apply or rename), legal per the schema, and unique per
  (mission, proposal id) pair; a collision is refused rather than merged.
- Evidence: `ProposalProvenance.source_evidence_event_ids` must be ULIDs. Only ULIDs mined from
  the generator evidence refs the proposal actually cites are carried, so no finding id is
  invented into an event id and the staleness check stays meaningful (empty list = no staleness
  claim, which `apply_proposals` treats as "no evidence to check", not as stale).

## D4 — Decision: honesty is additive, the exit-code contract is not

`docs/api/retrospective-schema.md` documents "omitting `--apply` always exits 0 on a valid
dry-run regardless of proposal count or detected conflicts". Changing that would be a contract
change on a P2 bug report and would break pinned exit-code tests. So the empty batch becomes
**loud, not failing**: a `diagnostics` block in the JSON envelope plus a Rich warning that names
the record shape, the finding counts, the number of proposals translated/planned, each
untranslatable id with its reason, and the next step. FR-007 pins the unchanged exit code with a
same-fixture positive control.

## D5 — Survey of the surfaces that must change together

- `src/specify_cli/retrospective/schema.py` — `GenProposal` dataclass (+ optional `payload`).
- `src/specify_cli/retrospective/reader.py` — `_PROPOSAL_KEYS` allow-list + `_proposal()` parse.
- `src/specify_cli/retrospective/writer.py` — `_gen_record_to_dict` / `_dict_to_gen_record`
  round trip; must emit `payload` **only when present** so existing records round-trip
  byte-identically (NFR-001).
- New `src/specify_cli/retrospective/generator_proposals.py` — the pure translation function.
- `src/specify_cli/cli/commands/agent_retrospect.py` — wire translation, diagnostics, and keep
  `--proposal-id` refusals accurate.
- `src/specify_cli/cli/commands/retrospect.py` — `create`'s `next_step` honesty (FR-006).
- `kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json` —
  the referenced generator-record contract gains the optional `payload` property.
- Untouched on purpose: `charter_pack_synthesizer/*` (NFR-002), `_build_findings` (C-001).

## D6 — Test surfaces (red first, through the pre-existing entry point)

- `tests/cli/test_agent_retrospect_synthesize.py` already has `_write_generator_retrospective()`
  and pins today's behaviour (`apply_mock.call_args.kwargs["proposals"] == []`). Those assertions
  are exactly the ones that must flip; the fixture is extended with a payload-bearing proposal.
- Round-trip conformance (SC-005) needs `retrospect create` → `synthesize` on one fixture
  mission. `tests/cli/commands/test_retrospect.py` (2,898 lines) already owns `create` fixtures.
- `tests/retrospective/` holds the generator/reader/writer unit tests
  (`test_generator*.py`, `test_reader*.py`, `test_writer*.py`).

## Open questions carried into plan

1. Where exactly the diagnostics block sits in the envelope — top level (`diagnostics`) vs nested
   under `result`. Decision in plan: top level, next to `status`/`outcome`, because
   `result` is a `SynthesisResult.model_dump()` owned by `charter_pack_synthesizer`.
2. Whether `--proposal-id` may name a *translated* proposal. Decision in plan: no new approval
   semantics — an `accepted` translated id works (via `auto_applicable`), a `pending` one is
   refused as pending with the remedy named; the refusal message learns the untranslatable case so
   it stops claiming application is entirely unsupported.
