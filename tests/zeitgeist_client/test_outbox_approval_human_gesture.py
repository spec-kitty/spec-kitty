"""Z8-C hard trust requirement: final disposition of queued Zeitgeist prose
is NEVER model-callable or scriptable. This file is the negative-case suite
that proves it — every test here shows a plausible automation/bypass attempt
failing closed.

Five structural guards, one test group each:

1. No controlling terminal -> refused (a script, a subprocess spawned by an
   MCP client/tool-calling harness, or a CI job has none).
2. A controlling terminal exists but the typed response is wrong -> refused
   (a blind "always answer yes" automation doesn't know the per-item
   challenge, which is derived from the item's own content hash).
3. No public decision function accepts an attestation/force/yes/no-confirm
   parameter a caller could use to skip the gesture (closed API surface).
4. No environment variable changes the outcome (no bypass knob exists to
   set in the first place).
5. The MCP stdio adapter (``mcp_stdio.py``) never gains an approve/reject
   tool, and ``outbox_approval.py`` imports nothing MCP-related — a model
   talking over MCP has structurally no tool that reaches this surface.

Test 1 is additionally proven against the REAL OS primitive (a subprocess
detached from any controlling terminal via ``start_new_session=True``/
``setsid``), not only via a monkeypatched seam — the seam tests everywhere
else in this file and in ``test_outbox_approval.py`` exist so the rest of
the suite is deterministic and never blocks on this session's own terminal.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from specify_cli.zeitgeist_client import mcp_stdio, outbox_approval

pytestmark = pytest.mark.fast


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


class FakeTTY:
    def __init__(self, response: str) -> None:
        self.response = response
        self.written: list[str] = []
        self.closed = False

    def write(self, text: str) -> int:
        self.written.append(text)
        return len(text)

    def flush(self) -> None:
        pass

    def readline(self) -> str:
        return self.response + "\n"

    def close(self) -> None:
        self.closed = True

    @property
    def transcript(self) -> str:
        return "".join(self.written)


# --- 1. no controlling terminal -> refused -----------------------------------


def test_approve_with_no_controlling_terminal_is_refused_and_item_stays_pending(
    state_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="ship it")
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: None)

    with pytest.raises(outbox_approval.HumanGestureRequired):
        outbox_approval.approve(item.item_id, actor="robert")
    assert outbox_approval.show(item.item_id).status == "pending"


def test_reject_with_no_controlling_terminal_is_also_refused(state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="ship it")
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: None)

    with pytest.raises(outbox_approval.HumanGestureRequired):
        outbox_approval.reject(item.item_id, actor="robert")


def test_real_subprocess_detached_from_any_controlling_terminal_fails_closed(state_root: Path) -> None:
    """The genuine OS-level proof: a Python process started with its own
    session (``start_new_session=True``, i.e. ``setsid``) has structurally no
    controlling terminal regardless of what this test runner's own stdin/
    stdout are attached to — ``/dev/tty`` cannot resolve to anything.
    Exactly the shape of a subprocess an MCP client or an automation
    harness would launch."""
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(Path(__file__).resolve().parents[2] / "src")!r})
        from specify_cli.zeitgeist_client import outbox_approval
        item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="ship it")
        try:
            outbox_approval.approve(item.item_id, actor="script")
        except outbox_approval.HumanGestureRequired:
            print("REFUSED")
        else:
            print("APPROVED-WITHOUT-A-HUMAN")  # would be the failure signature
        """
    )
    env = {"SPEC_KITTY_HOME": str(state_root), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        start_new_session=True,  # setsid: detach from any controlling terminal
        timeout=15,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "REFUSED"


# --- 2. wrong challenge -> refused --------------------------------------------


def test_approve_with_a_wrong_confirmation_phrase_is_refused(state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="ship it")
    tty = FakeTTY("yes")  # a naive "always answer yes" automation
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: tty)

    with pytest.raises(outbox_approval.HumanGestureRequired):
        outbox_approval.approve(item.item_id, actor="robert")
    assert outbox_approval.show(item.item_id).status == "pending"


def test_approve_challenge_is_bound_to_the_specific_item_not_reusable_across_items(
    state_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item_a = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="message A")
    item_b = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="message B")

    # An attestation harvested for item_a's challenge must not confirm item_b.
    tty = FakeTTY(item_a.item_id[:8])
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: tty)
    with pytest.raises(outbox_approval.HumanGestureRequired):
        outbox_approval.approve(item_b.item_id, actor="robert")


def test_approve_prompt_discloses_the_exact_content_directly_on_the_tty(
    state_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verbatim = "Ship the release notes to #team-a exactly as written."
    item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content=verbatim)
    tty = FakeTTY(item.item_id[:8])
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: tty)

    outbox_approval.approve(item.item_id, actor="robert")
    assert verbatim in tty.transcript


# --- 3. closed API surface: no bypass parameter exists -----------------------


@pytest.mark.parametrize("name", ["approve", "reject", "revoke"])
def test_decision_functions_accept_no_bypass_parameter(name: str) -> None:
    sig = inspect.signature(getattr(outbox_approval, name))
    params = set(sig.parameters)
    assert params == {"item_id", "actor"}
    forbidden = {"attestation", "force", "yes", "assume_yes", "no_confirm", "skip_confirmation", "auto", "gesture"}
    assert not (params & forbidden)
    assert sig.parameters["actor"].kind is inspect.Parameter.KEYWORD_ONLY


# --- 4. no environment-variable bypass ----------------------------------------


@pytest.mark.parametrize(
    "env",
    [
        {"SPEC_KITTY_ZEITGEIST_OUTBOX_AUTO_APPROVE": "1"},
        {"SPEC_KITTY_ZEITGEIST_OUTBOX_APPROVE": "yes"},
        {"CI": "true"},
        {"SPEC_KITTY_NONINTERACTIVE": "1"},
        {"DEBIAN_FRONTEND": "noninteractive"},
    ],
)
def test_no_plausible_bypass_environment_variable_avoids_the_tty_requirement(
    state_root: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    item = outbox_approval.submit(repo="spec-kitty", audience="team-a", content="ship it")
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: None)

    with pytest.raises(outbox_approval.HumanGestureRequired):
        outbox_approval.approve(item.item_id, actor="robert")


def test_outbox_approval_module_never_reads_os_environ() -> None:
    source = inspect.getsource(outbox_approval)
    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert "import os" not in source


# --- 5. never reachable via MCP -----------------------------------------------


def test_mcp_server_exposes_no_outbox_approval_tool() -> None:
    server = mcp_stdio.build_server()
    tool_manager = server._tool_manager  # noqa: SLF001 - introspecting the built tool registry is the point of this guard
    names = set(tool_manager._tools.keys())  # noqa: SLF001
    assert names == {"zeitgeist_status", "zeitgeist_watch", "zeitgeist_activity"}
    for name in names:
        lowered = name.lower()
        assert "approve" not in lowered
        assert "reject" not in lowered
        assert "outbox" not in lowered


def test_outbox_approval_module_imports_nothing_mcp_related() -> None:
    assert not any(name.startswith("mcp") for name in outbox_approval.__dict__)
    source = inspect.getsource(outbox_approval)
    assert "import mcp" not in source
    assert "fastmcp" not in source.lower()


def test_mcp_stdio_module_never_imports_outbox_approval() -> None:
    source = inspect.getsource(mcp_stdio)
    assert "outbox" not in source.lower()
