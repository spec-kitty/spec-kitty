"""Security regression tests for org-doctrine source implementations.

Covers the P1 findings from the Robert adversarial review (2026-05):

1. ``_safe_extract_tar`` / ``_safe_extract_zip`` — sibling-prefix bypass via
   ``str.startswith`` (now fixed to use ``Path.relative_to``).
2. ``_safe_extract_tar`` — symlink/hardlink in tar allows write-through to
   arbitrary paths.
3. ``ApiSource._fetch_artifacts`` / ``_fetch_drg_extensions`` — server-
   controlled filenames can achieve arbitrary file write via ``../../..`` or
   absolute paths.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import quote
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers — build malicious archives in memory
# ---------------------------------------------------------------------------


def _make_tar_gz(members: list[tuple[str, bytes]]) -> bytes:
    """Return a gzip-compressed tar containing *members* as (name, data) pairs."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _make_tar_gz_with_symlink(link_name: str, link_target: str) -> bytes:
    """Return a gzip-compressed tar with one symlink entry."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=link_name)
        info.type = tarfile.SYMTYPE
        info.linkname = link_target
        tf.addfile(info)
    return buf.getvalue()


def _make_tar_gz_with_hardlink(link_name: str, link_target: str) -> bytes:
    """Return a gzip-compressed tar with one hardlink entry."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=link_name)
        info.type = tarfile.LNKTYPE
        info.linkname = link_target
        tf.addfile(info)
    return buf.getvalue()


