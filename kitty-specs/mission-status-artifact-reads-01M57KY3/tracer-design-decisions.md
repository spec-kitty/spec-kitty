# Tracer: design decisions

- DD-1: a hand-written controller, not the generated interface. The generated `Integer sizeBytes` cannot hold a size over
  2 GiB, and a repeated `path` would be comma-joined by Spring binding.
- DD-2: the conformance cases are data (`cases.json`) that Python and Java both materialize. Symbolic links, NUL bytes,
  invalid UTF-8 and files over 256 KiB cannot be committed portably. Credentials are assembled from parts, so the
  repository never holds a literal token.
- DD-3: `ProblemBody` gains an optional `type`, emitted only by the artifact refusals, to match the reference body
  (`type: about:blank`). Existing bodies are unchanged.
- DD-4 (departs from plan.md, which said to widen `Allowlist`): the artifact reads have their own allowlist
  (`ArtifactAllowlist`) and their own source (`FilesystemMissionArtifactSource`). `Allowlist` and its tests pin "the event
  source never opens spec.md / status.json". Widening them would weaken that guarantee for the ledger reader, so it stays
  exactly as it was and is re-asserted by `ArtifactAllowlistReadmeParityTest`.
- DD-5: the strict UTF-8 check is a hand-written Table 3-7 validator, because ArchUnit rule 1b keeps `java.nio.ByteBuffer` out of
  the domain. `new String(bytes, UTF_8)` runs only after the validator accepts the bytes.
- DD-6: the casefold match of the root status records uses ASCII lowercase plus the 11 non-ASCII code points whose Python
  `casefold()` is pure ASCII (computed over all code points). This is exact for the two ASCII target names.
- DD-7: a long served content (over 4096 code points) is compared by the SHA-256 of its UTF-8 bytes, so `golden.json` stays
  small. `hashlib` is used with a justified `noqa: TID251` (a byte-for-byte body checksum; `charter.hasher` normalizes BOM and
  newlines).
- DD-8 (departs from plan answer 5): the hand-written response bodies live in `adapter.in.http.ArtifactBodies`, not in
  `adapter.in.http.dto`. `tests/ci/test_mission_status_api_build.py` pins the hand-mode `dto` package as empty while the
  service runs in generated mode (commit "keep the hand-mode dto package empty").
