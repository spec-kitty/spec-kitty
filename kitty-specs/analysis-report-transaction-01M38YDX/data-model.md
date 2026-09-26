# Report transaction data model

- Material manifest: stable logical input key, repository-relative path or qualified immutable dependency identity, content digest, absent sentinel. One authority serves recording and freshness.
- Git snapshot: declared branch, HEAD commit, unrelated staged entries including flags, relevant working input digests.
- Transaction outcome: committed or unchanged, failure before write, written-uncommitted, or committed-unqualified requiring recovery. Include commit SHA only when observed, never infer from a disk write.
- Report artifact: existing schema, structured findings and material input hashes; no domain replay protocol changes.
