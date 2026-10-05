"""Fire-and-forget Feedback Submission sender.

The parent serialises an envelope onto a detached child's stdin and returns
immediately. The child makes one bounded HTTPS (or loopback HTTP) POST and
exits 0 silently on every path. Answers never appear in argv, env, logs, or
disk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

import httpx

from specify_cli.feedback.endpoint import ResolvedEndpoint
from specify_cli.feedback.models import SurveyAnswers
from specify_cli.feedback.payload import ContextFields, build_submission
from specify_cli.version_utils import get_version

__all__ = [
    "build_and_hand_off",
    "hand_off",
]

_STDIN_BUDGET = 16 * 1024
_POST_TIMEOUT = httpx.Timeout(5.0)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_CHILD_MODULE = "specify_cli.feedback.sender"
_HandOffOutcome = Literal["handed_off", "not_sent", "no_endpoint"]


def _detach_kwargs() -> dict[str, int | bool]:
    """Platform-specific flags so the child survives parent exit."""
    if os.name == "nt" or sys.platform.startswith("win"):
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS — defined on Windows only.
        flags = int(getattr(subprocess, "DETACHED_PROCESS", 0x00000008))
        flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200))
        return {"creationflags": flags}
    return {"start_new_session": True}


def _url_allowed(url: str) -> bool:
    """Defence-in-depth: https, or http on a loopback host."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    hostname = parts.hostname
    if not parts.scheme or hostname is None:
        return False
    scheme = parts.scheme.lower()
    if scheme == "https":
        return True
    if scheme == "http":
        return hostname.lower() in _LOOPBACK_HOSTS
    return False


def _child_main() -> int:
    """Child entry: one POST from stdin envelope; always exit 0 silently."""
    try:
        raw = sys.stdin.buffer.read(_STDIN_BUDGET)
        envelope = json.loads(raw.decode("utf-8"))
        if not isinstance(envelope, dict):
            return 0
        url = envelope.get("url")
        body = envelope.get("body")
        if not isinstance(url, str) or not isinstance(body, dict):
            return 0
        if not _url_allowed(url):
            return 0
        version = get_version()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"spec-kitty-feedback/{version}",
        }
        with httpx.Client(
            timeout=_POST_TIMEOUT,
            follow_redirects=False,
            headers=headers,
        ) as client:
            client.post(url, json=body)
    except BaseException:
        return 0
    return 0


def hand_off(body: Mapping[str, object], endpoint_url: str) -> bool:
    """Spawn a detached child with the envelope on stdin. Never waits or raises."""
    try:
        envelope = json.dumps({"url": endpoint_url, "body": dict(body)}, separators=(",", ":"))
        payload = envelope.encode("utf-8")
        env = os.environ.copy()
        env["SPEC_KITTY_NON_INTERACTIVE"] = "1"
        argv = [sys.executable, "-m", _CHILD_MODULE]
        detach = _detach_kwargs()
        # Fixed argv, no shell; payload travels on stdin only (bandit S603).
        if "creationflags" in detach:
            proc = subprocess.Popen(  # noqa: S603
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=env,
                creationflags=int(detach["creationflags"]),
            )
        else:
            proc = subprocess.Popen(  # noqa: S603
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=env,
                start_new_session=True,
            )
        assert proc.stdin is not None
        proc.stdin.write(payload)
        proc.stdin.close()
        return True
    except BaseException:
        return False


def build_and_hand_off(
    answers: SurveyAnswers,
    context: ContextFields,
    endpoint: ResolvedEndpoint,
    *,
    consent: bool,
) -> _HandOffOutcome:
    """Consent-gated build + hand-off. Delivery failure is invisible to callers."""
    if not consent:
        return "not_sent"
    if endpoint.url is None:
        return "no_endpoint"
    body = build_submission(answers, context)
    hand_off(body, endpoint.url)
    return "handed_off"


if __name__ == "__main__":
    raise SystemExit(_child_main())
