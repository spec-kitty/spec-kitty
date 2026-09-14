"""Exercise the real HTTP boundary used by the automatic PR reporter."""

from __future__ import annotations

import io
import json
import traceback
import urllib.error
from email.message import Message
from pathlib import Path

import pytest
import yaml

from scripts.ci import fleet_verdict

pytestmark = pytest.mark.fast
TOKEN = "test-private-token-should-never-appear"


def test_report_job_has_only_pr_comment_write_permission() -> None:
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/ci-fleet-verdict.yml").read_text())
    # Least-privilege permissions live at job scope (#4342 GitHub Actions
    # hardening, S8264): no workflow-level default; identify carries the read
    # baseline and only report escalates with pull-requests: write.
    assert "permissions" not in workflow
    assert workflow["jobs"]["identify"]["permissions"] == {"contents": "read", "actions": "read"}
    assert workflow["jobs"]["report"]["permissions"] == {
        "contents": "read",
        "actions": "read",
        "pull-requests": "write",
    }


def test_http_post_success_sends_exact_payload_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def respond(request, *, timeout):
        calls.append(request)
        assert request.get_method() == "POST"
        assert request.full_url == "https://api.github.com/repos/spec-kitty/spec-kitty/issues/7/comments"
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        assert json.loads(request.data) == {"body": "actual verdict"}
        assert timeout == 30
        return io.BytesIO(b'{"id": 123}')

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setattr(fleet_verdict.urllib.request, "urlopen", respond)
    assert fleet_verdict.GitHub("spec-kitty/spec-kitty").request("issues/7/comments", {"body": "actual verdict"}) == {"id": 123}
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        json.dumps({"message": f"Resource not accessible by integration {TOKEN}\n" + "x" * 900, "secret": "raw-body-private"}).encode(),
        b"not JSON raw-body-private",
        b"[123]",
        b'{"message": 123}',
        b'{"message": "' + b"x" * 9000 + b'"}',
        None,
        b"[" * 1500,
    ],
    ids=["github-message", "non-json", "non-object", "non-string-message", "oversized", "read-error", "deeply-nested"],
)
def test_http_failure_is_bounded_safe_and_never_retries(monkeypatch: pytest.MonkeyPatch, body: bytes | None) -> None:
    calls = []
    reads = []

    class BoundedResponse(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            assert 0 < size <= 4096
            if body is None:
                raise OSError(f"private read failure {TOKEN}")
            return super().read(size)

    headers = Message()
    headers["X-GitHub-Request-Id"] = f"TEST:REQUEST:ID {TOKEN}\n" + "x" * 1000
    headers["X-Accepted-GitHub-Permissions"] = f"pull_requests=write {TOKEN}\t" + "x" * 1000
    headers["Authorization"] = f"Bearer {TOKEN}"
    headers["X-Private"] = "private-header-value"

    def refuse(request, *, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 403, TOKEN, headers, BoundedResponse(body or b""))

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setattr(fleet_verdict.urllib.request, "urlopen", refuse)
    payload = {"body": "verdict-private"}
    with pytest.raises(ValueError) as caught:
        fleet_verdict.GitHub("spec-kitty/spec-kitty").request("issues/7/comments", payload)
    output = "".join(traceback.format_exception(caught.value))
    assert "HTTP 403" in str(caught.value)
    assert "TEST:REQUEST:ID" in output
    assert "pull_requests=write" in output
    assert all(secret not in output for secret in [TOKEN, "raw-body-private", "private-header-value", "verdict-private"])
    assert len(str(caught.value)) < 1100
    assert "\n" not in str(caught.value)
    assert "\t" not in str(caught.value)
    assert "[redacted]" in output
    assert len(calls) == 1
    assert reads == [4096]
    if body and body.startswith(b'{"message": "Resource'):
        assert "Resource not accessible by integration" in output
        assert "[redacted]" in output
