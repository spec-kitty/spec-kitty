---
work_package_id: WP02
title: Verified fetch, cache and the single download owner
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-010
- NFR-003
- NFR-004
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 070ebdc5b3a3ed7d1ee350dab6412f1cf7cba5f5
created_at: '2026-10-29T22:28:44.008085+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Foundation
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/release_assets.py
- src/kernel/service_artifacts.py
- tests/kernel/test_release_assets.py
- tests/kernel/test_service_artifacts.py
- tests/kernel/service_release_fixture.py
- tests/architectural/test_release_asset_download_owner.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/release_assets.py
- src/kernel/service_artifacts.py
- tests/kernel/test_release_assets.py
- tests/kernel/test_service_artifacts.py
- tests/kernel/service_release_fixture.py
- tests/architectural/test_release_asset_download_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Verified fetch, cache and the single download owner

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`), and address every item. Record your changes with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- `kernel.release_assets` is the **only** module in `src/` that downloads a release asset. It accepts only `https://` and `file://`, has a 60 s inactivity timeout and honours proxy and CA environment variables. It never leaves a partial file at the destination (NFR-004).
- `kernel.service_artifacts` places a pinned asset in `<cache_root>/<service>/<tag>/<name>`. It re-verifies the sha256 on every resolve, deletes and refetches a mismatching copy, works offline from the cache or an asset directory, and never returns an unverified path (FR-002, FR-010 asset dir, NFR-003).
- A non-vacuous architectural gate enforces the single owner with an empty allowlist (FR-003, Standing Order #5).
- A shared fixture-release builder lets later WPs build `file://` releases in a few lines.

## Context & Constraints

- Read: `plan.md` (IC-02), `research.md` R-1, R-2, R-3, `data-model.md` (CachedAsset), `contracts/service-pin.schema.md`, ADR 2026-10-29-1 D-3, D-4, D-8.
- Precedents (mirror; do not import across layers):
  - `src/charter/offering/packs/pack_fetch.py`: `default_cache_root()`, "a poisoned cache is never trusted", scratch-then-rename and its Windows retry `_retrying`.
  - `src/kernel/git/remote.py`: the owner of git remote contact, and its timeout and no-prompt discipline.
  - `src/kernel/user_dirs.py::user_cache_dir(windows_local_appdata=False)`.
- `kernel` stays zero-dependency: use `urllib.request`, `ssl`, `hashlib`, `shutil`, `tempfile`. `ssl.create_default_context()` honours `SSL_CERT_FILE` / `SSL_CERT_DIR`. `urllib.request.getproxies()` honours `HTTPS_PROXY` / `NO_PROXY`.
- Error type: `ServiceArtifactError(RuntimeError)` with `.code` from `SERVICE_BINARY_MISSING` (unreachable, missing, cache not writable) or `SERVICE_BINARY_DIGEST_MISMATCH`. WP03 maps these to user refusals; keep the codes as module constants so WP03 imports them, not copies.

## Branch Strategy

- **Planning base branch**: `issue-6590-pinned-service-binaries`
- **Merge target branch**: `issue-6590-pinned-service-binaries`
- Worktree per lane from `lanes.json`: `spec-kitty agent action implement WP02 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T005 – `kernel.release_assets` (the download owner)

- **Purpose**: decide scheme, timeout, proxy, TLS and atomic write once.
- **Steps**:
  1. `asset_url(repository: str, tag: str, name: str) -> str`:
     - `https://…/<owner>/<repo>` → `<repository>/releases/download/<tag>/<name>` (strip a trailing `.git` and `/`);
     - `file:///dir` → `file:///dir/<tag>/<name>`;
     - any other scheme raises `ValueError`.
  2. `download(url: str, dest: Path, *, timeout: float = 60.0) -> None`:
     - only `https` and `file` schemes;
     - open with `urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context())` for https;
     - stream in 1 MiB chunks to `dest.with_name(dest.name + f".part-{os.getpid()}")` inside `dest.parent`, then `os.replace` into `dest`;
     - on any exception, remove the part file and re-raise as `ReleaseAssetUnavailable(url, reason)`. The reason must never include headers or credentials.
  3. Set a `User-Agent: spec-kitty/<version>` header. Read the version from `importlib.metadata`, falling back to `"dev"`; a lookup failure is never fatal.
  4. Redirects: GitHub release downloads redirect to `objects.githubusercontent.com`, and urllib follows them. Do not follow a redirect to a non-https URL; add a `HTTPRedirectHandler` subclass that refuses a downgrade.
- **Files**: `src/kernel/release_assets.py` (~110 lines).
- **Notes**: no retries in the owner. Callers decide; the sync script may retry once.

### Subtask T006 – `kernel.service_artifacts`

- **Purpose**: the cache, and the only way to get a verified asset path.
- **Steps**:
  1. `default_cache_root() -> Path` returns `user_cache_dir(windows_local_appdata=False) / "spec-kitty" / "services"`.
  2. `sha256_file(path) -> str` (streamed).
  3. `verify_asset(path: Path, asset: ServiceAsset) -> bool`: false when the file is missing, is not a regular file, is a symlink, or the digest differs.
  4. `cached_path(pin, asset, cache_root) -> Path` returns `cache_root / pin.service / pin.tag / asset.name`.
  5. `resolve_cached(pin, asset, *, cache_root=None) -> Path | None`: when the file verifies, return its path. When it exists but does not verify, delete it and return `None`. Never return an unverified path.
  6. `fetch_asset(pin, asset, *, offline=False, cache_root=None, asset_dir=None) -> Path`, in this order:
     1. `resolve_cached`;
     2. the asset directory (T007);
     3. unless offline, `download(asset_url(...), tmp)`, verify, rename into the cache (Windows retry as in `pack_fetch._retrying`);
     4. otherwise raise `ServiceArtifactError(SERVICE_BINARY_MISSING, …)`.
     A digest mismatch after download deletes the file and raises `SERVICE_BINARY_DIGEST_MISMATCH` naming the asset. On POSIX, chmod the final file `0o755` when it is a native target (not `.jar`, not a `.tar.gz`).
  7. Cache not writable (OSError on mkdir or rename): raise `SERVICE_BINARY_MISSING`, and include in the message that `SPEC_KITTY_SERVICE_ASSET_DIR` can supply the asset.
- **Files**: `src/kernel/service_artifacts.py` (~150 lines).

### Subtask T007 – Offline asset directory

- **Purpose**: air-gapped installs (FR-010).
- **Steps**: `asset_dir` defaults to `os.environ.get("SPEC_KITTY_SERVICE_ASSET_DIR")`. Look up `<asset_dir>/<name>` (flat) and then `<asset_dir>/<tag>/<name>`. On a verified hit, copy it into the cache (never run from the asset directory, which might be writable by others) and return the cache path. A file that fails verification is **not** deleted (it is not ours); raise `SERVICE_BINARY_DIGEST_MISMATCH` naming the path.
- **Files**: within `service_artifacts.py`.

### Subtask T008 – Shared fixture-release builder

- **Purpose**: one helper for all later tests.
- **Steps**: `tests/kernel/service_release_fixture.py` with a function `build_release(root: Path, *, service="write-service", tag="service-v0.1.0", assets: dict[ServiceTarget, bytes] | None = None, extras: dict[str, bytes] | None = None, corrupt: set[str] = frozenset()) -> tuple[ServicePin, Path]`. It:
  - writes files under `root/<tag>/`;
  - writes a `SHA256SUMS` in `sha256sum` format;
  - returns a `ServicePin` whose repository is `root.as_uri()`; a name listed in `corrupt` gets a digest that does not match its bytes.
  It must not be collected as a test, so do not prefix it `test_`. Default asset content can be a small shell or Python script; WP04 passes its own fake service bytes.
- **Parallel?**: yes, once WP01 has landed.

### Subtask T009 – Unit tests

- **Steps**:
  - `tests/kernel/test_release_assets.py` (`fast`):
    - `asset_url` shapes, including a trailing `.git`;
    - scheme refusal for `http`, `ftp` and empty;
    - a `file://` download writes atomically, leaving no `.part-*` behind;
    - a simulated mid-stream failure (a monkeypatched read that raises after the first chunk) leaves no destination and no part file;
    - an https-to-http redirect is refused. Use a handler unit test rather than the network.
  - `tests/kernel/test_service_artifacts.py` (`fast`):
    - fetch into an empty cache, then a second resolve does no I/O (monkeypatch `download` to raise);
    - a flipped byte in the cache is evicted and refetched;
    - a corrupt release asset raises `SERVICE_BINARY_DIGEST_MISMATCH` and leaves nothing cached;
    - offline with a warm cache succeeds; offline with an empty cache raises `SERVICE_BINARY_MISSING`;
    - the asset dir: flat and tagged layouts, copied into the cache, a wrong digest raises and the file is kept;
    - a symlink in the cache is refused;
    - a read-only cache root raises `SERVICE_BINARY_MISSING` with the asset-dir hint (skip on Windows when running as root).
- **Files**: two test modules (~250 lines total).

### Subtask T010 – Architectural gate

- **Purpose**: close the scattered-download defect class by construction.
- **Steps**:
  - `tests/architectural/test_release_asset_download_owner.py` scans every `src/**/*.py` except `src/kernel/release_assets.py`, and fails when a file references the literal `releases/download` or imports `urllib.request` **inside `src/kernel/` or `src/specify_cli/services/`**. Use AST for imports and token scanning for the literal.
  - The rest of `src/` keeps its existing HTTP clients (`charter_packs/sources/*`, `distribution/simple_index.py`, …). They are out of scope by design; document that in the docstring. Even so, `releases/download` is forbidden everywhere outside the owner.
  - Empty allowlist; per ADR 2026-09-30-1 none may be added.
  - Non-vacuity:
    - a scanned-file floor (count `src/**/*.py` now and set the floor about 10% lower);
    - a planted `import urllib.request` in a temp `src/kernel/x.py`-like file is flagged;
    - a planted `"…/releases/download/…"` literal is flagged;
    - the owner itself is not flagged (positive control).
  - Mark `pytestmark = pytest.mark.architectural`, like `tests/architectural/test_remote_contact_owner.py`; mirror its structure.

## Test Strategy

```bash
uv run --frozen pytest -q tests/kernel/test_release_assets.py tests/kernel/test_service_artifacts.py tests/architectural/test_release_asset_download_owner.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_remote_contact_owner.py
uv run --frozen ruff check src/kernel tests/kernel tests/architectural/test_release_asset_download_owner.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/kernel/release_assets.py src/kernel/service_artifacts.py
```

## Risks & Mitigations

- Proxy and CA in agent containers: rely on the stdlib environment handling. Do not disable verification.
- Windows: `os.replace` onto an open file fails. Reuse the retry pattern and keep handles closed.
- Large binaries: stream; never read the whole file into memory.

## Review Guidance

- Grep: no `urlopen` or `releases/download` outside the owner under `src/`.
- Verify that a corrupted cache can never be returned. Read every return path of `fetch_asset` and `resolve_cached`.
- The gate has a floor plus a planted violation, and its allowlist is empty.

## Progress & Status

`spec-kitty agent tasks add-history WP02 --note "..."`; `spec-kitty agent tasks mark-status T005 --status done`.
