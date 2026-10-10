"""HTTP-API backed org doctrine source.

Implements the ``Org Doctrine Source — HTTP API Protocol`` contract
(see ``kitty-specs/layered-doctrine-org-layer-01KRNPEE/contracts/
org-doctrine-source-api-contract.md``).

The adapter discovers artifact types via ``GET /artifact-types``, downloads
each typed list via ``GET /artifacts/{type}`` and writes every artifact body
to ``<target_dir>/<artifact_type>/<filename>``.  DRG fragments are optional
and land under ``<target_dir>/drg/<filename>``.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from kernel.clock import now_utc_stamp
from pathlib import Path
from typing import Any

import requests

from charter.drg import ArtifactKind

from .protocol import FetchResult

# Only plain filenames (letters, digits, dots, underscores, hyphens) are
# accepted. Path separators, null bytes and absolute anchors are all rejected.
# This prevents a compromised org-pack server from achieving arbitrary file
# write by supplying filenames like ``../../etc/passwd`` (P1 fix 2026-05).
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_server_filename(filename: str) -> None:
    """Raise ``ValueError`` if *filename* is not a plain safe basename.

    A safe basename matches ``^[A-Za-z0-9._-]+$`` — no slashes, no ``..``,
    no absolute paths. After validation the caller must still join the
    filename against a known ``subdir`` and assert ``is_relative_to(subdir)``
    as defence-in-depth.
    """
    if not _SAFE_FILENAME.fullmatch(filename):
        raise ValueError(f"Refusing unsafe artifact filename from server: {filename!r}. Filenames must match ^[A-Za-z0-9._-]+$.")


# Default artifact type list used when /artifact-types is unavailable (404).
# Widened to the 11 layered-repository kinds (#5824, operator decision) so a
# server with no /artifact-types endpoint still has its ``glossary_packs``,
# ``skills`` and ``assets`` fetched, not just the eight pre-addition kinds.
# Keyed on
# :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_layered_repository`.
DEFAULT_ARTIFACT_TYPES: tuple[str, ...] = tuple(kind.plural for kind in ArtifactKind if kind.has_layered_repository)


@dataclass
class ApiSource:
    """Source that pulls doctrine artifacts from a JSON HTTP API.

    Args:
        url: Base URL of the doctrine API (no trailing slash required).
        ref: Optional version pin echoed into ``pack_version`` when the
            server's ``/version`` endpoint is unavailable.
    """

    url: str
    ref: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, target_dir: Path) -> FetchResult:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []

        # Artifact type discovery.
        types_response = self._request("GET", "/artifact-types")
        if isinstance(types_response, _RequestError):
            return types_response.as_fetch_result()

        if types_response.status_code == 404:
            artifact_types: list[str] = list(DEFAULT_ARTIFACT_TYPES)
        else:
            credential_error = _credential_error(types_response)
            if credential_error:
                return credential_error
            if types_response.status_code >= 400:
                return FetchResult(
                    ok=False,
                    artifacts_written=0,
                    pack_version=None,
                    errors=[f"GET /artifact-types failed: {types_response.status_code}"],
                )
            try:
                payload = types_response.json() or {}
            except ValueError:
                payload = {}
            artifact_types = list(payload.get("types") or DEFAULT_ARTIFACT_TYPES)

        total_written = 0
        for artifact_type in artifact_types:
            written, err = self._fetch_artifact_type(target_dir, artifact_type)
            total_written += written
            if err:
                errors.append(err)

        # DRG fragments (optional).
        drg_written, drg_err = self._fetch_drg_extensions(target_dir)
        total_written += drg_written
        if drg_err:
            errors.append(drg_err)

        # Pack version (optional).
        pack_version = self._fetch_pack_version()

        if errors:
            return FetchResult(
                ok=False,
                artifacts_written=total_written,
                pack_version=pack_version,
                errors=errors,
            )

        return FetchResult(
            ok=True,
            artifacts_written=total_written,
            pack_version=pack_version,
            errors=[],
        )

    # ------------------------------------------------------------------
    # Endpoint helpers
    # ------------------------------------------------------------------
    def _fetch_artifact_type(self, target_dir: Path, artifact_type: str) -> tuple[int, str | None]:
        response = self._request("GET", f"/artifacts/{artifact_type}")
        if isinstance(response, _RequestError):
            return 0, response.message

        if response.status_code == 404:
            # Server simply doesn't expose this type.  Not an error.
            return 0, None
        credential_error = _credential_error(response)
        if credential_error:
            return 0, credential_error.errors[0]
        if response.status_code >= 400:
            return 0, (f"GET /artifacts/{artifact_type} failed: {response.status_code}")

        try:
            payload = response.json() or {}
        except ValueError:
            return 0, f"GET /artifacts/{artifact_type}: response is not JSON"

        items = payload.get("artifacts") or []
        subdir = target_dir / artifact_type
        subdir.mkdir(parents=True, exist_ok=True)
        written = 0
        for item in items:
            filename = item.get("filename")
            content = item.get("content")
            if not filename or content is None:
                continue
            try:
                _validate_server_filename(filename)
            except ValueError:
                continue  # skip unsafe filenames; log defensively
            dest = subdir / filename
            if not dest.is_relative_to(subdir):
                continue  # defence-in-depth: should never fire after validate
            dest.write_text(content, encoding="utf-8")
            written += 1
        return written, None

    def _fetch_drg_extensions(self, target_dir: Path) -> tuple[int, str | None]:
        response = self._request("GET", "/drg-extensions")
        if isinstance(response, _RequestError):
            return 0, response.message
        if response.status_code == 404:
            return 0, None
        credential_error = _credential_error(response)
        if credential_error:
            return 0, credential_error.errors[0]
        if response.status_code >= 400:
            return 0, f"GET /drg-extensions failed: {response.status_code}"

        try:
            payload = response.json() or {}
        except ValueError:
            return 0, "GET /drg-extensions: response is not JSON"

        fragments = payload.get("fragments") or []
        if not fragments:
            return 0, None

        subdir = target_dir / "drg"
        subdir.mkdir(parents=True, exist_ok=True)
        written = 0
        for fragment in fragments:
            filename = fragment.get("filename")
            content = fragment.get("content")
            if not filename or content is None:
                continue
            try:
                _validate_server_filename(filename)
            except ValueError:
                continue  # skip unsafe filenames; log defensively
            dest = subdir / filename
            if not dest.is_relative_to(subdir):
                continue  # defence-in-depth: should never fire after validate
            dest.write_text(content, encoding="utf-8")
            written += 1
        return written, None

    def _fetch_pack_version(self) -> str | None:
        response = self._request("GET", "/version")
        if isinstance(response, _RequestError):
            return self.ref
        if response.status_code == 404:
            # Fall back to HTTP response date if present, else ``self.ref``.
            return response.headers.get("Date") or self.ref or _iso_now()
        if response.status_code >= 400:
            return self.ref
        try:
            payload = response.json() or {}
        except ValueError:
            return self.ref
        return payload.get("version") or self.ref

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str) -> requests.Response | _RequestError:
        endpoint = f"{self.url.rstrip('/')}{path}"
        try:
            response = requests.request(
                method,
                endpoint,
                headers=self._headers(),
                timeout=30,
            )
        except requests.RequestException as exc:
            return _RequestError(f"Network error calling {endpoint}: {exc}")

        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            time.sleep(retry_after)
            try:
                response = requests.request(
                    method,
                    endpoint,
                    headers=self._headers(),
                    timeout=30,
                )
            except requests.RequestException as exc:
                return _RequestError(f"Network error on 429-retry for {endpoint}: {exc}")
        return response

    def _headers(self) -> dict[str, str]:
        custom_header = os.environ.get("SPEC_KITTY_ORG_AUTH_HEADER")
        if custom_header:
            return {"Authorization": custom_header, "Accept": "application/json"}
        token = os.environ.get("SPEC_KITTY_ORG_TOKEN")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


@dataclass
class _RequestError:
    """Sentinel returned by :meth:`ApiSource._request` for transport failures."""

    message: str

    def as_fetch_result(self) -> FetchResult:
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=None,
            errors=[self.message],
        )


def _credential_error(response: requests.Response) -> FetchResult | None:
    if response.status_code in (401, 403):
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=None,
            errors=["Authentication failed against the doctrine API. Set SPEC_KITTY_ORG_TOKEN (or SPEC_KITTY_ORG_AUTH_HEADER for custom auth schemes) and retry."],
        )
    return None


def _parse_retry_after(value: Any) -> float:
    if value is None:
        return 2.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 2.0


def _iso_now() -> str:
    return now_utc_stamp()
