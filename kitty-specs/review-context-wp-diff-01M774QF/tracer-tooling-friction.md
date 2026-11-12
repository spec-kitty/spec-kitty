# Tracer: tooling friction (#7578)

Seeded 2026-11-12. Append dated entries: what got in the way, the workaround, and a suggested fix.

- 2026-11-12: `spec-kitty spec-commit` writes its own commit message with no way to add trailers (Co-Authored-By). The required attribution is applied during history cleanup instead.
- 2026-11-12: the rc7 gist could not be fetched raw (gist.githubusercontent.com is blocked by the session proxy). It was read through WebFetch summaries, so quotes are paraphrased.
- 2026-11-12: `meta.json` `purpose_context` (written at create) says the Mission "inlines a bounded diff". Ruling Q1 later chose commands only. The specify contract forbids rewriting creation metadata (no metadata-update lifecycle event), so the stale sentence stays and is noted in the PR. Suggested fix: a sanctioned metadata-amend event.
- 2026-11-12: `finalize-tasks` reports literal owned files that do not exist yet and asks for `create_intent`. The tasks-packages template does not mention `create_intent`, so every new file needed a second pass.
