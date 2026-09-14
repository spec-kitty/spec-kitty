"""Comprehensive tests for SaaSTrackerClient.

Covers auth injection, synchronous endpoints, async endpoints (push/run with
202 polling), polling timeout, 401 refresh, 429 rate-limit, error envelope
parsing, and network errors.
"""

from __future__ import annotations

import hashlib
import json as json_module
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from kernel.clock import datetime
from specify_cli.tracker.saas_client import (
    SaaSTrackerClient,
    SaaSTrackerClientError,
    _parse_error_envelope,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _expected_idempotency_key(
    *,
    project_root: Path | None,
    write_kind: str,
    payload: dict[str, Any],
    at: datetime,
) -> str:
    """Independently recompute the digest ``_content_digest`` promises to mint.

    Reimplements the documented contract (canonical JSON, ``sort_keys=True``,
    sha256) from scratch rather than calling ``_content_digest`` — the only
    form of assertion that fails when the implementation drifts from that
    contract, e.g. by folding in a per-instance/per-call salt (#313).
    """
    window_seconds = SaaSTrackerClient._IDEMPOTENCY_RESEND_WINDOW.total_seconds()
    resend_bucket = int(at.timestamp() // window_seconds)
    canonical = json_module.dumps(
        {
            "project_root": str(project_root) if project_root is not None else "",
            "write_kind": write_kind,
            "payload": payload,
            "resend_bucket": resend_bucket,
        },
        sort_keys=True,
    )
    return "logical-operation:write:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()  # noqa: TID251 - idempotency-key body checksum, not charter content


def _make_response(
    status_code: int = 200,
    json_body: dict[str, Any] | None = None,
    *,
    text: str = "",
) -> httpx.Response:
    """Build a fake httpx.Response with the given status and JSON body."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://example.com"),
    )
    if json_body is not None:
        import json as _json

        resp._content = _json.dumps(json_body).encode()
        resp.headers["content-type"] = "application/json"
    elif text:
        resp._content = text.encode()
    else:
        resp._content = b""
    return resp


@pytest.fixture()
def mock_credential_store() -> MagicMock:
    store = MagicMock()
    store.get_access_token.return_value = "test-access-token"
    store.get_team_slug.return_value = "team-acme"
    store.get_refresh_token.return_value = "test-refresh-token"
    return store


@pytest.fixture()
def mock_sync_config() -> MagicMock:
    config = MagicMock()
    config.get_server_url.return_value = "https://saas.example.com"
    # The client now resolves its base URL via the canonical target authority
    # (#2146), not the raw get_server_url accessor.
    config.resolve_runtime_target.return_value.resolved_server_url = "https://saas.example.com"
    return config


@pytest.fixture()
def client(mock_credential_store: MagicMock, mock_sync_config: MagicMock) -> SaaSTrackerClient:
    return SaaSTrackerClient(
        credential_store=mock_credential_store,
        sync_config=mock_sync_config,
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# Error envelope parsing
# ---------------------------------------------------------------------------


class TestParseErrorEnvelope:
    def test_parses_full_envelope(self) -> None:
        resp = _make_response(
            422,
            {
                "error_code": "missing_installation",
                "error_category": "identity_resolution",
                "message": "No installation found",
                "retryable": False,
                "user_action_required": True,
                "source": "jira",
                "retry_after_seconds": None,
            },
        )
        envelope = _parse_error_envelope(resp)
        assert envelope["error_code"] == "missing_installation"
        assert envelope["error_category"] == "identity_resolution"
        assert envelope["message"] == "No installation found"
        assert envelope["retryable"] is False
        assert envelope["user_action_required"] is True
        assert envelope["source"] == "jira"

    def test_handles_malformed_json(self) -> None:
        resp = _make_response(500, text="Internal Server Error")
        envelope = _parse_error_envelope(resp)
        assert envelope["error_code"] is None
        assert envelope["error_category"] is None
        assert envelope["message"] == "HTTP 500"

    def test_handles_partial_envelope(self) -> None:
        resp = _make_response(400, {"message": "Bad request"})
        envelope = _parse_error_envelope(resp)
        assert envelope["message"] == "Bad request"
        assert envelope["error_code"] is None
        assert envelope["error_category"] is None
        assert envelope["retryable"] is False


# ---------------------------------------------------------------------------
# Auth injection
# ---------------------------------------------------------------------------


class TestAuthInjection:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bearer_token_on_every_request(self, mock_httpx_client_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_httpx_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_httpx_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        client._request("GET", "/api/v1/tracker/status")

        _, kwargs = mock_http.request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-access-token"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_team_slug_header_on_every_request(self, mock_httpx_client_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_httpx_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_httpx_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        client._request("GET", "/api/v1/tracker/status")

        _, kwargs = mock_http.request.call_args
        assert kwargs["headers"]["X-Team-Slug"] == "team-acme"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_token_fetched_at_request_time(self, mock_httpx_client_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Token is read on each call, not cached at construction."""
        mock_http = MagicMock()
        mock_httpx_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_httpx_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        # First request uses the original token
        client._request("GET", "/api/v1/tracker/status")

        # Change token
        client._credential_store.get_access_token.return_value = "new-token"  # type: ignore[attr-defined]
        client._request("GET", "/api/v1/tracker/status")

        calls = mock_http.request.call_args_list
        assert calls[0][1]["headers"]["Authorization"] == "Bearer test-access-token"
        assert calls[1][1]["headers"]["Authorization"] == "Bearer new-token"

    def test_no_token_raises(self, client: SaaSTrackerClient) -> None:
        client._credential_store.get_access_token.return_value = None  # type: ignore[attr-defined]
        with pytest.raises(SaaSTrackerClientError, match="spec-kitty auth login") as exc_info:
            client._request("GET", "/api/v1/tracker/status")
        assert exc_info.value.error_code == "unauthenticated"
        assert exc_info.value.status_code == 401
        assert exc_info.value.details["category"] == "unauthenticated"
        assert exc_info.value.user_action_required is True

    def test_missing_team_slug_raises_error(self, client: SaaSTrackerClient) -> None:
        """FR-015: Missing X-Team-Slug must raise, not silently omit the header."""
        client._credential_store.get_team_slug.return_value = None  # type: ignore[attr-defined]
        with pytest.raises(SaaSTrackerClientError, match="spec-kitty auth login") as exc_info:
            client._request("GET", "/api/v1/tracker/status")
        assert exc_info.value.error_code == "unauthenticated"
        assert exc_info.value.details["category"] == "unauthenticated"

    def test_empty_team_slug_raises_error(self, client: SaaSTrackerClient) -> None:
        """FR-015: Empty string team slug must also raise."""
        client._credential_store.get_team_slug.return_value = ""  # type: ignore[attr-defined]
        with pytest.raises(SaaSTrackerClientError, match="spec-kitty auth login") as exc_info:
            client._request("GET", "/api/v1/tracker/status")
        assert exc_info.value.error_code == "unauthenticated"
        assert exc_info.value.details["category"] == "unauthenticated"


# ---------------------------------------------------------------------------
# Synchronous endpoints
# ---------------------------------------------------------------------------


class TestPull:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_pull_200(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"items": [{"id": "1"}], "cursor": "abc"})

        result = client.pull("jira", "proj-1")

        assert result == {"items": [{"id": "1"}], "cursor": "abc"}
        _, kwargs = mock_http.request.call_args
        assert kwargs["json"]["provider"] == "jira"
        assert kwargs["json"]["project_slug"] == "proj-1"
        assert kwargs["json"]["limit"] == 100

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_pull_with_cursor_and_filters(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"items": []})

        client.pull("jira", "proj-1", limit=50, cursor="xyz", filters={"status": ["open"]})

        _, kwargs = mock_http.request.call_args
        assert kwargs["json"]["cursor"] == "xyz"
        assert kwargs["json"]["filters"] == {"status": ["open"]}
        assert kwargs["json"]["limit"] == 50

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_pull_uses_post_method(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"items": []})

        client.pull("jira", "proj-1")

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/api/v1/tracker/pull/")


