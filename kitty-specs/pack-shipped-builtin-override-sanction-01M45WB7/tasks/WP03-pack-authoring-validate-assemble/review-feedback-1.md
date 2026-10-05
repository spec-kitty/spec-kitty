**Issue 1 (blocking, FR-014 and the symlink edge case): `doctrine pack validate` passes a dangling-symlink sanction file that the runtime rejects as malformed.**

`src/specify_cli/doctrine/pack_validator.py:511` only checks the file when `(pack_dir / PACK_POLICY_FILENAME).exists()` is true. `Path.exists()` follows symlinks, so a `replaceable-builtins.yaml` symlink whose target is missing (inside or outside the pack root) is skipped without any finding. The runtime parser treats that same file as present and malformed. `override_policy._present` uses `exists() or is_symlink()`, so `load_pack_sanction` raises `OverridePolicyError ... resolves outside root`.

Reproduced at 959b9b0b7. The pack root holds only `replaceable-builtins.yaml -> /nonexistent/x.yaml`:
- `validate_pack(pack).ok` is `True`, with no `pack_sanction` error.
- `load_pack_sanction("mypack", pack)` raises `OverridePolicyError`, so the consumer's `doctor doctrine` goes RC=1 (FR-006).

This is the exact case FR-014 says must never ship. The spec edge case says: "symlink or path that resolves outside the pack root ... treated as malformed". It is also inconsistent with the assembler in this WP: `pack_assembler.py:_detect_sanction_conflicts` correctly uses `candidate.exists() or candidate.is_symlink()`.

Fix: gate on the same presence predicate the parser uses. Use `exists() or is_symlink()`, or call `_validate_pack_sanction` unconditionally, since `load_pack_sanction` already returns an empty policy for an absent file. Add a red-first test in `TestPackSanctionValidation`: a dangling symlink, and a symlink escaping the pack root to an existing file. Each should produce one `pack_sanction` error naming the file. Skip the test on platforms without symlink support, following the existing repo pattern.

**Accepted as-is (no change needed):**
- No inert-entry advisory when the pack has no `drg/fragment.yaml`. `load_org_pack` raises `OrgPackMissingError`, so such a pack contributes no nodes at runtime and cannot override anything. The skip is documented in the `_validate_pack_sanction` docstring, and the advisory is informational only.

**Everything else passed review:**
- Red to green: 12 failed / 5 passed at 5f1308bd1, all passing at HEAD.
- There is a single parser. `specify_cli` only `safe_dump`s on write.
- Sanction conflicts and malformed inputs are detected before any write, including the `--force` rmtree path. Both are reported via `all_conflicts` and `_maybe_write_conflicts`.
- The union is written before `validate_pack`.
- The advisory uses `load_org_pack` node URNs.
- ruff, format, mypy and C901 are clean, with no new suppressions.
