# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi · Provenance is checked once, at vendor time, not on every user fetch: the pinned digest stays the trust root and the user runtime never needs gh (NFR-003, C-003).

2026-11-01 · pi · A file:// repository skips the provenance step because it carries no attestation; a non-GitHub https repository refuses with SERVICE_ATTESTATION_UNSUPPORTED and --no-attestation is the explicit escape.

2026-11-01 · pi · The provenance command pins both --signer-workflow and --source-ref: without them gh would accept an attestation from any workflow of the repository or any ref.