class TestStatus:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_status_200(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"connected": True, "last_sync": "2026-01-01"})

        result = client.status("jira", "proj-1")

        assert result["connected"] is True
        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1].endswith("/api/v1/tracker/status/")
        assert kwargs["params"]["provider"] == "jira"
        assert kwargs["params"]["project_slug"] == "proj-1"


class TestMappings:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_mappings_200(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"fields": [{"src": "title", "dst": "summary"}]})

        result = client.mappings("jira", "proj-1")

        assert result["fields"][0]["src"] == "title"
        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1].endswith("/api/v1/tracker/mappings/")


# ---------------------------------------------------------------------------
# Async-capable endpoints (push, run)
# ---------------------------------------------------------------------------


class TestPush:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_200_sync(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 3, "errors": []})

        result = client.push("jira", "proj-1", [{"title": "Bug"}])
        assert result == {"pushed": 3, "errors": []}

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_has_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        client.push("jira", "proj-1", [])

        _, kwargs = mock_http.request.call_args
        idem_key = kwargs["headers"]["Idempotency-Key"]
        assert idem_key.startswith("logical-operation:write:")
        # Length of a sha256 hexdigest suffix IS the contract (fixed hash format).
        assert len(idem_key.removeprefix("logical-operation:write:")) == 64

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_idempotency_key_deterministic_across_invocations(self, mock_cls: MagicMock, client: SaaSTrackerClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """A resend of an unchanged write (e.g. after a crash) must mint the
        same key so the server's receipt store dedupes it (#61) — a random
        key per invocation silently re-applies the write instead.

        Asserting each key against an independently recomputed digest (not
        just ``first_key == second_key``) pins the cross-*process* property:
        a per-instance salt would still make two calls on the SAME instance
        collide while breaking determinism for a resend from a fresh process
        (#313)."""
        from kernel.clock import now_utc

        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        frozen = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: frozen)

        items = [{"title": "Bug"}]
        client.push("jira", "proj-1", items)
        _, kwargs = mock_http.request.call_args
        first_key = kwargs["headers"]["Idempotency-Key"]

        client.push("jira", "proj-1", items)
        _, kwargs = mock_http.request.call_args
        second_key = kwargs["headers"]["Idempotency-Key"]

        expected_key = _expected_idempotency_key(
            project_root=client._project_root,
            write_kind=client._PUSH_PATH,
            payload={"provider": "jira", "project_slug": "proj-1", "items": items},
            at=frozen,
        )

        assert first_key == expected_key
        assert second_key == expected_key

    def test_content_digest_raises_for_non_json_payload(self, client: SaaSTrackerClient) -> None:
        """A non-serialisable payload must fail loudly instead of being
        stringified into a per-process idempotency key (#315)."""
        payload = {"provider": "jira", "project_slug": "proj-1", "items": [{"opaque": object()}]}

        with pytest.raises(TypeError, match="not JSON serializable"):
            client._content_digest(client._PUSH_PATH, payload)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_idempotency_key_pins_explicit_project_root_in_digest(
        self, mock_cls: MagicMock, mock_credential_store: MagicMock, mock_sync_config: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The digest's ``project_root`` branch is exercised with a concrete,
        non-default path — not only the fixture's tmp-path stand-in — so a
        derivation that silently drops or mis-stringifies it is caught
        (#313)."""
        from kernel.clock import now_utc

        explicit_root = tmp_path / "explicit-project-root"
        explicit_root.mkdir()
        client = SaaSTrackerClient(
            credential_store=mock_credential_store,
            sync_config=mock_sync_config,
            timeout=5.0,
            project_root=explicit_root,
        )
        assert client._project_root == explicit_root

        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        frozen = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: frozen)

        items = [{"title": "Bug"}]
        client.push("jira", "proj-1", items)
        _, kwargs = mock_http.request.call_args
        actual_key = kwargs["headers"]["Idempotency-Key"]

        expected_key = _expected_idempotency_key(
            project_root=explicit_root,
            write_kind=client._PUSH_PATH,
            payload={"provider": "jira", "project_slug": "proj-1", "items": items},
            at=frozen,
        )

        assert actual_key == expected_key

    def test_project_root_is_resolved_so_a_relative_root_is_not_cwd_dependent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A relative ``project_root`` must resolve to the same absolute path
        (and therefore the same idempotency digest) regardless of which
        directory the process happened to be run from (#314): storing the
        raw ``Path(project_root)`` made ``_content_digest`` cwd-dependent."""
        from kernel.clock import now_utc

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        frozen = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: frozen)

        relative_client = SaaSTrackerClient(timeout=5.0, project_root=Path("proj"))
        absolute_client = SaaSTrackerClient(timeout=5.0, project_root=project_dir)

        assert relative_client._project_root == project_dir.resolve()
        assert relative_client._project_root.is_absolute()
        payload = {"provider": "jira", "project_slug": "proj-1", "items": [{"title": "Bug"}]}
        relative_digest = relative_client._content_digest(relative_client._PUSH_PATH, payload)
        absolute_digest = absolute_client._content_digest(absolute_client._PUSH_PATH, payload)
        assert relative_digest == absolute_digest

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_idempotency_key_changes_with_payload(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        client.push("jira", "proj-1", [{"title": "Bug"}])
        _, kwargs = mock_http.request.call_args
        first_key = kwargs["headers"]["Idempotency-Key"]

        client.push("jira", "proj-1", [{"title": "Different bug"}])
        _, kwargs = mock_http.request.call_args
        second_key = kwargs["headers"]["Idempotency-Key"]

        assert first_key != second_key

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_idempotency_key_stable_within_resend_window(self, mock_cls: MagicMock, client: SaaSTrackerClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two attempts landing in the same resend-window bucket collide,
        even when the wall clock advances between them (a crash-and-resend
        seconds later must still dedupe, per #61)."""
        from kernel.clock import now_utc, timedelta

        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        base = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: base)
        client.push("jira", "proj-1", [{"title": "Bug"}])
        _, kwargs = mock_http.request.call_args
        first_key = kwargs["headers"]["Idempotency-Key"]

        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: base + timedelta(seconds=5))
        client.push("jira", "proj-1", [{"title": "Bug"}])
        _, kwargs = mock_http.request.call_args
        second_key = kwargs["headers"]["Idempotency-Key"]

        assert first_key == second_key

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_idempotency_key_changes_after_resend_window_elapses(
        self, mock_cls: MagicMock, client: SaaSTrackerClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A repeat of an unchanged write, once the resend window has fully
        elapsed, must mint a new key — otherwise a logically-static write
        (e.g. `run`) could only ever execute once per checkout, and a stale
        `retryable: True` failure receipt would wedge every future resend
        forever (#61 squad pass 2 MAJOR)."""
        from kernel.clock import now_utc

        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        base = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: base)
        client.push("jira", "proj-1", [{"title": "Bug"}])
        _, kwargs = mock_http.request.call_args
        first_key = kwargs["headers"]["Idempotency-Key"]

        later = base + client._IDEMPOTENCY_RESEND_WINDOW * 2
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: later)
        client.push("jira", "proj-1", [{"title": "Bug"}])
        _, kwargs = mock_http.request.call_args
        second_key = kwargs["headers"]["Idempotency-Key"]

        assert first_key != second_key

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_custom_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 1})

        client.push("jira", "proj-1", [], idempotency_key="my-key-123")

        _, kwargs = mock_http.request.call_args
        assert kwargs["headers"]["Idempotency-Key"] == "my-key-123"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_202_polls_until_completed(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        # First call: POST push -> 202
        # Second call: GET operation -> pending
        # Third call: GET operation -> completed
        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-1"}),
            _make_response(200, {"status": "pending"}),
            _make_response(200, {"status": "completed", "result": {"pushed": 2}}),
        ]
        result = client.push("jira", "proj-1", [{"title": "X"}])
        assert result == {"pushed": 2}

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_202_polls_failed_raises(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-2"}),
            _make_response(200, {"status": "failed", "error": "Provider rejected"}),
        ]
        with pytest.raises(SaaSTrackerClientError, match="Provider rejected"):
            client.push("jira", "proj-1", [{"title": "Y"}])


