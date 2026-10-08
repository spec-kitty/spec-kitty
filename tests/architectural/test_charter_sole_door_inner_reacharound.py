"""Gate 5 (FR-007/FR-010, WP04): zero-tolerance `._inner` reach-around on
``charter.activation.resolver.ActiveCharterService`` outside ``src/charter/**`` (and
``tests/charter/**``).

A post-plan squad delegate found that ``src/specify_cli/invocation/registry.py``
and ``src/specify_cli/invocation/org_profiles.py`` both read
``service._inner.agent_profiles`` directly -- reaching straight past the
wrapper's own charter-activation filtering to the raw, unfiltered
``AgentProfileRepository``. Left open, this defeats every gate the sibling
FR-001-006/008 work ships: a "sole door" factory with a documented side door
is not a sole door. FR-010 closes the two known sites onto the pinned
``ActiveCharterService.agent_profile_repository`` accessor (WP01, FR-001); this
module is the durable, non-fakeable proof that closure holds and cannot be
silently reopened anywhere else in the codebase (C-002: zero-tolerance, no
shrink-only allowlist -- see NFR-001/C-002 in
``kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/spec.md``).

Detection strategy
-------------------
A bare ``grep -r "._inner"`` is too broad: ``src/specify_cli/auth/transport.py``
and ``src/specify_cli/events/decision_log.py`` both hold unrelated, legitimate
``self._inner`` wrapper attributes (an ``OAuthHttpClient`` wrapper and a
decision-log delegate, respectively) that have nothing to do with
``ActiveCharterService`` -- a bare scan would false-positive on both (debugger-debbie
finding, post-tasks squad). This gate instead resolves, per file, which local
names are bound (directly or by import alias) to a *construction* of a
``charter.activation.resolver.ActiveCharterService`` -- either the sanctioned factory
(``build_activation_aware_doctrine_service``, FR-008's unified builder) or the
wrapper's own constructor (``charter.activation.resolver.ActiveCharterService``) -- and flags a
reach-around only when its receiver is one of those tainted names, or an inline
construction call. ``self._inner`` on an untainted receiver (the two
false-positive risks above) is never flagged, because ``self`` is never
assigned from either constructor.

Detection widenings (A2/A3/A4) were applied by an earlier fold commit; see
that commit's message for the measured before/after catch rate.

Landing-fold gate hardening: scope widening and message rewrite
------------------------------------------------------------------
**Scope widening.** NFR-001 says "zero ``._inner`` accesses outside
``src/charter/**``", and ``tests/`` is outside ``src/``. This gate previously
scanned only ``_SRC_ROOT``. It now also scans ``tests/``, exempting
``src/charter/**`` (the wrapper's own implementation), ``tests/charter/**``
(that layer's own test suite, which legitimately exercises ``._inner``
directly per its own module docstring), and this gate's own fixture file
(whose planted-violation test bodies are string literals *containing* the
substring ``._inner``, not real attribute-access AST nodes -- but the
exemption is named explicitly rather than relying on that distinction holding
forever).

**Message rewrite.** The violation message previously read "Use the
``agent_profile_repository`` accessor (or ``raw_repository(kind)`` for other
gated kinds) instead of..." -- phrasing that blanket-advertises
``raw_repository(kind)`` as an equally-sanctioned remedy alongside
``agent_profile_repository``, when ``raw_repository``'s own docstring records
that it does NOT apply charter activation filtering (i.e. it hands back an
unfiltered repository, by design, through the sole door). A gate must not
advertise an ungated-sounding escape hatch as the interchangeable remedy. The
message now names the ONE accessor that fits the SPECIFIC kind actually
reached (resolved from the trailing attribute immediately following the
reach-around, e.g. ``service._inner.agent_profiles`` -> ``"agent_profiles"``
-> "use the `agent_profile_repository` accessor"), falling back to naming
both only when the trailing kind cannot be resolved statically.

Known limitation (documented, not hidden): this is a static, per-file,
name-based approximation -- not full dataflow/type inference. A caller that
threads a ``ActiveCharterService`` through an unconventional indirection (e.g. a
dict of services, a ``for`` loop over a computed iterable, or a return value
re-assigned across module boundaries) could in principle evade detection.
This is the same class of tradeoff ``test_mission_resolver_walker_gate.py``
already accepts for its own taint heuristic. Extending the taint model is a
deliberate, reviewed edit to this file, not silent scope creep.

Zero-tolerance (C-002): no allowlist. Only ``src/charter/**`` and
``tests/charter/**`` -- directory-prefix keyed, never by individual file or
line -- plus this gate's own named fixture-file exemption, are exempt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file
from tests.architectural._sole_door_scan import REPO_ROOT, _Bindings, _lookup_module

pytestmark = pytest.mark.architectural

_SRC_ROOT = REPO_ROOT / "src"
_TESTS_ROOT = REPO_ROOT / "tests"

# The wrapper's own implementation lives here; ._inner access inside it is
# the sole door's construction, not a reach-around. Directory-prefix keyed
# (G-2 style), never per-file/per-line.
_EXEMPT_DIR_PREFIXES = ("src/charter/", "tests/charter/")

# This gate's own fixture file: its planted-violation test bodies are STRING
# LITERALS containing "._inner" (never real ast.Attribute nodes in this file's
# own tree), but the exemption is named explicitly rather than relying on that
# distinction holding forever as this file grows.
_EXEMPT_FILES = frozenset({"tests/architectural/test_charter_sole_door_inner_reacharound.py"})

# The one sanctioned construction path for a charter.activation.resolver.ActiveCharterService
# outside src/charter/** (FR-008's unified builder).
_FACTORY_FUNC_NAME = "build_activation_aware_doctrine_service"
_FACTORY_MODULES = frozenset({"specify_cli.doctrine_service_factory", "charter.activation.doctrine_service_builder"})

# The wrapper's own constructor -- tracked too so the taint heuristic stays
# correct even though NFR-001's sibling gate independently forbids
# constructing it directly outside src/charter/**.
_CTOR_NAME = "ActiveCharterService"
_CTOR_MODULE = "charter.activation.resolver"

#: The pinned lineage/mutation accessor for the ``agent_profiles`` kind
#: (FR-001). Named specifically so the violation message never has to fall
#: back to advertising every accessor as an equally valid, blanket remedy.
_AGENT_PROFILES_KIND = "agent_profiles"


def _collect_import_aliases(tree: ast.AST) -> _Bindings:
    aliases = _Bindings()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                aliases.from_imports[local] = (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name
                aliases.module_aliases[local] = alias.name
    return aliases


def _dotted_prefix(node: ast.expr) -> str | None:
    """Return the dotted-name string of a Name/Attribute chain, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_prefix(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _matches_sanctioned_origin(module: str, name: str) -> bool:
    return (module in _FACTORY_MODULES and name == _FACTORY_FUNC_NAME) or (module == _CTOR_MODULE and name == _CTOR_NAME)


def _call_constructs_doctrine_service(call: ast.Call, aliases: _Bindings) -> bool:
    """True if *call* invokes the factory or the wrapper constructor.

    Resolves by import alias (``from module import name as local``), by
    module-qualified reference (``module.name(...)``), or by module import
    alias (``import module as m`` then ``m.name(...)``) -- never by bare
    text matching (mirrors NFR-001's qualname-resolution requirement for the
    sibling raw-construction gate). The module-qualified branch resolves
    through the shared :func:`_lookup_module` primitive (Gates 1-3 use the
    same one), so ``from pkg import sub`` then ``sub.Cls(...)`` resolves too.
    """
    func = call.func
    if isinstance(func, ast.Name):
        origin = aliases.from_imports.get(func.id)
        return origin is not None and _matches_sanctioned_origin(*origin)
    if isinstance(func, ast.Attribute):
        dotted = _dotted_prefix(func.value)
        if dotted is None:
            return False
        resolved_module = _lookup_module(dotted, [aliases])
        return _matches_sanctioned_origin(resolved_module, func.attr)
    return False


def _taint_if_construction(
    tainted: set[str],
    target: ast.expr,
    value: ast.expr,
    aliases: _Bindings,
) -> None:
    if isinstance(target, ast.Name) and isinstance(value, ast.Call) and _call_constructs_doctrine_service(value, aliases):
        tainted.add(target.id)


def _tainted_names(tree: ast.AST, aliases: _Bindings) -> set[str]:
    """Names (file-wide, flow-insensitive -- deliberately coarse, mirrors
    ``test_mission_resolver_walker_gate.py``) assigned from a construction
    call.

    Handles ``ast.Assign`` (bare name and tuple-unpack targets),
    ``ast.AnnAssign`` (the default spelling in a mypy-clean codebase), and
    walrus (``ast.NamedExpr``).
    """
    tainted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List)):
                    for sub_target, sub_value in zip(target.elts, node.value.elts, strict=False):
                        _taint_if_construction(tainted, sub_target, sub_value, aliases)
                else:
                    _taint_if_construction(tainted, target, node.value, aliases)
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                _taint_if_construction(tainted, node.target, node.value, aliases)
        elif isinstance(node, ast.NamedExpr):
            _taint_if_construction(tainted, node.target, node.value, aliases)
    return tainted


