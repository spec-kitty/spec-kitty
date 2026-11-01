# Contracts

This mission adds **no** new or changed contract.

`contracts/synthesis-envelope.schema.json` — the `charter synthesize --json` envelope
schema — keeps its field names, types, required set and enum values. The only observable
change is the *spelling* of the repository-relative path strings in `files_written`,
`files_planned`, `planned_deletes` and `written_artifacts[].path`: they are POSIX
(`.kittify/charter-packs/PROVENANCE.md`) on every operating system, where Windows
previously rendered `\` (#6277). A JSON schema expresses a string as `type: string` and
cannot, and does not need to, encode the separator; the contract that changes is the
documented meaning of those strings, and it is recorded in `spec.md` (C-001) and in the
`[Unreleased]` changelog entry.
