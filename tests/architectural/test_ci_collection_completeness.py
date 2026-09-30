"""Guards retired from ``.github/workflows``'s CI-selection model (planning#57).

Formerly SC-013 / FR-013 / NFR-005: "nothing is uncollectable on a push to
``main``" (issue `#2957
<https://github.com/Priivacy-ai/spec-kitty/issues/2957>`_). That invariant was
evaluated against the real per-job selectors parsed out of the five live
``.github/workflows/*.yml`` files (:func:`tests.architectural._gate_coverage.
load_workflow_models`) under the worst reachable dorny filter state. Those
five files were the leftover pre-programme GitHub Actions YAML deleted by
planning#57 (PROGRAM.md §2: "All private. No GitHub Actions. No branch
protection... Nothing on GitHub enforces anything") — there is no longer a
CI-selection matrix on disk for this model to evaluate, so the SC-013/NFR-005
tests that depended on it (the collection-completeness oracle, the planted
NFR-005 violation checks, the push-disjunct self-mutation check, the
monotonicity proof, the WP01/splice checks, and the ratchet-baseline-freedom
check) were retired with it rather than left calling a helper that now raises
``FileNotFoundError`` — the same norm this module's own trap 1 below already
followed for ``drift-detector.yml``.

WHAT REMAINS is everything in this file that never read a workflow file off
disk in the first place:

* **Trap 1** — the orphan-baseline reach checker (``baseline_reaches`` and its
  AST helpers) is a pure source-level analysis with no live-repo dependency at
  all; it is exercised only against literal source snippets constructed
  in-line.
* **The activation model** (:func:`tests.architectural._gate_coverage.
  job_runs_under`, ``split_top_level``, ``normalize_condition``) is exercised
  here only against literal ``if:`` condition strings supplied by each test,
  never against a parsed workflow file. It stays load-bearing pure-unit
  coverage for that evaluator regardless of whether any workflow YAML exists.
"""

from __future__ import annotations

import ast

import pytest

from tests.architectural import _gate_coverage as gc

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_GATE_COVERAGE_MODULE = "_gate_coverage"


def test_restored_windows_suite_runs_on_push_without_filter_match_live() -> None:
    """A push to main runs the Windows suite even when no filter group matches."""
    active = gc.active_job_keys(
        gc.load_workflow_models(),
        event_name=gc.PUSH_EVENT,
        active_groups=frozenset(),
    )

    assert ("ci-windows.yml", "windows-critical") in active

# Every ``_gate_coverage`` surface that reads or writes a frozen baseline. The
# point of trap 1 is that this module reaches NONE of them.
_BASELINE_SURFACES = frozenset(
    {
        "BASELINE_PATH",
        "baseline_diff",
        "check",
        "freeze_baselines",
        "load_baseline",
        "load_baseline_nodeids",
        "update_baseline",
        "write_baseline_nodeids",
    },
)

# Opening a baseline by literal path would reach it without naming a surface at
# all, so the checker also watches path CONSTRUCTION (call arguments and ``/``
# operands) for these names.
_BASELINE_FILENAMES: tuple[str, ...] = (
    "_gate_coverage_baseline.json",
    "_baselines.yaml",
)


