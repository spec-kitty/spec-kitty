---
affected_files: []
cycle_number: 1
mission_slug: pinned-service-binaries-01M64N66
reproduction_command:
reviewed_at: '2026-10-29T23:56:31Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1, reviewer-renata)

The resolution order, the Java 25 jar gate, the protocol check running before any fetch, `verify_before_exec`, and the unpinned opt-in (exactly "1", explicit path only, with a warning) are all correct. The out-of-scope edits to `test_no_dead_modules.py` and `_baselines.yaml` are correct and minimal. Fix the three items below; item 4 is optional.

**Issue 1: an asset-directory digest mismatch gets a wrong remedy and loses the bad file's path (FR-010, FR-005 "concrete remedy").**
When `SPEC_KITTY_SERVICE_ASSET_DIR` holds a tampered file, `kernel.service_artifacts` raises `SERVICE_BINARY_DIGEST_MISMATCH` naming the asset-dir file. `resolution._fetch` then throws that message away and always uses the remedy "delete <cache path> and run `spec-kitty service fetch`". Reproduced with an offline run, a tampered `<asset_dir>/<name>` and an empty cache. The remedy names a cache file that does not exist. It tells an air-gapped user to fetch online. It never names the bad file.
Fix: give the asset-directory mismatch its own remedy that names the asset-dir file, for example "replace <asset_dir file> with the pinned release asset (check it against the release's SHA256SUMS)". Keep the cache remedy for a corrupt cache or download. Choose between them from the error, not by guessing: carry the path or the source on `ServiceArtifactError` (WP02 is approved, but a small additive attribute is fine if you coordinate), or check the asset-dir candidates in resolution. Add a test that asserts the remedy names the asset-dir file and does not name the cache path.

**Issue 2: not every refusal path proves that nothing was spawned.**
`_no_spawn` (Popen patched to fail) is used in only 6 tests. It is not used in these refusal tests: malformed pin, protocol mismatch, explicit jar without Java, explicit file missing, broken install provider, native asset missing with no Java, jar unavailable, unknown host with no Java, unknown host with no jar pinned, and the two `verify_before_exec` refusals.
Fix: make the Popen guard part of the autouse fixture (or apply it to every test that expects a `ServiceRefusal`). The jar-tier tests that legitimately need a fake `find_java` already patch `find_java`, so the guard does not get in their way.

**Issue 3: an unwritable cache is reported as "not available", and the cause is lost.**
`_fetch` turns every `SERVICE_BINARY_MISSING` into "<asset> ... is not available" with the fetch/asset-dir remedy. For the cache-not-writable case, the kernel's message ("the service cache <dir> is not writable ...") is dropped. The asset-dir hint alone does not help, because asset-dir files are copied into that same cache. Keep the cause in the message, for example by appending the kernel reason or by giving the not-writable case a variant that names the cache directory and says to fix its permissions. Add a test.

**Issue 4 (optional, but cheap): the injected `env` does not keep resolution away from the real process environment.**
`resolve_binary(..., env={})` still consults `os.environ["SPEC_KITTY_SERVICE_ASSET_DIR"]`. When `env` has no asset dir, `ctx.asset_dir` is `None`, and `fetch_asset` then falls back to `os.environ`. Reproduced: with `env={}` and the variable set in the process, the asset dir is used. Either pass the env's value explicitly, including "no asset dir" (for example a sentinel, or the env lookup moved fully into resolution), or document that `env` covers only the explicit and opt-in variables. `find_java()` likewise reads `os.environ` rather than `env`.

Non-blocking notes:
- `_binary_providers` calls `entry.load()` outside the try. A broken companion wheel (an ImportError) would crash with a traceback instead of raising a `BINARY_MISSING` refusal. Nothing registers a provider today.
- An unpinned explicit `.jar` gets `argv_prefix=(path,)`, not `java -jar`. That is acceptable for a developer opt-in, but worth a line in the docstring.
