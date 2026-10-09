"""AST scanner for the single-authority owned-checkout gate (contracts/architectural-gate.md).

Not a test module (mirrors the existing underscore-prefixed non-test helpers
in this directory -- ``_lock_gate_scan.py``, ``_os_detection_scan.py``):
pytest never collects it, so it carries no ``pytestmark``.

Implements every rule G1-G6 of ``contracts/architectural-gate.md`` as a small,
typed API: each visitor function takes ``(tree, rel_path)`` and returns a
``list[Offender]``. Every source is parsed through
``tests.architectural._ast_scan.parse_file`` / ``parse_source``, which fails
closed -- never ``except SyntaxError: continue``
(``test_scanner_parse_fail_closed.py`` bans that shape).

This module is built now (owned-checkout-lifecycle-authority WP01) so its
self-tests (``test_owned_checkout_gate_selftest.py``) are green from the
start, over *synthetic* sources only. The closing WP (WP18) is the one that
calls ``iter_python_sources`` against the live ``src/`` tree and asserts the
G1-G6 floors; no WP01 test does that (a gate floor on the live tree here
would go red the moment WP18 converts everything -- see the WP01 prompt's
"Gate floors on the live tree are forbidden" constraint).

**Rules**:

- ``claim_references`` (**G1**): every reference to ``resolve_ownership_claim``.
- ``validator_calls`` (**G2**): calls to ``resolve_owned_mission(`` /
  ``adopt_owned_checkout(``.
- ``mint_references`` (**G3**): any ``OwnedCheckout._mint`` reference.
- ``effective_root_identifiers`` (**G4**): the identifier ``effective_root``
  anywhere it can appear (parameter, field, keyword, TypedDict/dict key,
  attribute). Docstrings and comments never count.
- ``bare_owned_root_paths`` (**G5**): a bare ``Path``-typed owned root under
  any of the banned names.
- ``owned_signature_pins`` (**G6**): the positive pin -- named consumers must
  declare ``owned: OwnedCheckout | None``.

**Where** a reference is allowed (the minter module, the CLI claim-input
helper, the carrier's own definition site) is the *caller's* decision,
expressed as a module allowlist constant by WP18 -- kept out of the visitors
so the self-tests can exercise them without any path context.

**Exemptions** (named rules, never a path list of offenders):

- ``ORG_PACK_MODULE_RULE``: ``effective_root`` inside ``src/charter/**``,
  ``src/specify_cli/cli/commands/_doctrine_collect.py`` and
  ``src/specify_cli/analysis_inputs.py`` is the unrelated
  ``OrgPackConfig.effective_root`` root concept, not the owned-checkout one.
- ``ORG_PACK_METHOD_RULE``: a *called* ``Attribute(attr="effective_root")`` is
  exempt from G4 anywhere (an uncalled attribute read is still flagged).
- ``CARRIER_FIELD_RULE``: the fields of
  ``mission_runtime.owned_checkout.OwnedCheckout`` (matched by
  fully-qualified module path + class name) are exempt from G5, and so are
  the keyword parameters of that class's ``_mint`` construction door (they ARE
  those fields; added by WP18 -- G5 needs it because ``_mint(owned_root=...)``
  is the sole way the fields are populated).
- ``CLI_CLAIM_INPUT_RULE``: a parameter annotated with the CLI claim-input
  alias ``OwnedCheckoutOption``, or its help-preserving
  ``Annotated[Path | None, owned_checkout_option(help=...)]`` form, is exempt
  from G5.
- ``MIGRATIONS_CHECKOUT_ROOT_RULE``: the ``checkout_root`` name under
  ``src/specify_cli/upgrade/migrations/**`` is exempt from G5 (historical
  migrations, an unrelated sense); the other G5 names and G4 still apply.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from tests.architectural._ast_scan import UnparseableSourceError, parse_source

__all__ = [
    "Offender",
    "bare_owned_root_paths",
    "claim_references",
    "effective_root_identifiers",
    "iter_python_sources",
    "mint_references",
    "owned_signature_pins",
    "validator_calls",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]

_CLAIM_FUNCTION_NAME = "resolve_ownership_claim"
_VALIDATOR_FUNCTION_NAMES = frozenset({"resolve_owned_mission", "adopt_owned_checkout"})
_MINT_ATTR_NAME = "_mint"
_MINTER_CLASS_NAME = "OwnedCheckout"
_EFFECTIVE_ROOT_NAME = "effective_root"
_BARE_OWNED_ROOT_NAMES = frozenset({"owned_root", "owned_checkout", "checkout_root", "effective_root"})

# -- Named exemption scope ---------------------------------------------------

#: ORG_PACK_MODULE_RULE: effective_root here is OrgPackConfig.effective_root
#: (src/charter/offering/drg/org_pack_config.py:374), a different concept.
ORG_PACK_MODULE_PATHS: tuple[str, ...] = (
    "src/charter/",
    "src/specify_cli/cli/commands/_doctrine_collect.py",
    "src/specify_cli/analysis_inputs.py",
)

#: CARRIER_FIELD_RULE: the one module + class whose fields are exempt from G5.
CARRIER_MODULE_PATH = "src/mission_runtime/owned_checkout.py"
CARRIER_CLASS_NAME = "OwnedCheckout"

#: CLI_CLAIM_INPUT_RULE: the alias name that exempts a parameter from G5
#: (either as a bare ``Name``, e.g. ``owned_checkout: OwnedCheckoutOption``,
#: or qualified by this module, e.g. ``_owned_checkout.OwnedCheckoutOption``),
#: plus the help-preserving Annotated call name.
CLI_CLAIM_INPUT_ALIAS_NAME = "OwnedCheckoutOption"
CLI_CLAIM_INPUT_ALIAS_QUALIFIER = "_owned_checkout"
CLI_CLAIM_INPUT_HELPER_CALL_NAME = "owned_checkout_option"

#: MIGRATIONS_CHECKOUT_ROOT_RULE: checkout_root is exempt from G5 here only.
MIGRATIONS_MODULE_PREFIX = "src/specify_cli/upgrade/migrations/"


@dataclass(frozen=True)
class Offender:
    """One gate violation: which rule, where, and a human-readable detail."""

    rule: str  # "G1".."G6"
    rel_path: str  # repo-relative, posix
    lineno: int
    detail: str  # e.g. "keyword effective_root=" / "param owned_root: Path | None"


def _is_org_pack_module(rel_path: str) -> bool:
    return any(rel_path == p or rel_path.startswith(p) for p in ORG_PACK_MODULE_PATHS)


def _is_migrations_module(rel_path: str) -> bool:
    return rel_path.startswith(MIGRATIONS_MODULE_PREFIX)


def _is_carrier_module(rel_path: str) -> bool:
    return rel_path == CARRIER_MODULE_PATH


def _is_docstring_expr(node: ast.AST) -> bool:
    """True when ``node`` is a module/class/function's leading docstring ``Expr``."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _iter_non_docstring_bodies(tree: ast.Module) -> Iterator[ast.AST]:
    """Walk the tree yielding every node, skipping each body's leading docstring statement.

    Both the wrapping ``Expr`` statement AND its child ``Constant`` are
    excluded -- ``ast.walk`` descends into an ``Expr`` and yields its
    ``.value`` too, so skipping only the ``Expr`` node still let a docstring
    that is exactly ``"effective_root"`` reach the ``Constant`` check below
    and get flagged (the review-cycle-1 finding).
    """
    doc_bearing: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            first_stmt = body[0] if body else None
            # ``isinstance(first_stmt, ast.Expr)`` is redundant at runtime
            # given ``_is_docstring_expr`` already implies it, but mypy
            # cannot narrow ``first_stmt`` through that function call, so the
            # explicit check here is what lets ``.value`` type-check.
            if first_stmt is not None and _is_docstring_expr(first_stmt) and isinstance(first_stmt, ast.Expr):
                doc_bearing.add(id(first_stmt))
                doc_bearing.add(id(first_stmt.value))
    for node in ast.walk(tree):
        if id(node) in doc_bearing:
            continue
        yield node


