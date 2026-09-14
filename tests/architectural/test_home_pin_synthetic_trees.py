"""T015 — the synthetic materialiser's correctness, proven WHERE THE PROOF ACTUALLY RUNS.

``pytest.ini`` sets ``testpaths = tests`` with **no ``python_files`` override**, so
``_home_pin_synthetic.py`` is **never collected** and assertions placed there would never run.
They live here.

What this module buys
---------------------
Every downstream transition in ``test_spec_kitty_home_pin_guard.py`` reads "the guard red on this
tree" as evidence about the **guard**. That reading is only sound if the tree really contains what
its builder claims. A builder that silently fails to write a file, or a source string that quietly
stops producing a member, would make a transition green **for the wrong reason** — DIR-041's
canonical failure. This module is the independent check: for each named tree, the classifier's
member sites and walked file set are compared against the **hand-enumerated** description authored
beside the source strings, so such a tree reds **here** instead of greening a transition there.

The counterpart guard (T015(4), FR-009)
----------------------------------------
``discover(Path("tests"))`` must find **no** member under any test-owned fixture root — the
property that makes "no synthetic tree is checked in" mechanical rather than a promise. It is a
population-0 claim, so it ships with a **positive control** over a materialised tree that plants a
member under exactly such a root: an over-narrow matcher returns ``set()``, greens forever, and
still greens the day someone checks a tree in.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.architectural import _home_pin_scan as scan
from tests.architectural import _home_pin_synthetic as synthetic

pytestmark = pytest.mark.architectural

#: The real walk root, exactly as the shipped guard roots it.
TESTS_ROOT = Path("tests")

#: Directory names that, under ``tests/``, hold test-owned fixture material rather than collected
#: test modules. A synthetic tree checked in would land under one of these — it is where such a
#: thing is naturally put, and where a reviewer would not look for a 41st member.
FIXTURE_ROOT_NAMES: frozenset[str] = frozenset(
    {"fixtures", "fixture", "_fixtures", "data", "testdata", "golden", "snapshots", "synthetic"}
)

#: The trees that are built to be scanned cleanly. The ``SyntaxError`` tree is deliberately absent
#: — it is built to RAISE, and SC-013 exercises it in the guard module.
CLEAN_TREE_BUILDERS: dict[str, Callable[[Path], synthetic.SyntheticTree]] = {
    "census_frozen": synthetic.census_frozen_tree,
    "extra_member_in_an_existing_file": synthetic.extra_member_in_an_existing_file,
    "extra_member_under_a_novel_name": synthetic.extra_member_under_a_novel_name,
    "owner_requesting_witness": synthetic.owner_requesting_witness_tree,
    "colliding_pair": synthetic.colliding_pair_tree,
    "outermost_versus_innermost": synthetic.outermost_versus_innermost_tree,
    "member_under_a_fixture_root": synthetic.member_under_a_fixture_root_tree,
}


def member_sites(root: Path) -> set[tuple[str, str]]:
    """``(relpath, innermost qualname)`` for every member the classifier finds under ``root``."""
    return {(member.relpath, member.key[1]) for member in scan.discover(root)}


def walked_relpaths(root: Path) -> set[str]:
    """Every ``.py`` the classifier's un-narrowed walk enumerates under ``root``."""
    return {path.relative_to(root).as_posix() for path in scan.enumerate_py_files(root)}


def members_under_a_fixture_root(root: Path) -> set[tuple[str, str]]:
    """The ONE matcher. Run over the real tree it must be empty; over the control, exactly one hit."""
    return {
        site
        for site in member_sites(root)
        if FIXTURE_ROOT_NAMES & set(Path(site[0]).parts)
    }


