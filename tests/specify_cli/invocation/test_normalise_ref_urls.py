"""URL handling of ``invocation.writer.normalise_ref`` (#5270).

``--artifact`` values flow through ``normalise_ref``. A value carrying a URI
scheme (``<scheme>://...``) is a link, not a filesystem path, and must be
recorded verbatim: path-resolving ``https://host/x`` collapsed the ``//`` and
stored ``https:/host/x``.

Decided behaviour:

- any RFC 3986 scheme of two or more characters followed by ``://`` passes
  through unchanged -- ``http``, ``https``, and also ``file``/``s3``/``git+ssh``
  (a ``file://`` URI is already absolute and unambiguous; rewriting it into a
  bare path would change what the operator recorded);
- a single-letter "scheme" is a Windows drive letter (``C:\\x``, ``C:/x``) and
  stays on the path-normalisation branch;
- ordinary relative/absolute paths are normalised exactly as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.invocation.writer import normalise_ref

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/spec-kitty/spec-kitty/pull/5266",
        "http://example.com/a/b",
        "https://example.com/a/../b?q=1#frag",
        "HTTPS://Example.com/Path",
        "file:///tmp/report.md",
        "s3://bucket/key/with//double",
        "git+ssh://git@github.com/org/repo.git",
    ],
)
def test_url_scheme_refs_are_recorded_verbatim(url: str, tmp_path: Path) -> None:
    assert normalise_ref(url, tmp_path) == url


@pytest.mark.parametrize("drive_path", ["C:/x/../y", "C:\\x\\..\\y"])
def test_windows_drive_paths_are_not_mistaken_for_a_scheme(drive_path: str, tmp_path: Path) -> None:
    """A drive letter is path-normalised, never passed through as a URL."""
    if "\\" in drive_path and Path("a\\b").name == "a\\b":
        # On POSIX a backslash is a filename character, so no ``..`` collapse
        # happens; the ref still takes the path branch (repo-relative).
        assert normalise_ref(drive_path, tmp_path) == drive_path
        return
    result = normalise_ref(drive_path, tmp_path)
    assert ".." not in result
    assert result.endswith("y")


def test_relative_path_still_normalised(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    assert normalise_ref("docs/../docs/out.md", tmp_path) == str(Path("docs") / "out.md")


def test_absolute_path_inside_repo_still_made_relative(tmp_path: Path) -> None:
    target = tmp_path / "src" / "foo.py"
    target.parent.mkdir()
    target.write_text("x")
    assert normalise_ref(str(target), tmp_path) == str(Path("src") / "foo.py")


def test_scheme_without_double_slash_stays_a_path(tmp_path: Path) -> None:
    """Only ``scheme://`` counts as a URL; ``name:rest`` is still a path."""
    assert normalise_ref("notes:draft/../final.md", tmp_path) == "final.md"
