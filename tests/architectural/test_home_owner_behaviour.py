"""The canonical owner's statics, its contract binding, and the one limb that proves it works.

WP03/T012 (R1a). Binding contract:
``kitty-specs/isolated-home-pin-guard-r1a-01KZNMA3/contracts/canonical-home-owner.md``.

**SC-011 green is not evidence the owner works, and this module is written around that.**
C-014 limbs (i) and (ii) are properties of *pytest's fixture machinery*, not of the owner's body:
an owner whose body is ``return None`` with no ``setenv`` and no ``mkdir`` satisfies both, and so
does every AST assertion below. **SC-012 limb 1** — :func:`test_owner_pins_the_env_and_creates_the
_directory_before_the_body_runs` — carries the entire behavioural load alone, and it is the only
test here that can fail on an inert owner. It computes its expected value **from its own
``tmp_path``** and never from the fixture's return, which is why FR-005 pins the owner to ``None``.

``pytest.raises(Exception)`` does NOT catch ``ScopeMismatch``
-------------------------------------------------------------
pytest converts ``ScopeMismatch`` into ``Failed``, whose MRO is
``(Failed, OutcomeException, BaseException, object)`` — **``Exception`` is not in it**. A
``pytest.raises(Exception)`` therefore does not catch it and the exception escapes as a setup
**ERROR**, which costs an implementer an hour. That is not left as prose here:
:func:`test_the_scope_mismatch_route_is_not_reachable_through_the_exception_hierarchy` asserts the
subclass relation mechanically, so the day pytest changes it this module reds instead of quietly
catching nothing.

``pytester`` is deliberately not used
--------------------------------------
Measured: **zero** uses under ``tests/``, it is not auto-loaded, and there is **no root
``conftest.py``** — enabling it needs a rootdir conftest or an ``addopts`` change, **both outside
C-006's blast radius**. The in-scope route is a module-scoped fixture calling
``request.getfixturevalue(<owner>)``.

No ``ast.parse`` and no ``NodeVisitor``
----------------------------------------
This module imports ``_home_pin_scan``, so WP02's seam guard polices it. Every parse routes through
:func:`_home_pin_scan.parse_module`.

This module writes **no** ``SPEC_KITTY_HOME`` pin of its own and is therefore **not** a member of
the behaviour class — it costs neither of ``E``'s two irrevocable slots. The one real-tree probe
that *is* a member lives in ``test_home_owner_never_wins.py``.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural import _home_pin_scan as scan

pytestmark = pytest.mark.architectural

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
CONFTEST_PATH = TESTS_ROOT / "conftest.py"
CONFTEST_RELPATH = "conftest.py"
CONTRACT_PATH = (
    REPO_ROOT
    / "kitty-specs"
    / "isolated-home-pin-guard-r1a-01KZNMA3"
    / "contracts"
    / "canonical-home-owner.md"
)

#: FR-005's placement floor. The owner is added **strictly after** this line; line 298 is the
#: ``return home_base`` of ``_isolated_worker_home``.
PLACEMENT_FLOOR = 298

#: The definition-ordering anchors either side of the owner's insertion point. Asserted by NAME so
#: the check survives every benign edit that moves the lines, and reds on a reorder — which a
#: scalar definition index cannot see (SC-010).
ANCHOR_BEFORE = "_isolated_worker_home"
ANCHOR_AFTER = "_enable_saas_sync_feature_flag"

#: ``tests/conftest.py``'s ordered definition names **at the merge base**,
#: ``9117219081c1f88cf0b90937b9cb46723ceebcd2`` (``git merge-base HEAD
#: feat/isolated-home-pin-guard``), where ``git diff --stat <merge-base> HEAD -- tests/conftest.py``
#: was **empty** — the file was byte-identical to the base when this list was taken.
#:
#: **Frozen here rather than recomputed from git at test time, deliberately.** T010's own DoD
#: records that *"the ancestry itself does not survive the squash or rebase a lane consolidation may
#: perform"*; an SC-010 limb that shells out to ``git show <merge-base>:tests/conftest.py`` would go
#: unrunnable in exactly the situation T010 anticipates, and would put a git surface inside a module
#: collected under NFR-001's six-second import budget. Regenerate (only alongside a reviewed,
#: intentional conftest change) with::
#:
#:     python - <<'PY'
#:     import ast, pathlib
#:     tree = ast.parse(pathlib.Path("tests/conftest.py").read_text(encoding="utf-8"))
#:     for _, _, name in sorted(
#:         (n.lineno, n.col_offset, n.name) for n in ast.walk(tree)
#:         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
#:     ):
#:         print(name)
#:     PY
MERGE_BASE_DEFINITION_NAMES: tuple[str, ...] = (
    "_worker_id",
    "_worker_home_base",
    "_apply_home_env",
    "_BootstrapLease",
    "to_json",
    "with_state",
    "pytest_addoption",
    "pytest_configure",
    "pytest_collection_modifyitems",
    "_fail_on_wall_clock_assertions",
    "_isolated_worker_home",
    "_enable_saas_sync_feature_flag",
    "_isolate_global_encoding_provenance",
    "_isolated_route",
    "_plain_cli_console_seam",
    "reset_spec_kitty_queue_state",
    "_truncate_db",
    "clean_spec_kitty_queue",
    "_neutralize_worktree_detection",
    "_always_main_repo",
    "_venv_python",
    "_venv_pip",
    "_venv_has_required_runtime",
    "_venv_is_valid",
    "_test_venv_environment_hash",
    "_process_start_token",
    "_read_bootstrap_lease",
    "_write_bootstrap_lease",
    "_lease_is_live_and_fresh",
    "_expected_temp_path",
    "_remove_path_without_following_symlinks",
    "_remove_recorded_temp",
    "_lease_owned_by",
    "_heartbeat_bootstrap_lease",
    "_claim_bootstrap_lease",
    "_publish_bootstrap_lease",
    "_cleanup_failed_bootstrap",
    "_ensure_test_venv",
    "_venv_site_packages",
    "_seed_offline_test_venv",
    "_create_test_venv",
    "test_venv",
    "_build_tool_available",
    "build_artifacts",
    "installed_wheel_venv",
    "isolated_env",
    "run_cli",
    "_run_cli",
    "temp_repo",
    "feature_repo",
    "mission_slug",
    "merge_repo",
    "mock_worktree",
    "mock_main_repo",
    "conflicting_wps_repo",
    "git_stale_workspace",
    "dirty_worktree_repo",
    "test_project",
    "clean_project",
    "dirty_project",
    "project_with_worktree",
    "dual_branch_repo",
    "seed_to_planned",
    "_is_reaper_controller",
    "_reaper_mission_dir_names",
    "_reaper_branch_names",
    "_reaper_worktree_dir_names",
    "_registered_worktree_paths",
    "_test_homes_root",
    "_xdist_testrunuid",
    "_current_run_test_home_dirs",
    "_prompt_tmp_entry_names",
    "ReaperSnapshot",
    "ReapResult",
    "is_empty",
    "capture_reaper_snapshot",
    "reap_session_delta",
    "sweep_tmp_residue",
    "reap_test_home_dirs",
    "assert_no_leaked_test_residue",
    "_register_test_home_atexit_reaper",
    "_reap_test_homes_at_exit",
    "_finalize_test_home_atexit_targets",
    "pytest_sessionstart",
    "pytest_sessionfinish",
)


# ---------------------------------------------------------------------------
# The contract binding — the document is parsed, never merely cited
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OwnerContract:
    """What ``contracts/canonical-home-owner.md`` declares, read out of the document itself."""

    name: str
    autouse: str
    scope: str


_NAME_ROW = re.compile(r"^\|\s*\*\*Fixture name\*\*\s*\|\s*`([A-Za-z_][A-Za-z0-9_]*)`\s*\|")
_AUTOUSE_ROW = re.compile(r"^\|\s*`autouse`\s*\|\s*([^|]+?)\s*\|")
_SCOPE_ROW = re.compile(r"^\|\s*Scope\s*\|\s*([^|]+?)\s*\|")


def _cell(text: str) -> str:
    """A table cell stripped of the markdown emphasis and code fencing it carries."""
    return text.replace("*", "").replace("`", "").strip()


def read_owner_contract(path: Path) -> OwnerContract:
    """Parse the declared name, autouse stance and scope out of the binding contract.

    **The binding is mechanical, not adjacency.** An unbound contract drifts on the first rename,
    which is the failure this function exists to make impossible: every property asserted of the
    conftest fixture below is asserted against *this* return value, never against a literal
    repeated in the test.
    """
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        for field, pattern in (
            ("name", _NAME_ROW),
            ("autouse", _AUTOUSE_ROW),
            ("scope", _SCOPE_ROW),
        ):
            match = pattern.match(line)
            if match is not None and field not in found:
                found[field] = _cell(match.group(1))
    missing = {"name", "autouse", "scope"} - set(found)
    if missing:
        raise AssertionError(
            f"{path} does not declare {sorted(missing)} in the parseable table form this "
            "binding depends on — the contract has drifted out of machine reach"
        )
    return OwnerContract(name=found["name"], autouse=found["autouse"], scope=found["scope"])


CONTRACT = read_owner_contract(CONTRACT_PATH)
OWNER_NAME = CONTRACT.name


# ---------------------------------------------------------------------------
# AST helpers — every parse routes through the seam
# ---------------------------------------------------------------------------

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
_DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def definition_names(tree: ast.Module) -> tuple[str, ...]:
    """Every ``def`` / ``async def`` / ``class`` name in the module, in **source order**.

    The whole module, not only the names preceding the anchor: the narrower form cannot see a
    reorder *below* the anchor, and conftest fixture resolution depends on the ordering throughout.
    """
    return tuple(
        node.name
        for _, _, node in sorted(
            (node.lineno, node.col_offset, node)
            for node in ast.walk(tree)
            if isinstance(node, _DEFINITION_NODES)
        )
    )


def owner_node(tree: ast.Module, name: str) -> FunctionNode:
    """The single ``def`` named ``name``. Raises if it is absent or declared more than once."""
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if [node.name for node in matches] != [name]:
        raise AssertionError(
            f"expected exactly one definition named {name!r} in {CONFTEST_RELPATH}, found "
            f"{[node.lineno for node in matches]}"
        )
    return matches[0]


def _fixture_decorators(node: FunctionNode) -> list[ast.expr]:
    return [
        decorator
        for decorator in node.decorator_list
        if _decorator_name(decorator) == "fixture"
    ]


def _decorator_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else None


def _decorator_keywords(node: FunctionNode) -> dict[str, ast.expr]:
    return {
        keyword.arg: keyword.value
        for decorator in _fixture_decorators(node)
        if isinstance(decorator, ast.Call)
        for keyword in decorator.keywords
        if keyword.arg is not None
    }


def _called_attributes(node: ast.AST) -> set[str]:
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
    }


@pytest.fixture(scope="module")
def conftest_tree() -> ast.Module:
    """``tests/conftest.py``, parsed once through the seam.

    Module-scoped and **pin-free**: this module writes no ``SPEC_KITTY_HOME``, so
    ``_home_pin_scan``'s ``SCOPE-EXPLICIT`` inert sub-form (pin-bearing fixtures carrying an
    explicit ``scope=``) is not touched by this declaration.
    """
    return scan.parse_module(CONFTEST_PATH)


# ---------------------------------------------------------------------------
# T012(5)-(6) — the contract binding, and the assertion that closes FR-010
# ---------------------------------------------------------------------------


def test_the_conftest_fixture_carries_the_name_the_contract_declares(
    conftest_tree: ast.Module,
) -> None:
    """T012(5): the document is PARSED, so it cannot drift from the code on a rename."""
    assert OWNER_NAME in definition_names(conftest_tree), (
        f"{CONTRACT_PATH.name} declares the owner as {OWNER_NAME!r}, and no definition of that "
        f"name exists in {CONFTEST_RELPATH}"
    )


def test_the_contract_declares_the_stance_the_conftest_fixture_carries(
    conftest_tree: ast.Module,
) -> None:
    """The document's `autouse` / scope cells and the fixture's decorator must agree."""
    assert CONTRACT.autouse == "False"
    assert CONTRACT.scope == "function"
    keywords = _decorator_keywords(owner_node(conftest_tree, OWNER_NAME))
    assert "scope" not in keywords, (
        "function scope is fixed by the ABSENCE of `scope=`; an explicit `scope=` on a "
        "pin-bearing fixture is registered inert as SCOPE-EXPLICIT and would falsify a "
        "population-0 assertion in the module that ships it"
    )
    autouse = keywords.get("autouse")
    assert autouse is None or (isinstance(autouse, ast.Constant) and autouse.value is False)


def test_the_declared_owner_name_is_a_member_of_owner_param_names() -> None:
    """**The assertion that closes FR-010's circularity, and the reason this WP exists at T012.**

    ``_home_pin_scan.OWNER_PARAM_NAMES`` ships ``canonical_home`` taken from FR-010's PROSE, at a
    moment when the contract naming the owner did not yet exist — its own docstring records the
    entry as *provisional and unbound* and names this subtask as the closing obligation. Measured
    in WP01's review: removing or renaming ``canonical_home`` reds only WP01's own fixture tree
    (the author's string on both sides of the equality), and ``runtime_home`` can be deleted
    outright with the suite green.

    **Without this assertion, naming the owner anything else leaves FR-010's limb PERMANENTLY
    INERT with every WP01 assertion still green**, and the shrink-only ratchet then greens on
    every disappearance — the failure FR-010 exists to prevent (*"the guard goes blind in
    proportion to R1b's adoption"*). The operand is outside this author's control: it is WP01's
    frozenset, which this WP may not edit.
    """
    assert OWNER_NAME in scan.OWNER_PARAM_NAMES, (
        f"the contract declares the owner {OWNER_NAME!r}, which is NOT in "
        f"OWNER_PARAM_NAMES={sorted(scan.OWNER_PARAM_NAMES)}. FR-010's resolver limb would be "
        "permanently inert and every WP01 assertion would still be green. `_home_pin_scan.py` is "
        "lane-a's write scope — rename the owner to a member of that set, never widen the set here"
    )


def test_the_owner_alias_limb_actually_fires_on_the_owner_name() -> None:
    """Membership in the frozenset is not the same claim as the RESOLVER honouring it.

    A future edit could keep ``canonical_home`` in ``OWNER_PARAM_NAMES`` while ``normalise_params``
    stopped consulting the set. This constructs the effect instead of reading it: a parameter set
    naming only the owner and ``monkeypatch`` must satisfy the silhouette after normalisation.
    """
    normalised = scan.normalise_params(frozenset({OWNER_NAME, "monkeypatch"}))
    assert normalised >= scan.SILHOUETTE
    # Positive control: a name NOT in the set must not normalise to `tmp_path`, or the check above
    # would pass for a `normalise_params` that maps everything.
    assert not scan.normalise_params(frozenset({"unrelated_home", "monkeypatch"})) >= scan.SILHOUETTE


# ---------------------------------------------------------------------------
# T012(4) — SC-005's owner limbs and SC-010, AST-asserted. ALL of it is SHAPE.
# ---------------------------------------------------------------------------


def test_owner_is_non_autouse_function_scoped_and_returns_none(
    conftest_tree: ast.Module,
) -> None:
    """SC-005's shape limbs. **None of this is evidence the owner does anything.**"""
    node = owner_node(conftest_tree, OWNER_NAME)
    assert _fixture_decorators(node), f"{OWNER_NAME} is not decorated as a pytest fixture"
    keywords = _decorator_keywords(node)
    assert "scope" not in keywords
    assert keywords.get("autouse") is None or (
        isinstance(keywords["autouse"], ast.Constant) and keywords["autouse"].value is False
    )
    returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
    yields = [
        child for child in ast.walk(node) if isinstance(child, (ast.Yield, ast.YieldFrom))
    ]
    assert [child for child in returns if child.value is not None] == []
    assert yields == [], (
        "the owner yields nothing: FR-005 pins the fixture value to None so a probe cannot "
        "compare the environment against the fixture's own report"
    )


def test_owner_establishes_by_setenv_only_and_creates_the_directory(
    conftest_tree: ast.Module,
) -> None:
    """FR-006's STATIC half — and it is only half; SC-012 carries the behavioural one."""
    node = owner_node(conftest_tree, OWNER_NAME)
    end = node.end_lineno or node.lineno
    forms = {
        site.form
        for site in scan.find_write_sites(conftest_tree, key=scan.NEEDLE)
        if node.lineno <= site.lineno <= end
    }
    assert forms == {"setenv"}, (
        f"the owner must establish the home through `monkeypatch.setenv` and nothing else; "
        f"found write forms {sorted(forms)}"
    )
    called = _called_attributes(node)
    assert "setattr" not in called, (
        "no `monkeypatch.setattr(Path, 'home', ...)` and no process-global patch — C-005 binds "
        "`tests/conftest.py:272-286`'s env-var-only decision unchanged, and the `setattr` form is "
        "what silently won over ~16 `tests/sync` cases"
    )
    assert "mkdir" in called, "the owner creates the home directory before the test body runs"


def test_owner_is_added_strictly_after_the_placement_floor(conftest_tree: ast.Module) -> None:
    """FR-005/SC-005's placement. **This limb alone leaves the real risk untouched** — see below."""
    assert owner_node(conftest_tree, OWNER_NAME).lineno > PLACEMENT_FLOOR


def test_conftest_definition_order_is_unchanged_with_the_owner_removed(
    conftest_tree: ast.Module,
) -> None:
    """SC-010 / NFR-005 — **one known addition, then exact equality, over the whole module.**

    Never a scalar definition INDEX: a scalar is invariant under
    insert-one-above-plus-delete-one-above, and in a Mission governed by C-002 it was the last
    surviving scalar comparand. Never "unchanged" outright either — FR-005 requires this very WP
    to add the owner to this very file, so that reading is unsatisfiable. The satisfiable and
    strictly stronger form is: remove exactly one known name, then demand equality of the ORDERED
    list, ordering on **both** sides of the anchor.

    This is the only limb that sees an insertion *above* line 253, which would shift
    ``_isolated_worker_home`` down and change conftest fixture ordering **while the old line range
    shows no modification** — so the diff-shaped criterion above is satisfiable with its risk
    untouched.
    """
    names = definition_names(conftest_tree)
    assert [name for name in names if name == OWNER_NAME] == [OWNER_NAME]
    assert set(names) - set(MERGE_BASE_DEFINITION_NAMES) == {OWNER_NAME}, (
        "exactly ONE known addition is carved out — the owner FR-005 mandates. Any other new "
        "definition in tests/conftest.py is outside C-001's single permitted edit"
    )
    assert tuple(name for name in names if name != OWNER_NAME) == MERGE_BASE_DEFINITION_NAMES


def test_the_owner_sits_between_its_named_ordering_anchors(conftest_tree: ast.Module) -> None:
    """NFR-005's *"must not reorder relative to ``_isolated_worker_home``"*, anchored by NAME.

    Independent of the frozen merge-base list above: this limb holds even if that list is
    regenerated, and it names the two definitions the insertion point sits between rather than a
    position that a benign edit elsewhere would move.
    """
    names = definition_names(conftest_tree)
    index = names.index(OWNER_NAME)
    assert (names[index - 1], names[index + 1]) == (ANCHOR_BEFORE, ANCHOR_AFTER)


def test_the_owner_is_a_member_of_the_behaviour_class_the_guard_walks() -> None:
    """FR-005: the owner is **itself a class member**, which is why ``E`` exists at all.

    Asserted through the production classifier rather than by reading the body: ``discover()``
    must attribute a ``fixture``-kind member inside the owner's line range whose value resolves to
    ``<tmp_path>/home``. An owner that pinned something else, or nothing, is not here.
    """
    tree = scan.parse_module(CONFTEST_PATH)
    node = owner_node(tree, OWNER_NAME)
    end = node.end_lineno or node.lineno
    inside = {
        member
        for member in scan.discover(TESTS_ROOT)
        if member.relpath == CONFTEST_RELPATH and node.lineno <= member.lineno <= end
    }
    assert {(member.kind, member.resolved_value) for member in inside} == {
        ("fixture", scan.TMP_PATH_HOME)
    }


# ---------------------------------------------------------------------------
# T012(1) — SC-012 limb 1. THE ONLY TEST IN THIS MODULE THAT CAN FAIL ON AN
# INERT OWNER.
# ---------------------------------------------------------------------------


def test_owner_pins_the_env_and_creates_the_directory_before_the_body_runs(
    canonical_home: None,
    tmp_path: Path,
) -> None:
    """**SC-012 limb 1 — the entire behavioural load of SC-011/SC-012 limb 1 sits here.**

    The expected value is **computed in this body from this test's own ``tmp_path``**, never read
    from the fixture's return. That is what FR-005's ``return None`` buys: the tempting
    ``assert os.environ[NEEDLE] == canonical_home`` compares the environment against the fixture's
    **own report** and passes for an owner whose body is ``return None``.

    ``is_dir()`` is asserted **at body entry**, so a fixture that sets the variable without
    creating the directory reds here.
    """
    assert canonical_home is None, (
        "the owner must yield None (FR-005); a fixture returning its own path re-opens the "
        "circular comparison SC-012 exists to exclude"
    )
    expected = str(tmp_path / "home")
    assert os.environ[scan.NEEDLE] == expected
    assert Path(os.environ[scan.NEEDLE]).is_dir()


# ---------------------------------------------------------------------------
# T012(2) — C-014 limb (i): ScopeMismatch, loud at SETUP
# ---------------------------------------------------------------------------


def test_the_scope_mismatch_route_is_not_reachable_through_the_exception_hierarchy() -> None:
    """The hour-costing fact, asserted rather than written in a comment.

    pytest converts ``ScopeMismatch`` into ``Failed``. ``Failed`` derives from
    ``OutcomeException`` derives from ``BaseException`` — **``Exception`` is not in the MRO**, so
    ``pytest.raises(Exception)`` does not catch it and the exception escapes the fixture as a setup
    ERROR rather than a caught failure. If pytest ever changes this, the module reds here instead
    of silently catching nothing below.
    """
    assert issubclass(pytest.fail.Exception, BaseException)
    assert not issubclass(pytest.fail.Exception, Exception)


@pytest.fixture(scope="module")
def scope_inversion(request: pytest.FixtureRequest) -> str:
    """A **module-scoped** request for the **function-scoped** owner. C-014 limb (i).

    ``pytester`` is not the route: zero uses under ``tests/``, not auto-loaded, and no root
    ``conftest.py`` — enabling it needs a rootdir conftest or an ``addopts`` change, both outside
    C-006's blast radius. ``request.getfixturevalue`` reaches the same machinery in scope.
    """
    with pytest.raises(pytest.fail.Exception) as excinfo:
        request.getfixturevalue(OWNER_NAME)
    return str(excinfo.value)


def test_a_higher_scoped_request_for_the_owner_raises_scope_mismatch(
    scope_inversion: str,
) -> None:
    """SC-011 / C-014 limb (i). **A property of pytest's fixture machinery, not of the body.**

    An owner whose body is ``return None`` passes this. It is here because SC-011 binds it
    normatively, not because it is evidence.
    """
    assert "ScopeMismatch" in scope_inversion
    assert OWNER_NAME in scope_inversion


# ---------------------------------------------------------------------------
# T012(3) — C-014 limb (ii): non-instantiation, observed as the ABSENCE OF THE
# EFFECT and never by reading source
# ---------------------------------------------------------------------------


def test_a_test_not_naming_the_owner_never_sees_the_owners_effect(tmp_path: Path) -> None:
    """C-014 limb (ii), asserted by observing the absence of the EFFECT.

    Its **positive control is its sibling**
    :func:`test_owner_pins_the_env_and_creates_the_directory_before_the_body_runs`, in this same
    module and this same process: that test requests the owner and observes
    ``str(tmp_path / "home")``; this one does not request it and must not. Make the owner
    ``autouse=True`` and this test reds while that one stays green — which is the pair, and the
    reason this limb is not written as "grep the source for autouse".

    ``tmp_path`` is unique per test, so an ambient ``SPEC_KITTY_HOME`` inherited from the operator's
    environment can never coincide with the value asserted absent.
    """
    would_be = str(tmp_path / "home")
    assert os.environ.get(scan.NEEDLE) != would_be
    assert not (tmp_path / "home").exists()
