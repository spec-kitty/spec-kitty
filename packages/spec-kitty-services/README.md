# spec-kitty-services

The optional companion of [`spec-kitty-cli`](https://pypi.org/project/spec-kitty-cli/). It carries the pinned, digest-verified
service binaries the CLI pins for one platform (the events write service, and the charter service once the CLI launches
it), so an install works offline from the first use:

```bash
pip install "spec-kitty-cli[services]"
```

- **Version-locked.** Its version always equals the `spec-kitty-cli` version. A companion built for another CLI version
  offers nothing, and the CLI fetches its own pinned build on first use instead.
- **Digest-checked.** The CLI runs a bundled binary only when its bytes match the sha256 the CLI itself pins.
- **Platforms.** linux x86_64 and aarch64 (glibc 2.39 or newer), macOS on Apple Silicon, Windows x64. Every other host
  gets a binary-free wheel, and the CLI fetches on first use as it does without the companion.
- **Never carried:** the events read service, which stays off user machines.

Built from the pinned `service-v*` release assets, never rebuilt. See ADR 2026-10-29-1, Amendment 2026-10-31, in the
spec-kitty repository.
