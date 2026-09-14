"""Unit tests for the network-isolated PlantUML invocation seam (WP01).

These run everywhere — no docker required. The security-critical flags on the
docker argv, the sha256 fail-closed behaviour, and the error-SVG detector are
pinned here; the *actual* network-isolated render is proven by the
``plantuml-egress-spike.yml`` CI matrix (both runners).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import sys
import time
from pathlib import Path

import pytest

# Import the render seam the way the docs workflows do: put scripts/docs on the
# path and import by module name (this registers it in sys.modules, which the
# frozen @dataclass in the module needs). Mirrors glossary_linker's bootstrap.
_DOCS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "docs"
if str(_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(_DOCS_DIR))

import plantuml_invoke  # noqa: E402  # deliberate post-bootstrap import (see above)

pytestmark = pytest.mark.unit


def _pins() -> plantuml_invoke.Pins:
    return plantuml_invoke.load_pins()


def test_pins_load_from_repo() -> None:
    pins = _pins()
    assert pins.plantuml_version
    assert len(pins.plantuml_jar_sha256) == 64  # (sha256 hex is exactly 64 chars)
    assert pins.jre_image_digest.startswith("eclipse-temurin@sha256:")


def test_docker_argv_carries_isolation_and_sandbox_flags(tmp_path: Path) -> None:
    pins = _pins()
    argv = plantuml_invoke.build_docker_argv(
        image_digest=pins.jre_image_digest,
        workdir=tmp_path,
        jar_path=tmp_path / "plantuml.jar",
        infile=tmp_path / "d.puml",
    )
    # Security-critical: network isolation + SANDBOX + headless must be present.
    assert "--network=none" in argv
    assert "-DPLANTUML_SECURITY_PROFILE=SANDBOX" in argv
    assert "-Djava.awt.headless=true" in argv
    assert pins.jre_image_digest in argv
    # Ordering: JVM opts before -jar; PlantUML opts after the jar.
    assert argv.index("-DPLANTUML_SECURITY_PROFILE=SANDBOX") < argv.index("-jar")
    assert argv.index("-jar") < argv.index("-failfast2")
    assert argv.index("-jar") < argv.index("-tsvg")


def test_verify_jar_sha256_rejects_mismatch(tmp_path: Path) -> None:
    jar = tmp_path / "plantuml.jar"
    jar.write_bytes(b"not the real jar")
    with pytest.raises(plantuml_invoke.PlantumlRenderError):
        plantuml_invoke.verify_jar_sha256(jar, _pins().plantuml_jar_sha256)


def test_verify_jar_sha256_accepts_match(tmp_path: Path) -> None:
    # File-integrity checksum of a synthetic jar (not a charter content hash);
    # sha256 is the algorithm under test in verify_jar_sha256.
    import hashlib

    jar = tmp_path / "plantuml.jar"
    payload = b"deterministic-bytes"
    jar.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()  # noqa: TID251 - file-integrity checksum under test
    plantuml_invoke.verify_jar_sha256(jar, expected)


def test_svg_is_error_detects_error_signatures() -> None:
    assert plantuml_invoke.svg_is_error(b"<svg><text>An error has occurred</text></svg>")
    assert plantuml_invoke.svg_is_error(b"<svg><text>Syntax Error?</text></svg>")
    assert not plantuml_invoke.svg_is_error(
        b'<svg><text>Agent Profile Schema</text><text>researcher-ryan</text></svg>'
    )


def test_extract_title_reads_plantuml_title() -> None:
    src = "@startyaml\ntitle Agent Profile Schema\nprofile_id: x\n@endyaml\n"
    assert plantuml_invoke.extract_title(src) == "Agent Profile Schema"
    assert plantuml_invoke.extract_title("@startyaml\nprofile_id: x\n@endyaml") is None


# ---- ensure_jar concurrency safety (fixes the unit-contract-residual flake) ---
#
# Root cause: the three test files that consumed this module each carried a
# verbatim-duplicated `_ensure_jar()` that downloaded to the SAME shared
# `plantuml.jar` path guarded only by `if not jar.exists()` — a check-then-act
# race. Under `pytest -n auto --dist loadfile`, those three files land on
# DIFFERENT xdist WORKER PROCESSES that can call `_ensure_jar()` concurrently:
# one worker's in-progress (truncated/empty) write is observed by another
# worker's `exists()` check, which then skips its own download and verifies a
# still-empty or partial file — `PlantumlRenderError: plantuml.jar sha256
# mismatch`, with a DIFFERENT "got" hash per worker (the CI signature).
#
# `ensure_jar` closes this by serializing the whole check-download-verify
# sequence behind a cross-process `fcntl.flock`, and by verifying a freshly
# downloaded file on a private temp path BEFORE atomically publishing it —
# so no caller can ever observe a partial file. This test proves that under
# real concurrent callers (no network — a monkeypatched slow, chunked
# "downloader" deterministically forces the same interleaving that exposed
# the bug in CI).

_RACE_PAYLOAD = b"race-safe-plantuml-jar-payload-" * 8192  # ~256KB, chunked to force interleaving
_RACE_PAYLOAD_SHA256 = hashlib.sha256(_RACE_PAYLOAD).hexdigest()  # noqa: TID251 - file-integrity checksum under test


def _slow_chunked_download(_url: str, dest: Path) -> None:
    """Stand-in for the real ``urlretrieve``: writes ``_RACE_PAYLOAD`` in small
    chunks with a short sleep between each, so concurrent, unsynchronized
    writers to the SAME destination path would genuinely interleave/truncate
    each other — reproducing the CI race deterministically, with no network."""
    chunk_size = 4096
    with open(dest, "wb") as fh:
        for offset in range(0, len(_RACE_PAYLOAD), chunk_size):
            fh.write(_RACE_PAYLOAD[offset : offset + chunk_size])
            time.sleep(0.001)


def test_ensure_jar_is_race_safe_under_concurrent_callers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plantuml_invoke, "_download_once", _slow_chunked_download)
    pins = plantuml_invoke.Pins(
        plantuml_version="race-test",
        plantuml_jar_sha256=_RACE_PAYLOAD_SHA256,
        plantuml_jar_url="unused://patched-downloader",
        jre_image="n/a",
        jre_image_digest="n/a",
    )
    dest = tmp_path / "plantuml.jar"

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        jars = list(pool.map(lambda _: plantuml_invoke.ensure_jar(pins, dest), range(8)))

    # Every concurrent caller must get back a fully-provisioned, verified jar —
    # never a partial/empty one, and never a PlantumlRenderError.
    for jar in jars:
        assert jar == dest
        plantuml_invoke.verify_jar_sha256(jar, _RACE_PAYLOAD_SHA256)
    assert dest.read_bytes() == _RACE_PAYLOAD
