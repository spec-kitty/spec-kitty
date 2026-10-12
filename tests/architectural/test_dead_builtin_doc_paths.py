"""Architectural gate: live documentation must not name a pre-move built-in
path.

Split out of ``test_no_dead_doctrine_paths.py`` (mission
``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP01, FR-001) --
Gate D is the only ``docs/``-scoped gate of the three that file used to
carry (Gate A + Gate B are ``src/``-wide, now in ``test_no_dead_cli_paths.py``;
Gate C is ``src/charter/offering/``-scoped, still in ``test_no_dead_doctrine_paths.py``).
``docs/``-scoping is a third, distinct concern, so it gets its own explicitly
named home rather than being folded into whichever other module was
convenient.

Originally: mission ``relocate-builtin-doctrine-packs-01KYT87F`` T024 /
FR-011.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.architectural._dead_path_scan import _REPO_ROOT

#: Without this the CI shard that selects ``-m architectural`` collects none of
#: these tests, and the gate silently never runs.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Gate D -- live documentation must not name a pre-move built-in path
# (mission relocate-builtin-doctrine-packs-01KYT87F, T024 / FR-011)
# ---------------------------------------------------------------------------

#: The two path shapes the relocation retired from ``src/charter/offering/``: the
#: per-kind built-in content home ``src/charter/offering/<kind>/built-in`` and the
#: sharded per-kind fragments ``src/charter/offering/<kind>.graph.yaml``. Both now live
#: under ``packs/built-in/``.
#:
#: The leading ``(^|[^A-Za-z0-9_./-])`` is a LEFT BOUNDARY (#6096). ``git grep -E``
#: has no look-behind, so without it the shape matched as an unanchored substring
#: and any longer path whose tail was ``…/src/charter/offering/<kind>/built-in``
#: (a ``packs/…/src/…`` path, an absolute ``/…/src/…`` path, a ``…/blob/…/src/…``
#: URL) was wrongly flagged as the retired TOP-LEVEL home. The boundary admits a
#: match only at start-of-line or after a character that cannot be part of a path
#: (not ``/``, a word char, ``.`` or ``-``), so a genuine top-level reference is
#: still caught while a nested tail is not. Because the boundary excludes ``/``, a
#: slash-preceded reference -- including a leading ``./src/charter/offering/…`` -- is
#: treated as nested and left to ``test_no_dead_src_path_literals.py``, whose
#: ``(?<!\w)src/`` lookbehind still flags it (``/`` is not a word char), exactly as
#: the blob-URL case already is. That general ``src/``-literal gate, not Gate D,
#: owns ``src/`` literals nested in a longer path. Scope is forward-slash paths
#: (#6096); a backslash-separated tail is out of scope here (and not handled by the
#: sibling gate either). This tightens the left boundary only; the two forbidden
#: shapes and ``_GUARD_DOC_EXCLUSIONS`` are unchanged.
_MOVED_BUILTIN_DOC_RE = r"(^|[^A-Za-z0-9_./-])(src/charter/offering/[a-z_]+/built-in|src/charter/offering/[a-zA-Z0-9_.-]*\.graph\.yaml)"

#: Documentation subtrees excluded from the live-reference guard, each because
#: its references are NOT live pointers to where doctrine currently lives:
#:  * ``docs/adr`` -- immutable decision snapshots (the Terminology Canon keeps
#:    historical wording frozen; an ADR records the world as it was).
#:  * ``docs/plans`` -- point-in-time mission planning and adversarial-squad
#:    analysis (line-numbered ``*.graph.yaml`` citations, and hypothetical paths
#:    such as ``src/charter/offering/values/built-in/…`` that never existed on disk).
#:  * the generated retrieval index -- a derived aggregate that mirrors the
#:    ``docs/plans`` headings it indexes, so it carries their frozen wording and
#:    is regenerated, never hand-edited.
#:  * the relocation migration note -- its whole job is to document the move, so
#:    its old->new mapping table NAMES the retired ``src/charter/offering/.../built-in``
#:    paths as the "from" column. That is a record of where content used to live,
#:    not a live pointer to where it lives now (same rationale as ``docs/adr``).
_GUARD_DOC_EXCLUSIONS = (
    ":(exclude)docs/adr",
    ":(exclude)docs/plans",
    ":(exclude)docs/development/docs-retrieval-index.yaml",
    ":(exclude)docs/migrations/relocate-builtin-doctrine-packs.md",
)


def _grep_moved_builtin_doc_paths(cwd: Path, pathspecs: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    """Run Gate D's ``git grep`` for a retired pre-move built-in path.

    The live gate and its regression test share this one matcher so both
    exercise the identical mechanism (``_MOVED_BUILTIN_DOC_RE`` fed to
    ``git grep -nE``); the test differs only in ``cwd`` and ``pathspecs``.
    Returns the ``CompletedProcess``; ``git grep`` exit status is 0 when
    matches are found (dead refs present), 1 when clean, and anything else on a
    grep error.
    """
    return subprocess.run(
        ["git", "grep", "-nE", _MOVED_BUILTIN_DOC_RE, "--", *pathspecs],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_no_live_doc_names_a_pre_move_builtin_path() -> None:
    """FR-011 committed guard: the T024 live-reference sweep is observable, not
    eyeballed. ``git grep`` of live ``docs/`` (minus the snapshot/derived subtrees
    pinned above) for a retired ``src/charter/offering/`` built-in path must return zero;
    a hit means a live doc still sends a reader to a home that moved to
    ``packs/built-in/`` (see docs/migrations/relocate-builtin-doctrine-packs.md)."""
    result = _grep_moved_builtin_doc_paths(_REPO_ROOT, ("docs", *_GUARD_DOC_EXCLUSIONS))
    if result.returncode not in (0, 1):
        pytest.skip(f"git grep unavailable ({result.returncode}): {result.stderr.strip()}")
    # git grep exit status: 0 == matches found (dead refs present); 1 == clean.
    assert result.returncode == 1, (
        "Live documentation still names a pre-move built-in path. Repoint each to "
        "packs/built-in/ (drop the inner `built-in` segment):\n" + result.stdout
    )


def test_gate_d_rejects_a_nested_tail_but_still_catches_a_top_level_ref(tmp_path: Path) -> None:
    """#6096 non-vacuity (both directions): the retired built-in path shape as the
    TAIL of a longer path must not trip Gate D, while a genuine TOP-LEVEL reference
    still must.

    ``git grep -E`` has no look-behind, so the pre-fix ``_MOVED_BUILTIN_DOC_RE``
    matched as an unanchored substring and flagged any ``…/src/charter/offering/<kind>/built-in``
    (or ``…/*.graph.yaml``) tail as if it named the retired top-level home. The
    left-boundary anchor admits a match only at start-of-line or after a non-path,
    non-word character.

    This exercises the real ``git grep`` + ``_MOVED_BUILTIN_DOC_RE`` against a
    throwaway repo, so it is self-mutation-proven in both directions: removing the
    anchor re-reds the "tail not flagged" assertions (the over-match returns), and
    breaking the match re-reds the "genuine ref flagged" positive controls (the
    gate stops catching the real dead ref). A gate-unmask cannot self-validate.
    """
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    # Genuine TOP-LEVEL references -- the gate must still catch these.
    (docs / "genuine_builtin.md").write_text(
        "See src/charter/offering/foo/built-in for the retired home.\n",
        encoding="utf-8",
    )
    (docs / "genuine_graph.md").write_text(
        "The fragment src/charter/offering/foo.graph.yaml moved to packs/built-in/.\n",
        encoding="utf-8",
    )

    # TAILS of longer paths -- the #6096 over-match. The gate must NOT flag these.
    (docs / "nested_pack_tail.md").write_text(
        "Pack content lives at packs/internal/x/src/charter/offering/foo/built-in today.\n",
        encoding="utf-8",
    )
    (docs / "absolute_path_tail.md").write_text(
        "Absolute: /home/runner/work/spec-kitty/spec-kitty/src/charter/offering/foo/built-in\n",
        encoding="utf-8",
    )
    (docs / "blob_url_tail.md").write_text(
        "URL: https://github.com/spec-kitty/spec-kitty/blob/main/src/charter/offering/foo.graph.yaml\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = _grep_moved_builtin_doc_paths(repo, ("docs",))
    if result.returncode not in (0, 1):
        pytest.skip(f"git grep unavailable ({result.returncode}): {result.stderr.strip()}")
    flagged = {line.split(":", 1)[0] for line in result.stdout.splitlines() if line}

    # Positive controls: genuine top-level references are still reported.
    assert "docs/genuine_builtin.md" in flagged, result.stdout
    assert "docs/genuine_graph.md" in flagged, result.stdout
    # The #6096 fix: a retired shape that is only the tail of a longer path is not reported.
    assert "docs/nested_pack_tail.md" not in flagged, result.stdout
    assert "docs/absolute_path_tail.md" not in flagged, result.stdout
    assert "docs/blob_url_tail.md" not in flagged, result.stdout
