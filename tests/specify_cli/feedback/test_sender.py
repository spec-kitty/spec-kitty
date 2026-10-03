"""Unit tests for the fire-and-forget Feedback Submission sender (WP03 / T017)."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from specify_cli.feedback.models import Rating, SurveyAnswers, SurveyTrigger, normalize_harness
from specify_cli.feedback.payload import ContextFields, build_submission
from specify_cli.feedback.sender import _child_main, _detach_kwargs, hand_off

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SECRET_COMMENT = "never-in-argv-please"
_RATING_VALUE = 5


def _sample_body() -> dict[str, object]:
    return build_submission(
        SurveyAnswers(rating=Rating(_RATING_VALUE), comment=_SECRET_COMMENT, email=None),
        ContextFields(
            spec_kitty_version="0.0.0",
            distribution="spec-kitty-cli",
            trigger=SurveyTrigger.ON_DEMAND,
            harness=normalize_harness("cli"),
            os="other",
            mission_type=None,
        ),
    )


def test_hand_off_argv_hygiene(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeStdin:
        def write(self, data: bytes) -> int:
            captured["stdin"] = data
            return len(data)

        def close(self) -> None:
            return None

    class _FakeProc:
        stdin = _FakeStdin()

    def _fake_popen(argv: list[str], **kwargs: Any) -> _FakeProc:
        captured["argv"] = list(argv)
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr("specify_cli.feedback.sender.subprocess.Popen", _fake_popen)

    assert hand_off(_sample_body(), "http://127.0.0.1:9/x") is True
    assert captured["argv"] == [captured["argv"][0], "-m", "specify_cli.feedback.sender"]
    argv_joined = " ".join(captured["argv"])
    assert _SECRET_COMMENT not in argv_joined
    assert str(_RATING_VALUE) not in captured["argv"]  # rating never a discrete arg
    assert _SECRET_COMMENT.encode() in captured["stdin"]
    assert captured["kwargs"]["env"]["SPEC_KITTY_NON_INTERACTIVE"] == "1"


def test_detach_kwargs_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.feedback.sender.os.name", "posix")
    monkeypatch.setattr("specify_cli.feedback.sender.sys.platform", "linux")
    assert _detach_kwargs() == {"start_new_session": True}


def test_detach_kwargs_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.feedback.sender.os.name", "nt")
    monkeypatch.setattr("specify_cli.feedback.sender.sys.platform", "win32")
    result = _detach_kwargs()
    assert "creationflags" in result
    assert isinstance(result["creationflags"], int)
    assert result["creationflags"] != 0


def test_hand_off_returns_false_when_popen_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> None:
        raise OSError("spawn failed")

    monkeypatch.setattr("specify_cli.feedback.sender.subprocess.Popen", _boom)
    assert hand_off(_sample_body(), "http://127.0.0.1:9/x") is False


def test_hand_off_uses_creationflags_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeStdin:
        def write(self, data: bytes) -> int:
            return len(data)

        def close(self) -> None:
            return None

    class _FakeProc:
        stdin = _FakeStdin()

    def _fake_popen(argv: list[str], **kwargs: Any) -> _FakeProc:
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(
        "specify_cli.feedback.sender._detach_kwargs",
        lambda: {"creationflags": 0x123},
    )
    monkeypatch.setattr("specify_cli.feedback.sender.subprocess.Popen", _fake_popen)
    assert hand_off(_sample_body(), "http://127.0.0.1:9/x") is True
    assert captured["kwargs"]["creationflags"] == 0x123


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://feedback.example.test/v1", True),
        ("http://127.0.0.1:9/x", True),
        ("http://feedback.example.test/v1", False),
        ("ftp://127.0.0.1/x", False),
        ("not-a-url", False),
        ("http:///nohost", False),
    ],
)
def test_url_allowed_table(url: str, allowed: bool) -> None:
    from specify_cli.feedback.sender import _url_allowed

    assert _url_allowed(url) is allowed


def test_url_allowed_urlsplit_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.feedback.sender import _url_allowed

    def _boom(_url: str) -> None:
        raise ValueError("bad")

    monkeypatch.setattr("specify_cli.feedback.sender.urlsplit", _boom)
    assert _url_allowed("https://x.test") is False


def test_child_main_rejects_non_object_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.sender.sys.stdin",
        MagicMock(buffer=io.BytesIO(b"[1,2,3]")),
    )
    assert _child_main() == 0


def test_child_main_rejects_bad_url_or_body_types(monkeypatch: pytest.MonkeyPatch) -> None:
    envelope = json.dumps({"url": 123, "body": "nope"}).encode()
    monkeypatch.setattr(
        "specify_cli.feedback.sender.sys.stdin",
        MagicMock(buffer=io.BytesIO(envelope)),
    )
    assert _child_main() == 0


def test_build_and_hand_off_consent_and_endpoint_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint
    from specify_cli.feedback.sender import build_and_hand_off

    calls: list[Any] = []
    monkeypatch.setattr(
        "specify_cli.feedback.sender.hand_off",
        lambda body, url: calls.append((body, url)) or True,
    )
    answers = SurveyAnswers(rating=Rating(1))
    context = ContextFields(
        spec_kitty_version="0",
        distribution="spec-kitty-cli",
        trigger=SurveyTrigger.ON_DEMAND,
        harness=normalize_harness("cli"),
        os="other",
        mission_type=None,
    )
    assert (
        build_and_hand_off(
            answers,
            context,
            ResolvedEndpoint(url="http://127.0.0.1:1/x", source="env"),
            consent=False,
        )
        == "not_sent"
    )
    assert calls == []
    assert (
        build_and_hand_off(
            answers,
            context,
            ResolvedEndpoint(url=None, source="none"),
            consent=True,
        )
        == "no_endpoint"
    )
    assert calls == []
    assert (
        build_and_hand_off(
            answers,
            context,
            ResolvedEndpoint(url="http://127.0.0.1:1/x", source="env"),
            consent=True,
        )
        == "handed_off"
    )
    assert len(calls) == 1


def test_child_main_invalid_json_returns_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.sender.sys.stdin",
        MagicMock(buffer=io.BytesIO(b"not-json")),
    )
    assert _child_main() == 0


def test_child_main_rejects_non_loopback_http(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(204)

    transport = httpx.MockTransport(_handler)
    real_client = httpx.Client

    def _client(**kwargs: Any) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("specify_cli.feedback.sender.httpx.Client", _client)
    envelope = json.dumps({"url": "http://feedback.example.test/v1", "body": {"rating": 1}}).encode()
    monkeypatch.setattr(
        "specify_cli.feedback.sender.sys.stdin",
        MagicMock(buffer=io.BytesIO(envelope)),
    )
    assert _child_main() == 0
    assert calls == []


def test_child_main_posts_once_without_auth_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    transport = httpx.MockTransport(_handler)
    real_client = httpx.Client

    def _client(**kwargs: Any) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("specify_cli.feedback.sender.httpx.Client", _client)
    monkeypatch.setattr("specify_cli.feedback.sender.get_version", lambda: "9.9.9")
    body = {"rating": 2, "trigger": "on_demand"}
    envelope = json.dumps({"url": "http://127.0.0.1:8765/x", "body": body}).encode()
    monkeypatch.setattr(
        "specify_cli.feedback.sender.sys.stdin",
        MagicMock(buffer=io.BytesIO(envelope)),
    )
    assert _child_main() == 0
    assert len(seen) == 1
    req = seen[0]
    assert req.method == "POST"
    assert "Authorization" not in req.headers
    assert "Cookie" not in req.headers
    assert "Proxy-Authorization" not in req.headers
    assert req.headers["Content-Type"] == "application/json"
    assert req.headers["User-Agent"] == "spec-kitty-feedback/9.9.9"
