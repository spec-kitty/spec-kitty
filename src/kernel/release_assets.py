"""The one owner of release-asset downloads (#6590, FR-003, NFR-004).

Every download of a service release asset in ``src/`` goes through
:func:`download`, so the scheme policy, the inactivity timeout, the proxy and
CA handling, the redirect rule and the atomic write are decided here once
(``tests/architectural/test_release_asset_download_owner.py`` enforces it,
with an empty allowlist). The precedent is ``kernel.git.remote``, the one
owner of git remote contact.

- **Schemes**: only ``https://`` and ``file://`` (fixtures and offline
  mirrors). Anything else is a :class:`ValueError`.
- **Timeout**: :data:`DEFAULT_TIMEOUT` seconds of socket inactivity.
- **Proxy and TLS**: ``urllib.request.ProxyHandler`` reads ``HTTPS_PROXY`` /
  ``NO_PROXY``; ``ssl.create_default_context()`` reads ``SSL_CERT_FILE`` /
  ``SSL_CERT_DIR``. Certificate verification is never disabled.
- **Redirects**: followed (GitHub serves assets from another host) but never
  to a non-https URL.
- **Atomicity**: bytes stream into ``<dest>.part-<pid>`` beside *dest* and are
  renamed into place; on any failure, an interrupt (Ctrl-C) included, the part
  file is removed, so *dest* is either absent, its previous content, or the
  complete download.

No retries: callers decide. The module is standard-library only (``kernel``
is the zero-dependency root layer).
"""

from __future__ import annotations

import contextlib
import errno
import http.client
import importlib.metadata
import os
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import IO

__all__ = ["ReleaseAssetUnavailable", "asset_url", "download"]

#: Seconds of socket inactivity after which a download aborts (NFR-004).
DEFAULT_TIMEOUT = 60.0

_CHUNK = 1024 * 1024
_HTTPS = "https"
_FILE = "file"
_SCHEME_ERROR = "release assets come only from https:// or file:// sources"
_FILE_HOST_ERROR = "a file:// source must name no host (or localhost), not a remote share"
_LOCAL_HOSTS = ("", "localhost")
_DISTRIBUTION = "spec-kitty-cli"
_URL_USERINFO_PREFIX = "***@"
#: ``errno`` values of a failure to write the download locally (a full disk, a permission, a read-only mount).
_LOCAL_ERRNOS = frozenset(code for code in (errno.ENOSPC, errno.EACCES, errno.EPERM, errno.EROFS, errno.EFBIG, getattr(errno, "EDQUOT", None)) if code is not None)


class ReleaseAssetUnavailable(RuntimeError):
    """A release asset could not be downloaded.

    ``url`` has any ``user:secret@`` part redacted, and ``reason`` is a short
    description (an exception type, an HTTP status) that never carries a
    header, a credential or a response body. ``local_error`` is the ``OSError``
    when the bytes could not be *written* here (a full disk, a permission, a
    read-only mount), so a caller can point at its cache instead of the network;
    it is ``None`` for every remote failure.
    """

    def __init__(self, url: str, reason: str, *, local_error: OSError | None = None) -> None:
        self.url = _redact(url)
        self.reason = reason
        self.local_error = local_error
        super().__init__(f"cannot download {self.url}: {reason}")


def _redact(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if "@" not in parts.netloc:
        return url
    host = parts.netloc.rsplit("@", 1)[1]
    return urllib.parse.urlunsplit(parts._replace(netloc=_URL_USERINFO_PREFIX + host))


def _scheme(url: str) -> str:
    return urllib.parse.urlsplit(url).scheme.lower()


def asset_url(repository: str, tag: str, name: str) -> str:
    """The download URL of release asset *name* of *tag* in *repository*.

    ``https://host/<owner>/<repo>[.git]`` gives
    ``https://host/<owner>/<repo>/releases/download/<tag>/<name>`` (GitHub's
    public asset URL). ``file:///dir`` gives ``file:///dir/<tag>/<name>``, the
    same relative layout for fixtures and mirrors.
    """
    scheme = _scheme(repository)
    base = repository.rstrip("/")
    if scheme == _HTTPS:
        base = base.removesuffix(".git").rstrip("/")
        return f"{base}/releases/download/{tag}/{name}"
    if scheme == _FILE:
        return f"{base}/{tag}/{name}"
    raise ValueError(f"{_SCHEME_ERROR}; got scheme {scheme or '(none)'!r}")


class _NoDowngradeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but refuse one that leaves https."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if _scheme(newurl) != _HTTPS:
            raise urllib.error.HTTPError(_redact(newurl), code, "refusing a redirect to a non-https URL", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _user_agent() -> str:
    try:
        version = importlib.metadata.version(_DISTRIBUTION)
    except (importlib.metadata.PackageNotFoundError, OSError, ValueError):
        # Metadata missing or unreadable (a source tree, a broken install): only the User-Agent changes.
        version = "dev"
    return f"spec-kitty/{version}"


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": _user_agent()})


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        _NoDowngradeRedirectHandler(),
    )


def _open(url: str, timeout: float) -> IO[bytes]:
    """Open *url* for streaming (https through the guarded opener, file directly)."""
    if _scheme(url) == _FILE:
        return open(urllib.request.url2pathname(urllib.parse.urlsplit(url).path), "rb")
    response: IO[bytes] = _opener().open(_request(url), timeout=timeout)
    return response


def _reason(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"URLError: {type(exc.reason).__name__}" if isinstance(exc.reason, BaseException) else "URLError"
    if isinstance(exc, OSError) and exc.strerror:
        return f"{type(exc).__name__}: {exc.strerror}"
    return type(exc).__name__


def _local_error(exc: BaseException) -> OSError | None:
    """*exc* when it is a local write failure (by ``errno``), never a network error such as a ``URLError``."""
    if isinstance(exc, OSError) and not isinstance(exc, urllib.error.URLError) and exc.errno in _LOCAL_ERRNOS:
        return exc
    return None


def download(url: str, dest: Path, *, timeout: float = DEFAULT_TIMEOUT) -> None:
    """Download *url* to *dest* atomically (``dest.parent`` must exist).

    Raises :class:`ValueError` for a scheme other than https or file, and
    :class:`ReleaseAssetUnavailable` for any transfer or write failure; in
    that case no part file is left and *dest* is untouched.
    """
    if _scheme(url) not in (_HTTPS, _FILE):
        raise ValueError(f"{_SCHEME_ERROR}; got {_redact(url)!r}")
    if _scheme(url) == _FILE and urllib.parse.urlsplit(url).netloc.lower() not in _LOCAL_HOSTS:
        raise ValueError(f"{_SCHEME_ERROR}: {_FILE_HOST_ERROR}; got {_redact(url)!r}")
    dest = Path(dest)
    part = dest.with_name(f"{dest.name}.part-{os.getpid()}")
    source_opened = False
    try:
        with _open(url, timeout) as source:
            source_opened = True
            with open(part, "wb") as sink:
                shutil.copyfileobj(source, sink, _CHUNK)
        os.replace(part, dest)
    except Exception as exc:
        # Only once the source is open can a full disk or a permission error be ours, not the source's.
        local = _local_error(exc) if source_opened else None
        raise ReleaseAssetUnavailable(url, _reason(exc), local_error=local) from exc
    finally:
        # Also on KeyboardInterrupt: never leave a part file. After the rename there is none.
        with contextlib.suppress(OSError):
            part.unlink()