class TestRun:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_200_sync(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pulled": 5, "pushed": 3})

        result = client.run("jira", "proj-1")
        assert result == {"pulled": 5, "pushed": 3}
        _, kwargs = mock_http.request.call_args
        assert kwargs["json"]["pull_first"] is True
        assert kwargs["json"]["limit"] == 100

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_has_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        client.run("jira", "proj-1")

        _, kwargs = mock_http.request.call_args
        idem_key = kwargs["headers"]["Idempotency-Key"]
        assert idem_key.startswith("logical-operation:write:")
        # Length of a sha256 hexdigest suffix IS the contract (fixed hash format).
        assert len(idem_key.removeprefix("logical-operation:write:")) == 64

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_idempotency_key_deterministic_across_invocations(self, mock_cls: MagicMock, client: SaaSTrackerClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same rationale as push (#61): a resend after process death must
        collide with the earlier attempt's key, not mint a fresh one.

        Asserting against an independently recomputed digest, rather than
        only ``first_key == second_key``, pins the cross-*process* property
        rather than an incidental per-instance one (#313)."""
        from kernel.clock import now_utc

        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        frozen = now_utc()
        monkeypatch.setattr("specify_cli.tracker.saas_client.now_utc", lambda: frozen)

        client.run("jira", "proj-1")
        _, kwargs = mock_http.request.call_args
        first_key = kwargs["headers"]["Idempotency-Key"]

        client.run("jira", "proj-1")
        _, kwargs = mock_http.request.call_args
        second_key = kwargs["headers"]["Idempotency-Key"]

        expected_key = _expected_idempotency_key(
            project_root=client._project_root,
            write_kind=client._RUN_PATH,
            payload={"provider": "jira", "project_slug": "proj-1", "pull_first": True, "limit": 100},
            at=frozen,
        )

        assert first_key == expected_key
        assert second_key == expected_key

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_idempotency_key_differs_from_push_for_same_project(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Different write kinds (endpoints) must not collide even when the
        routing payload otherwise matches."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"ok": True})

        client.run("jira", "proj-1")
        _, kwargs = mock_http.request.call_args
        run_key = kwargs["headers"]["Idempotency-Key"]

        mock_http.request.return_value = _make_response(200, {"pushed": 0})
        client.push("jira", "proj-1", [])
        _, kwargs = mock_http.request.call_args
        push_key = kwargs["headers"]["Idempotency-Key"]

        assert run_key != push_key

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_202_polls_until_completed(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-run"}),
            _make_response(200, {"status": "running"}),
            _make_response(200, {"status": "completed", "result": {"synced": 10}}),
        ]
        result = client.run("jira", "proj-1")
        assert result == {"synced": 10}


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------


class TestRetryBehaviors:
    @patch("specify_cli.tracker.saas_client._force_refresh_sync")
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_401_refresh_retry_success(
        self,
        mock_cls: MagicMock,
        mock_force_refresh: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        # First: 401, after refresh: 200
        mock_http.request.side_effect = [
            _make_response(401, {"message": "Unauthorized"}),
            _make_response(200, {"ok": True}),
        ]
        result = client._request_with_retry("GET", "/api/v1/tracker/status")
        assert result.status_code == 200
        mock_force_refresh.assert_called_once()

    @patch("specify_cli.tracker.saas_client._force_refresh_sync")
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_401_double_failure_halts(
        self,
        mock_cls: MagicMock,
        mock_force_refresh: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        # 401 both times
        mock_http.request.side_effect = [
            _make_response(401, {"message": "Unauthorized"}),
            _make_response(401, {"message": "Unauthorized"}),
        ]
        with pytest.raises(SaaSTrackerClientError, match="Session expired"):
            client._request_with_retry("GET", "/api/v1/tracker/status")

    @patch("specify_cli.tracker.saas_client._force_refresh_sync")
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_401_refresh_itself_fails(
        self,
        mock_cls: MagicMock,
        mock_force_refresh: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(401, {"message": "Unauthorized"})
        mock_force_refresh.side_effect = RuntimeError("refresh failed")

        with pytest.raises(SaaSTrackerClientError, match="Session expired"):
            client._request_with_retry("GET", "/api/v1/tracker/status")

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_429_respects_retry_after(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """#3115 (WP06, FR-005) -- corrected pointer (round 2).

        This node was the round-1 attribution site, on the strength of the
        issue body's own wording. It is **not** one of the tests CI actually
        failed on: the live CI log (`fast-tests-sync`, job 91126025663, run
        30621215287, base `bb2020fea9`) shows two different real victims --
        ``test_saas_client_poll_timing.py`` (the seam-based successor of the retired ``TestPolling`` suite)
        (see its docstring below, `:497` class / the test a few lines above
        this one in file order) and
        ``TestSearchIssues.test_429_retries_then_raises`` in
        `tests/sync/tracker/test_saas_client_origin.py:261` (outside this
        WP's write scope -- flagged in the WP06 report, not edited here).
        This test has never been observed red, locally or on CI. The
        stdlib-``time``-module mechanism this docstring used to describe here
        is still correct and is not re-derived -- see the real victim's
        docstring for the full attribution, the quoted failure text, and the
        round-2 corrections (magnitude exclusion, completed `daemon.py`
        census, the `0.05`/doubling fingerprint measurement).
        """
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(429, {"message": "Rate limited", "retry_after_seconds": 3}),
            _make_response(200, {"ok": True}),
        ]

        result = client._request_with_retry("GET", "/api/v1/tracker/status")
        assert result.status_code == 200
        mock_sleep.assert_called_once_with(3.0)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_429_defaults_to_5s_when_missing(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(429, {"message": "Rate limited"}),
            _make_response(200, {"ok": True}),
        ]

        client._request_with_retry("GET", "/api/v1/tracker/status")
        mock_sleep.assert_called_once_with(5.0)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_429_double_failure_raises(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(429, {"message": "Rate limited", "retry_after_seconds": 1}),
            _make_response(429, {"message": "Still rate limited"}),
        ]

        with pytest.raises(SaaSTrackerClientError, match="Still rate limited"):
            client._request_with_retry("GET", "/api/v1/tracker/status")

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_4xx_error_envelope_parsed(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            422,
            {
                "error_code": "missing_installation",
                "error_category": "identity_resolution",
                "message": "Jira app not installed",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError, match="Jira app not installed") as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")
        assert "action required" in str(exc_info.value)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_5xx_error_envelope_parsed(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(500, {"error_code": "internal_error", "message": "Something broke"})

        with pytest.raises(SaaSTrackerClientError, match="Something broke"):
            client._request_with_retry("GET", "/api/v1/tracker/status")

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_malformed_error_response(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(500, text="Internal Server Error")

        with pytest.raises(SaaSTrackerClientError, match="HTTP 500"):
            client._request_with_retry("GET", "/api/v1/tracker/status")


class TestNetworkErrors:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_connect_error(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SaaSTrackerClientError, match="Cannot connect"):
            client._request("GET", "/api/v1/tracker/status")

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_timeout_error(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = httpx.ReadTimeout("Read timed out")

        with pytest.raises(SaaSTrackerClientError, match="Cannot connect"):
            client._request("GET", "/api/v1/tracker/status")


# ---------------------------------------------------------------------------
# Constructor defaults
# ---------------------------------------------------------------------------


class TestConstructorDefaults:
    def test_legacy_construction_kwargs_still_accepted(self, mock_credential_store: MagicMock, mock_sync_config: MagicMock) -> None:
        """``sync_config``/``credential_store`` are legacy kwargs the conftest compat
        shim absorbs; the base URL is resolved through ``resolve_server_target()``
        now, not from ``sync_config``, since issue #5 retired the sync transport."""
        c = SaaSTrackerClient(
            credential_store=mock_credential_store,
            sync_config=mock_sync_config,
        )
        assert c._credential_store is mock_credential_store

    @pytest.mark.parametrize(("exception", "reason"), [(RuntimeError, "symlink loop"), (OSError, "cwd removed")])
    def test_project_root_resolution_failures_are_client_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        exception: type[BaseException],
        reason: str,
    ) -> None:
        project_root = tmp_path / "proj"

        def unresolved_path(self: Path) -> Path:
            raise exception(reason)

        monkeypatch.setattr(Path, "resolve", unresolved_path)

        with pytest.raises(SaaSTrackerClientError, match="Cannot resolve project root") as exc_info:
            SaaSTrackerClient(project_root=project_root)

        assert exc_info.value.error_code == "project_root_resolution_failed"
        assert exc_info.value.details == {"project_root": str(project_root), "reason": reason}


# ---------------------------------------------------------------------------
# Regression tests for Codex review cycle 1 fixes
# ---------------------------------------------------------------------------


class TestAsyncErrorEnvelopeParsing:
    """Fix 1 (FR-017/NFR-002): Failed async operations must parse the error
    envelope dict, not dump it as a raw string."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_failed_operation_parses_error_envelope_dict(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """When the 'error' field is an ErrorEnvelope dict, the raised exception
        must contain the human-readable 'message' and 'user_action_required',
        not a repr of the dict."""
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        error_envelope = {
            "error_code": "provider_auth_expired",
            "error_category": "auth",
            "message": "Jira OAuth token has expired",
            "user_action_required": True,
        }
        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-err-envelope"}),
            _make_response(200, {"status": "failed", "error": error_envelope}),
        ]
        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.push("jira", "proj-1", [{"title": "Bug"}])

        error_text = str(exc_info.value)
        # Must contain the readable message
        assert "Jira OAuth token has expired" in error_text
        # user_action_required is boolean True → generic guidance appended
        assert "action required" in error_text
        # Must NOT contain raw dict syntax
        assert "{'error_code'" not in error_text
        assert "provider_auth_expired" not in error_text

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_failed_operation_with_string_error_still_works(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """When the 'error' field is a plain string, it should still work."""
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-str-err"}),
            _make_response(200, {"status": "failed", "error": "Something went wrong"}),
        ]
        with pytest.raises(SaaSTrackerClientError, match="Something went wrong"):
            client.push("jira", "proj-1", [{"title": "Bug"}])

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_failed_operation_with_no_error_field(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """When the 'error' field is missing, a fallback message is used."""
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(202, {"operation_id": "op-no-err"}),
            _make_response(200, {"status": "failed"}),
        ]
        with pytest.raises(SaaSTrackerClientError, match="Operation failed"):
            client.push("jira", "proj-1", [{"title": "Bug"}])


# ---------------------------------------------------------------------------
# WP03: Enriched error attributes (T013 + T014)
# ---------------------------------------------------------------------------


class TestErrorEnrichmentAttributes:
    """T013: Verify enriched SaaSTrackerClientError attributes from PRI-12 envelope."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_preserves_error_code(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """error_code is extracted from the envelope 'error_code' field."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            400,
            {
                "error_code": "binding_not_found",
                "message": "No binding exists for this mission",
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.error_code == "binding_not_found"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_preserves_status_code(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """status_code is the HTTP status from the response."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            400,
            {"error_code": "binding_not_found", "message": "Not found"},
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.status_code == 400

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_preserves_details(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """details dict is the full parsed envelope."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            422,
            {
                "error_code": "mapping_disabled",
                "error_category": "configuration",
                "message": "Mapping is disabled",
                "retryable": False,
                "user_action_required": False,
                "source": "jira",
                "retry_after_seconds": None,
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        details = exc_info.value.details
        assert isinstance(details, dict)
        assert details["error_code"] == "mapping_disabled"
        assert details["error_category"] == "configuration"
        assert details["source"] == "jira"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_user_action_required(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """user_action_required is True when envelope says so."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            422,
            {
                "error_code": "missing_installation",
                "message": "App not installed",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.user_action_required is True

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_backward_compat_str(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """str(e) still returns the human-readable message."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(
            400,
            {"error_code": "binding_not_found", "message": "No binding found"},
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert str(exc_info.value) == "No binding found"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_enrichment_missing_envelope(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Empty/malformed body: error_code=None, status_code preserved."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.return_value = _make_response(400, text="Bad Request")

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.error_code is None
        assert exc_info.value.status_code == 400
        assert str(exc_info.value) == "HTTP 400"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_429_enrichment_has_error_code_and_status(
        self,
        mock_cls: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """Double 429 raises with error_code='rate_limited' and status_code=429."""
        mock_sleep = MagicMock()
        client._sleep = mock_sleep
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(429, {"message": "Rate limited", "retry_after_seconds": 1}),
            _make_response(429, {"message": "Still rate limited"}),
        ]

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.error_code == "rate_limited"
        assert exc_info.value.status_code == 429

    @patch("specify_cli.tracker.saas_client._force_refresh_sync")
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_401_enrichment_has_error_code_and_status(
        self,
        mock_cls: MagicMock,
        mock_force_refresh: MagicMock,
        client: SaaSTrackerClient,
    ) -> None:
        """Double 401 raises with error_code='session_expired' and status_code=401."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_http.request.side_effect = [
            _make_response(401, {"message": "Unauthorized"}),
            _make_response(401, {"message": "Unauthorized"}),
        ]
        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client._request_with_retry("GET", "/api/v1/tracker/status")

        assert exc_info.value.error_code == "session_expired"
        assert exc_info.value.status_code == 401
        assert exc_info.value.user_action_required is True


class TestErrorEnrichmentRegression:
    """T014: Regression — existing callers constructing SaaSTrackerClientError('msg') still work."""

    def test_existing_str_pattern(self) -> None:
        """Plain string construction with no kwargs must still work."""
        err = SaaSTrackerClientError("Something failed")
        assert str(err) == "Something failed"
        assert err.error_code is None
        assert err.status_code is None
        assert err.details == {}
        assert err.user_action_required is False

    def test_isinstance_runtime_error(self) -> None:
        """SaaSTrackerClientError is still a RuntimeError subclass."""
        err = SaaSTrackerClientError("boom")
        assert isinstance(err, RuntimeError)

    def test_enriched_construction(self) -> None:
        """Full kwarg construction exposes all attributes."""
        err = SaaSTrackerClientError(
            "Binding not found",
            error_code="binding_not_found",
            status_code=404,
            details={"error_code": "binding_not_found", "source": "jira"},
            user_action_required=True,
        )
        assert str(err) == "Binding not found"
        assert err.error_code == "binding_not_found"
        assert err.status_code == 404
        assert err.details == {"error_code": "binding_not_found", "source": "jira"}
        assert err.user_action_required is True

    def test_catch_as_exception(self) -> None:
        """Can be caught as generic Exception (callers that do except Exception)."""
        # noqa justified: the assertion under test IS catchability via the
        # blanket `except Exception` callers use — narrowing the caught type
        # here would stop testing that contract.
        with pytest.raises(Exception):  # noqa: B017
            raise SaaSTrackerClientError("test")

    def test_catch_as_runtime_error(self) -> None:
        """Can be caught as RuntimeError (existing callers)."""
        with pytest.raises(RuntimeError):
            raise SaaSTrackerClientError("test")