# ---------------------------------------------------------------------------
# G1 -- claim-primitive references
# ---------------------------------------------------------------------------


def claim_references(tree: ast.Module, rel_path: str) -> list[Offender]:
    """G1: every reference to ``resolve_ownership_claim``, any form."""
    offenders: list[Offender] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and node.name == _CLAIM_FUNCTION_NAME:
            offenders.append(Offender("G1", rel_path, node.lineno, f"import {_CLAIM_FUNCTION_NAME}"))
        elif isinstance(node, ast.Name) and node.id == _CLAIM_FUNCTION_NAME:
            offenders.append(Offender("G1", rel_path, node.lineno, f"name {_CLAIM_FUNCTION_NAME}"))
        elif isinstance(node, ast.Attribute) and node.attr == _CLAIM_FUNCTION_NAME:
            offenders.append(Offender("G1", rel_path, node.lineno, f"attribute .{_CLAIM_FUNCTION_NAME}"))
        elif isinstance(node, ast.Call) and _is_dynamic_lookup_of(node, _CLAIM_FUNCTION_NAME):
            offenders.append(Offender("G1", rel_path, node.lineno, f"dynamic lookup of {_CLAIM_FUNCTION_NAME!r}"))
    return offenders


def _is_dynamic_lookup_of(call: ast.Call, target_name: str) -> bool:
    """True for ``getattr(x, "name")`` / ``importlib.import_module("name")`` / ``__import__("name")``."""
    func = call.func
    func_name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if func_name not in {"getattr", "import_module", "__import__"}:
        return False
    return any(isinstance(arg, ast.Constant) and arg.value == target_name for arg in call.args)


