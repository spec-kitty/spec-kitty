"""Per-PR changelog fragments (``docs/changelog/unreleased/``) and their assembly into the changelog.

A pull request adds one file per changelog section instead of editing the shared
``CHANGELOG.md``, so two PRs never conflict on the changelog. At release time the fragments
are folded into the ``## [Unreleased]`` section and deleted. The assembled section must read
exactly as if the entries had been written into the changelog by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release.changelog_fragments import (
    FRAGMENT_DIR_REL,
    assemble,
    fragment_problems,
    load_fragments,
    main,
)
from scripts.release.extract_changelog import extract_changelog_section

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CHANGELOG = """\
---
title: Changelog
updated: '2026-10-31'
---
# Changelog

## [Unreleased] - 4.0.0rc8

_4.0.0rc8 candidate cycle._

### Added

- **Existing added entry** (#1).

### Fixed

- **Existing fixed entry** (#2). **Before:** it broke. **After:** it works.

## [4.0.0rc7] - 2026-10-15

### Fixed

- **Released entry** (#0).
"""

_HAND_WRITTEN = """\
---
title: Changelog
updated: '2026-10-31'
---
# Changelog

## [Unreleased] - 4.0.0rc8

_4.0.0rc8 candidate cycle._

### Breaking

- **A breaking entry** (#30). **Before:** old. **After:** new.

### Added

- **Existing added entry** (#1).
- **Fragment added entry** (#10).

### Fixed

- **Existing fixed entry** (#2). **Before:** it broke. **After:** it works.
- **Fragment fix nine** (#9).
  - a nested detail line
- **Fragment fix eleven** (#11).

## [4.0.0rc7] - 2026-10-15

### Fixed

- **Released entry** (#0).
"""


def _write(directory: Path, name: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _fragment_dir(tmp_path: Path) -> Path:
    directory = tmp_path / FRAGMENT_DIR_REL
    _write(directory, "README.md", "# Fragments\n\nNot a fragment.\n")
    _write(directory, "10.added.md", "- **Fragment added entry** (#10).\n")
    _write(directory, "11.fixed.md", "\n- **Fragment fix eleven** (#11).\n\n")
    _write(directory, "9.fixed.md", "- **Fragment fix nine** (#9).\n  - a nested detail line\n")
    _write(directory, "30.breaking.md", "- **A breaking entry** (#30). **Before:** old. **After:** new.\n")
    return directory


def test_assembly_reads_exactly_like_the_hand_written_changelog(tmp_path: Path) -> None:
    fragments, problems = load_fragments(_fragment_dir(tmp_path))

    assert problems == []
    assert assemble(_CHANGELOG, fragments) == _HAND_WRITTEN


def _release_cut(text: str) -> str:
    """Retitle the Unreleased heading the way the release chore does before tagging."""
    return text.replace("## [Unreleased] - 4.0.0rc8", "## [4.0.0rc8] - 2026-11-02")


def test_release_extraction_of_the_assembled_section_matches_the_hand_written_one(tmp_path: Path) -> None:
    fragments, _ = load_fragments(_fragment_dir(tmp_path))

    assembled = extract_changelog_section(_release_cut(assemble(_CHANGELOG, fragments)), "4.0.0rc8")

    assert assembled == extract_changelog_section(_release_cut(_HAND_WRITTEN), "4.0.0rc8")
    assert "Fragment fix nine" in assembled


def test_fragments_sort_numerically_then_by_name(tmp_path: Path) -> None:
    directory = tmp_path / FRAGMENT_DIR_REL
    for name in ("100.fixed.md", "9.fixed.md", "my-branch.fixed.md", "10.fixed.md"):
        _write(directory, name, f"- **{name}** (#1).\n")

    fragments, _ = load_fragments(directory)

    assert [fragment.path.name for fragment in fragments] == ["9.fixed.md", "10.fixed.md", "100.fixed.md", "my-branch.fixed.md"]


def test_no_fragments_leaves_the_changelog_byte_identical() -> None:
    assert assemble(_CHANGELOG, []) == _CHANGELOG


@pytest.mark.parametrize(
    ("name", "text", "needle"),
    [
        ("6862.fixes.md", "- **x** (#1).\n", "section"),
        ("6862.md", "- **x** (#1).\n", "name"),
        ("Fix_It.fixed.md", "- **x** (#1).\n", "name"),
        ("6862.fixed.txt", "- **x** (#1).\n", "name"),
        ("6862.fixed.md", "\n\n", "empty"),
        ("6862.fixed.md", "Some prose first.\n- **x** (#1).\n", "start with"),
        ("6862.fixed.md", "- **x** (#1).\n\n### Fixed\n", "heading"),
        ("6862.fixed.md", "- **x** (#1).\n\n  ```bash\n  echo hi\n", "fence"),
    ],
)
def test_malformed_fragments_are_reported(tmp_path: Path, name: str, text: str, needle: str) -> None:
    directory = tmp_path / FRAGMENT_DIR_REL
    _write(directory, name, text)

    _, problems = load_fragments(directory)

    assert len(problems) == 1
    assert name in problems[0]
    assert needle in problems[0]


def test_a_heading_inside_a_fenced_block_is_allowed(tmp_path: Path) -> None:
    directory = tmp_path / FRAGMENT_DIR_REL
    _write(directory, "1.added.md", "- **Shows output** (#1).\n\n  ```text\n  ## not a heading\n  ```\n")

    assert fragment_problems(directory) == []


def test_assembly_refuses_a_changelog_without_an_unreleased_section(tmp_path: Path) -> None:
    fragments, _ = load_fragments(_fragment_dir(tmp_path))

    with pytest.raises(ValueError, match="Unreleased"):
        assemble("# Changelog\n\n## [1.0.0] - 2026-01-01\n", fragments)


def test_assemble_write_folds_fragments_in_and_deletes_them(tmp_path: Path) -> None:
    directory = _fragment_dir(tmp_path)
    changelog = _write(tmp_path, "CHANGELOG.md", _CHANGELOG)

    code = main(["assemble", "--write", "--changelog", str(changelog), "--fragments", str(directory), "--today", "2026-11-02"])

    assert code == 0
    assert changelog.read_text(encoding="utf-8") == _HAND_WRITTEN.replace("updated: '2026-10-31'", "updated: '2026-11-02'")
    assert sorted(path.name for path in directory.iterdir()) == ["README.md"]


def test_assemble_without_write_is_a_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = _fragment_dir(tmp_path)
    changelog = _write(tmp_path, "CHANGELOG.md", _CHANGELOG)

    assert main(["assemble", "--changelog", str(changelog), "--fragments", str(directory)]) == 0

    assert changelog.read_text(encoding="utf-8") == _CHANGELOG
    assert "Fragment fix nine" in capsys.readouterr().out
    assert len(list(directory.glob("*.fixed.md"))) == 2


def test_assemble_refuses_malformed_fragments_and_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = _fragment_dir(tmp_path)
    _write(directory, "12.fixes.md", "- **x** (#12).\n")
    changelog = _write(tmp_path, "CHANGELOG.md", _CHANGELOG)

    assert main(["assemble", "--write", "--changelog", str(changelog), "--fragments", str(directory)]) == 1

    assert changelog.read_text(encoding="utf-8") == _CHANGELOG
    assert "12.fixes.md" in capsys.readouterr().err
    assert (directory / "10.added.md").exists()


def test_the_live_fragment_directory_is_well_formed() -> None:
    """Every fragment a pull request adds must have a valid name and shape."""
    live = Path(__file__).resolve().parents[2] / FRAGMENT_DIR_REL

    assert fragment_problems(live) == []


def test_the_tag_guard_reads_the_same_fragment_directory() -> None:
    """``validate_release`` runs as a plain script, so it mirrors two constants; they must agree."""
    from scripts.release import changelog_fragments, validate_release

    assert "/".join(validate_release._FRAGMENT_DIR) == changelog_fragments.FRAGMENT_DIR_REL
    assert validate_release._NON_FRAGMENTS == changelog_fragments.NON_FRAGMENTS


def test_assembly_refuses_text_that_would_swallow_the_released_sections(tmp_path: Path) -> None:
    """Defense in depth behind the shape check: never write a changelog whose [Unreleased] grew past its end."""
    from scripts.release.changelog_fragments import Fragment

    open_fence = Fragment(tmp_path / "1.added.md", "1", "Added", ("- **E** (#1). Example:", "", "  ```bash", "  echo hi"))

    with pytest.raises(ValueError, match="past the next release heading"):
        assemble(_CHANGELOG, [open_fence])


def test_a_subdirectory_is_reported_not_crashed_on(tmp_path: Path) -> None:
    from scripts.release.changelog_fragments import fragment_paths

    directory = tmp_path / FRAGMENT_DIR_REL
    (directory / "sub").mkdir(parents=True)
    _write(directory, "1.fixed.md", "- **x** (#1).\n")

    assert [path.name for path in fragment_paths(directory)] == ["1.fixed.md"]
    assert any("subdirectories" in problem for problem in fragment_problems(directory))
