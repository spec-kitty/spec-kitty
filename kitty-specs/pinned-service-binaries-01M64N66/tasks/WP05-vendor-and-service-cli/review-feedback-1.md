# WP05 review feedback (cycle 1, reviewer-renata)

Most of this WP is sound. Verified:
- the lockfile stays byte-identical on refusal (byte assertions);
- downloads go only through `kernel.release_assets`, and git contact only through `kernel.git.remote`; both gates are green;
- annotated tags are peeled, with a real-git test;
- the userinfo refusal works;
- `stop` exits 1 on UNCONFIRMED;
- `host.py` uses `is_windows`;
- `creation_proof` (REUSED gives NOT_RUNNING with no signal), which is the follow-up I raised on WP04, so no regression;
- the dead-symbol cleanup.

One blocking item, plus one test gap.

**Issue 1 (blocking): `map_assets` pins another service's build when this service has none for a target.**
`_pick` narrows by service name only when there are several candidates. A single candidate is taken whatever service it belongs to. Reproduced:

    map_assets("write-service", ["spec-kitty-write-service-0.1.0-linux-x64",
        "spec-kitty-read-service-0.1.0-macos-arm64", "spec-kitty-read-service-0.1.0.jar",
        "contract-bundles-0.1.0.tar.gz"])
    -> macos-arm64: spec-kitty-read-service-0.1.0-macos-arm64, jvm: spec-kitty-read-service-0.1.0.jar, ...

The service-v* releases carry both Java services (ADR 2026-10-29-1). So a release that lacks one write-service target pins the read service's binary or jar as the write service. Its digest matches SHA256SUMS, so every later verification passes. The launcher would then start the read service, which the CLI must never launch (D-6, C-007). The vendor command is the only bump path, so this mapping has to fail closed.

Fix:
- For builds (native and jar), drop every candidate whose name names another known service (any other `KNOWN_SERVICES` entry), even when it is the only one.
- Better: accept a build only when its name identifies this service. The contract says the write-service prefix is whatever spec-kitty-events names `command-cli`'s binary. So take the deployable prefix as an input (a `--asset-prefix` option, defaulting to `spec-kitty-<service>`) and match `<prefix>-<ver>-<target>` / `<prefix>-<ver>.jar` exactly.
- Optionally, check that `<ver>` equals the tag's version.
- Add a test with the release above (read-service-only macos and jar): it must not pin them for write-service. The result must be either an omitted target or a refusal, never another service's build.
- Shared extras (`contract-bundles-*`, etc.) stay as they are.

**Issue 2: `status` lacks the two promised proofs (Review Guidance).**
By reading the code, `status` only reads the endpoint and does one handshake, and its JSON has no token field. No test proves either. Add a test that:
- runs `status --json` against a real published endpoint (for example via `fake_service`, or a planted `endpoint.json` plus a monkeypatched `ServiceClient`);
- has `subprocess.Popen` and `ServiceLauncher.ensure` patched to fail;
- asserts that the token value does not appear in stdout or stderr.

Non-blocking:
- `status` evicts a corrupt cached copy (through `resolve_cached`). That is consistent with every resolve, but the module docstring says "It reads only"; say that it evicts.
- `vendor` with a `file://` repository and no `--commit` exits 1 (`SERVICE_VENDOR_COMMIT_REQUIRED`). Arguably that is a usage error (2).
- The out-of-map edits are needed and minimal:
  - `remote_tag_commit` is required by the remote-contact gate and is tested against real git;
  - the regenerated `docs/api/cli-commands.md` passes the parity gate;
  - the two `test_json_contract_enumeration` entries carry evidence strings.
