# WP01 review feedback — cycle 2 (orchestrator reopen, before the harness freeze)

Cycle 1 approved WP01. The reviewer raised three non-blocking notes and pointed out that the harness freezes after approval (NFR-001). The orchestrator reopens WP01 to fold them while that is still cheap. All three are small, and the existing cells must stay green and be re-captured on the same `base_commit`.

1. **Capture full commit messages, not only subjects** (`new_commits`). Today, dropping the `COORD_SEED_TRAILER: <mission_id>` line from the coordination commit would not turn anything red. Capture the full message (`%B`), normalised by the same whitelist (ULID and mid8 numbering, timestamps, tmp paths), together with the changed paths. Add a planted break that drops the trailer, and record it.
2. **`owned_root_mismatch` must also watch the other repository.** Capture the `other/repo` pre/post state (porcelain, tree, branches), so residue written there would be caught.
3. **Fix the flat module docstring cell count** (it says 13; there are 15).

Re-capture the snapshots serially on the unchanged `src/` (`git diff f0f3daa55 HEAD -- src/` stays empty), check that regeneration is reproducible, and confirm 58 passed.