@pytest.mark.parametrize("name", sorted(CLEAN_TREE_BUILDERS))
def test_each_tree_contains_exactly_what_its_builder_claims(tmp_path: Path, name: str) -> None:
    """T015(3): ``discover(root)``'s member sites EQUAL the hand-enumerated set, per tree.

    Set equality, never a count (C-002; the golden-count ratchet, retired by #4315, held this same
    line at zero headroom). Equality rather than containment is the point: it catches a tree that
    grew a member as well as one that lost a file.
    """
    tree = CLEAN_TREE_BUILDERS[name](tmp_path / name)
    assert member_sites(tree.root) == set(tree.sites), (
        f"synthetic tree {name!r} does not contain what its builder claims. A tree that silently "
        f"fails to write a file must red HERE, not green a transition downstream."
    )


@pytest.mark.parametrize("name", sorted(CLEAN_TREE_BUILDERS))
def test_each_tree_wrote_every_file_it_claims(tmp_path: Path, name: str) -> None:
    """T015(3), the other half: a memberless file that fails to write is invisible to member sites.

    ``census_frozen`` deliberately carries two memberless modules for exactly this reason — without
    this assertion the tree could lose them and every member-level equality would still green.
    """
    tree = CLEAN_TREE_BUILDERS[name](tmp_path / name)
    assert walked_relpaths(tree.root) == set(tree.files)


def test_no_member_of_the_real_tree_lives_under_a_fixture_root() -> None:
    """T015(4) / FR-009: the counterpart guard. NOTHING synthetic is checked in under ``tests/``.

    A checked-in tree sits inside the classifier's never-narrowed walk, so its deliberate 41st
    members land in ``discovered`` and ``discovered == census u E`` could never green. Every cheap
    repair is barred — directory exclusion by C-003/NFR-001, a census row by C-007, a third ``E``
    entry by fixed arity — so this assertion is the whole defence.
    """
    planted = members_under_a_fixture_root(TESTS_ROOT)
    assert planted == set(), (
        f"member(s) found under a test-owned fixture root: {sorted(planted)}. Synthetic trees are "
        f"MATERIALISED into tmp_path, never checked in (FR-009)."
    )


def test_the_fixture_root_matcher_can_actually_see_a_planted_member(tmp_path: Path) -> None:
    """The POSITIVE CONTROL for the assertion above. Same matcher, a tree that DOES plant one.

    Without this, an over-narrow matcher returns ``set()`` and the population-0 claim above is its
    own proof — C-003 form (ii)'s named failure.
    """
    tree = synthetic.member_under_a_fixture_root_tree(tmp_path / "planted")
    assert members_under_a_fixture_root(tree.root) == {("fixtures/test_planted.py", "planted_home")}


def test_the_materialiser_ships_no_assignment_bound_pin_constant() -> None:
    """T015(7): the materialiser must not become SC-002b's first counterexample.

    A convenient ``ENV = "SPEC_KITTY_HOME"`` here would be an assignment-bound constant valued the
    pin, in ``tests/`` — the population SC-002b asserts is 0. The pin appears in this package only
    INSIDE larger source strings, where it is not the value of any binding.
    """
    own = Path(synthetic.__file__)
    bindings = scan.module_level_bindings(scan.parse_module(own))
    offenders = {
        name
        for name, value in bindings.items()
        if isinstance(value, ast.Constant) and value.value == scan.NEEDLE
    }
    assert offenders == set(), f"{own.name} binds {sorted(offenders)} to the pin — this reds SC-002b"


def test_the_materialiser_holds_no_assertions() -> None:
    """The materialiser is a file writer. An assertion there would never run (``testpaths = tests``).

    Asserted by AST through the seam's parser: ``ast.parse`` is banned in every module importing
    ``_home_pin_scan`` (WP02's anti-drift rule), including this one, so the tree comes from
    ``scan.parse_module``. ``ast.walk`` is not banned and the seam guard itself uses it.
    """
    tree = scan.parse_module(Path(synthetic.__file__))
    asserts = sorted(node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert))
    assert asserts == [], (
        f"_home_pin_synthetic.py holds assert statement(s) at {asserts}. It is NEVER COLLECTED, so "
        f"those never run — the proof belongs in this module."
    )
