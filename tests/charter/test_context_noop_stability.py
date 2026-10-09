"""Render-path no-op-stability regression guard (#2373 / #1914).

Locks in the already-shipped #2773 render-path fix: ``build_charter_context``
MUST NOT write any git-tracked artifact. Only the gitignored runtime file
``.kittify/charter/context-state.json`` may change on disk (untracked).

Authoritative grounding:
- ``kitty-specs/charter-deadcode-noop-campsite-01KXW0NY/contracts/no-op-stability.contract.md``
  (guarantees G1, G3).
- ``kitty-specs/charter-deadcode-noop-campsite-01KXW0NY/data-model.md`` (LM-1).
- ``kitty-specs/charter-deadcode-noop-campsite-01KXW0NY/research.md`` §3.

LM-1 — the masking landmine
----------------------------
This working checkout carries a *local*, uncommitted
``.git/info/exclude`` entry (``.kittify/charter-packs/``, ``.kittify/charter/provenance/``)
that hides doctrine churn from ``git status`` in day-to-day development. The
*committed* ``.gitignore`` tracks those artifacts (with targeted negations for
``directive/``, ``tactic/``, ``styleguide/``, ``procedure/``, ``overlays/``,
``graph.yaml``) — a cleanliness assertion run directly against this checkout
would be a **false pass**: it can't observe churn that the local exclude is
already hiding.

The fixture below sidesteps the mask by cloning this repo's current commit
into a throwaway temp directory. ``.git/info/exclude`` lives outside version
control and is per-checkout — a fresh ``git clone`` never inherits it — so the
clone observes exactly the committed ``.gitignore`` state, where
``.kittify/charter-packs/**`` and ``.kittify/charter/*`` are genuinely git-tracked.
``_assert_doctrine_is_git_tracked`` asserts this precondition explicitly so a
future regression in the fixture itself (e.g. someone "simplifying" it back
to the live checkout) fails loudly instead of silently passing vacuously.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from charter.activation.context import build_charter_context
from kernel.charter_pack_paths import PROJECT_PACK_ROOT_POSIX

# Real subprocess git clones/checkouts against a throwaway temp repo: not a
# pure-logic test, and structurally incompatible with mutmut's forked sandbox.
pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MISSION_TYPE = "software-dev"


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _clone_doctrine_tracked_repo(dest: Path) -> Path:
    """Clone this repo's current commit into ``dest``, sans the LM-1 exclude mask.

    A fresh ``git clone`` gets a fresh, empty ``.git/info/exclude`` — the
    local mask that hides doctrine churn in this working checkout is never
    copied. The clone therefore observes the committed ``.gitignore`` state,
    where ``.kittify/charter-packs/**`` and ``.kittify/charter/*`` are tracked.

    The committed ``charter.yaml`` now carries the WP04 (C-A1)
    ``mission_type_activations`` provisioning key (emitted by the charter
    generation path — ``charter.activation.compiler.provision_mission_type_activations``),
    so the clone is already a provisioned, ``PackContext.from_config``-readable
    baseline with no fixture-side append/commit required.
    """
    head_sha = _run_git(["rev-parse", "HEAD"], cwd=_REPO_ROOT).stdout.strip()
    _run_git(
        ["clone", "--local", "--no-hardlinks", "--no-checkout", "--quiet", str(_REPO_ROOT), str(dest)],
        cwd=_REPO_ROOT,
    )
    _run_git(["checkout", "--quiet", head_sha], cwd=dest)
    return dest


def _assert_doctrine_is_git_tracked(repo: Path) -> None:
    """Fail loudly if the fixture is vacuous instead of proving nothing.

    Reviewer guidance for this WP is explicit: a green cleanliness assertion
    against a fixture that doesn't actually track doctrine is a false pass.
    """
    tracked_doctrine = _run_git(["ls-files", PROJECT_PACK_ROOT_POSIX], cwd=repo).stdout.strip().splitlines()
    assert tracked_doctrine, (
        f"Fixture is vacuous: {PROJECT_PACK_ROOT_POSIX}/** is not git-tracked in the "
        "cloned repo. LM-1 requires a doctrine-tracked fixture for this guard "
        "to mean anything."
    )
    tracked_charter_yaml = _run_git(["ls-files", ".kittify/charter/charter.yaml"], cwd=repo).stdout.strip()
    assert tracked_charter_yaml, "Fixture is vacuous: .kittify/charter/charter.yaml is not git-tracked."

    exclude_path = repo / ".git" / "info" / "exclude"
    exclude_text = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    assert PROJECT_PACK_ROOT_POSIX not in exclude_text, (
        "Fixture leaked the LM-1 local exclude mask into the clone; the "
        "cleanliness assertion below would be vacuous."
    )


def _tracked_status_lines(repo: Path) -> list[str]:
    """``git status --porcelain`` lines for tracked content only.

    Untracked (``??``) entries are excluded on purpose: G1/G3 explicitly
    permit the gitignored runtime file ``.kittify/charter/context-state.json``
    to appear untracked after a render. Only modified/added/deleted entries
    against already-tracked content indicate a real regression.
    """
    status = _run_git(["status", "--porcelain"], cwd=repo).stdout.splitlines()
    return [line for line in status if line and not line.startswith("??")]


@pytest.fixture
def doctrine_tracked_repo(tmp_path: Path) -> Path:
    """A doctrine-tracked clone of this repo, verified clean before use."""
    repo = _clone_doctrine_tracked_repo(tmp_path / "doctrine-tracked-repo")
    _assert_doctrine_is_git_tracked(repo)
    assert _tracked_status_lines(repo) == [], "fixture must start from a clean tracked tree"
    return repo


class TestRenderPathNoOpStability:
    """build_charter_context must not write any git-tracked artifact."""

    def test_fixture_doctrine_is_git_tracked_not_masked(self, doctrine_tracked_repo: Path) -> None:
        """Explicit LM-1 guard: this fixture is doctrine-tracked, not masked.

        Belt-and-braces companion to the fixture's own internal assertion —
        pins the precondition as a first-class, independently readable test
        so a reviewer (or future refactor) sees it fail on its own if the
        fixture ever regresses back to the masked checkout.
        """
        _assert_doctrine_is_git_tracked(doctrine_tracked_repo)

    def test_g1_single_render_produces_no_tracked_diff(self, doctrine_tracked_repo: Path) -> None:
        """G1: clean tree, fresh DRG -> render leaves 0 tracked-file diffs."""
        result = build_charter_context(
            doctrine_tracked_repo,
            action="implement",
            mission_type=_MISSION_TYPE,
        )

        assert result.mode == "bootstrap"
        assert _tracked_status_lines(doctrine_tracked_repo) == []

    def test_g3_second_render_also_produces_no_tracked_diff(self, doctrine_tracked_repo: Path) -> None:
        """G3: any governed op run twice -> the 2nd run is also 0 tracked-file diffs."""
        first = build_charter_context(
            doctrine_tracked_repo,
            action="implement",
            mission_type=_MISSION_TYPE,
        )
        assert _tracked_status_lines(doctrine_tracked_repo) == [], "1st render already left tracked churn"

        second = build_charter_context(
            doctrine_tracked_repo,
            action="implement",
            mission_type=_MISSION_TYPE,
        )

        # Second load transitions bootstrap -> compact (state-driven depth);
        # confirms the render actually re-executed the real path rather than
        # short-circuiting before it could write anything.
        assert first.first_load is True
        assert second.first_load is False
        assert _tracked_status_lines(doctrine_tracked_repo) == []
