"""Red-first regression: ``tracer-append`` routes through the owned Mission checkout (#7081).

On ``main`` the command resolves ``get_main_repo_root()`` unconditionally
(``src/specify_cli/cli/commands/agent/tracer_append.py:105-125``), so an invocation made
from an owned ``single_branch`` checkout ``P`` writes its tracer entry into the repository
root checkout ``R`` and the tag commit is refused ``PROTECTED_BRANCH_REFUSED`` on ``main`` —
leaving an untracked ``kitty-specs/<slug>/traces/<category>.md`` behind in ``R``. The
command also exposed no ``--owned-checkout``.

This module drives the real command entry point against two real checkouts (``R`` on
``main``, ``P`` a linked worktree on the Mission branch) and pins:

1. flagless adoption — an invocation from inside ``P`` writes into ``P`` and leaves ``R``
   untouched;
2. the explicit selector — ``--owned-checkout P`` from ``R`` does the same;
3. refuse-before-write — ``--owned-checkout R`` exits 1 with a typed owned refusal and
   never reaches the writer;
4. the non-owned path — no flag and no adoptable checkout keeps today's write surface.
"""

from __future__ import annotations

import json
import subprocess
import typer
import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.coordination.commit_outcome import SurfaceOutcome
from specify_cli.coordination.write_seam import WriteSeamResult

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

SLUG = "tracer-owned-01M6G9FW"
BRANCH = "kitty/mission-tracer-owned-01M6G9FW"
MID = "01M6G9FWJDPXEKG88H3968Y7GG"
CATEGORY = "approach"
ENTRY = "owned routing probe"
ACTOR = "tester"

_MODULE = "specify_cli.cli.commands.agent.tracer_append"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _mission_meta() -> dict[str, object]:
    return {
        "mission_id": MID,
        "mission_slug": SLUG,
        "slug": SLUG,
        "mission_type": "software-dev",
        "topology": "single_branch",
        # A protected landing target plus the minted mission branch is exactly
        # the shape `spec-kitty specify` writes for an owned single_branch mission.
        "target_branch": "main",
        "mission_branch": BRANCH,
        "flattened": False,
    }


@pytest.fixture
def tracer_module():  # type: ignore[no-untyped-def]
    """Import the command module by path.

    ``specify_cli.cli.commands.agent.__init__`` rebinds the package attribute of the same
    name to the *function*, so a plain ``import ... as m`` would bind the function, not the
    module (see ``tests/mission_runtime/test_coord_read_seam_callers.py``).
    """
    return importlib.import_module(_MODULE)


def _app(module) -> typer.Typer:  # type: ignore[no-untyped-def]
    app = typer.Typer()
    app.command()(module.tracer_append)
    return app


