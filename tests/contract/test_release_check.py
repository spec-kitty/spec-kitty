"""Planted-violation tests for ``contracts/tools/release_check.py`` (FR-022, D-17).

The fixture root ``contracts/tools/fixtures/release_check/root`` holds a clean control module (``clean``, version
1.0.0 with its CHANGELOG heading) and two planted ones: ``no-heading`` (version 1.2.0, the CHANGELOG has only a 1.1.0
heading) and ``mismatch`` (version 2.0.0). The script builds through the shared ``bundle.py``, so the bundle step is
real here (``--bundle-only``: no JVM).
"""

from __future__ import annotations

import hashlib
import shlex
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
ROOT = TOOLS_DIR / "fixtures" / "release_check" / "root"
SCRIPT = TOOLS_DIR / "release_check.py"
MIN_PATHS = ("--min-paths", "1")


@pytest.fixture(scope="module")
def releaser() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "release_check_under_test", syspath=TOOLS_DIR)


def _run(releaser: ModuleType, out: Path, *args: str, root: Path = ROOT) -> tuple[int, str]:
    lines: list[str] = []
    code = releaser.run(["--root", str(root), "--out", str(out), *MIN_PATHS, *args], out=lines.append)
    return code, "\n".join(lines)


def _release_line(output: str) -> list[str]:
    (line,) = [line for line in output.splitlines() if line.startswith("GH_RELEASE_ARGS ")]
    return shlex.split(line.removeprefix("GH_RELEASE_ARGS "))


# -- the clean control --------------------------------------------------------------------------------


