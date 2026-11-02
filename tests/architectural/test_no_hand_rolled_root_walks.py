"""No new hand-rolled ancestor walk outside ``kernel.ancestor_walk`` (#7056).

Every repo/project-root walk in this repository goes through the shared, ceiling-aware
primitive, so ``GIT_CEILING_DIRECTORIES`` bounds them all and a hermetic tree inside an
enclosing checkout cannot resolve into it (#7022 fixed three walks; #7056 fixed the
rest). This gate keeps the next ``[p, *p.parents]`` loop from quietly reintroducing the
hole.

It is a **negative invariant with a positive control and a shrink-only allowlist**: the
corpus is asserted non-empty, a synthetic hand-rolled walk must be reported, and every
exemption must still match a live hit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural._hand_rolled_root_walk_scan import (
    EXEMPTIONS,
    PRIMITIVE,
    Exemption,
    Hit,
    exemption_for,
    scan_source,
    scan_tree,
    stale_exemptions,
    unexempted,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def hits() -> list[Hit]:
    return scan_tree(_REPO_ROOT)


def test_the_scan_covers_a_non_empty_corpus(hits: list[Hit]) -> None:
    assert hits, "the scanner found no ancestor walk at all — its own corpus is broken"
    assert any(hit.path == PRIMITIVE for hit in hits), (
        "the primitive's own walk must be in the census; a scan that misses it is not "
        "reading the file it is supposed to allow"
    )


def test_only_the_primitive_and_its_exemptions_hold_a_hand_rolled_walk(hits: list[Hit]) -> None:
    violations = unexempted(hits)

    assert violations == [], "hand-rolled ancestor walks must call kernel.ancestor_walk instead:\n" + "\n".join(
        hit.describe() for hit in violations
    )


def test_a_starred_parents_walk_is_reported() -> None:
    source = "def f(start):\n    for parent in [start, *start.parents]:\n        return parent\n"

    found = scan_source(source, "synthetic.py")

    assert len(found) == 1
    assert found[0].line == 2
    assert found[0].function == "f"


def test_a_tuple_parents_walk_is_reported() -> None:
    source = "def f(start):\n    for parent in (start, *start.parents):\n        return parent\n"

    assert len(scan_source(source, "synthetic.py")) == 1


def test_a_list_concat_parents_walk_is_reported() -> None:
    source = "def f(cwd):\n    for parent in [cwd] + list(cwd.parents):\n        return parent\n"

    found = scan_source(source, "synthetic.py")

    assert len(found) == 1
    assert found[0].function == "f"


def test_the_shared_primitive_walk_is_reported_too() -> None:
    # The primitive is *allowed* by the gate, but the scanner still sees it: that is the
    # positive control for the allow rule, not a hole in the scan.
    source = "def iter_ancestors(start):\n    for candidate in (start, *start.parents):\n        yield candidate\n"

    assert len(scan_source(source, PRIMITIVE)) == 1


def test_a_predicate_style_walk_is_not_reported() -> None:
    source = "def f(start):\n    return find_ancestor(start, lambda p: (p / '.git').is_dir())\n"

    assert scan_source(source, "synthetic.py") == []


def test_a_bare_parents_membership_check_is_not_reported() -> None:
    # Not a loop and not a walk: it classifies a path against a known ancestor.
    source = "def f(root, path):\n    return root == path or root in path.parents\n"

    assert scan_source(source, "synthetic.py") == []


def test_every_exemption_names_a_reason() -> None:
    assert EXEMPTIONS, "an empty exemption list would make this gate vacuous"
    for entry in EXEMPTIONS:
        assert isinstance(entry, Exemption)
        assert entry.reason.strip(), f"{entry.path}::{entry.function} has no reason"
        assert len(entry.reason) > 40, f"{entry.path}::{entry.function}'s reason is not a reason"


def test_every_exemption_still_matches_a_hit(hits: list[Hit]) -> None:
    stale = stale_exemptions(hits)

    assert stale == [], "remove these exemptions (the walk was migrated or deleted):\n" + "\n".join(
        f"{entry.path}::{entry.function}" for entry in stale
    )


def test_an_exemption_is_keyed_by_file_and_function() -> None:
    hit = Hit(path="src/some/module.py", line=10, function="walk", snippet="[p, *p.parents]")

    assert exemption_for(hit) is None