def _make_zip(members: list[tuple[str, bytes]]) -> bytes:
    """Return a zip archive containing *members*."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()


def _make_stream_response(
    chunks: list[bytes],
    *,
    url: str = "https://example.com/pack.zip",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.reason = "OK"
    resp.url = url
    resp.headers = headers or {}
    resp.iter_content.return_value = iter(chunks)
    return resp


# ---------------------------------------------------------------------------
# _safe_extract_tar — path traversal (sibling-prefix bypass)
# ---------------------------------------------------------------------------


class TestSafeExtractTarPathTraversal:
    """The old ``startswith`` check could be bypassed by a sibling-prefix path
    (e.g., ``/nonexistent/target-evil/x`` starts with ``/nonexistent/target``).

    The fix uses ``Path.relative_to`` which correctly rejects sibling paths.
    """

    def test_normal_member_is_extracted(self, tmp_path: Path) -> None:
        """Sanity: a legitimate archive member is extracted correctly."""
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        data = _make_tar_gz([("file.yaml", b"key: value\n")])
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            _safe_extract_tar(tf, tmp_path)
        assert (tmp_path / "file.yaml").exists()

    @pytest.mark.parametrize(
        "evil_name",
        [
            "../evil.yaml",
            "../../etc/passwd",
            "/etc/passwd",
            "/nonexistent/evil",
        ],
    )
    def test_path_traversal_is_rejected(
        self, tmp_path: Path, evil_name: str
    ) -> None:
        """Path-traversal entries must raise TarError, not extract."""
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        data = _make_tar_gz([(evil_name, b"evil\n")])
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf, pytest.raises(tarfile.TarError, match="(?i)path traversal|Refusing"):
            _safe_extract_tar(tf, tmp_path)

    def test_sibling_prefix_bypass_is_rejected(self, tmp_path: Path) -> None:
        """Sibling-prefix bypass: ``/nonexistent/target-evil/x`` must not escape via
        startswith(``/nonexistent/target``).

        This is the exact attack vector fixed by the P1 patch (2026-05).
        """
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        # Create the target dir so its suffix-neighbor has the same str prefix.
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        sibling = tmp_path / "target-evil"
        sibling.mkdir()

        # Construct an archive entry whose resolved path lands in target-evil/.
        # From inside target_dir, ``../../target-evil/x`` resolves to sibling/x.
        evil_member = "../../" + sibling.name + "/x.yaml"
        data = _make_tar_gz([(evil_member, b"evil\n")])

        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf, pytest.raises(tarfile.TarError, match="(?i)path traversal|Refusing"):
            _safe_extract_tar(tf, target_dir)

        # Confirm nothing landed in the sibling dir.
        assert not list(sibling.iterdir())


# ---------------------------------------------------------------------------
# _safe_extract_tar — symlink / hardlink rejection
# ---------------------------------------------------------------------------


class TestSafeExtractTarSymlinkRejection:
    """Malicious tars can create symlinks that redirect subsequent writes."""

    def test_symlink_entry_is_rejected(self, tmp_path: Path) -> None:
        """Symlink entries must raise TarError before extraction begins."""
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        data = _make_tar_gz_with_symlink("etc", "/etc")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf, pytest.raises(tarfile.TarError, match="(?i)symlink|Refusing"):
            _safe_extract_tar(tf, tmp_path)

    def test_hardlink_entry_is_rejected(self, tmp_path: Path) -> None:
        """Hardlink entries must raise TarError before extraction begins."""
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        data = _make_tar_gz_with_hardlink("shadow", "/etc/shadow")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf, pytest.raises(tarfile.TarError, match="(?i)symlink|hardlink|Refusing"):
            _safe_extract_tar(tf, tmp_path)

    def test_symlink_does_not_land_on_disk(self, tmp_path: Path) -> None:
        """No symlink must appear on disk after a rejected extraction."""
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        data = _make_tar_gz_with_symlink("mylink", "/etc")
        with (
            tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf,
            contextlib.suppress(tarfile.TarError),
        ):
            _safe_extract_tar(tf, tmp_path)

        assert not list(tmp_path.iterdir()), (
            "symlink must not have been written to disk"
        )


# ---------------------------------------------------------------------------
# _safe_extract_zip — path traversal
# ---------------------------------------------------------------------------


class TestSafeExtractZipPathTraversal:
    """Zip path-traversal checks mirror the tar fix."""

    @pytest.mark.parametrize(
        "evil_name",
        [
            "../evil.yaml",
            "../../etc/passwd",
        ],
    )
    def test_path_traversal_is_rejected(
        self, tmp_path: Path, evil_name: str
    ) -> None:
        from specify_cli.doctrine.sources.https_source import _safe_extract_zip  # noqa: PLC0415

        data = _make_zip([(evil_name, b"evil\n")])
        with zipfile.ZipFile(io.BytesIO(data)) as zf, pytest.raises(zipfile.BadZipFile, match="(?i)path traversal|Refusing"):
            _safe_extract_zip(zf, tmp_path)

    def test_sibling_prefix_bypass_is_rejected(self, tmp_path: Path) -> None:
        from specify_cli.doctrine.sources.https_source import _safe_extract_zip  # noqa: PLC0415

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        sibling = tmp_path / "target-evil"
        sibling.mkdir()

        evil_member = "../../" + sibling.name + "/x.yaml"
        data = _make_zip([(evil_member, b"evil\n")])
        with zipfile.ZipFile(io.BytesIO(data)) as zf, pytest.raises(zipfile.BadZipFile, match="(?i)path traversal|Refusing"):
            _safe_extract_zip(zf, target_dir)

        assert not list(sibling.iterdir())


# ---------------------------------------------------------------------------
# ApiSource — server-controlled filename traversal
# ---------------------------------------------------------------------------


def _make_api_response(
    status_code: int, body: dict, headers: dict | None = None
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.headers = headers or {}
    return resp


class TestApiSourceFilenameTraversal:
    """ApiSource must validate server-supplied filenames before writing."""

    @pytest.mark.parametrize(
        "evil_filename",
        [
            "../../etc/passwd",
            "../outside.yaml",
            "/etc/passwd",
            "/nonexistent/evil",
            "foo/bar.yaml",          # path separator inside basename
            "foo\x00bar.yaml",       # null byte
        ],
    )
    def test_artifact_traversal_filename_is_skipped(
        self, tmp_path: Path, evil_filename: str
    ) -> None:
        """Evil filenames from /artifacts/{type} are silently skipped (not written)."""
        from specify_cli.doctrine.sources.api_source import ApiSource  # noqa: PLC0415

        source = ApiSource(url="https://example.com/api")

        # Patch _request to return a scripted artifact list with evil filename.
        artifact_response = _make_api_response(
            200,
            {"artifacts": [{"filename": evil_filename, "content": "evil: true\n"}]},
        )

        with patch.object(source, "_request", return_value=artifact_response):
            written, err = source._fetch_artifact_type(tmp_path, "directives")

        assert written == 0, (
            f"Evil filename {evil_filename!r} must not be written; got written={written}"
        )
        # Nothing must have escaped the target_dir.
        for p in tmp_path.rglob("*"):
            assert tmp_path in p.parents or p == tmp_path, (
                f"File escaped target_dir: {p}"
            )

    def test_safe_filename_is_written(self, tmp_path: Path) -> None:
        """A safe filename from the server IS written correctly."""
        from specify_cli.doctrine.sources.api_source import ApiSource  # noqa: PLC0415

        source = ApiSource(url="https://example.com/api")
        artifact_response = _make_api_response(
            200,
            {"artifacts": [{"filename": "my-directive.yaml", "content": "key: val\n"}]},
        )

        with patch.object(source, "_request", return_value=artifact_response):
            written, err = source._fetch_artifact_type(tmp_path, "directives")

        assert written == 1
        assert (tmp_path / "directives" / "my-directive.yaml").exists()

    @pytest.mark.parametrize(
        "evil_filename",
        [
            "../../drg/escape.yaml",
            "/etc/passwd",
        ],
    )
    def test_drg_extension_traversal_filename_is_skipped(
        self, tmp_path: Path, evil_filename: str
    ) -> None:
        """Evil filenames from /drg-extensions are silently skipped."""
        from specify_cli.doctrine.sources.api_source import ApiSource  # noqa: PLC0415

        source = ApiSource(url="https://example.com/api")
        drg_response = _make_api_response(
            200,
            {"fragments": [{"filename": evil_filename, "content": "evil: true\n"}]},
        )

        with patch.object(source, "_request", return_value=drg_response):
            written, err = source._fetch_drg_extensions(tmp_path)

        assert written == 0, (
            f"Evil DRG filename {evil_filename!r} must not be written; got written={written}"
        )


# ---------------------------------------------------------------------------
# HttpsBundleSource — size-limit / decompression-bomb guards
# ---------------------------------------------------------------------------


class TestHttpsBundleSourceSizeLimits:
    def test_declared_raw_archive_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.doctrine.sources import https_source  # noqa: PLC0415
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource  # noqa: PLC0415

        monkeypatch.setattr(https_source, "MAX_ARCHIVE_BYTES", 4)
        source = HttpsBundleSource(url="https://example.com/pack.zip")
        response = _make_stream_response(
            [],
            headers={"Content-Length": "5"},
        )
        monkeypatch.setattr(source, "_get_with_retry", lambda _url: response)

        result = source.fetch(tmp_path)

        assert result.ok is False
        assert "raw byte limit" in " ".join(result.errors)
        assert not any(tmp_path.iterdir())

    def test_streamed_raw_archive_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.doctrine.sources import https_source  # noqa: PLC0415
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource  # noqa: PLC0415

        monkeypatch.setattr(https_source, "MAX_ARCHIVE_BYTES", 3)
        source = HttpsBundleSource(url="https://example.com/pack.zip")
        response = _make_stream_response([b"ab", b"cd"])
        monkeypatch.setattr(source, "_get_with_retry", lambda _url: response)

        result = source.fetch(tmp_path)

        assert result.ok is False
        assert "raw byte limit" in " ".join(result.errors)
        assert not any(tmp_path.iterdir())

    def test_tar_extracted_byte_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.doctrine.sources import https_source  # noqa: PLC0415
        from specify_cli.doctrine.sources.https_source import _safe_extract_tar  # noqa: PLC0415

        monkeypatch.setattr(https_source, "MAX_EXTRACTED_BYTES", 1)
        data = _make_tar_gz([("file.yaml", b"xx")])

        with (
            tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf,
            pytest.raises(
                https_source.ArchiveSizeLimitError,
                match="extracted byte limit",
            ),
        ):
            _safe_extract_tar(tf, tmp_path)

    def test_zip_member_count_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.doctrine.sources import https_source  # noqa: PLC0415
        from specify_cli.doctrine.sources.https_source import _safe_extract_zip  # noqa: PLC0415

        monkeypatch.setattr(https_source, "MAX_ARCHIVE_MEMBERS", 0)
        data = _make_zip([("file.yaml", b"x")])

        with (
            zipfile.ZipFile(io.BytesIO(data)) as zf,
            pytest.raises(
                https_source.ArchiveSizeLimitError,
                match="member count limit",
            ),
        ):
            _safe_extract_zip(zf, tmp_path)


# ---------------------------------------------------------------------------
# GitSource — token redaction
# ---------------------------------------------------------------------------


def test_git_source_redacts_injected_oauth_token_from_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kernel.git.runner import GitResult  # noqa: PLC0415
    from specify_cli.doctrine.sources.git_source import GitSource  # noqa: PLC0415

    token = "ghp_secret/with@reserved"
    monkeypatch.setenv("GIT_TOKEN", token)
    source = GitSource(url="https://github.com/acme/private-pack.git")

    def _fake_clone(url: str, dest: Path, **_kwargs: object) -> GitResult:
        assert token not in url
        assert quote(token, safe="") in url
        return GitResult(
            returncode=128,
            stdout=b"",
            stderr=(
                b"fatal: unable to access "
                b"'https://oauth2:ghp_secret/with@reserved@github.com/acme/private-pack.git/'"
            ),
        )

    # The clone is the kernel owner's (``kernel.git.remote.clone_repository``).
    monkeypatch.setattr("specify_cli.doctrine.sources.git_source.clone_repository", _fake_clone)

    result = source.fetch(tmp_path / "clone")

    assert result.ok is False
    error_text = " ".join(result.errors)
    assert token not in error_text
    assert "oauth2:<redacted>@" in error_text


_OPERATOR_SECRET = "hunter2"
_OPERATOR_URL = f"https://user:{_OPERATOR_SECRET}@git.example.test/acme/pack.git"


def _time_out_like_a_real_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the kernel runner's ``subprocess.run`` time out exactly as a stalled transport does.

    ``run_git`` turns the real ``TimeoutExpired`` (whose ``str`` is the FULL argv,
    URL included) into ``GitCommandError.stderr``; nothing here fakes that step.
    """

    def _stalled(argv: list[str], *, timeout: float, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr("kernel.git.runner.subprocess.run", _stalled)


def test_git_source_clone_timeout_never_surfaces_an_operator_credentialed_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A credential written into the operator's own URL (not the injected oauth2 form) must not leak on timeout."""
    from specify_cli.doctrine.sources.git_source import GitSource  # noqa: PLC0415

    monkeypatch.delenv("GIT_TOKEN", raising=False)
    _time_out_like_a_real_git(monkeypatch)

    result = GitSource(url=_OPERATOR_URL).fetch(tmp_path / "clone")

    assert result.ok is False
    assert _OPERATOR_SECRET not in " ".join(result.errors)
    assert result.errors == ["git clone timed out after 120s"]
    assert not (tmp_path / "clone").exists()


def test_git_source_update_fetch_timeout_never_surfaces_the_remote_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.doctrine.sources.git_source import GitSource  # noqa: PLC0415

    (tmp_path / ".git").mkdir()
    monkeypatch.delenv("GIT_TOKEN", raising=False)
    _time_out_like_a_real_git(monkeypatch)

    result = GitSource(url=_OPERATOR_URL).fetch(tmp_path)

    assert result.ok is False
    assert _OPERATOR_SECRET not in " ".join(result.errors)
    assert result.errors == ["git fetch timed out after 15s"]
    assert (tmp_path / ".git").is_dir()


def test_git_source_git_not_runnable_reports_a_fixed_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.doctrine.sources.git_source import GitSource  # noqa: PLC0415

    def _missing(argv: list[str], **_kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", " ".join(argv))

    monkeypatch.setattr("kernel.git.runner.subprocess.run", _missing)

    result = GitSource(url=_OPERATOR_URL).fetch(tmp_path / "clone")

    assert result.ok is False
    assert _OPERATOR_SECRET not in " ".join(result.errors)
    assert result.errors == ["git could not be run"]


def test_git_source_update_fetch_failure_is_redacted_and_leaves_the_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git.runner import GitResult  # noqa: PLC0415
    from specify_cli.doctrine.sources.git_source import GitSource  # noqa: PLC0415

    (tmp_path / ".git").mkdir()
    source = GitSource(url="https://github.com/acme/private-pack.git")
    seen: list[tuple[Path, str]] = []

    def _failed_fetch(cwd: Path, remote: str, **_kwargs: object) -> GitResult:
        seen.append((cwd, remote))
        return GitResult(returncode=1, stdout=b"", stderr=b"fatal: unable to access 'https://oauth2:tok@github.com/x.git/'")

    monkeypatch.setattr("specify_cli.doctrine.sources.git_source.fetch_tags", _failed_fetch)

    result = source.fetch(tmp_path)

    assert seen == [(tmp_path, "origin")]
    assert result.ok is False
    assert "tok" not in " ".join(result.errors)
    assert (tmp_path / ".git").is_dir()