# ---------------------------------------------------------------------------
# G2 -- validator-call site
# ---------------------------------------------------------------------------


def validator_calls(tree: ast.Module, rel_path: str) -> list[Offender]:
    """G2: calls to ``resolve_owned_mission(`` / ``adopt_owned_checkout(``, any reference form.

    Resolves ``import ... as`` aliases the same way G1 does (via
    ``ast.alias``), and a dynamic ``getattr(module, "resolve_owned_mission")(...)``
    lookup.
    """
    offenders: list[Offender] = []
    bound_names = _VALIDATOR_FUNCTION_NAMES | _import_aliases_for(tree, _VALIDATOR_FUNCTION_NAMES)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in bound_names:
            offenders.append(Offender("G2", rel_path, node.lineno, f"call {name}("))
        elif any(_is_dynamic_lookup_of(node, target) for target in _VALIDATOR_FUNCTION_NAMES):
            offenders.append(Offender("G2", rel_path, node.lineno, "dynamic lookup of a validator function"))
    return offenders


def _import_aliases_for(tree: ast.Module, target_names: frozenset[str]) -> set[str]:
    """Local names bound to any of ``target_names`` via ``from … import x as alias``."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in target_names and alias.asname:
                    aliases.add(alias.asname)
    return aliases


# ---------------------------------------------------------------------------
# G3 -- mint-site reference
# ---------------------------------------------------------------------------


def mint_references(tree: ast.Module, rel_path: str) -> list[Offender]:
    """G3: any reference to ``OwnedCheckout._mint``, in every form.

    Covers the bare name (``OwnedCheckout._mint(...)``), an ``import ... as``
    alias, the package-root attribute-chain spelling MR-1/MR-2 force
    (``mission_runtime.OwnedCheckout._mint(...)``), and the dynamic
    ``getattr(OwnedCheckout, "_mint")`` lookup.
    """
    offenders: list[Offender] = []
    aliases = _names_bound_to_owned_checkout(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == _MINT_ATTR_NAME and _names_owned_checkout(node.value, aliases):
            offenders.append(Offender("G3", rel_path, node.lineno, f"…{_names_display(node.value)}.{_MINT_ATTR_NAME}("))
        elif isinstance(node, ast.Call) and _is_dynamic_mint_lookup(node, aliases):
            offenders.append(Offender("G3", rel_path, node.lineno, f'getattr(…, "{_MINT_ATTR_NAME}")'))
    return offenders


def _names_bound_to_owned_checkout(tree: ast.Module) -> set[str]:
    """Every local name that refers to ``OwnedCheckout`` -- direct or ``import ... as``."""
    names = {_MINTER_CLASS_NAME}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _MINTER_CLASS_NAME and alias.asname:
                    names.add(alias.asname)
    return names


def _names_owned_checkout(node: ast.expr, aliases: set[str]) -> bool:
    """True when ``node`` (a ``Call``/``Attribute``'s receiver) names ``OwnedCheckout``.

    Matches a bare/aliased ``Name`` (``OC._mint``) and the package-root
    attribute-chain spelling (``mission_runtime.OwnedCheckout._mint`` --
    ``node`` is ``Attribute(value=Name("mission_runtime"), attr="OwnedCheckout")``),
    regardless of what the leading package name is bound to.
    """
    if isinstance(node, ast.Name):
        return node.id in aliases
    if isinstance(node, ast.Attribute):
        return node.attr in aliases
    return False


def _names_display(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return "…"


def _is_dynamic_mint_lookup(call: ast.Call, aliases: set[str]) -> bool:
    """True for ``getattr(OwnedCheckout, "_mint")`` (any spelling of the receiver)."""
    func = call.func
    func_name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if func_name != "getattr" or len(call.args) < 2:
        return False
    target, attr_arg = call.args[0], call.args[1]
    if not (isinstance(attr_arg, ast.Constant) and attr_arg.value == _MINT_ATTR_NAME):
        return False
    return _names_owned_checkout(target, aliases)


# ---------------------------------------------------------------------------
# G4 -- effective_root identifier ban
# ---------------------------------------------------------------------------


def effective_root_identifiers(tree: ast.Module, rel_path: str) -> list[Offender]:
    """G4: the identifier ``effective_root`` anywhere except a called ``.effective_root(...)`` attribute.

    Comments/docstrings never count (``_iter_non_docstring_bodies``).
    ``ORG_PACK_MODULE_RULE`` is applied here, by ``rel_path``: a module under
    its scope returns no offenders.
    """
    if _is_org_pack_module(rel_path):
        return []
    offenders: list[Offender] = []
    called_attribute_nodes = {
        node.func for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == _EFFECTIVE_ROOT_NAME
    }
    # An ``AnnAssign``'s ``.target`` is itself a child ``Name`` node that
    # ``ast.walk`` also visits separately -- without this exclusion set, a
    # single annotated field (e.g. a TypedDict key) would be counted twice:
    # once via the ``AnnAssign`` branch, once via the generic bare-``Name``
    # branch below.
    annassign_target_ids = {id(node.target) for node in ast.walk(tree) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    for node in _iter_non_docstring_bodies(tree):
        offenders.extend(_effective_root_hits(node, rel_path, called_attribute_nodes, annassign_target_ids))
    return offenders


def _effective_root_hits(
    node: ast.AST,
    rel_path: str,
    called_attribute_nodes: set[ast.Attribute],
    annassign_target_ids: set[int],
) -> list[Offender]:
    if isinstance(node, ast.arg) and node.arg == _EFFECTIVE_ROOT_NAME:
        return [Offender("G4", rel_path, node.lineno, "param effective_root")]
    if isinstance(node, ast.keyword) and node.arg == _EFFECTIVE_ROOT_NAME:
        return [Offender("G4", rel_path, node.lineno, "keyword effective_root=")]
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id == _EFFECTIVE_ROOT_NAME:
            return [Offender("G4", rel_path, node.lineno, "identifier effective_root")]
        return []
    if isinstance(node, ast.Name) and node.id == _EFFECTIVE_ROOT_NAME and id(node) not in annassign_target_ids:
        return [Offender("G4", rel_path, node.lineno, "identifier effective_root")]
    if isinstance(node, ast.Attribute) and node.attr == _EFFECTIVE_ROOT_NAME and node not in called_attribute_nodes:
        return [Offender("G4", rel_path, node.lineno, "attribute .effective_root")]
    if isinstance(node, ast.Constant) and node.value == _EFFECTIVE_ROOT_NAME:
        return [Offender("G4", rel_path, node.lineno, 'string "effective_root"')]
    return []


# ---------------------------------------------------------------------------
# G5 -- bare owned-root Path parameters/fields
# ---------------------------------------------------------------------------


def bare_owned_root_paths(tree: ast.Module, rel_path: str) -> list[Offender]:
    """G5: a parameter or class-body field named a banned owned-root alias, annotated bare ``Path``.

    ``ORG_PACK_MODULE_RULE`` is applied here too (the contract: the rule
    "takes them out of G4/G5 scope") -- a module under its scope returns no
    offenders, so ``OrgPackConfig.effective_root``'s own parameter never
    trips this rule either.
    """
    if _is_org_pack_module(rel_path):
        return []
    offenders: list[Offender] = []
    for classdef in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        offenders.extend(_scan_class_fields(classdef, rel_path))
    carrier_mint_ids = _carrier_mint_method_ids(tree, rel_path)
    for funcdef in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        if id(funcdef) in carrier_mint_ids:
            continue
        offenders.extend(_scan_function_params(funcdef, rel_path))
    return offenders


def _carrier_mint_method_ids(tree: ast.Module, rel_path: str) -> set[int]:
    """``CARRIER_FIELD_RULE`` extension: the ``_mint`` door of the carrier class.

    ``OwnedCheckout._mint`` (matched by the same fully-qualified module path +
    class name as the fields) takes the carrier's own fields as keyword
    parameters -- it is the one construction door for exactly those fields, so
    its parameters are the fields, not a second bare-path representation.
    Every other method of the class, and any ``_mint`` elsewhere, is scanned.
    """
    if not _is_carrier_module(rel_path):
        return set()
    return {
        id(stmt)
        for classdef in ast.walk(tree)
        if isinstance(classdef, ast.ClassDef) and classdef.name == CARRIER_CLASS_NAME
        for stmt in classdef.body
        if isinstance(stmt, ast.FunctionDef) and stmt.name == _MINT_ATTR_NAME
    }


def _scan_class_fields(classdef: ast.ClassDef, rel_path: str) -> list[Offender]:
    is_carrier = _is_carrier_module(rel_path) and classdef.name == CARRIER_CLASS_NAME
    if is_carrier:
        return []
    offenders: list[Offender] = []
    for stmt in classdef.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        if name in _BARE_OWNED_ROOT_NAMES and _applies_g5_name(name, rel_path) and _is_bare_path_annotation(stmt.annotation):
            offenders.append(Offender("G5", rel_path, stmt.lineno, f"field {name}: {ast.dump(stmt.annotation)[:40]}"))
    return offenders


def _scan_function_params(funcdef: ast.FunctionDef | ast.AsyncFunctionDef, rel_path: str) -> list[Offender]:
    offenders: list[Offender] = []
    all_args = [
        *funcdef.args.posonlyargs,
        *funcdef.args.args,
        *([funcdef.args.vararg] if funcdef.args.vararg else []),
        *funcdef.args.kwonlyargs,
        *([funcdef.args.kwarg] if funcdef.args.kwarg else []),
    ]
    for param in all_args:
        name = param.arg
        if name not in _BARE_OWNED_ROOT_NAMES or not _applies_g5_name(name, rel_path):
            continue
        if _is_cli_claim_input_exempt(param.annotation):
            continue
        if _is_bare_path_annotation(param.annotation):
            offenders.append(Offender("G5", rel_path, param.lineno, f"param {name}: {ast.dump(param.annotation)[:40] if param.annotation else ''}"))
    return offenders


def _applies_g5_name(name: str, rel_path: str) -> bool:
    return not (name == "checkout_root" and _is_migrations_module(rel_path))


def _is_cli_claim_input_exempt(annotation: ast.expr | None) -> bool:
    """CLI_CLAIM_INPUT_RULE: ``OwnedCheckoutOption`` or its ``Annotated[Path | None, owned_checkout_option(...)]`` form."""
    if annotation is None:
        return False
    if _is_owned_checkout_option_alias(annotation):
        return True
    if isinstance(annotation, ast.Subscript) and _annotation_name(annotation.value) == "Annotated":
        elts = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        for elt in elts[1:]:
            if isinstance(elt, ast.Call) and _annotation_name(elt.func) == CLI_CLAIM_INPUT_HELPER_CALL_NAME:
                return True
    return False


def _is_owned_checkout_option_alias(node: ast.expr) -> bool:
    """True for the bare ``OwnedCheckoutOption`` name, or ``_owned_checkout.OwnedCheckoutOption`` qualified.

    Requiring the qualifier for the ``Attribute`` form (rather than matching
    on ``.attr`` alone) keeps an unrelated ``anything.OwnedCheckoutOption``
    from being silently exempted.
    """
    if isinstance(node, ast.Name):
        return node.id == CLI_CLAIM_INPUT_ALIAS_NAME
    if isinstance(node, ast.Attribute) and node.attr == CLI_CLAIM_INPUT_ALIAS_NAME:
        return isinstance(node.value, ast.Name) and node.value.id == CLI_CLAIM_INPUT_ALIAS_QUALIFIER
    return False


def _annotation_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _parse_string_annotation(value: str) -> ast.expr | None:
    """Parse a string annotation's own source, returning its expression.

    Fails closed via :func:`parse_source` -- never a silent ``except
    SyntaxError`` (``test_scanner_parse_fail_closed.py`` bans that shape).
    Returns ``None`` for a value with no expression body (an empty string)
    instead of letting ``.body[0]`` raise ``IndexError``. Raises
    :class:`UnparseableSourceError` (an explicit, ``-O``-safe check -- never
    a stripped-under-``-O`` ``assert``) if the parsed statement is not a bare
    expression.
    """
    module = parse_source(value, display="<string-annotation>")
    if not module.body:
        return None
    stmt = module.body[0]
    if not isinstance(stmt, ast.Expr):
        raise UnparseableSourceError(f"string annotation is not a bare expression: {value!r}")
    return stmt.value


_PATH_ANNOTATION_NAMES = frozenset({"Path", "PathLike"})


def _is_bare_path_annotation(node: ast.expr | None) -> bool:
    """True when ``node`` annotates a bare ``Path``/``os.PathLike`` (optionally unioned with ``None``)."""
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parsed = _parse_string_annotation(node.value)
        return parsed is not None and _is_bare_path_annotation(parsed)
    if isinstance(node, ast.Name):
        return node.id in _PATH_ANNOTATION_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _PATH_ANNOTATION_NAMES
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_bare_path_annotation(node.left) or _is_bare_path_annotation(node.right)
    if isinstance(node, ast.Subscript):
        return _is_bare_path_subscript(node)
    return False


def _is_bare_path_subscript(node: ast.Subscript) -> bool:
    head = _annotation_name(node.value)
    if head == "Optional":
        return _is_bare_path_annotation(node.slice)
    if head in {"Union", "Annotated"}:
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        # Annotated: only the first element (the type) is checked; the metadata
        # after it is where CLI_CLAIM_INPUT_RULE looks, not here.
        candidates = elts if head == "Union" else elts[:1]
        return any(_is_bare_path_annotation(elt) for elt in candidates)
    return head == "PathLike"


# ---------------------------------------------------------------------------
# G6 -- positive signature pin
# ---------------------------------------------------------------------------

_OWNED_PARAM_NAME = "owned"


def owned_signature_pins(tree: ast.Module, rel_path: str, required: Mapping[str, str]) -> list[Offender]:
    """G6: each qualname in ``required`` (function or class) must declare ``owned: OwnedCheckout | None``.

    ``required`` maps a bare def/class name to a human-readable detail string
    (the consumer identity); callers supply the §7 consumer list (WP18 wires
    the live map). Per-file semantics: a required name **present** in
    ``tree`` without the pin is an offender; a required name **absent** from
    this ``tree`` is silently skipped (``continue``), because one file's AST
    is not expected to contain every §7 consumer -- most modules will only
    ever hold a handful of them, so treating "not found in this file" as an
    offender would mean every scan of every unrelated file reports every
    other consumer missing.

    WP18 hand-off: because absence is per-file-silent here, WP18's live-tree
    driver MUST separately assert that every §7 consumer name was found in
    at least one scanned file (a set-difference between ``required.keys()``
    and the union of qualnames actually seen across the whole traversal) --
    a renamed or deleted consumer must still fail the gate somewhere, even
    though no single file's call to this function will catch it alone.
    """
    offenders: list[Offender] = []
    defs_by_name = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for name, detail in required.items():
        node = defs_by_name.get(name)
        if node is None:
            continue
        if not _declares_owned_pin(node):
            offenders.append(Offender("G6", rel_path, node.lineno, f"{name} missing owned: OwnedCheckout | None pin ({detail})"))
    return offenders


def _declares_owned_pin(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    if isinstance(node, ast.ClassDef):
        # Build (name, annotation) pairs directly inside the comprehension
        # guard so mypy narrows ``n.target`` to ``ast.Name`` in the same
        # expression, instead of losing that narrowing across a separate
        # `fields = [...]` list (avoids a `# type: ignore[union-attr]`).
        field_annotations = [(n.target.id, n.annotation) for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
        return any(name == _OWNED_PARAM_NAME and _is_owned_checkout_optional(annotation) for name, annotation in field_annotations)
    all_args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return any(a.arg == _OWNED_PARAM_NAME and _is_owned_checkout_optional(a.annotation) for a in all_args)


def _is_owned_checkout_optional(node: ast.expr | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parsed = _parse_string_annotation(node.value)
        return parsed is not None and _is_owned_checkout_optional(parsed)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        sides = (node.left, node.right)
        has_owned_checkout = any(_annotation_name(side) == _MINTER_CLASS_NAME for side in sides)
        has_none = any(_is_none_leaf(side) for side in sides)
        return has_owned_checkout and has_none
    return False


def _is_none_leaf(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    return isinstance(node, ast.Name) and node.id == "None"


# ---------------------------------------------------------------------------
# Live-tree traversal (WP18 consumes this; no WP01 test calls it against src/)
# ---------------------------------------------------------------------------


def iter_python_sources(root: Path) -> Iterator[tuple[Path, str]]:
    """Yield sorted ``(path, rel_path)`` pairs for every ``.py`` file under ``root``, skipping ``__pycache__``."""
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            rel_path = path.resolve().relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            rel_path = path.as_posix()
        yield path, rel_path
