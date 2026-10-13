"""Real-tree docs-freshness gate: the committed retrieval index must be fresh.

Issue #6183 (task D of #6166), operator ruling 2026-10-13: *run the docs
freshness check on docs-only changes, but not the heavy architectural battery.*

Background (#6150, fixed by #6144): a docs-only push to ``main`` added
``docs/architecture/acceptance-scenario-contract.md`` + an ADR without
regenerating ``docs/development/docs-retrieval-index.yaml``. That left
``check_docs_freshness --ci`` red with ``DOCS-INDEX-DRIFT`` — but no CI job ran
the real-tree freshness check on the docs change itself, so it surfaced only
later, on an unrelated code PR.

The sibling ``test_docs_index_freshness.py`` exercises
``_check_docs_index_drift`` against synthetic ``tmp_path`` fixtures (the checker
*logic*); ``test_docs_index.py::test_committed_live_index_is_sorted_headed_and_nonempty``
asserts the committed index is sorted/headed/non-empty but **not** that it is
*fresh* against the live tree. Neither catches a new or edited ``docs/**/*.md``
page that was never folded into the committed index. This gate closes that gap
by running the same ``DOCS-INDEX-DRIFT`` sub-check against the **real**
repository tree.

Where it runs: ``tests/docs`` is executed by the ``tests (docs)`` router job,
gated on the ``docs`` filter group (``docs/**`` / ``tests/docs/**`` /
``scripts/docs/**``). A docs-only push/PR matches that group, so this gate runs
on the docs change itself — and, because the retrieval index is derived solely
from ``docs/**/*.md``, only a docs change can drift it, so the ``docs``-gated
home gives exactly the right coverage with no new workflow, no ``ci-router.yml``
edit, and no heavy-battery cost. It is deliberately **not** marked ``fast`` (a
full index regeneration over the live docs tree is seconds-class, not an
inner-loop test).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import check_docs_freshness as orchestrator
from specify_cli.docs.index_model import DEFAULT_INDEX_PATH

#: Repo root: tests/docs/<this file> -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Full-tree regeneration + compare is seconds-class; keep it off the ``fast``
# inner loop (Rule 1 of the marker-correctness gate), but it is a plain unit
# assertion otherwise (no subprocess, no network).
pytestmark = pytest.mark.unit


def test_committed_retrieval_index_is_fresh_against_the_live_docs_tree() -> None:
    """``docs/development/docs-retrieval-index.yaml`` must match the live tree.

    This is the real-tree form of the ``DOCS-INDEX-DRIFT`` sub-check of
    ``check_docs_freshness``. A failure means a ``docs/**/*.md`` page was added,
    removed, renamed, or had its title/description/headings changed without
    regenerating the committed index.
    """
    docs_root = _REPO_ROOT / "docs"
    index_path = _REPO_ROOT / DEFAULT_INDEX_PATH

    findings = orchestrator._check_docs_index_drift(index_path, docs_root)

    drifted = [f.location for f in findings if f.rule_id == "DOCS-INDEX-DRIFT"]
    assert not drifted, (
        "The committed docs retrieval index is stale against the live docs tree "
        f"({len(drifted)} drifted page(s)): {drifted[:10]}"
        f"{' …' if len(drifted) > 10 else ''}. "
        "Regenerate it and commit the diff: "
        "PYTHONPATH=. uv run python scripts/docs/docs_index.py --write"
    )