def _is_string_literal(node: ast.expr, value: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _is_inner_getattr_call(call: ast.Call) -> bool:
    """True for ``getattr(recv, "_inner")`` or
    ``object.__getattribute__(recv, "_inner")``.
    """
    func = call.func
    is_getattr = isinstance(func, ast.Name) and func.id == "getattr"
    is_object_getattribute = isinstance(func, ast.Attribute) and func.attr == "__getattribute__" and isinstance(func.value, ast.Name) and func.value.id == "object"
    if not (is_getattr or is_object_getattribute):
        return False
    return len(call.args) >= 2 and _is_string_literal(call.args[1], "_inner")


def _is_inner_dict_subscript(node: ast.Subscript) -> bool:
    """True for ``<recv>.__dict__["_inner"]``."""
    value = node.value
    if not (isinstance(value, ast.Attribute) and value.attr == "__dict__"):
        return False
    return _is_string_literal(node.slice, "_inner")


def _receiver_is_tainted(receiver: ast.expr, tainted: set[str], aliases: _Bindings) -> bool:
    if isinstance(receiver, ast.Name) and receiver.id in tainted:
        return True
    return isinstance(receiver, ast.Call) and _call_constructs_doctrine_service(receiver, aliases)


def _attribute_wrapping(tree: ast.AST) -> dict[int, ast.Attribute]:
    """``id(expr) -> the ast.Attribute using expr as its `.value``.

    Landing-fold gate hardening: lets the caller learn the SPECIFIC trailing
    kind a reach-around reached (``service._inner.agent_profiles`` ->
    ``"agent_profiles"``) regardless of which of the three reach-around
    spellings (``.attr``, ``getattr(...)``, ``__dict__[...]``) produced the
    tainted expression, so the violation message can name the ONE accessor
    that fits instead of blanket-advertising every accessor as an equally
    valid remedy.
    """
    return {id(node.value): node for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def _trailing_kind(node: ast.expr, wrapping: dict[int, ast.Attribute]) -> str | None:
    outer = wrapping.get(id(node))
    return outer.attr if outer is not None else None


def _find_inner_reacharounds(path: Path) -> list[tuple[int, str | None]]:
    """Return ``(lineno, trailing_kind)`` for every flagged reach-around in *path*.

    Covers three spellings: direct ``.attr == "_inner"`` access,
    ``getattr(recv, "_inner")`` / ``object.__getattribute__(recv, "_inner")``,
    and ``recv.__dict__["_inner"]``. ``trailing_kind`` is the specific
    gated-property name immediately following the reach-around
    (``"agent_profiles"``, ``"tactics"``, ...) when resolvable, else ``None``
    -- used only to make the violation message name the one accessor that
    fits (landing-fold gate hardening).
    """
    tree = parse_file(path)

    aliases = _collect_import_aliases(tree)
    tainted = _tainted_names(tree, aliases)
    wrapping = _attribute_wrapping(tree)
    violations: list[tuple[int, str | None]] = []

    for node in ast.walk(tree):
        receiver: ast.expr
        if isinstance(node, ast.Attribute) and node.attr == "_inner":
            receiver = node.value
        elif isinstance(node, ast.Call) and _is_inner_getattr_call(node):
            receiver = node.args[0]
        elif isinstance(node, ast.Subscript) and _is_inner_dict_subscript(node):
            assert isinstance(node.value, ast.Attribute)
            receiver = node.value.value
        else:
            continue
        if _receiver_is_tainted(receiver, tainted, aliases):
            violations.append((node.lineno, _trailing_kind(node, wrapping)))

    return violations


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _is_exempt(rel: str) -> bool:
    return rel.startswith(_EXEMPT_DIR_PREFIXES) or rel in _EXEMPT_FILES


def _iter_scan_files(roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        files.extend(sorted(root.rglob("*.py")))
    return [p for p in files if "__pycache__" not in p.parts]


def _scan_tree_for_violations(
    roots: tuple[Path, ...],
) -> dict[str, list[tuple[int, str | None]]]:
    """Scan every ``*.py`` under *roots*, skipping the exempt directories/files.

    Scope is derived from ``root.rglob("*.py")`` wholesale for each root -- no
    hardcoded subdirectory list a new package could silently fall outside of
    (mirrors ``test_mission_resolver_walker_gate.py``'s G-3 guarantee).
    """
    violations: dict[str, list[tuple[int, str | None]]] = {}
    for py_file in _iter_scan_files(roots):
        rel = _rel(py_file)
        if _is_exempt(rel):
            continue
        hits = _find_inner_reacharounds(py_file)
        if hits:
            violations[rel] = hits
    return violations


def _remedy_message(kind: str | None) -> str:
    """The specific accessor to point a violator at for *kind*.

    A gate must not advertise a blanket "use raw_repository(kind) for
    anything else" as if it were an interchangeable, equally-sanctioned
    remedy alongside ``agent_profile_repository`` -- ``raw_repository``
    itself returns an UNFILTERED repository (its own docstring: "does not
    apply charter activation filtering"), so recommending it generically
    reads as advertising an escape hatch. Name the ONE accessor that fits the
    kind actually reached; only fall back to naming both when the trailing
    kind could not be resolved, and even then, tell the caller to name their
    OWN specific kind rather than treating the fallback as a blanket license.
    """
    if kind == _AGENT_PROFILES_KIND:
        return "use the `agent_profile_repository` accessor"
    if kind:
        return f'use `raw_repository("{kind}")`'
    return (
        "use the `agent_profile_repository` accessor for agent-profile "
        "lineage/provenance operations, or `raw_repository(kind)` naming "
        "YOUR specific gated kind -- never a blanket substitute for either"
    )


# ---------------------------------------------------------------------------
# Scope-derivation sanity check
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Known false-positive risks stay clean (debugger-debbie finding)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The main gate
# ---------------------------------------------------------------------------


def test_no_inner_reacharound_on_doctrine_service_outside_charter() -> None:
    """Zero reach-around access on a ``charter.activation.resolver.ActiveCharterService``
    outside ``src/charter/**`` and ``tests/charter/**`` (FR-010, NFR-001).

    Zero-tolerance (C-002): no allowlist. To fix a violation, use the
    ``agent_profile_repository`` accessor (for ``agent_profiles`` lineage /
    provenance operations) or ``ActiveCharterService.raw_repository(kind)`` naming
    the SPECIFIC other gated kind (for any other gated kind's raw repository
    operations) instead of reaching past the sole door.
    """
    violations = _scan_tree_for_violations((_SRC_ROOT, _TESTS_ROOT))

    if violations:
        details = "\n".join(
            f"  {path}: " + "; ".join(f"line {lineno} ({_remedy_message(kind)})" for lineno, kind in hits) for path, hits in sorted(violations.items())
        )
        pytest.fail(
            "Found a `._inner` reach-around (direct attribute access, "
            "getattr()/object.__getattribute__(), or __dict__ subscript) on a "
            "charter.activation.resolver.ActiveCharterService outside src/charter/** and "
            "tests/charter/** (FR-010). Each finding below names the ONE "
            "sanctioned accessor for the kind actually reached.\n\n"
            f"Violations:\n{details}"
        )


# ---------------------------------------------------------------------------
# Self-mutation proof (NFR-003): the gate must actually bite, in both
# directions -- true positive AND true negative, at function-local scope.
# ---------------------------------------------------------------------------


def test_planted_reacharound_at_function_local_scope_is_detected(tmp_path: Path) -> None:
    """A planted ``._inner`` reach-around on a tainted variable is caught.

    Reproduces the exact real-violation shape (``service = <factory>(...)``
    then ``service._inner.<kind>``) at function-local scope -- not
    module-level-only, matching the actual shape of the real violations
    (spec.md NFR-003).
    """
    planted = tmp_path / "planted_reacharound.py"
    planted.write_text(
        "from specify_cli.doctrine_service_factory import (\n"
        "    build_activation_aware_doctrine_service,\n"
        ")\n"
        "\n"
        "\n"
        "def build_catalog(repo_root):\n"
        "    service = build_activation_aware_doctrine_service(repo_root)\n"
        "    inner_repo = service._inner.agent_profiles\n"
        "    return inner_repo\n",
        encoding="utf-8",
    )

    hits = _find_inner_reacharounds(planted)
    assert [lineno for lineno, _ in hits] == [8], (
        "Anti-mutant test failed to detect a planted ._inner reach-around on a "
        f"doctrine-service-typed variable; got {hits!r}. The gate does not bite "
        "-- investigate the taint heuristic before trusting the green main gate."
    )
    assert hits[0][1] == "agent_profiles", hits


def test_planted_unrelated_inner_attribute_is_not_detected(tmp_path: Path) -> None:
    """A planted, unrelated ``._inner`` attribute must NOT be flagged.

    Mirrors the real ``auth/transport.py``/``events/decision_log.py`` shape:
    a scratch class with its own, wholly unrelated ``._inner`` wrapper
    attribute. Proves the gate's scoping is neither too broad (this test)
    nor too narrow (the sibling true-positive test above) -- both
    assertions required by the WP04 risk mitigation.
    """
    planted = tmp_path / "planted_unrelated_inner.py"
    planted.write_text(
        "class ScratchWrapper:\n    def __init__(self, inner):\n        self._inner = inner\n\n    def call(self):\n        return self._inner.request()\n",
        encoding="utf-8",
    )

    hits = _find_inner_reacharounds(planted)
    assert hits == [], f"Gate falsely flagged an unrelated ._inner attribute access: {hits!r}. The taint heuristic is too broad."


def test_getattr_string_reach_around_is_flagged(tmp_path: Path) -> None:
    """``getattr(service, "_inner")`` reaches the same attribute.

    A gate that only pattern-matches ``ast.Attribute`` with ``attr ==
    "_inner"`` is structurally blind to this one-line reach-around reopening.
    Injected at function-local scope (NFR-003).
    """
    planted = tmp_path / "getattr_reacharound.py"
    planted.write_text(
        "from specify_cli.doctrine_service_factory import (\n"
        "    build_activation_aware_doctrine_service,\n"
        ")\n"
        "\n"
        "\n"
        "def build_catalog(repo_root):\n"
        "    service = build_activation_aware_doctrine_service(repo_root)\n"
        '    return getattr(service, "_inner").agent_profiles\n',
        encoding="utf-8",
    )

    hits = _find_inner_reacharounds(planted)
    assert [lineno for lineno, _ in hits] == [8], hits
    assert hits[0][1] == "agent_profiles"
