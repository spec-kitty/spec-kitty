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
_MOVED_BUILTIN_DOC_RE = r"src/charter/offering/[a-z_]+/built-in|src/charter/offering/[a-zA-Z0-9_.-]*\.graph\.yaml"

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


def test_no_live_doc_names_a_pre_move_builtin_path() -> None:
    """FR-011 committed guard: the T024 live-reference sweep is observable, not
    eyeballed. ``git grep`` of live ``docs/`` (minus the snapshot/derived subtrees
    pinned above) for a retired ``src/charter/offering/`` built-in path must return zero;
    a hit means a live doc still sends a reader to a home that moved to
    ``packs/built-in/`` (see docs/migrations/relocate-builtin-doctrine-packs.md)."""
    result = subprocess.run(
        ["git", "grep", "-nE", _MOVED_BUILTIN_DOC_RE, "--", "docs", *_GUARD_DOC_EXCLUSIONS],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        pytest.skip(f"git grep unavailable ({result.returncode}): {result.stderr.strip()}")
    # git grep exit status: 0 == matches found (dead refs present); 1 == clean.
    assert result.returncode == 1, (
        "Live documentation still names a pre-move built-in path. Repoint each to "
        "packs/built-in/ (drop the inner `built-in` segment):\n" + result.stdout
    )