def _two_checkouts(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(repository_root R, owned checkout P, P's mission dir)`` on real git."""
    r_root = tmp_path / "primary"
    r_root.mkdir()
    _git(r_root, "init", "-q", "-b", "main")
    _git(r_root, "config", "user.name", "Test")
    _git(r_root, "config", "user.email", "test@example.invalid")
    _git(r_root, "config", "commit.gpgsign", "false")
    (r_root / "README.md").write_text("seed\n", encoding="utf-8")
    (r_root / ".kittify").mkdir()
    (r_root / ".kittify" / "config.yaml").write_text("project: tracer-owned\n", encoding="utf-8")
    _git(r_root, "add", "-A")
    _git(r_root, "commit", "-qm", "seed")

    p_root = tmp_path / "owned"
    _git(r_root, "worktree", "add", "-q", "-b", BRANCH, str(p_root))
    mission_dir = p_root / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps(_mission_meta()), encoding="utf-8")
    _git(p_root, "add", "-A")
    _git(p_root, "commit", "-qm", "owned mission")
    return r_root, p_root, mission_dir


def _invoke(app: typer.Typer, extra: list[str]) -> object:
    args = ["--mission", SLUG, "--category", CATEGORY, "--entry", ENTRY, "--actor", ACTOR, "--json", *extra]
    return CliRunner().invoke(app, args, catch_exceptions=False)


def _json_payload(output: str) -> dict[str, object]:
    """The command's JSON envelope, ignoring any logger warning line printed before it.

    The owned-refusal renderer prints an indented envelope, so decode from the first
    ``{`` with ``raw_decode`` rather than parsing a single line.
    """
    start = output.find("{")
    assert start >= 0, f"no JSON payload in output: {output!r}"
    payload, _end = json.JSONDecoder().raw_decode(output[start:])
    return payload  # type: ignore[no-any-return]


def _traces(root: Path) -> list[Path]:
    return sorted(root.rglob("traces/*.md"))


def test_help_exposes_the_owned_selector(tracer_module, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """``tracer-append --help`` advertises the shared owned selector."""
    result = CliRunner().invoke(_app(tracer_module), ["--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "--owned-checkout" in result.output


def test_flagless_invocation_from_the_owned_checkout_writes_into_it(
    tmp_path: Path,
    tracer_module,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """The issue's own reproduction: cwd inside ``P``, no flag, the write lands in ``P``."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    r_root, p_root, mission_dir = _two_checkouts(tmp_path)
    monkeypatch.chdir(mission_dir)

    result = _invoke(_app(tracer_module), [])

    assert result.exit_code == 0, result.output
    payload = _json_payload(result.output)
    assert payload["ok"] is True, payload
    assert payload["commit_ref"] == BRANCH
    assert "PROTECTED_BRANCH_REFUSED" not in result.output
    written = _traces(p_root)
    assert written == [mission_dir / "traces" / f"{CATEGORY}.md"]
    assert ENTRY in written[0].read_text(encoding="utf-8")
    # The repository root checkout is untouched: no tracer residue, no new commit.
    assert _traces(r_root) == []
    assert _git(r_root, "status", "--porcelain") == ""
    assert _git(r_root, "rev-parse", "main") == _git(p_root, "merge-base", "main", BRANCH)


def test_explicit_selector_from_the_repository_root_writes_into_the_owned_checkout(
    tmp_path: Path,
    tracer_module,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """``--owned-checkout P`` selects the same surface as flagless adoption."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    r_root, p_root, mission_dir = _two_checkouts(tmp_path)
    monkeypatch.chdir(r_root)

    result = _invoke(_app(tracer_module), ["--owned-checkout", str(p_root)])

    assert result.exit_code == 0, result.output
    assert _json_payload(result.output)["ok"] is True
    assert _traces(p_root) == [mission_dir / "traces" / f"{CATEGORY}.md"]
    assert _traces(r_root) == []


def test_repository_root_claim_refuses_before_writing(
    tmp_path: Path,
    tracer_module,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """An invalid owned target is refused typed, and the writer is never reached."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    r_root, p_root, _mission_dir = _two_checkouts(tmp_path)
    monkeypatch.chdir(r_root)
    writes: list[dict[str, object]] = []

    def _spy(**kwargs: object) -> WriteSeamResult:
        writes.append(dict(kwargs))
        raise AssertionError("the writer must not be reached on an invalid owned target")

    monkeypatch.setattr(tracer_module, "append_tracer_finding", _spy)

    result = _invoke(_app(tracer_module), ["--owned-checkout", str(r_root)])

    assert result.exit_code == 1, result.output
    payload = _json_payload(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"  # type: ignore[index]
    assert writes == []
    assert _traces(r_root) == []
    assert _traces(p_root) == []


# Heading anchor for the added refusal cases.


def test_foreign_checkout_claim_refuses_before_writing(
    tmp_path: Path,
    tracer_module,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """``--owned-checkout`` naming a checkout that does not own the Mission refuses typed."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    r_root, p_root, _mission_dir = _two_checkouts(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git(foreign, "init", "-q", "-b", "main")
    _git(foreign, "config", "user.name", "Test")
    _git(foreign, "config", "user.email", "test@example.invalid")
    (foreign / "README.md").write_text("other\n", encoding="utf-8")
    _git(foreign, "add", "-A")
    _git(foreign, "commit", "-qm", "other")
    monkeypatch.chdir(r_root)

    def _spy(**_kwargs: object) -> WriteSeamResult:
        raise AssertionError("the writer must not be reached on a foreign owned target")

    monkeypatch.setattr(tracer_module, "append_tracer_finding", _spy)

    result = _invoke(_app(tracer_module), ["--owned-checkout", str(foreign)])

    assert result.exit_code == 1, result.output
    payload = _json_payload(result.output)
    assert payload["ok"] is False
    # The claim primitive's typed refusal, surfaced unchanged through the shared
    # owned CLI seam: a checkout of a different repository cannot own this Mission.
    assert payload["error"]["code"] == "OWNERSHIP_FOREIGN"  # type: ignore[index]
    assert _traces(r_root) == []
    assert _traces(p_root) == []
    assert _traces(foreign) == []


def test_non_owned_invocation_keeps_the_repository_root_surface(
    tmp_path: Path,
    tracer_module,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """No flag and no adoptable checkout: the fact is absent and today's surface stands."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    r_root, _p_root, _mission_dir = _two_checkouts(tmp_path)
    monkeypatch.chdir(r_root)
    captured: list[dict[str, object]] = []

    def _capture(**kwargs: object) -> WriteSeamResult:
        captured.append(dict(kwargs))
        return WriteSeamResult(
            status="committed",
            entry_id="approach-0000000000",
            destination_surface="main",
            commit_hash="0" * 40,
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="main",
                    status="committed",
                    commit_hash="0" * 40,
                    committed=(f"kitty-specs/{SLUG}/traces/{CATEGORY}.md",),
                ),
            ),
        )

    monkeypatch.setattr(tracer_module, "append_tracer_finding", _capture)

    result = _invoke(_app(tracer_module), [])

    assert result.exit_code == 0, result.output
    assert len(captured) == 1
    assert captured[0]["repo_root"] == r_root
    assert captured[0]["owned"] is None
    assert captured[0]["mission_slug"] == SLUG
