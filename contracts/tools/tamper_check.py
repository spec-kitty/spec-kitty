"""Plant a tampered Gradle dependency-verification file and require the build to refuse it (FR-018, NFR-003).

The plant: copy the contracts directory to a temporary location, replace the leading characters of every
``<sha256 value="`` in the copy's ``gradle/verification-metadata.xml`` (so no recorded checksum matches the
artefact it names), then run the *copy's* ``tools/bundle.py``. A build that honours strict dependency
verification stops with ``DEPENDENCY_VERIFICATION_FAILED`` (exit 2); that is the pass. The original tree is never
touched. The Gradle run needs the JVM and the network, so it executes in CI only.

Verdicts: ``PLANT_DETECTED`` (exit 0); ``PLANT_NOT_DETECTED`` (exit 1: the build accepted the tampered metadata, or
failed for a reason other than verification while still exiting below 2); ``PLANT_INCONCLUSIVE`` (exit 2: the build
could not run, for example ``JVM_MISSING``, so it proved nothing). Also exit 2: ``METADATA_MISSING`` and
``ZERO_CHECKSUMS``. The last line is always ``counts: checksums_tampered=N``.

Run as a bare script (``python contracts/tools/tamper_check.py --contracts contracts``). Standard library only.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

CHECK_NAME = "tamper_check"
METADATA = Path("gradle") / "verification-metadata.xml"
CHECKSUM = re.compile(r'(<sha256 value=")([0-9a-f]{8})')
DEFAULT_MODULE = "full"
DEFAULT_MODULE_ROOT = "tools/fixtures/spike"
EXPECTED_CODE = "DEPENDENCY_VERIFICATION_FAILED"
TIMEOUT_SECONDS = 1800
TAMPER_PREFIX = "deadbeef"
ALTERNATIVE_PREFIX = "feedface"
IGNORED = shutil.ignore_patterns("__pycache__", ".gradle", "build", "*.pyc")

Runner = Callable[[Sequence[str]], tuple[int, str]]


def subprocess_runner(command: Sequence[str]) -> tuple[int, str]:
    completed = subprocess.run(  # noqa: S603 -- argument list built here, interpreter is sys.executable, no shell
        list(command), capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
    )
    return completed.returncode, completed.stdout + completed.stderr


def tamper(text: str) -> tuple[str, int]:
    """``text`` with the first eight characters of every checksum replaced, and how many were replaced."""

    def replace(match: re.Match[str]) -> str:
        return match.group(1) + (ALTERNATIVE_PREFIX if match.group(2) == TAMPER_PREFIX else TAMPER_PREFIX)

    return CHECKSUM.subn(replace, text)


def run(argv: Sequence[str] | None = None, *, runner: Runner = subprocess_runner, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Plant tampered Gradle verification metadata and require the build to refuse it.")
    parser.add_argument("--contracts", default="contracts", type=Path)
    parser.add_argument("--module", default=DEFAULT_MODULE)
    parser.add_argument("--module-root", default=DEFAULT_MODULE_ROOT, help="the root of the module to build, relative to --contracts")
    args = parser.parse_args(argv)

    tampered = 0

    def finish(code: str, detail: str, status: int) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")
        out(f"counts: checksums_tampered={tampered}")
        return status

    source = args.contracts / METADATA
    if not source.is_file():
        return finish("METADATA_MISSING", f"{source} does not exist", 2)
    with tempfile.TemporaryDirectory(prefix="tamper-check-") as scratch:
        copy = Path(scratch) / "contracts"
        shutil.copytree(args.contracts, copy, ignore=IGNORED)
        text, tampered = tamper((copy / METADATA).read_text(encoding="utf-8"))
        if tampered == 0:
            return finish("ZERO_CHECKSUMS", f"{source} holds no <sha256 value=...> to tamper with", 2)
        (copy / METADATA).write_text(text, encoding="utf-8", newline="\n")
        status, output = runner(
            [
                sys.executable,
                str(copy / "tools" / "bundle.py"),
                "--root",
                str(copy / args.module_root),
                "--out",
                str(Path(scratch) / "out"),
                "--module",
                args.module,
            ]
        )
    if status == 2 and EXPECTED_CODE in output:
        return finish("PLANT_DETECTED", f"the build refused the tampered metadata ({EXPECTED_CODE}); {tampered} checksums were altered in the copy", 0)
    detail = " | ".join(line for line in output.splitlines() if line.strip())[-300:]
    if status == 2:
        return finish("PLANT_INCONCLUSIVE", f"the build could not run, so the plant proves nothing: {detail}", 2)
    return finish("PLANT_NOT_DETECTED", f"the build exited {status} and did not refuse the tampered metadata: {detail}", 1)


if __name__ == "__main__":
    sys.exit(run())