def _dotted(node: ast.expr) -> str | None:
    """``a.b.c`` for a pure ``Name``/``Attribute`` chain, else ``None``."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _names_the_module(dotted: str, aliases: frozenset[str]) -> bool:
    """Whether ``dotted`` denotes ``_gate_coverage`` — by alias or by full path."""
    return dotted in aliases or dotted.split(".")[-1] == _GATE_COVERAGE_MODULE


def _module_aliases(tree: ast.Module) -> frozenset[str]:
    """Every local name bound to ``_gate_coverage``, transitively.

    Covers the aliased from-import (``… import _gate_coverage as gc``), the
    aliased dotted import (``import pkg._gate_coverage as gate``) and plain
    re-bindings (``other = gc``), so renaming the import is not an escape.
    """
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == _GATE_COVERAGE_MODULE
            )
        elif isinstance(node, ast.Import):
            aliases.update(
                alias.asname
                for alias in node.names
                if alias.asname
                and alias.name.split(".")[-1] == _GATE_COVERAGE_MODULE
            )
    while True:
        grown = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            for target in node.targets
            if isinstance(target, ast.Name)
        } - aliases
        if not grown:
            break
        aliases |= grown
    return frozenset(aliases)


def _attribute_reach(node: ast.Attribute, aliases: frozenset[str]) -> set[str]:
    """``gc.load_baseline`` / ``pkg._gate_coverage.load_baseline``."""
    if node.attr not in _BASELINE_SURFACES:
        return set()
    dotted = _dotted(node)
    if dotted is None:
        return set()
    prefix = dotted.rpartition(".")[0]
    return {f"attribute {dotted}"} if _names_the_module(prefix, aliases) else set()


def _import_reach(node: ast.ImportFrom) -> set[str]:
    """``from tests.architectural._gate_coverage import load_baseline``."""
    if (node.module or "").split(".")[-1] != _GATE_COVERAGE_MODULE:
        return set()
    return {
        f"import {alias.name}"
        for alias in node.names
        if alias.name in _BASELINE_SURFACES
    }


def _getattr_reach(node: ast.Call, aliases: frozenset[str]) -> set[str]:
    """``getattr(gc, "load_baseline")`` — the string-indirection escape.

    Only the ``getattr`` BUILTIN counts: the behavioural half of trap 1
    legitimately calls ``monkeypatch.setattr(gc, "load_baseline", …)`` to sabotage
    the reader, and sabotaging it is the opposite of reaching it.
    """
    getattr_arity = 2
    if not (isinstance(node.func, ast.Name) and node.func.id == "getattr"):
        return set()
    if len(node.args) < getattr_arity:
        return set()
    dotted = _dotted(node.args[0])
    name = node.args[1]
    if dotted is None or not _names_the_module(dotted, aliases):
        return set()
    if isinstance(name, ast.Constant) and name.value in _BASELINE_SURFACES:
        return {f"getattr {name.value}"}
    return set()


def _path_literal_reach(node: ast.AST) -> set[str]:
    """A baseline filename used to BUILD a path: a call argument or a ``/`` operand.

    Deliberately narrower than "any string containing the name": this module's
    prose NAMES the baseline it refuses to touch, and so does
    :data:`_BASELINE_FILENAMES` itself. Both are inert text; ``Path("…json")``
    and ``root / "…json"`` are not.
    """
    if isinstance(node, ast.Call):
        # Keyword arguments are call arguments too. Reading only ``node.args``
        # let ``open(file="…_baseline.json")`` escape BOTH halves of the proof:
        # the static reader missed it, and the behavioural half cannot see it
        # either because it never goes through the module whose attributes that
        # half sabotages. Review found this; it is the one escape that defeated
        # the backstop as well as the reader.
        operands: list[ast.expr] = [*node.args, *(kw.value for kw in node.keywords)]
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        operands = [node.left, node.right]
    else:
        return set()
    return {
        f"literal path {name}"
        for operand in operands
        for text in _string_parts(operand)
        for name in _BASELINE_FILENAMES
        if name in text
    }


def _string_parts(node: ast.expr) -> list[str]:
    """Static string content of *node*: a plain literal or an f-string's fixed parts.

    ``Path(f"{root}/_gate_coverage_baseline.json")`` is a ``JoinedStr``, not a
    ``Constant``, so reading only ``Constant`` let it slip past. The interpolated
    slots are unknowable statically; the literal segments around them are not,
    and the filename lives in one of those.
    """
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else []
    if isinstance(node, ast.JoinedStr):
        return [
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ]
    return []


def baseline_reaches(source: str) -> set[str]:
    """Every way ``source`` could reach the orphan ratchet's baseline machinery.

    An AST read (not a substring scan) so a module's prose may NAME the surfaces
    it refuses to touch — explaining the refusal is the point — while four real
    access shapes still trip it: attribute access through any name bound to the
    module, ``from … import`` of a baseline symbol, ``getattr`` with a string
    constant, and path construction from a baseline filename.

    Residual, stated rather than papered over: a name assembled at runtime
    (``"load_" + "baseline"``), a filename bound to a variable before reaching
    ``Path``, ``importlib.import_module``, ``__import__``, ``sys.modules[…]``, a
    module returned from a function, and tuple-unpack or walrus alias binding
    (``a, b = gc, None``; ``(alias := gc)``) are outside this source checker.
    The load-bearing companion assertion is structural: the removed orphan
    baseline APIs and sidecar must not exist on the live model at all.
    """
    tree = ast.parse(source)
    aliases = _module_aliases(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found |= _attribute_reach(node, aliases)
        elif isinstance(node, ast.ImportFrom):
            found |= _import_reach(node)
        elif isinstance(node, ast.Call):
            found |= _getattr_reach(node, aliases) | _path_literal_reach(node)
        elif isinstance(node, ast.BinOp):
            found |= _path_literal_reach(node)
    return found


# ---------------------------------------------------------------------------
# Trap 1 — the gate must not be able to launder its findings into a baseline.
# ---------------------------------------------------------------------------


# Source shapes that all reach the same baseline reader. The first version of
# this guard caught only the first of them, which is the failure mode this
# mission exists to eliminate: a guard that LOOKS airtight and is not. Each
# entry is a self-mutation of the module under test, expressed as source.
_BASELINE_ESCAPES: dict[str, str] = {
    "aliased attribute": (
        "from tests.architectural import _gate_coverage as gc\n"
        "gc.load_baseline()\n"
    ),
    "getattr indirection": (
        "from tests.architectural import _gate_coverage as gc\n"
        "getattr(gc, 'load_baseline')()\n"
    ),
    "direct symbol import": (
        "from tests.architectural._gate_coverage import load_baseline\n"
        "load_baseline()\n"
    ),
    "renamed module import": (
        "import tests.architectural._gate_coverage as gate\n"
        "gate.load_baseline()\n"
    ),
    "fully dotted access": (
        "import tests.architectural._gate_coverage\n"
        "tests.architectural._gate_coverage.load_baseline()\n"
    ),
    "rebound alias": (
        "from tests.architectural import _gate_coverage as gc\n"
        "sneaky = gc\n"
        "sneaky.update_baseline()\n"
    ),
    "literal baseline path": (
        "from pathlib import Path\n"
        "Path('tests/architectural/_gate_coverage_baseline.json').read_text()\n"
    ),
    "literal path by joining": (
        "from pathlib import Path\n"
        "data = Path('tests/architectural') / '_gate_coverage_baseline.json'\n"
    ),
    # The two below defeated BOTH halves of trap 1 until review found them: the
    # static reader missed them, and the behavioural half never sees them because
    # they bypass the module whose attributes it sabotages.
    "literal path as a keyword argument": (
        "open(file='tests/architectural/_gate_coverage_baseline.json').read()\n"
    ),
    "literal path inside an f-string": (
        "from pathlib import Path\n"
        "root = 'tests/architectural'\n"
        "data = Path(f'{root}/_gate_coverage_baseline.json').read_text()\n"
    ),
}

# Prose may name every surface it refuses to touch — that is the whole point of
# reading the AST instead of grepping.
_BASELINE_PROSE_ONLY = (
    '"""Refuses to call load_baseline or read _gate_coverage_baseline.json."""\n'
    "from tests.architectural import _gate_coverage as gc\n"
    "gc.collect_universe()\n"
)


@pytest.mark.parametrize(
    ("shape", "source"),
    sorted(_BASELINE_ESCAPES.items()),
)
def test_the_baseline_reach_checker_catches_every_known_escape(
    shape: str, source: str,
) -> None:
    """NFR-005 applied to the checker itself: each escape must be reported."""
    assert baseline_reaches(source), (
        f"the baseline-reach checker misses the {shape!r} escape, so trap 1 "
        "could be walked around by rewriting one import line"
    )


def test_the_baseline_reach_checker_does_not_fire_on_prose() -> None:
    """Naming the forbidden surfaces in a docstring is not reaching them."""
    assert not baseline_reaches(_BASELINE_PROSE_ONLY)


# ---------------------------------------------------------------------------
# The activation model itself (pure units — no collection, no subprocess).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (None, True),
        (True, True),
        (False, False),
        ("always()", True),
        ("always() && needs.changes.outputs.cli == 'true'", False),
        ("always() && needs.changes.outputs.core_misc == 'true'", False),
        (
            "always() && (needs.changes.outputs.cli == 'true' "
            "|| github.event_name == 'push')",
            True,
        ),
        ("always() && github.event_name == 'push'", True),
        ("always() && github.event_name == 'pull_request'", False),
        ("always() && github.event_name != 'pull_request'", True),
        ("needs.fast-tests-cli.result == 'success'", True),
        ("needs.kernel-tests.result != 'failure'", True),
        (
            "${{ (always()) && "
            "!contains(github.event.pull_request.labels.*.name, 'pr:deferred') }}",
            True,
        ),
        ("some.unmodelled.expression == 'true'", False),
    ],
)
def test_job_runs_under_push_with_no_group_active(
    condition: str | bool | None,
    expected: bool,
) -> None:
    """The activation truth table, including the fail-closed unknown-term case."""
    assert (
        gc.job_runs_under(
            condition, event_name=gc.PUSH_EVENT, active_groups=frozenset(),
        )
        is expected
    )


def test_job_runs_under_honours_an_active_group() -> None:
    """A group-gated job runs once its group is active — the monotonicity premise."""
    condition = "always() && needs.changes.outputs.cli == 'true'"
    assert not gc.job_runs_under(
        condition, event_name=gc.PUSH_EVENT, active_groups=frozenset(),
    )
    assert gc.job_runs_under(
        condition, event_name=gc.PUSH_EVENT, active_groups=frozenset({"cli"}),
    )


def test_fork_guard_holds_on_the_core_repository() -> None:
    """The fork guard is modelled for upstream ``main``: a push still runs the job."""
    guard = (
        "(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request'"
        " || github.event_name == 'workflow_dispatch') && needs.changes.outputs.cli == 'true'"
    )
    assert gc.job_runs_under(guard, event_name=gc.PUSH_EVENT, active_groups=frozenset({"cli"}))
    assert not gc.job_runs_under(guard, event_name=gc.PUSH_EVENT, active_groups=frozenset())
    assert not gc.job_runs_under(
        "github.repository == 'someone/spec-kitty'", event_name=gc.PUSH_EVENT, active_groups=frozenset(),
    )


def test_label_guard_blocks_only_pull_requests() -> None:
    """``!contains(labels...)`` is vacuously true when there is no pull request."""
    guard = "!contains(github.event.pull_request.labels.*.name, 'pr:skip-ci')"
    assert gc.job_runs_under(guard, event_name=gc.PUSH_EVENT, active_groups=frozenset())
    assert not gc.job_runs_under(
        guard, event_name=gc.PULL_REQUEST_EVENT, active_groups=frozenset(),
    )


@pytest.mark.parametrize(
    ("expr", "operator", "expected"),
    [
        ("a && b", "&&", ["a", "b"]),
        ("a && (b && c)", "&&", ["a", "(b && c)"]),
        ("a || b || c", "||", ["a", "b", "c"]),
        ("(a || b) && c", "||", ["(a || b) && c"]),
        ("", "&&", []),
    ],
)
def test_split_top_level_respects_parentheses(
    expr: str, operator: str, expected: list[str],
) -> None:
    assert gc.split_top_level(expr, operator) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("${{ always() }}", "always()"),
        ("((always()))", "always()"),
        ("always()\n  && github.event_name == 'push'", "always() && github.event_name == 'push'"),
        ("(a) && (b)", "(a) && (b)"),
    ],
)
def test_normalize_condition(raw: str, expected: str) -> None:
    assert gc.normalize_condition(raw) == expected
