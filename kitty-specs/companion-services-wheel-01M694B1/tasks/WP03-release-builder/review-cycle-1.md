---
affected_files: []
cycle_number: 1
mission_slug: companion-services-wheel-01M694B1
reproduction_command:
reviewed_at: '2026-10-31T15:12:36Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review: changes requested (claude::reviewer-renata)

## Blocking

1. `scripts/build_services_wheel.py:183-211` (`_wheel_problems`): `--verify` only constrains `spec_kitty_services/bin/*` and the manifest. Every other member is trusted as long as RECORD agrees with it, and RECORD is written by whoever wrote the wheel, so it proves nothing against tampering. Reproduced on the built fixture wheels. I rewrote the linux-x64 wheel with a RECORD that matches its contents, and `--verify` exits 0 for each of these changes:
   - a root `evil.pth`, which runs code at every interpreter start after install;
   - a replaced provider `spec_kitty_services/__init__.py`;
   - an extra module `spec_kitty_services/evil.py`;
   - a `dist-info/WHEEL` whose `Tag:` and `Root-Is-Purelib` disagree with the file name.

   FR-010 says the guard fails "when a companion wheel's contents differ from the pinned digests", and the script's own docstring says "nothing else is bundled". Fix: require the archive's member set to be exactly what the writer produces (source files, manifest, `bin/<pinned assets>`, and the 4 dist-info files). Then require every non-`bin/` member to be byte-equal to the writer's output for that version and tag. The simplest form: rebuild the expected wheel with `writer.build_companion_wheel`, using the already digest-checked bundled binaries, and compare the wheel bytes. The build is deterministic, so this is exact. Also refuse duplicate member names. Add red tests for a root `.pth`, a changed `__init__.py` and an extra non-bin module, each with a RECORD that is consistent with the change. Today `_rewrite` in the test leaves RECORD stale, so the existing "added binary" test does not reach this case.

## Non-blocking (fold if cheap)

2. `build()` (`:127-147`): `--out` may already hold wheels. In my probe, a stale `...-win_amd64.whl` survived a fallback-only build and the build exited 0. Refuse a non-empty `--out` (the docstring already says "must not already hold wheels"), or clear its `*.whl` before the move.
3. `--glibc-floor bad` exits 0 when no Linux target is pinned. Validate the floor up front, for example with `writer.platform_tag("linux-x64", floor)`.
4. Stable codes: `--verify` on a non-zip `.whl` raises a `BadZipFile` traceback, a RECORD line with an unexpected shape raises a bare `ValueError` with no code, and a RECORD that names a missing member raises `KeyError`. Map all three to `COMPANION_VERIFY_FAILED`. The `ValueError`s from the floor and the version (`main`, `:268`) also print without a code.
5. The build does not check pin asset names against the writer's `_ASSET_NAME`. A pin name like `.x` or `C:x` passes `service_pin` but produces a wheel whose manifest the provider rejects. Refuse at build time.

## Verified OK
- `fetch_asset` is the only fetch path (C-003).
- No jar or read service is packed.
- A corrupt asset refuses with `SERVICE_BINARY_DIGEST_MISMATCH` and leaves no wheel and no scratch directory.
- The size gate is 95/60 MB.
- Builds are deterministic, and the smoke build plus verify pass on the real checkout.
- The end-to-end test goes through `resolution.resolve_binary` and the extracted provider, including a tamper control.
- The WP02 folds are correct.
- No test touches the network.
