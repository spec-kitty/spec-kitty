# Approach — host-aware-mode-predicate-01M7X6B1

- **[2026-11-20][plan] One predicate plus delegation.** The approach is one host-aware predicate beside `FileState`. The effect validator and every planner's action ladder delegate to `effect_action`, so they cannot disagree. An AST ratchet gate closes the class (#4810). Windows is emulated on Linux by synthesizing NTFS modes in `os.stat`/`lstat`/`fstat`, with `chmod` toggling only the write bit.
