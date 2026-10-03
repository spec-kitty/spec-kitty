"""Tests for ``contracts/tools/tamper_check.py``: the planted tampered-metadata negative (FR-018).

The plant copies ``contracts/``, replaces the leading characters of every ``<sha256 value="`` in the copy's
``gradle/verification-metadata.xml`` and runs the copy's ``bundle.py``, which must refuse with
``DEPENDENCY_VERIFICATION_FAILED`` (exit 2). The JVM run is CI-only, so here ``bundle.py`` is a faked process;
what is asserted for real is the copy, the tamper and the verdict logic.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
SCRIPT = TOOLS_DIR / "tamper_check.py"
METADATA = Path("gradle") / "verification-metadata.xml"
SHA256 = re.compile(r'<sha256 value="([0-9a-f]+)"')


@pytest.fixture(scope="module")
def tamperer() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "tamper_check_under_test", syspath=TOOLS_DIR)


def _run(tamperer: ModuleType, runner: Callable[[Sequence[str]], tuple[int, str]], *args: str, contracts: Path = CONTRACTS) -> tuple[int, str]:
    lines: list[str] = []
    code = tamperer.run(["--contracts", str(contracts), *args], runner=runner, out=lines.append)
    return code, "\n".join(lines)


def _bundle_says(status: int, text: str, seen: list[list[str]] | None = None) -> Callable[[Sequence[str]], tuple[int, str]]:
    def run(command: Sequence[str]) -> tuple[int, str]:
        if seen is not None:
            seen.append(list(command))
        return status, text

    return run


def test_a_refusing_build_is_the_plant_detected(tamperer: ModuleType) -> None:
    code, output = _run(tamperer, _bundle_says(2, "CONTRACT-CHECK bundle: DEPENDENCY_VERIFICATION_FAILED: full: Dependency verification failed"))

    assert code == 0, output
    assert "PLANT_DETECTED" in output
    assert output.splitlines()[-1].startswith("counts: checksums_tampered=")


def test_the_copy_has_every_checksum_prefix_replaced_and_the_original_is_untouched(tamperer: ModuleType) -> None:
    original = (CONTRACTS / METADATA).read_text(encoding="utf-8")
    originals = SHA256.findall(original)
    seen: list[list[str]] = []
    inspected: list[list[str]] = []

    def inspecting(command: Sequence[str]) -> tuple[int, str]:
        seen.append(list(command))
        copy_root = Path(command[1]).parents[1]
        inspected.append(SHA256.findall((copy_root / METADATA).read_text(encoding="utf-8")))
        return 2, "DEPENDENCY_VERIFICATION_FAILED"

    code, output = _run(tamperer, inspecting)

    assert code == 0, output
    (tampered,) = inspected
    assert len(tampered) == len(originals) > 100
    assert all(new[:8] != old[:8] and len(new) == len(old) for new, old in zip(tampered, originals, strict=True)), "every prefix changed, every length kept"
    assert (CONTRACTS / METADATA).read_text(encoding="utf-8") == original
    assert f"checksums_tampered={len(originals)}" in output
    command = seen[0]
    assert command[1].endswith("tools/bundle.py") and str(CONTRACTS) not in command[1], "the copy's bundle.py runs, not the original"
    assert "--module" in command and "full" in command


def test_a_build_that_accepts_the_tampered_metadata_is_a_failure(tamperer: ModuleType) -> None:
    code, output = _run(tamperer, _bundle_says(0, "counts: modules=1 bundles=1 path_items=5"))

    assert code == 1 and "PLANT_NOT_DETECTED" in output


def test_a_build_that_fails_for_another_reason_proves_nothing(tamperer: ModuleType) -> None:
    code, output = _run(tamperer, _bundle_says(2, "CONTRACT-CHECK bundle: JVM_MISSING: no java on PATH"))

    assert code == 2 and "PLANT_INCONCLUSIVE" in output
    assert output.splitlines()[-1].startswith("counts: ")


def test_a_validation_failure_is_not_a_verification_failure(tamperer: ModuleType) -> None:
    code, output = _run(tamperer, _bundle_says(1, "CONTRACT-CHECK bundle: VALIDATION_FAILED: full: x"))

    assert code == 1 and "PLANT_NOT_DETECTED" in output


def test_missing_metadata_cannot_do_its_job(tamperer: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()

    code, output = _run(tamperer, _bundle_says(2, "DEPENDENCY_VERIFICATION_FAILED"), contracts=tmp_path)

    assert code == 2 and "METADATA_MISSING" in output


def test_metadata_without_a_checksum_cannot_do_its_job(tamperer: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle" / "verification-metadata.xml").write_text("<verification-metadata/>\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()

    code, output = _run(tamperer, _bundle_says(2, "DEPENDENCY_VERIFICATION_FAILED"), contracts=tmp_path)

    assert code == 2 and "ZERO_CHECKSUMS" in output
