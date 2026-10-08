"""HTTPS-bundle backed org doctrine source.

``HttpsBundleSource`` downloads a tar.gz or zip archive over HTTPS, extracts
it into ``target_dir`` and returns a :class:`FetchResult`.  Atomic-write
semantics are layered on by :func:`specify_cli.charter_packs.snapshot.write_snapshot`.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

import requests

from .protocol import FetchResult

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
_ARTIFACTORY_PATH_MARKER = "/artifactory/"


class ArchiveSizeLimitError(Exception):
    """Raised when a fetched archive exceeds doctrine source safety limits."""


@dataclass(frozen=True)
class _ArtifactoryMetadata:
    """Version and checksum co-attested by one Artifactory AQL result."""

    version: str
    sha256: str


@dataclass(frozen=True)
class _ArtifactoryItem:
    """Exact Artifactory item identity plus its AQL endpoint."""

    aql_url: str
    repo: str
    path: str
    name: str


@dataclass(frozen=True)
class _BufferedArchive:
    """Temporary archive plus its exact downloaded-body checksum."""

    path: Path
    sha256: str


@dataclass
class HttpsBundleSource:
    """Source that fetches a packed doctrine archive over HTTPS.

    Args:
        url: Direct download URL for the archive.
        ref: Optional version pin used to populate ``pack_version`` when the
            server does not return an ``ETag`` header.
        if_none_match: Optional ETag from a previous fetch.  Sent as
            ``If-None-Match`` so an unchanged remote returns HTTP 304 and
            skips the download body.
    """

    url: str
    ref: str | None = None
    if_none_match: str | None = None
    source_type: str = "https"

    @property
    def canonical_url(self) -> str | None:
        """Return the single Requests-normalized URL used by every boundary."""
        return _canonical_https_url(self.url)

    @property
    def is_artifactory(self) -> bool:
        """Whether this source requires Artifactory provenance validation."""
        canonical_url = self.canonical_url
        parsed = _safe_urlsplit(canonical_url) if canonical_url is not None else None
        return self.source_type == "artifactory" or (parsed is not None and _ARTIFACTORY_PATH_MARKER in parsed.path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, target_dir: Path) -> FetchResult:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        canonical_url = self.canonical_url
        if canonical_url is None:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["HTTPS doctrine source URL is invalid."],
            )

        parsed = _safe_urlsplit(canonical_url)
        assert parsed is not None
        is_artifactory = self.source_type == "artifactory" or _ARTIFACTORY_PATH_MARKER in parsed.path
        artifactory_item = _artifactory_item(canonical_url)
        if is_artifactory and artifactory_item is None:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["Artifactory source requires a valid Artifactory item URL containing /artifactory/<repo>/<item>."],
            )

        try:
            response = self._get_with_retry(canonical_url)
        except requests.RequestException as exc:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[f"Network error fetching {_safe_url_for_error(canonical_url)}: {type(exc).__name__}"],
            )

        try:
            return self._consume_response(response, target_dir, artifactory_item, canonical_url)
        finally:
            response.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        custom_header = os.environ.get("SPEC_KITTY_ORG_AUTH_HEADER")
        if custom_header:
            headers["Authorization"] = custom_header
        else:
            token = os.environ.get("SPEC_KITTY_ORG_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        if self.if_none_match:
            headers["If-None-Match"] = self.if_none_match
        return headers

    def _consume_response(
        self,
        response: requests.Response,
        target_dir: Path,
        artifactory_item: _ArtifactoryItem | None,
        canonical_url: str,
    ) -> FetchResult:
        """Validate, buffer, provenance-check, then extract one response."""
        if response.status_code == 304:
            if not self.if_none_match:
                return FetchResult(
                    ok=False,
                    artifacts_written=0,
                    pack_version=None,
                    errors=["Remote returned HTTP 304 without an If-None-Match validator."],
                )
            return FetchResult(
                ok=True,
                artifacts_written=0,
                pack_version=self.ref,
                unchanged=True,
                etag=self.if_none_match,
            )

        if response.status_code in (401, 403):
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["Authentication failed. Set SPEC_KITTY_ORG_TOKEN to a valid bearer token for the doctrine bundle endpoint."],
            )
        if response.status_code >= 400:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[f"HTTP {response.status_code} fetching {_safe_url_for_error(canonical_url)}."],
            )

        archive_kind = self._detect_archive(response)
        if archive_kind is None:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[f"Could not determine archive format from Content-Type ({response.headers.get('Content-Type', '<missing>')}) or URL suffix."],
            )

        buffered, buffer_error = self._buffer_archive(response, archive_kind)
        if buffer_error is not None:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[buffer_error],
            )
        assert buffered is not None

        metadata: _ArtifactoryMetadata | None = None
        if artifactory_item is not None:
            metadata, metadata_error = self._fetch_artifactory_metadata(artifactory_item, canonical_url)
            if metadata_error is not None:
                buffered.path.unlink(missing_ok=True)
                return FetchResult(
                    ok=False,
                    artifacts_written=0,
                    pack_version=None,
                    errors=[metadata_error],
                )
            assert metadata is not None
            if not hmac.compare_digest(metadata.sha256, buffered.sha256):
                buffered.path.unlink(missing_ok=True)
                return FetchResult(
                    ok=False,
                    artifacts_written=0,
                    pack_version=None,
                    errors=["JFrog metadata checksum does not match the downloaded archive; the mutable artifact changed during fetch."],
                )

        try:
            extracted = self._extract(buffered.path, target_dir, archive_kind)
        except (
            ArchiveSizeLimitError,
            tarfile.TarError,
            zipfile.BadZipFile,
            OSError,
        ) as exc:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[f"Archive extraction failed: {exc}"],
            )
        finally:
            buffered.path.unlink(missing_ok=True)

        return FetchResult(
            ok=True,
            artifacts_written=extracted,
            pack_version=metadata.version if metadata is not None else self.ref,
            etag=response.headers.get("ETag"),
        )

    @staticmethod
    def _buffer_archive(response: requests.Response, archive_kind: str) -> tuple[_BufferedArchive | None, str | None]:
        """Stream one bounded response body to disk and hash those exact bytes."""
        tmp_path: Path | None = None
        digest = hashlib.sha256()  # noqa: TID251 - downloaded-body integrity checksum
        try:
            content_length = _parse_content_length(response.headers.get("Content-Length"))
            if content_length is not None and content_length > MAX_ARCHIVE_BYTES:
                raise ArchiveSizeLimitError(f"Archive exceeds raw byte limit: {content_length} > {MAX_ARCHIVE_BYTES}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{archive_kind}") as tmp:
                tmp_path = Path(tmp.name)
                total = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        raise ArchiveSizeLimitError(f"Archive exceeds raw byte limit: {total} > {MAX_ARCHIVE_BYTES}")
                    digest.update(chunk)
                    tmp.write(chunk)
        except (ArchiveSizeLimitError, OSError, requests.RequestException) as exc:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            detail = str(exc) if not isinstance(exc, requests.RequestException) else type(exc).__name__
            return None, f"Failed to buffer archive: {detail}"
        assert tmp_path is not None
        return _BufferedArchive(path=tmp_path, sha256=digest.hexdigest()), None

    def _fetch_artifactory_metadata(self, item: _ArtifactoryItem, canonical_url: str) -> tuple[_ArtifactoryMetadata | None, str | None]:
        """Read one AQL result that co-attests version and body checksum."""
        payload, error = self._post_artifactory_aql(item)
        if error is not None:
            return None, error
        metadata = _extract_aql_metadata(payload, item)
        if metadata is None:
            return None, (
                "JFrog AQL did not return the exact artifact with one non-empty "
                "version property and a valid SHA-256 checksum: "
                f"{_safe_url_for_error(canonical_url)}"
            )
        return metadata, None

    def _post_artifactory_aql(
        self,
        item: _ArtifactoryItem,
    ) -> tuple[object | None, str | None]:
        """Fetch, decode, and close one co-attested JFrog AQL result."""
        try:
            response = self._post_artifactory_aql_with_retry(item)
        except requests.RequestException as exc:
            return None, f"Failed to read JFrog AQL metadata: {type(exc).__name__}"
        try:
            if response.status_code >= 400:
                return None, (f"Failed to read JFrog AQL metadata: HTTP {response.status_code}")
            try:
                return response.json(), None
            except (ValueError, TypeError):
                return None, ("Failed to read JFrog AQL metadata: invalid JSON response")
        finally:
            response.close()

    def _post_artifactory_aql_with_retry(self, item: _ArtifactoryItem) -> requests.Response:
        headers = _without_conditional_header(self._headers())
        headers["Content-Type"] = "text/plain"
        criteria = json.dumps(
            {
                "repo": item.repo,
                "path": item.path,
                "name": item.name,
                "type": "file",
            },
            separators=(",", ":"),
        )
        query = f'items.find({criteria}).include("repo","path","name","sha256","virtual_repos","@version")'
        kwargs: dict[str, Any] = {
            "headers": headers,
            "data": query,
            "timeout": 30,
        }
        response = requests.post(  # noqa: S113 - timeout supplied below
            item.aql_url, **kwargs
        )
        if response.status_code == 429 or 500 <= response.status_code < 600:
            delay = 2.0 if response.status_code >= 500 else 1.0
            response.close()
            time.sleep(delay)
            response = requests.post(  # noqa: S113 - timeout supplied in kwargs
                item.aql_url,
                **kwargs,
            )
        return response

    def _get_with_retry(self, request_url: str) -> requests.Response:
        response = requests.get(  # noqa: S113 - timeout supplied below
            request_url,
            headers=self._headers(),
            stream=True,
            timeout=30,
        )
        if 500 <= response.status_code < 600:
            response.close()
            time.sleep(2.0)
            response = requests.get(
                request_url,
                headers=self._headers(),
                stream=True,
                timeout=30,
            )
        elif response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            response.close()
            time.sleep(retry_after)
            response = requests.get(
                request_url,
                headers=self._headers(),
                stream=True,
                timeout=30,
            )
        return response

    @staticmethod
    def _detect_archive(response: requests.Response) -> str | None:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "gzip" in content_type or "x-tar" in content_type:
            return "tar.gz"
        if "zip" in content_type:
            return "zip"
        url = response.url.lower()
        if url.endswith(".tar.gz") or url.endswith(".tgz"):
            return "tar.gz"
        if url.endswith(".zip"):
            return "zip"
        return None

    @staticmethod
    def _extract(archive_path: Path, target_dir: Path, kind: str) -> int:
        if kind == "tar.gz":
            with tarfile.open(archive_path, "r:gz") as tf:
                _safe_extract_tar(tf, target_dir)
        else:  # zip
            with zipfile.ZipFile(archive_path) as zf:
                _safe_extract_zip(zf, target_dir)

        _flatten_single_top_dir(target_dir)
        return sum(1 for _ in target_dir.rglob("*.yaml"))


def _artifactory_item(artifact_url: str) -> _ArtifactoryItem | None:
    """Derive exact AQL item identity from an Artifactory download URL."""
    canonical_url = _canonical_https_url(artifact_url)
    if canonical_url is None:
        return None
    parsed = _safe_urlsplit(canonical_url)
    assert parsed is not None
    if _ARTIFACTORY_PATH_MARKER not in parsed.path:
        return None
    prefix, item_path = parsed.path.split(_ARTIFACTORY_PATH_MARKER, maxsplit=1)
    segments = _decode_artifactory_segments(item_path)
    if segments is None or len(segments) < 2:
        return None
    repository = segments[0]
    path = "/".join(segments[1:-1]) or "."
    name = segments[-1]
    aql_path = f"{prefix}{_ARTIFACTORY_PATH_MARKER}api/search/aql"
    return _ArtifactoryItem(
        aql_url=urlunsplit((parsed.scheme, _safe_netloc(parsed), aql_path, "", "")),
        repo=repository,
        path=path,
        name=name,
    )


def _decode_artifactory_segments(item_path: str) -> list[str] | None:
    """Decode URL path segments without allowing encoded structure changes."""
    raw_segments = item_path.split("/")
    if not raw_segments or any(not segment for segment in raw_segments):
        return None
    decoded_segments: list[str] = []
    for raw_segment in raw_segments:
        if re.search(r"%(?![0-9A-Fa-f]{2})", raw_segment):
            return None
        try:
            decoded = unquote(raw_segment, errors="strict")
        except UnicodeDecodeError:
            return None
        if decoded in {".", ".."} or "/" in decoded or "\\" in decoded or any(ord(character) < 32 or ord(character) == 127 for character in decoded):
            return None
        decoded_segments.append(decoded)
    return decoded_segments


def _without_conditional_header(headers: dict[str, str]) -> dict[str, str]:
    """Return request headers without an artifact-body conditional."""
    return {name: value for name, value in headers.items() if name.lower() != "if-none-match"}


def _safe_url_for_error(url: str) -> str:
    """Return an archive URL safe to include in operator-visible errors."""
    parsed = _safe_urlsplit(url)
    if parsed is None:
        return "<invalid HTTPS URL>"
    return urlunsplit((parsed.scheme, _safe_netloc(parsed), parsed.path, "", ""))


def _safe_urlsplit(url: str) -> SplitResult | None:
    """Parse one URL without allowing malformed authorities to escape."""
    try:
        return urlsplit(url)
    except ValueError:
        return None


def _canonical_https_url(url: str) -> str | None:
    """Normalize one HTTPS URL once, rejecting parser-differential inputs."""
    if "\\" in url or re.search(r"%(?![0-9A-Fa-f]{2})", url) or any(ord(char) < 32 or ord(char) == 127 for char in url):
        return None
    canonical_url = url
    for _ in range(4):
        try:
            prepared = requests.Request(method="GET", url=canonical_url).prepare()
        except (requests.RequestException, UnicodeError, ValueError):
            return None
        if prepared.url is None:
            return None
        if prepared.url == canonical_url:
            break
        canonical_url = prepared.url
    else:
        return None

    parsed = _safe_urlsplit(canonical_url)
    if parsed is None or parsed.scheme != "https" or not parsed.hostname:
        return None
    try:
        _ = parsed.port
    except ValueError:
        return None
    if not _is_valid_hostname(parsed.hostname):
        return None
    return canonical_url


def _is_valid_hostname(hostname: str) -> bool:
    """Validate an IP literal or IDNA DNS hostname before network access."""
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in hostname):
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return True

    if "%" in hostname:
        return False

    candidate = hostname[:-1] if hostname.endswith(".") else hostname
    if not candidate or len(candidate) > 253:
        return False
    if all(char.isdigit() or char == "." for char in candidate):
        return False
    try:
        prepared = requests.Request(method="GET", url=f"https://{candidate}/").prepare()
    except (requests.RequestException, UnicodeError, ValueError):
        return False
    if prepared.url is None:
        return False
    prepared_url = _safe_urlsplit(prepared.url)
    if prepared_url is None or prepared_url.hostname is None:
        return False
    ascii_hostname = prepared_url.hostname
    if len(ascii_hostname) > 253:
        return False
    labels = ascii_hostname.split(".")
    return all(
        label and len(label) <= 63 and label[0] != "-" and label[-1] != "-" and all(char.isascii() and (char.isalnum() or char == "-") for char in label)
        for label in labels
    )


def _safe_netloc(parsed: Any) -> str:
    """Rebuild a URL authority without embedded credentials."""
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    return f"{hostname}:{port}" if port is not None else hostname


def _extract_aql_metadata(payload: object, item: _ArtifactoryItem) -> _ArtifactoryMetadata | None:
    """Validate one exact AQL item and return its co-attested provenance."""
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1:
        return None
    result = results[0]
    if not isinstance(result, dict):
        return None
    virtual_repos = result.get("virtual_repos")
    repo_matches = result.get("repo") == item.repo or (isinstance(virtual_repos, list) and item.repo in virtual_repos)
    if not repo_matches or result.get("path") != item.path or result.get("name") != item.name:
        return None
    checksum = result.get("sha256")
    if not isinstance(checksum, str):
        return None
    normalized = checksum.strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        return None
    properties = result.get("properties")
    if not isinstance(properties, list):
        return None
    versions: list[str] = []
    for prop in properties:
        if not isinstance(prop, dict) or prop.get("key") != "version":
            continue
        value = prop.get("value")
        if isinstance(value, str) and value.strip():
            versions.append(value.strip())
    if len(versions) != 1:
        return None
    return _ArtifactoryMetadata(version=versions[0], sha256=normalized)


def _parse_retry_after(value: Any) -> float:
    if value is None:
        return 2.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 2.0


def _parse_content_length(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_extract_tar(tf: tarfile.TarFile, target_dir: Path) -> None:
    """Extract *tf* into *target_dir* with defence against common tar attacks.

    Checks performed before any bytes reach disk:

    1. **Path traversal / zip-slip** — uses ``Path.relative_to`` so that a
       sibling-prefix name (``/tmp/target-evil/x`` when base is
       ``/tmp/target``) is correctly rejected (the old ``startswith`` check
       was vulnerable to this bypass, P1 fix 2026-05).
    2. **Symlinks and hardlinks** — refused unconditionally; a malicious tar
       can create ``etc -> /etc`` then write ``etc/passwd`` through it.
    3. **Non-regular, non-directory entries** — character/block devices,
       FIFOs and other special files are refused.
    """
    base = target_dir.resolve()
    members = tf.getmembers()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveSizeLimitError(f"Archive exceeds member count limit: {len(members)} > {MAX_ARCHIVE_MEMBERS}")
    extracted_bytes = 0
    for member in members:
        # --- type guard (before path check) ---
        if member.issym() or member.islnk():
            raise tarfile.TarError(f"Refusing symlink/hardlink entry: {member.name}")
        if not member.isfile() and not member.isdir():
            raise tarfile.TarError(f"Refusing non-file/non-dir entry: {member.name} (type={member.type!r})")
        if member.isfile():
            extracted_bytes += member.size
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise ArchiveSizeLimitError(f"Archive exceeds extracted byte limit: {extracted_bytes} > {MAX_EXTRACTED_BYTES}")
        # --- path traversal guard (use relative_to, not startswith) ---
        member_path = (target_dir / member.name).resolve()
        try:
            member_path.relative_to(base)
        except ValueError as exc:
            raise tarfile.TarError(f"Refusing path traversal entry: {member.name}") from exc
    tf.extractall(target_dir)  # noqa: S202  # nosec B202 - paths and types validated above


def _safe_extract_zip(zf: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract *zf* into *target_dir* with defence against path traversal.

    Uses ``Path.relative_to`` instead of the old ``str.startswith`` check
    which was vulnerable to the sibling-prefix bypass (P1 fix 2026-05).
    """
    base = target_dir.resolve()
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveSizeLimitError(f"Archive exceeds member count limit: {len(members)} > {MAX_ARCHIVE_MEMBERS}")
    extracted_bytes = 0
    for info in members:
        name = info.filename
        if not info.is_dir():
            extracted_bytes += info.file_size
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise ArchiveSizeLimitError(f"Archive exceeds extracted byte limit: {extracted_bytes} > {MAX_EXTRACTED_BYTES}")
        member_path = (target_dir / name).resolve()
        try:
            member_path.relative_to(base)
        except ValueError as exc:
            raise zipfile.BadZipFile(f"Refusing path traversal entry: {name}") from exc
    zf.extractall(target_dir)  # noqa: S202  # nosec B202 - paths validated above


def _flatten_single_top_dir(target_dir: Path) -> None:
    """If the archive nested everything under a single top-level dir, hoist it.

    Many bundles produce ``my-pack-v1.2.0/<contents>``.  Operators expect the
    extracted ``target_dir`` to *be* the pack root, so we lift the contents
    one level when there is exactly one child directory and no sibling files.
    """
    entries = list(target_dir.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        return
    inner = entries[0]
    for child in list(inner.iterdir()):
        child.rename(target_dir / child.name)
    inner.rmdir()
