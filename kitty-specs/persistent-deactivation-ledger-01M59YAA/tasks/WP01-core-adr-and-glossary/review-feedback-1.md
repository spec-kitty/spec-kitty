# WP01 review feedback (cycle 1)

Reviewer: claude (reviewer-renata). Verdict: changes requested. The ADR, the three amendment
blocks, the inventory/index rows and the retrieval index are accurate and complete; every link and
anchor resolves; the docs checks are green. Two glossary statements are wrong and must be fixed,
because `docs/context/charter.md` is the canonical term authority later WPs, doctor messages and
docs copy from.

1. [MEDIUM] docs/context/charter.md:96 - The Activation ledger definition says the effective set is
   "never less than its [Required floor]". That is invented behaviour: the floor only protects
   required ids from being subtracted by the deny-list (data-model.md §2: `D* = resolve_deny(D) - R`;
   conformance row `[A] | ∅ | {R1} | {A}` and `[] → ∅`). An allow list `[A]` with `R = {R1}` has
   effective set `{A}`, which is less than the floor. - Required fix: replace the clause with wording
   that matches the algebra, for example "The effective set of a kind is its allow state minus its
   [Effective deny](#effective-deny); a deny entry never subtracts a [Required floor](#required-floor)
   id."

2. [MEDIUM] docs/context/charter.md:142 - The Required floor **Location** names
   `src/charter/offering/packs/`. The floor reader (`_iter_org_charter_docs`,
   `read_org_required_ids`) lives in `src/charter/activation/org_pack_discovery.py`
   (data-model.md §4), and the new ADR itself says "the floor lives in activation" (Consequences,
   SPDD residual / research D-07, C-002). - Required fix: point the Location at
   `src/charter/activation/org_pack_discovery.py` (keep `org-charter.yaml` (`required_<plural>`)).

3. [LOW] docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md:292 - The
   Confirmation section records the conformance cases but not the full operator ruling
   `conformance_corpus`: the corpus lives in the ported test cases and the open-packs content, the
   cases are meant to port to open-packs and the Java offering, and there is no separate export
   script. - Required fix: name the ruling and add that sentence (one line).

Not defects (checked): the supersede is scoped to 2026-07-18-1 Decision 2 only; the amendments are
append-only (nothing above them changed); FR-021 recording rule (row only when
`.kittify/migration-ledger.jsonl` exists, `not_recorded` otherwise) matches WP08 T051.2 and the
carry-forward note; the Activation ledger "Do NOT use when" guard names the Migration Ledger, the
decision ledger and the status event log; front matter and description length (162) are valid.