def test_clean_module_with_its_tag_builds_checksums_verifies_and_prints_the_release_arguments(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-clean-v1.0.0")

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 verified=1"
    assert output.count("counts:") == 1
    directory = tmp_path / "release" / "clean"
    bundle = directory / "openapi.yaml"
    checksum = (directory / "openapi.yaml.sha256").read_text(encoding="utf-8")
    assert checksum == f"{hashlib.sha256(bundle.read_bytes()).hexdigest()}  openapi.yaml\n"  # noqa: TID251 -- file-integrity digest of a bundle
    arguments = _release_line(output)
    assert arguments[:4] == ["gh", "release", "create", "contract-clean-v1.0.0"]
    assert "--latest=false" in arguments and "--prerelease" not in arguments
    assert str(bundle) in arguments and str(directory / "openapi.yaml.sha256") in arguments
    assert "nothing was published" in output


def test_without_a_tag_the_candidate_tag_is_derived_for_every_module(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path)

    assert code == 1, "the planted modules fail in the same run"
    assert "CHANGELOG_HEADING_MISSING: contract-no-heading-v1.2.0:" in output
    assert "GH_RELEASE_ARGS gh release create contract-clean-v1.0.0 " in output
    assert "contract-mismatch-v2.0.0" in output, "mismatch is only a mismatch against a tag; its derived tag is consistent"
    assert output.splitlines()[-1] == "counts: modules=4 bundles=3 verified=3"


def test_a_prerelease_version_adds_prerelease_and_still_never_latest(releaser: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(ROOT / "clean", root / "clean")
    (root / "clean" / "openapi.yaml").write_text((root / "clean" / "openapi.yaml").read_text(encoding="utf-8").replace("1.0.0", "1.1.0-rc.1"), encoding="utf-8")
    (root / "clean" / "CHANGELOG.md").write_text("# Changelog\n\n## 1.1.0-rc.1\n\nEntry.\n", encoding="utf-8")

    code, output = _run(releaser, tmp_path / "out", "--tag", "contract-clean-v1.1.0-rc.1", root=root)

    assert code == 0, output
    arguments = _release_line(output)
    assert "--prerelease" in arguments and "--latest=false" in arguments


# -- -SNAPSHOT: work in progress, never released ----------------------------------------------------------


def test_a_snapshot_release_tag_is_refused_with_its_own_code(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-snapshot-v1.0.0-SNAPSHOT")

    assert code == 1
    assert "CONTRACT-CHECK release_check: SNAPSHOT_RELEASE_REFUSED: contract-snapshot-v1.0.0-SNAPSHOT:" in output
    assert "GH_RELEASE_ARGS" not in output, "no release command is printed for a snapshot"
    assert not (tmp_path / "release").exists(), "nothing is built or checksummed for a refused snapshot tag"


def test_the_snapshot_refusal_does_not_depend_on_the_module_or_its_version(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-absent-v2.0.0-SNAPSHOT")

    assert code == 1 and "SNAPSHOT_RELEASE_REFUSED: contract-absent-v2.0.0-SNAPSHOT:" in output
    assert "MODULE_UNKNOWN" not in output


@pytest.mark.parametrize("tag", ["contract-clean-v1.0.0-snapshot", "contract-clean-v1.0.0-SNAPSHOT2"])
def test_only_the_exact_snapshot_suffix_gets_the_snapshot_code(releaser: ModuleType, tmp_path: Path, tag: str) -> None:
    _, output = _run(releaser, tmp_path, "--tag", tag)

    assert "SNAPSHOT_RELEASE_REFUSED" not in output


def test_a_prerelease_ending_in_snapshot_is_still_a_snapshot(releaser: ModuleType, tmp_path: Path) -> None:
    _, output = _run(releaser, tmp_path, "--tag", "contract-clean-v1.0.0-rc.1-SNAPSHOT")

    assert "SNAPSHOT_RELEASE_REFUSED: contract-clean-v1.0.0-rc.1-SNAPSHOT:" in output


def test_a_dry_run_without_a_tag_builds_a_snapshot_module_but_prints_no_release_command(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--module", "snapshot")

    assert code == 0, output
    assert "SNAPSHOT_RELEASE_REFUSED" not in output
    assert "SNAPSHOT_DRY_RUN: contract-snapshot-v1.0.0-SNAPSHOT:" in output
    assert "GH_RELEASE_ARGS" not in output
    assert (tmp_path / "release" / "snapshot" / "openapi.yaml.sha256").is_file()
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 verified=1"


# -- tag rules ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tag", ["v1.0.0", "contract-clean-1.0.0", "contract-clean-v1.0", "contract--v1.0.0", "contract-clean-v01.0.0", "contract-Clean-v1.0.0", "preview/clean/p1"]
)
def test_a_malformed_tag_fails_with_tag_form(releaser: ModuleType, tmp_path: Path, tag: str) -> None:
    code, output = _run(releaser, tmp_path, "--tag", tag)

    assert code == 1 and f"CONTRACT-CHECK release_check: TAG_FORM: {tag}:" in output
    assert "GH_RELEASE_ARGS" not in output, "no argument list is printed for a tag that failed"


def test_a_tag_for_a_module_that_does_not_exist_fails_with_module_unknown(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-absent-v1.0.0")

    assert code == 1 and "MODULE_UNKNOWN: contract-absent-v1.0.0:" in output
    assert "GH_RELEASE_ARGS" not in output


def test_a_tag_version_that_is_not_the_module_version_fails_with_version_mismatch(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-mismatch-v1.0.0")

    assert code == 1
    assert "VERSION_MISMATCH: contract-mismatch-v1.0.0:" in output and "2.0.0" in output
    assert "GH_RELEASE_ARGS" not in output


def test_a_version_without_a_changelog_heading_fails(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-no-heading-v1.2.0")

    assert code == 1
    assert "CHANGELOG_HEADING_MISSING: contract-no-heading-v1.2.0:" in output
    assert "GH_RELEASE_ARGS" not in output
    assert not (tmp_path / "release" / "no-heading").exists(), "a tag that failed its rules is not built"


def test_a_missing_changelog_file_is_a_missing_heading(releaser: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(ROOT / "clean", root / "clean")
    (root / "clean" / "CHANGELOG.md").unlink()

    code, output = _run(releaser, tmp_path / "out", "--tag", "contract-clean-v1.0.0", root=root)

    assert code == 1 and "CHANGELOG_HEADING_MISSING" in output


# -- the checksum file, verified with sha256sum -c semantics ------------------------------------------------


def test_verify_accepts_a_matching_checksum_file_and_rejects_every_tamper(releaser: ModuleType, tmp_path: Path) -> None:
    directory = tmp_path / "release"
    directory.mkdir()
    (directory / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    releaser.write_checksum(directory)

    assert releaser.verify_checksum(directory) is None

    (directory / "openapi.yaml").write_text("openapi: 3.1.1\n", encoding="utf-8")
    assert "does not match" in (releaser.verify_checksum(directory) or "")

    (directory / "openapi.yaml.sha256").write_text("not a checksum line\n", encoding="utf-8")
    assert releaser.verify_checksum(directory) is not None

    (directory / "openapi.yaml.sha256").unlink()
    assert releaser.verify_checksum(directory) is not None


def test_a_failed_verification_is_reported_with_checksum_mismatch(releaser: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        releaser, "write_checksum", lambda directory: (directory / "openapi.yaml.sha256").write_text("0" * 64 + "  openapi.yaml\n", encoding="utf-8")
    )

    code, output = _run(releaser, tmp_path, "--tag", "contract-clean-v1.0.0")

    assert code == 1 and "CHECKSUM_MISMATCH: contract-clean-v1.0.0:" in output
    assert "GH_RELEASE_ARGS" not in output
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 verified=0"


def test_release_arguments_always_carry_latest_false(releaser: ModuleType) -> None:
    for tag, prerelease in (("contract-x-v1.0.0", False), ("contract-x-v1.0.0-rc.1", True), ("contract-x-v0.0.1-alpha", True)):
        arguments = releaser.release_arguments(tag, ["a", "b"], prerelease=releaser.is_prerelease(tag.rsplit("-v", 1)[1]), notes="n")
        assert "--latest=false" in arguments
        assert ("--prerelease" in arguments) is prerelease


@pytest.mark.parametrize(
    ("tag", "module", "version", "prerelease"),
    [
        ("contract-clean-v1.0.0", "clean", "1.0.0", False),
        ("contract-clean-v1.0.0-v2", "clean", "1.0.0-v2", True),
        ("contract-clean-v1.0.0-rc.1", "clean", "1.0.0-rc.1", True),
        ("contract-clean-v1.0.0+build-x", "clean", "1.0.0+build-x", False),
        ("contract-clean-v1.0.0-rc.1+build-x", "clean", "1.0.0-rc.1+build-x", True),
        ("contract-mission-status-v1.0.0-v2", "mission-status", "1.0.0-v2", True),
    ],
)
def test_the_tag_is_split_into_module_and_version_and_only_a_prerelease_part_makes_a_prerelease(
    releaser: ModuleType, tag: str, module: str, version: str, prerelease: bool
) -> None:
    """Regression: the workflow once split on the last ``-v`` and treated build metadata containing a hyphen as a prerelease."""
    match = releaser.TAG_PATTERN.match(tag)

    assert match is not None and (match["module"], match["version"]) == (module, version)
    assert releaser.is_prerelease(match["version"]) is prerelease


def test_the_release_arguments_carry_the_notes_and_verify_the_tag(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path, "--tag", "contract-clean-v1.0.0")

    assert code == 0, output
    arguments = _release_line(output)
    assert "--verify-tag" in arguments
    assert arguments[arguments.index("--notes") + 1] == "Contract clean 1.0.0. Verify the bundle with: sha256sum -c openapi.yaml.sha256"


def test_the_arguments_file_holds_exactly_the_arguments_after_gh_release_create_one_per_line(releaser: ModuleType, tmp_path: Path) -> None:
    args_file = tmp_path / "args.txt"

    code, output = _run(releaser, tmp_path / "out", "--tag", "contract-clean-v1.0.0", "--args-file", str(args_file))

    assert code == 0, output
    printed = _release_line(output)
    assert args_file.read_text(encoding="utf-8").splitlines() == printed[3:]
    assert printed[3] == "contract-clean-v1.0.0"


def test_an_arguments_file_is_not_written_when_the_release_check_fails(releaser: ModuleType, tmp_path: Path) -> None:
    args_file = tmp_path / "args.txt"

    code, _ = _run(releaser, tmp_path / "out", "--tag", "contract-mismatch-v1.0.0", "--args-file", str(args_file))

    assert code == 1 and not args_file.exists()


def test_an_arguments_file_without_a_tag_cannot_do_its_job(releaser: ModuleType, tmp_path: Path) -> None:
    code, output = _run(releaser, tmp_path / "out", "--args-file", str(tmp_path / "args.txt"))

    assert code == 2 and "ARGS_FILE_NEEDS_TAG" in output


# -- cannot do its job: exit 2 ---------------------------------------------------------------------------


def test_a_root_without_modules_cannot_do_its_job(releaser: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "root" / "tools").mkdir(parents=True)

    code, output = _run(releaser, tmp_path / "out", root=tmp_path / "root")

    assert code == 2 and "NO_MODULE" in output
    assert output.splitlines()[-1].startswith("counts: ")


@pytest.mark.parametrize("make", ["absent", "empty"])
def test_an_absent_or_empty_root_cannot_do_its_job(releaser: ModuleType, tmp_path: Path, make: str) -> None:
    root = tmp_path / "root"
    if make == "empty":
        root.mkdir()

    code, output = _run(releaser, tmp_path / "out", root=root)

    assert code == 2 and "MODULE_ROOT_EMPTY" in output


def test_an_empty_bundle_cannot_be_released(releaser: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bundle

    monkeypatch.setattr(bundle, "write_bundle", lambda module, out_dir: _empty_bundle(module, out_dir))

    code, output = _run(releaser, tmp_path, "--tag", "contract-clean-v1.0.0")

    assert code == 2 and "BUNDLE_EMPTY: clean:" in output
    assert output.splitlines()[-1].startswith("counts: ")
    assert not (tmp_path / "release").exists() or not list((tmp_path / "release").rglob("openapi.yaml.sha256"))


def test_a_bundle_step_that_cannot_run_blocks_the_release_before_any_checksum_is_written(releaser: ModuleType, tmp_path: Path) -> None:
    """The bundle step refuses an output directory inside the repository with exit 2; the release stops there."""
    inside = TOOLS_DIR / "release-output-must-not-be-here"

    code, output = _run(releaser, inside, "--tag", "contract-clean-v1.0.0")

    assert code == 2, output
    assert "CONTRACT-CHECK release_check: BUNDLE_STEP_BLOCKED: CONTRACT-CHECK bundle: OUT_INSIDE_REPOSITORY" in output
    assert output.splitlines()[-1].startswith("counts: ")
    assert not inside.exists(), "nothing was written, so no checksum file exists"


def _empty_bundle(module: Path, out_dir: Path) -> Path:
    target = out_dir / "bundle" / module.name / "openapi.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    return target


def test_the_script_never_publishes() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"gh"' in source, "the argument list names gh"
    assert "subprocess" not in source and "os.system" not in source, "nothing in the script can run gh"
