"""``kernel.release_assets``: the one owner of release-asset downloads (FR-003, NFR-004).

Covers the URL shape, the scheme refusal, the atomic write (no ``.part-*``
left behind, no destination on a mid-stream failure), the redirect-downgrade
refusal and the bounded, credential-free failure reason. No network: every
download reads a ``file://`` fixture or a monkeypatched stream.
"""

from __future__ import annotations

import email.message
import http.client
import importlib.metadata
import io
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from kernel import release_assets
from kernel.release_assets import DEFAULT_TIMEOUT, ReleaseAssetUnavailable, asset_url, download

pytestmark = pytest.mark.fast


# --------------------------------------------------------------------------- #
# asset_url
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "repository",
    [
        "https://github.com/spec-kitty/spec-kitty-events",
        "https://github.com/spec-kitty/spec-kitty-events/",
        "https://github.com/spec-kitty/spec-kitty-events.git",
        "https://github.com/spec-kitty/spec-kitty-events.git/",
    ],
)
def test_https_asset_url_uses_the_release_download_shape(repository: str) -> None:
    assert asset_url(repository, "service-v0.1.0", "a.jar") == "https://github.com/spec-kitty/spec-kitty-events/releases/download/service-v0.1.0/a.jar"


def test_file_asset_url_uses_the_tag_directory(tmp_path: Path) -> None:
    url = asset_url(tmp_path.as_uri(), "service-v0.1.0", "a.jar")
    assert url == f"{tmp_path.as_uri()}/service-v0.1.0/a.jar"
    assert asset_url(tmp_path.as_uri() + "/", "service-v0.1.0", "a.jar") == url


@pytest.mark.parametrize("repository", ["http://example.com/o/r", "ftp://example.com/o/r", "", "github.com/o/r"])
def test_asset_url_refuses_other_schemes(repository: str) -> None:
    with pytest.raises(ValueError, match="https:// or file://"):
        asset_url(repository, "service-v0.1.0", "a.jar")


# --------------------------------------------------------------------------- #
# download
# --------------------------------------------------------------------------- #


def test_default_timeout_is_sixty_seconds() -> None:
    assert DEFAULT_TIMEOUT == 60.0


@pytest.mark.parametrize("url", ["http://example.com/a", "ftp://example.com/a", "", "data:,x", "file://evil.example/share/a"])
def test_download_refuses_other_schemes(tmp_path: Path, url: str) -> None:
    with pytest.raises(ValueError, match="https:// or file://"):
        download(url, tmp_path / "out")
    assert list(tmp_path.iterdir()) == []


def test_file_download_writes_atomically(tmp_path: Path) -> None:
    source = tmp_path / "src" / "asset.bin"
    source.parent.mkdir()
    payload = os.urandom(3 * 1024 * 1024 + 17)
    source.write_bytes(payload)
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    download(source.as_uri(), dest_dir / "asset.bin")

    assert (dest_dir / "asset.bin").read_bytes() == payload
    assert [p.name for p in dest_dir.iterdir()] == ["asset.bin"]


def test_download_replaces_an_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "asset.bin"
    source.write_bytes(b"new")
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"old")
    download(source.as_uri(), dest)
    assert dest.read_bytes() == b"new"


def test_missing_file_source_raises_unavailable_and_leaves_nothing(tmp_path: Path) -> None:
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    with pytest.raises(ReleaseAssetUnavailable) as info:
        download((tmp_path / "absent.bin").as_uri(), dest_dir / "out.bin")
    assert info.value.reason
    assert list(dest_dir.iterdir()) == []


class _FailsAfterFirstChunk(io.RawIOBase):
    def __init__(self) -> None:
        self.calls = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return b"x" * 1024
        raise TimeoutError("timed out")


def test_mid_stream_failure_leaves_no_destination_and_no_part_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _FailsAfterFirstChunk()
    monkeypatch.setattr(release_assets, "_open", lambda url, timeout: stream)
    dest = tmp_path / "out.bin"

    with pytest.raises(ReleaseAssetUnavailable) as info:
        download("https://example.invalid/o/r/releases/download/t/a", dest)

    assert stream.calls >= 2, "the failure must happen after the first chunk was written"
    assert list(tmp_path.iterdir()) == []
    assert "TimeoutError" in info.value.reason


