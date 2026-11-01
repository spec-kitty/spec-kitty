# Quickstart: proving the platform-floor guard

Everything below runs against fixtures; the pins are empty, so no real service release is needed
and nothing reaches the network.

## Build the wheels from fixture pins

```bash
uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py -q
```

The fixture repository the module builds in `tmp_path` copies the real companion source and writes
pins whose assets are minimal native binaries: ELF for `linux-x64` / `linux-arm64`, Mach-O for
`macos-arm64`, PE for `windows-x64`.

## See the refusal a maintainer would hit

```bash
# A linux-x64 asset whose ELF version needs include GLIBC_2.42, declared floor 2_39
uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py \
  -q -k "floor_above_the_declared or platform_floor"
```

The failure prints, on stderr, a line shaped like:

```
SERVICE_PLATFORM_FLOOR_EXCEEDED linux-x64: write-service-0.1.0-linux-x64 needs glibc 2_42 from its ELF version needs, above the 2_39 the wheel tag would claim; raise --glibc-floor to 2_42 in release.yml, or pin a build that does not need it
```

and `--out` holds no wheel.

## Read the floors the build measures

```bash
uv run --frozen python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from scripts.service_platform import read_floor

data = Path("some/pinned/binary").read_bytes()
print(read_floor(data, "linux-x64"))   # e.g. "2_39", or None when the ELF states no floor
PY
```

`read_floor` raises `UnreadableBinary` with a reason for anything it cannot parse — that reason is
what the build reports as `SERVICE_PLATFORM_FLOOR_UNREADABLE`.

## Raise a floor deliberately

```bash
# .github/workflows/release.yml, build-companion-wheels
python scripts/build_services_wheel.py --out dist-services --glibc-floor 2_42 --macos-floor 12_0
```

Both inputs are validated up front; the tag follows the declared value, and the binaries must not
need more. Changing a floor changes which hosts can install the companion, so it lands with a
changelog entry, not as a drive-by.

## The invariant to keep

```bash
# After any change here: same inputs, same wheel bytes as before.
uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py -q -k "reproducible or exactly_its_pinned_assets"
```
