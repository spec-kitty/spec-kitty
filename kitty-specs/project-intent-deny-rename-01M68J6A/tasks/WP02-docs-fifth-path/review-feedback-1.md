# WP02 review cycle 1 — changes requested

The shape is right: Decision 4 gains the fifth path and states its limit, the amendment records the
ruling and the rejected alternative, AGENTS.md and the command reference agree, the changelog entry is
impact-first with before/after at 950 characters, and the docs-retrieval index picked up the new
anchor (`errors=0`). Three wording findings, all in the normative ADR text or the rule bullet it
mirrors — the ADR is what a maintainer will quote, so these have to be exact.

## D1 (medium) — the gate sentence now contradicts the fifth path

Decision 4's guard paragraph still says the gate "proves none removes a deny entry". The rename *does*
remove an entry (the old spelling) while adding another. As written, the ADR says both "five paths
change a deny list, one of them removes an entry" and "no path removes an entry".

Fix: qualify the claim, e.g. "proves that no migration or built-in preset removes a deny entry other
than by the pinned rename".

## D2 (low) — "the alternative ... is the defect it closes" names the wrong thing

"The alternative" has no antecedent: the sentence contrasts "rewriting the id" with nothing. What was
previous behaviour, not an alternative.

Fix: "leaving the entry stale — reported as `DENY_UNKNOWN_ID`, with the artifact back in force — is
the defect this closes."

## D3 (low) — AGENTS.md still says migrations never touch a deny key

The bullet ends "...mission-type seeding and migrations never touch a deny key, and synthesis reaches
one only through that rename." The `4.0.0rc8_project_intent_directive_rename` migration reaches one
through exactly that rename, so the first half is false as written.

Fix: "...never touch a deny key except through that rename" (and drop the trailing synthesis clause,
or keep it — but the exception must be in the sentence that makes the universal claim).

## Confirmed, no change needed

- The `updated:` / **Status:** lines carry 2026-10-31, and the amendment is appended in the file's
  style.
- The superseded residual is struck through and points at the amendment, so the ADR keeps one story.
- The `charter-commands.md` bullet is user-facing (what to do) and correctly says a declared-id entry
  is untouched.
- The changelog entry cites `(#6565)`, leads with the impact, and has before/after.