def test_download_passes_the_timeout_to_the_opener(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []

    def fake_open(url: str, timeout: float) -> io.BytesIO:
        seen.append(timeout)
        return io.BytesIO(b"data")

    monkeypatch.setattr(release_assets, "_open", fake_open)
    download("https://example.invalid/a", tmp_path / "a", timeout=7.5)
    download("https://example.invalid/b", tmp_path / "b")
    assert seen == [7.5, DEFAULT_TIMEOUT]
    assert (tmp_path / "a").read_bytes() == b"data"


def test_failure_reason_never_carries_credentials_or_headers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = email.message.Message()
    headers["Authorization"] = "token s3cret"

    def fake_open(url: str, timeout: float) -> io.BytesIO:
        raise urllib.error.HTTPError(url, 404, "Not Found s3cret", headers, None)

    monkeypatch.setattr(release_assets, "_open", fake_open)
    with pytest.raises(ReleaseAssetUnavailable) as info:
        download("https://user:s3cret@example.invalid/a", tmp_path / "a")
    text = str(info.value)
    assert "s3cret" not in text
    assert "HTTP 404" in info.value.reason
    assert "***@" in info.value.url


def test_user_agent_names_spec_kitty() -> None:
    request = release_assets._request("https://example.invalid/a")
    assert request.get_header("User-agent", "").startswith("spec-kitty/")


def test_user_agent_falls_back_to_dev_when_the_version_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr(importlib.metadata, "version", boom)
    assert release_assets._user_agent() == "spec-kitty/dev"


# --------------------------------------------------------------------------- #
# Redirects
# --------------------------------------------------------------------------- #


def _redirect(newurl: str) -> urllib.request.Request | None:
    handler = release_assets._NoDowngradeRedirectHandler()
    request = urllib.request.Request("https://github.com/o/r/releases/download/t/a")
    return handler.redirect_request(request, io.BytesIO(), 302, "Found", http.client.HTTPMessage(), newurl)


def test_https_to_http_redirect_is_refused() -> None:
    with pytest.raises(urllib.error.HTTPError, match="non-https"):
        _redirect("http://objects.githubusercontent.com/a")


def test_https_to_https_redirect_is_followed() -> None:
    followed = _redirect("https://objects.githubusercontent.com/a")
    assert followed is not None
    assert followed.full_url == "https://objects.githubusercontent.com/a"


def test_opener_installs_the_downgrade_refusal() -> None:
    handlers = vars(release_assets._opener())["handlers"]
    assert any(isinstance(h, release_assets._NoDowngradeRedirectHandler) for h in handlers)


def test_opener_honours_a_proxy_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """``ProxyHandler`` registers only when a proxy is configured, so set one rather than rely on the runner's env."""
    for name in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)  # urllib lets the lowercase variable win over the uppercase one
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    handlers = vars(release_assets._opener())["handlers"]
    proxies = [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]
    assert proxies, "the opener must pick up HTTPS_PROXY from the environment"
    assert proxies[0].proxies.get("https") == "http://proxy.invalid:3128"


# --------------------------------------------------------------------------- #
# F8: certificate and hostname verification are on (non-vacuity)
# --------------------------------------------------------------------------- #


def _https_context(opener: urllib.request.OpenerDirector) -> ssl.SSLContext:
    handlers = [handler for handler in opener.handlers if isinstance(handler, urllib.request.HTTPSHandler)]
    assert len(handlers) == 1, f"expected exactly one HTTPS handler, got {handlers}"
    context: ssl.SSLContext = handlers[0]._context  # the context every https:// download is opened with
    return context


def test_the_https_opener_requires_a_verified_certificate_and_hostname() -> None:
    context = _https_context(release_assets._opener())
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_the_context_probe_sees_an_unverified_context() -> None:
    """Control: the probe reads the opener's real context, so a disabled check would turn the test above red."""
    unverified = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    context = _https_context(unverified)
    assert context.verify_mode != ssl.CERT_REQUIRED
    assert context.check_hostname is False


# --------------------------------------------------------------------------- #
# F10: Ctrl-C mid-download leaves nothing behind
# --------------------------------------------------------------------------- #


class _InterruptedAfterFirstChunk(io.RawIOBase):
    """A stream whose second read is the user's Ctrl-C."""

    def __init__(self) -> None:
        self.calls = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return b"x" * 1024
        raise KeyboardInterrupt


def test_an_interrupted_download_leaves_no_part_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _InterruptedAfterFirstChunk()
    monkeypatch.setattr(release_assets, "_open", lambda url, timeout: stream)

    with pytest.raises(KeyboardInterrupt):
        download("https://example.invalid/o/r/releases/download/t/a", tmp_path / "out.bin")

    assert stream.calls >= 2, "the interrupt must come after the first chunk was written"
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# F9: a local write failure stays visible through ReleaseAssetUnavailable
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("code", "text"), [(28, "No space left on device"), (13, "Permission denied"), (30, "Read-only file system")])
def test_a_local_write_failure_is_kept_as_local_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, text: str) -> None:
    source = tmp_path / "rel" / "t" / "a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"bytes")

    def failing_copy(src: object, dst: object, length: int = 0) -> None:
        raise OSError(code, text)

    monkeypatch.setattr(release_assets.shutil, "copyfileobj", failing_copy)
    with pytest.raises(ReleaseAssetUnavailable) as info:
        download(source.as_uri(), tmp_path / "out.bin")

    assert isinstance(info.value.local_error, OSError)
    assert info.value.local_error.errno == code
    assert text in info.value.reason


def test_a_network_failure_has_no_local_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_assets, "_open", lambda url, timeout: _FailsAfterFirstChunk())
    with pytest.raises(ReleaseAssetUnavailable) as info:
        download("https://example.invalid/o/r/releases/download/t/a", tmp_path / "out.bin")
    assert info.value.local_error is None
