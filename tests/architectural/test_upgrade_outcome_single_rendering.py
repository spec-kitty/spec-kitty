"""Single-rendering gate for ``spec-kitty upgrade`` (#4925).

Why this gate exists
--------------------
The upgrade exit code already had one authority (``UpgradeOutcome.derive_exit_code``).
The messages and the closing line did not: each presentation path assembled its own
error list, and the no-migrations path printed ``Project is already up to date!``
unconditionally, so a run that exited 1 told the operator it had succeeded.

The fix makes ``UpgradeOutcome`` (``specify_cli/upgrade/outcome.py``) own the kind,
the reasons, the ordered messages, the JSON status word and the closing line.
This gate keeps that true. It fails when:

1. **Closing text lives outside the outcome.** A string constant (docstrings and
   f-string parts included) in ``cli/commands/upgrade.py`` contains a fragment
   derived from the closing-line constants of ``outcome.py``. Each JSON builder
   must take its ``"status"`` from ``outcome.status``, its ``"errors"`` from the
   call ``outcome.errors()`` and its ``"warnings"`` from ``outcome.warnings()``,
   and must not assign any of the three by subscript after the dict literal. The
   tail renderer must reach a ``closing_line()`` call.
2. **A presentation function assembles its own messages.** A presentation function
   reads ``.errors``, ``.warnings``, ``.activation_errors``, ``.worktree_failures``,
   ``.drifted_paths`` or ``.surface_repair_messages`` as data (it must call
   ``outcome.errors()`` / ``outcome.warnings()`` instead), fetches one of them with
   ``getattr(<x>, "<name>")``, or takes a parameter named ``errors`` or
   ``effective_success``. A presentation function is one named ``_display*``,
   ``_render*``, ``_build_*`` or ``_print*``, or any function with a parameter named
   ``outcome`` that calls ``console.print`` or ``print``. The rule is scoped to
   presentation functions: ``upgrade()`` itself may append to ``result.warnings``
   before it renders.
3. **The exit code has more than one site.** ``derive_exit_code`` is called from
   exactly one place under ``src/`` (the finalizer); the only exit after the
   ``finalize_upgrade`` call inside ``upgrade()`` is ``raise typer.Exit(outcome.exit_code)``
   directly under a test of ``outcome.exit_code`` (``raise SystemExit``,
   ``sys.exit`` and ``os._exit`` count as exits); nothing in ``cli/commands/upgrade.py``
   assigns to an ``.exit_code`` attribute; and no presentation function exits at all.
4. **The exit code is not a function of the kind.** The only attribute
   ``derive_exit_code`` reads from ``self`` is ``kind`` (it may return the
   ``exit_code`` it has just stored), and the value it stores in ``self.exit_code``
   is an expression that reads ``self.kind``.

There is no allowlist: every rule starts and stays empty.

Non-vacuity (``architectural-gate-non-vacuity``)
------------------------------------------------
* Floor: the checker visits the real tail renderer, both JSON builders and the
  migration-section renderer, finds every closing-line constant in ``outcome.py``,
  finds the one ``derive_exit_code`` call and the one exit raise, and finds the
  one assignment to ``self.exit_code``.
* Self-mutation: every rule is a pure function over source text; a synthetic
  source carrying exactly that violation must be reported, and a compliant one
  must not.
* Authority parse: the closing fragments are derived from ``outcome.py`` source at
  run time, and a synthetic reworded closing line changes the derived fragments.
"""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

import pytest

import specify_cli
from specify_cli.upgrade import outcome as outcome_module

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SRC_ROOT = Path(specify_cli.__file__).resolve().parent.parent
_UPGRADE_CMD = _SRC_ROOT / "specify_cli" / "cli" / "commands" / "upgrade.py"
_OUTCOME = _SRC_ROOT / "specify_cli" / "upgrade" / "outcome.py"
_FINALIZER_SUFFIX = "specify_cli/upgrade/finalize.py"

_PRESENTATION_PREFIXES = ("_display", "_render", "_build_", "_print")
_OUTCOME_NAME = "outcome"
_PRINT = "print"
_CONSOLE = "console"
_JSON_BUILDER_SUFFIX = "_json_payload"
_TAIL_RENDERER = "_render_outcome_tail"
_SECTION_RENDERER = "_display_upgrade_results"
_JSON_BUILDERS = frozenset({"_build_migration_json_payload", "_build_no_migrations_json_payload"})
_COMMAND = "upgrade"
_FINALIZE_CALL = "finalize_upgrade"
_DERIVE = "derive_exit_code"
_CLOSING_PREFIX = "_CLOSING_"
_CLOSING_LINE_METHOD = "closing_line"
_EXIT_CODE = "exit_code"
_CALL_EXITS = frozenset({"sys", "os"})

# Message state a presentation function must obtain through ``outcome.errors()`` /
# ``outcome.warnings()`` rather than read directly.
_MESSAGE_ATTRIBUTES = frozenset(
    {
        "errors",
        "warnings",
        "activation_errors",
        "repair_preparation_errors",
        "worktree_failures",
        "drifted_paths",
        "surface_repair_messages",
    }
)
_FORBIDDEN_PARAMETERS = frozenset({"errors", "effective_success"})

# Distinguishing fragments that must never appear outside the outcome, in addition
# to the ones derived from the constants (so a constant cannot be reworded out of
# the net by editing both sides).
_PINNED_FRAGMENTS = (
    "already up to date",
    "upgrade complete",
    "upgrade failed",
    "dry run complete",
    "local edits were not updated",
)
_MIN_FRAGMENT_LENGTH = 12

# Floors, taken from the code as merged (outcome.py defines five closing lines).
_CLOSING_CONSTANT_FLOOR = 5
_SCANNED_FILE_FLOOR = 100


# --------------------------------------------------------------------------- #
# Pure checkers (source text in, violation strings out)
# --------------------------------------------------------------------------- #


def _functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _parameter_names(fn: ast.FunctionDef) -> list[str]:
    arguments = fn.args
    names = [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
    names.extend(a.arg for a in (arguments.vararg, arguments.kwarg) if a is not None)
    return names


def _is_print_call(node: ast.AST) -> bool:
    """``print(...)`` or ``console.print(...)``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == _PRINT
    return isinstance(func, ast.Attribute) and func.attr == _PRINT and isinstance(func.value, ast.Name) and func.value.id == _CONSOLE


def _is_presentation(fn: ast.FunctionDef) -> bool:
    """Named like a presentation function, or structurally one: takes ``outcome`` and prints."""
    if fn.name.startswith(_PRESENTATION_PREFIXES):
        return True
    return _OUTCOME_NAME in _parameter_names(fn) and any(_is_print_call(node) for node in ast.walk(fn))


def _presentation_functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [fn for fn in _functions(tree) if _is_presentation(fn)]


def presentation_function_names(source: str) -> set[str]:
    """Names of the presentation functions the checkers visit."""
    return {fn.name for fn in _presentation_functions(ast.parse(source))}


def closing_constants(outcome_source: str) -> dict[str, str]:
    """Module-level ``_CLOSING_*`` string constants of the outcome module, by name."""
    found: dict[str, str] = {}
    for node in ast.parse(outcome_source).body:
        target: ast.expr | None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id.startswith(_CLOSING_PREFIX) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            found[target.id] = value.value
    return found


def closing_fragments(constants: Mapping[str, str]) -> set[str]:
    """Distinguishing lowercase fragments: the literal text between format fields, plus the pinned ones."""
    fragments = set(_PINNED_FRAGMENTS)
    for text in constants.values():
        for piece in _literal_pieces(text):
            if len(piece) >= _MIN_FRAGMENT_LENGTH:
                fragments.add(piece.lower())
    return fragments


def _literal_pieces(template: str) -> list[str]:
    """Split a ``str.format`` template on its ``{...}`` fields and strip each literal piece."""
    pieces: list[str] = []
    current: list[str] = []
    depth = 0
    for char in template:
        if char == "{":
            depth += 1
            if depth == 1:
                pieces.append("".join(current))
                current = []
        elif char == "}" and depth:
            depth -= 1
        elif depth == 0:
            current.append(char)
    pieces.append("".join(current))
    return [piece.strip(" (") for piece in pieces if piece.strip(" (")]


def find_closing_text_leaks(source: str, fragments: set[str]) -> list[str]:
    """Rule 1a: any string constant (docstrings and f-string parts included) holding closing text."""
    leaks: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            leaks.extend(f"line {node.lineno}: string holds closing text {fragment!r}" for fragment in sorted(fragments) if fragment in lowered)
    return leaks


def _json_builders(tree: ast.AST) -> list[ast.FunctionDef]:
    return [fn for fn in _functions(tree) if fn.name.startswith("_build_") and fn.name.endswith(_JSON_BUILDER_SUFFIX)]


def _is_outcome_call(node: ast.AST, method: str) -> bool:
    """``outcome.<method>()`` with no arguments."""
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == _OUTCOME_NAME
    )


def _subscript_stores(fn: ast.FunctionDef, keys: frozenset[str]) -> list[tuple[str, int]]:
    """``(key, line)`` of each ``payload["<key>"] = ...`` (plain, augmented or annotated) for a key in *keys*."""
    return [
        (node.slice.value, node.lineno)
        for node in ast.walk(fn)
        if isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
        and node.slice.value in keys
    ]


def find_status_violations(source: str) -> list[str]:
    """Rule 1b: each JSON builder takes ``status``, ``errors`` and ``warnings`` from the outcome."""
    violations: list[str] = []
    for fn in _json_builders(ast.parse(source)):
        returned = [node.value for node in ast.walk(fn) if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)]
        for key_name, is_expected, expected in _JSON_OUTCOME_KEYS:
            values = [
                value
                for dict_node in returned
                for key, value in zip(dict_node.keys, dict_node.values, strict=True)
                if isinstance(key, ast.Constant) and key.value == key_name
            ]
            if not values:
                violations.append(f"{fn.name}: no {key_name!r} key found")
            violations.extend(f"{fn.name}: {key_name!r} is not {expected} (line {value.lineno})" for value in values if not is_expected(value))
        violations.extend(
            f"{fn.name}: assigns {key!r} by subscript (line {line}); build it in the returned dict from the outcome"
            for key, line in _subscript_stores(fn, _JSON_OUTCOME_KEY_NAMES)
        )
    return violations


def _is_outcome_attribute(node: ast.AST, attr: str) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == attr and isinstance(node.value, ast.Name) and node.value.id == _OUTCOME_NAME


# (key, predicate on the value, how the value must read) for the JSON fields the outcome owns.
_JSON_OUTCOME_KEYS: tuple[tuple[str, Callable[[ast.AST], bool], str], ...] = (
    ("status", lambda node: _is_outcome_attribute(node, "status"), "outcome.status"),
    ("errors", lambda node: _is_outcome_call(node, "errors"), "the call outcome.errors()"),
    ("warnings", lambda node: _is_outcome_call(node, "warnings"), "the call outcome.warnings()"),
)
_JSON_OUTCOME_KEY_NAMES = frozenset(key for key, _, _ in _JSON_OUTCOME_KEYS)


def _called_names(fn: ast.FunctionDef) -> set[str]:
    return {node.func.id for node in ast.walk(fn) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def _calls_closing_line(fn: ast.FunctionDef) -> bool:
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == _CLOSING_LINE_METHOD for node in ast.walk(fn))


def find_closing_line_violations(source: str) -> list[str]:
    """Rule 1c: the tail renderer reaches a ``closing_line()`` call through module functions."""
    by_name = {fn.name: fn for fn in _functions(ast.parse(source))}
    start = by_name.get(_TAIL_RENDERER)
    if start is None:
        return [f"{_TAIL_RENDERER} not found"]
    seen: set[str] = set()
    queue: deque[ast.FunctionDef] = deque([start])
    while queue:
        fn = queue.popleft()
        if fn.name in seen:
            continue
        seen.add(fn.name)
        if _calls_closing_line(fn):
            return []
        queue.extend(by_name[name] for name in sorted(_called_names(fn)) if name in by_name)
    return [f"{_TAIL_RENDERER} never reaches a {_CLOSING_LINE_METHOD}() call"]


def _call_receivers(fn: ast.FunctionDef) -> set[int]:
    """Ids of attribute nodes used as the callee of a call (``outcome.errors()``)."""
    return {id(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


def _getattr_of_message(node: ast.Call) -> str | None:
    """The message attribute name when *node* is ``getattr(<x>, "<message attribute>"[, default])``."""
    if not (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2):
        return None
    name = node.args[1]
    if isinstance(name, ast.Constant) and isinstance(name.value, str) and name.value in _MESSAGE_ATTRIBUTES:
        return name.value
    return None


def find_message_assembly_violations(source: str) -> list[str]:
    """Rule 2: presentation functions read no message state directly and take no error/success parameter."""
    violations: list[str] = []
    for fn in _presentation_functions(ast.parse(source)):
        called = _call_receivers(fn)
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr in _MESSAGE_ATTRIBUTES and id(node) not in called:
                violations.append(f"{fn.name}: reads .{node.attr} (line {node.lineno}); call outcome.errors()/warnings() instead")
            elif isinstance(node, ast.Call) and (fetched := _getattr_of_message(node)) is not None:
                violations.append(f"{fn.name}: fetches {fetched!r} with getattr (line {node.lineno}); call outcome.errors()/warnings() instead")
        violations.extend(f"{fn.name}: takes a parameter named {name!r}" for name in _parameter_names(fn) if name in _FORBIDDEN_PARAMETERS)
    return violations


def _exit_kind(node: ast.AST) -> str | None:
    """Classify a raise or call as an exit.

    ``'typer'`` for ``typer.Exit``/``Exit``, ``'sys'`` for ``sys.exit``, ``'os'`` for
    ``os._exit`` and ``'system'`` for ``SystemExit``; ``None`` for anything else.
    """
    target = node.exc if isinstance(node, ast.Raise) else node
    if isinstance(target, ast.Call):
        target = target.func
    if isinstance(target, ast.Attribute) and target.attr == "Exit":
        return "typer"
    if isinstance(target, ast.Name) and target.id == "Exit":
        return "typer"
    if isinstance(target, ast.Name) and target.id == "SystemExit":
        return "system"
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        if target.attr == "exit" and target.value.id == "sys":
            return "sys"
        if target.attr == "_exit" and target.value.id == "os":
            return "os"
    return None


def _is_outcome_exit(node: ast.Raise) -> bool:
    exc = node.exc
    return isinstance(exc, ast.Call) and _exit_kind(node) == "typer" and not exc.keywords and len(exc.args) == 1 and _is_outcome_attribute(exc.args[0], "exit_code")


def _exits_in(nodes: list[ast.stmt]) -> Iterator[ast.Raise | ast.Call]:
    for stmt in nodes:
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Raise) and _exit_kind(node) is not None) or (isinstance(node, ast.Call) and _exit_kind(node) in _CALL_EXITS):
                yield node


def _guarded_outcome_exits(nodes: list[ast.stmt]) -> set[int]:
    """Ids of the ``raise typer.Exit(outcome.exit_code)`` statements sitting directly in the body of an ``if`` testing ``outcome.exit_code``."""
    guarded: set[int] = set()
    for stmt in nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.If) and any(_is_outcome_attribute(part, "exit_code") for part in ast.walk(node.test)):
                guarded.update(id(child) for child in node.body if isinstance(child, ast.Raise) and _is_outcome_exit(child))
    return guarded


def count_outcome_exits(source: str) -> int:
    """How many ``typer.Exit(outcome.exit_code)`` raises follow the finalizer call in ``upgrade()``."""
    tail = _tail_after_finalizer(source)
    return sum(1 for node in _exits_in(tail or []) if isinstance(node, ast.Raise) and _is_outcome_exit(node))


def _tail_after_finalizer(source: str) -> list[ast.stmt] | None:
    command = next((fn for fn in _functions(ast.parse(source)) if fn.name == _COMMAND), None)
    if command is None:
        return None
    for index, stmt in enumerate(command.body):
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == _FINALIZE_CALL for n in ast.walk(stmt)):
            return command.body[index + 1 :]
    return None


def find_exit_code_assignments(source: str) -> list[str]:
    """Rule 3: nothing in the command module assigns to an ``.exit_code`` attribute (plain, augmented, annotated, unpacked, ``setattr``)."""
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == _EXIT_CODE and isinstance(node.ctx, ast.Store):
            violations.append(f"assigns .{_EXIT_CODE} (line {node.lineno}); only derive_exit_code may")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == _EXIT_CODE
        ):
            violations.append(f"sets .{_EXIT_CODE} with setattr (line {node.lineno}); only derive_exit_code may")
    return violations


def find_exit_site_violations(source: str) -> list[str]:
    """Rule 3 (command side): one guarded exit after the finalizer, no exit-code writes, and presentation functions never exit."""
    violations: list[str] = []
    tail = _tail_after_finalizer(source)
    if tail is None:
        violations.append(f"{_COMMAND}() or its {_FINALIZE_CALL} call not found")
    else:
        guarded = _guarded_outcome_exits(tail)
        for node in _exits_in(tail):
            if not (isinstance(node, ast.Raise) and _is_outcome_exit(node)):
                violations.append(f"{_COMMAND}(): exit after {_FINALIZE_CALL} is not typer.Exit(outcome.exit_code) (line {node.lineno})")
            elif id(node) not in guarded:
                violations.append(f"{_COMMAND}(): typer.Exit(outcome.exit_code) is not directly under a test of outcome.exit_code (line {node.lineno})")
    violations.extend(find_exit_code_assignments(source))
    for fn in _presentation_functions(ast.parse(source)):
        violations.extend(f"{fn.name}: presentation function exits (line {node.lineno})" for node in _exits_in(fn.body))
    return violations


def find_derive_calls(sources: Mapping[str, str]) -> list[str]:
    """Every ``derive_exit_code()`` call site in *sources* (path -> source), as ``path:line``."""
    sites: list[str] = []
    for path, source in sources.items():
        if _DERIVE not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == _DERIVE) or (isinstance(node.func, ast.Name) and node.func.id == _DERIVE)
            ):
                sites.append(f"{path}:{node.lineno}")
    return sites


def find_derive_site_violations(sources: Mapping[str, str]) -> list[str]:
    """Rule 3 (call side): exactly one call, and it is in the finalizer."""
    sites = find_derive_calls(sources)
    if len(sites) != 1:
        return [f"{_DERIVE} is called from {len(sites)} places, expected 1: {sites}"]
    if not sites[0].split(":")[0].endswith(_FINALIZER_SUFFIX):
        return [f"{_DERIVE} is called outside the finalizer: {sites[0]}"]
    return []


def _derive_function(tree: ast.AST) -> ast.FunctionDef | None:
    return next((fn for fn in _functions(tree) if fn.name == _DERIVE), None)


def derive_self_reads(source: str) -> set[str] | None:
    """Attributes ``derive_exit_code`` loads from ``self`` (``None`` if it is absent).

    The ``exit_code`` it returns right after storing it is not a read of another
    field, so a direct ``return self.exit_code`` is left out.
    """
    fn = _derive_function(ast.parse(source))
    if fn is None:
        return None
    returned = {id(node.value) for node in ast.walk(fn) if isinstance(node, ast.Return) and node.value is not None}
    return {
        node.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and not (id(node) in returned and node.attr == "exit_code")
    }


def _exit_code_stores(fn: ast.FunctionDef) -> list[ast.expr | None]:
    """Value assigned to ``self.exit_code`` by each assignment in *fn* (``None`` for a bare annotation)."""

    def is_target(target: ast.expr) -> bool:
        return isinstance(target, ast.Attribute) and target.attr == _EXIT_CODE and isinstance(target.value, ast.Name) and target.value.id == "self"

    stored: list[ast.expr | None] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if any(is_target(target) for target in targets):
            stored.append(node.value)
    return stored


def _reads_self_kind(node: ast.expr | None) -> bool:
    return node is not None and any(
        isinstance(part, ast.Attribute) and part.attr == "kind" and isinstance(part.ctx, ast.Load) and isinstance(part.value, ast.Name) and part.value.id == "self"
        for part in ast.walk(node)
    )


def find_exit_derivation_violations(source: str) -> list[str]:
    """Rule 4: the exit code is a function of ``self.kind`` and nothing else."""
    reads = derive_self_reads(source)
    if reads is None:
        return [f"{_DERIVE} not found"]
    violations = [f"{_DERIVE} reads self.{name}" for name in sorted(reads - {"kind"})]
    if "kind" not in reads:
        violations.append(f"{_DERIVE} does not read self.kind")
    fn = _derive_function(ast.parse(source))
    assert fn is not None
    stored = _exit_code_stores(fn)
    if not stored:
        violations.append(f"{_DERIVE} never assigns self.{_EXIT_CODE}")
    violations.extend(f"{_DERIVE} assigns self.{_EXIT_CODE} a value that does not read self.kind" for value in stored if not _reads_self_kind(value))
    # ``self`` handed to another callable would hide a read from the check above.
    attribute_receivers = {id(node.value) for node in ast.walk(fn) if isinstance(node, ast.Attribute)}
    violations.extend(
        f"{_DERIVE} passes self on (line {node.lineno})"
        for node in ast.walk(fn)
        if isinstance(node, ast.Name) and node.id == "self" and id(node) not in attribute_receivers
    )
    return violations


# --------------------------------------------------------------------------- #
# Live scans
# --------------------------------------------------------------------------- #


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def src_sources() -> dict[str, str]:
    return {path.relative_to(_SRC_ROOT).as_posix(): _read(path) for path in sorted(_SRC_ROOT.rglob("*.py"))}


@pytest.fixture(scope="module")
def command_source() -> str:
    return _read(_UPGRADE_CMD)


@pytest.fixture(scope="module")
def outcome_source() -> str:
    return _read(_OUTCOME)


def _assert_clean(violations: list[str]) -> None:
    assert violations == [], "\n".join(violations)


class TestLiveCode:
    """The merged code satisfies every rule, with no allowlist."""

    def test_closing_text_lives_in_the_outcome_only(self, command_source: str, outcome_source: str) -> None:
        fragments = closing_fragments(closing_constants(outcome_source))
        _assert_clean(find_closing_text_leaks(command_source, fragments))

    def test_status_comes_from_the_outcome_and_the_tail_prints_its_closing_line(self, command_source: str) -> None:
        _assert_clean(find_status_violations(command_source))
        _assert_clean(find_closing_line_violations(command_source))

    def test_presentation_functions_assemble_no_messages(self, command_source: str) -> None:
        _assert_clean(find_message_assembly_violations(command_source))

    def test_one_exit_code_site(self, command_source: str, src_sources: dict[str, str]) -> None:
        _assert_clean(find_exit_site_violations(command_source))
        _assert_clean(find_derive_site_violations(src_sources))

    def test_exit_code_is_a_function_of_the_kind(self, outcome_source: str) -> None:
        _assert_clean(find_exit_derivation_violations(outcome_source))


class TestFloor:
    """A gate that scanned nothing would pass; prove it saw the real code."""

    def test_visits_the_real_renderers_and_builders(self, command_source: str) -> None:
        visited = presentation_function_names(command_source)
        assert {_TAIL_RENDERER, _SECTION_RENDERER} | _JSON_BUILDERS <= visited

    def test_finds_every_closing_constant_and_matches_the_runtime_values(self, outcome_source: str) -> None:
        parsed = closing_constants(outcome_source)
        assert len(parsed) >= _CLOSING_CONSTANT_FLOOR
        assert parsed == {name: getattr(outcome_module, name) for name in parsed}

    def test_derived_fragments_cover_every_closing_line(self, outcome_source: str) -> None:
        fragments = closing_fragments(closing_constants(outcome_source))
        assert set(_PINNED_FRAGMENTS) <= fragments
        assert "managed file(s) with local edits were not updated." in fragments

    def test_finds_the_exit_sites(self, command_source: str, outcome_source: str, src_sources: dict[str, str]) -> None:
        assert count_outcome_exits(command_source) == 1
        tail = _tail_after_finalizer(command_source)
        assert tail is not None
        assert len(_guarded_outcome_exits(tail)) == 1
        derive = _derive_function(ast.parse(outcome_source))
        assert derive is not None
        assert len(_exit_code_stores(derive)) == 1
        assert len(src_sources) >= _SCANNED_FILE_FLOOR
        assert len(find_derive_calls(src_sources)) == 1
        assert derive_self_reads(outcome_source) == {"kind"}


_FRAGMENTS = closing_fragments({"_CLOSING_X": "Project is already up to date!"})

_COMPLIANT_COMMAND = """
def _print_closing_line(outcome):
    console.print(outcome.closing_line())

def _render_outcome_tail(outcome):
    _print_closing_line(outcome)
    for message in outcome.errors():
        console.print(message)

def _build_x_json_payload(outcome):
    return {"status": outcome.status, "errors": outcome.errors(), "warnings": outcome.warnings()}

def upgrade():
    outcome = finalize_upgrade(outcome)
    if outcome.exit_code != 0:
        raise typer.Exit(outcome.exit_code)
"""

_COMPLIANT_OUTCOME = """
class UpgradeOutcome:
    def derive_exit_code(self):
        self.exit_code = 0 if self.kind in SUCCESS_KINDS else 1
        return self.exit_code
"""


class TestSelfMutation:
    """Each rule reports a synthetic violation and passes the compliant twin."""

    def test_compliant_twins_pass(self) -> None:
        assert find_closing_text_leaks(_COMPLIANT_COMMAND, _FRAGMENTS) == []
        assert find_status_violations(_COMPLIANT_COMMAND) == []
        assert find_closing_line_violations(_COMPLIANT_COMMAND) == []
        assert find_message_assembly_violations(_COMPLIANT_COMMAND) == []
        assert find_exit_site_violations(_COMPLIANT_COMMAND) == []
        assert find_exit_derivation_violations(_COMPLIANT_OUTCOME) == []
        assert count_outcome_exits(_COMPLIANT_COMMAND) == 1

    @pytest.mark.parametrize(
        "mutation",
        [
            'def _render_x(outcome):\n    console.print("Project is already up to date!")\n',
            'def _render_x(outcome):\n    console.print(f"[green]{name}: Upgrade complete! done[/green]")\n',
            'def helper():\n    """Prints Upgrade failed. when it goes wrong."""\n',
            'def helper():\n    return "UPGRADE FINISHED, BUT 2 MANAGED FILE(S) WITH LOCAL EDITS WERE NOT UPDATED."\n',
        ],
    )
    def test_rule_1_closing_text_outside_the_outcome(self, mutation: str) -> None:
        fragments = closing_fragments(
            {
                "_CLOSING_NO_OP": "Project is already up to date!",
                "_CLOSING_APPLIED": "Upgrade complete! {from_version} -> {to_version}",
                "_CLOSING_FAILED": "Upgrade failed.",
                "_CLOSING_DRIFT": "Upgrade finished, but {count} managed file(s) with local edits were not updated.",
            }
        )
        assert find_closing_text_leaks(mutation, fragments)

    def test_rule_1_status_must_be_the_outcome_attribute(self) -> None:
        conditional = _COMPLIANT_COMMAND.replace('"status": outcome.status', '"status": "success" if ok else "failed"')
        assert find_status_violations(conditional)
        local = _COMPLIANT_COMMAND.replace('"status": outcome.status', '"status": status')
        assert find_status_violations(local)
        missing = _COMPLIANT_COMMAND.replace('"status": outcome.status, ', "")
        assert find_status_violations(missing)

    @pytest.mark.parametrize(
        "replacement",
        [
            '"errors": list(outcome.result.errors), "warnings"',
            '"errors": outcome.errors, "warnings"',
            '"errors": errors, "warnings"',
            '"errors": outcome.errors()[:1], "warnings"',
            '"errors": outcome.errors(limit=1), "warnings"',
        ],
    )
    def test_rule_1_errors_must_be_the_outcome_errors_call(self, replacement: str) -> None:
        mutated = _COMPLIANT_COMMAND.replace('"errors": outcome.errors(), "warnings"', replacement)
        assert any("'errors' is not" in violation for violation in find_status_violations(mutated))

    @pytest.mark.parametrize(
        "replacement",
        [
            '"warnings": list(outcome.result.warnings)}',
            '"warnings": outcome.warnings}',
            '"warnings": []}',
            '"warnings": outcome.warnings() + extra}',
        ],
    )
    def test_rule_1_warnings_must_be_the_outcome_warnings_call(self, replacement: str) -> None:
        mutated = _COMPLIANT_COMMAND.replace('"warnings": outcome.warnings()}', replacement)
        assert any("'warnings' is not" in violation for violation in find_status_violations(mutated))

    @pytest.mark.parametrize("key", ["errors", "warnings"])
    def test_rule_1_errors_and_warnings_keys_are_required(self, key: str) -> None:
        value = f"outcome.{key}()"
        mutated = _COMPLIANT_COMMAND.replace(f', "{key}": {value}', "").replace(f'"{key}": {value}, ', "")
        assert any(f"no '{key}' key found" in violation for violation in find_status_violations(mutated))

    @pytest.mark.parametrize(
        "assignment",
        [
            'payload["status"] = "success"',
            'payload["status"] += "x"',
            'payload["status"]: str = "success"',
            'payload["errors"] = []',
            'payload["warnings"] = []',
        ],
    )
    def test_rule_1_outcome_fields_are_not_assigned_by_subscript(self, assignment: str) -> None:
        mutated = f"def _build_x_json_payload(outcome):\n    payload = {{}}\n    {assignment}\n    return payload\n"
        assert any("by subscript" in violation for violation in find_status_violations(mutated))

    def test_rule_1_other_subscript_assignments_are_out_of_scope(self) -> None:
        twin = _COMPLIANT_COMMAND.replace("    return {", '    extra = {}\n    extra["note"] = 1\n    return {', 1)
        assert find_status_violations(twin) == []

    def test_rule_1_tail_must_reach_closing_line(self) -> None:
        mutated = _COMPLIANT_COMMAND.replace("console.print(outcome.closing_line())", "console.print(outcome.kind)")
        assert find_closing_line_violations(mutated)
        assert find_closing_line_violations("def other():\n    pass\n")

    @pytest.mark.parametrize(
        "mutation",
        [
            "def _render_x(outcome):\n    for e in outcome.result.errors:\n        print(e)\n",
            "def _display_x(result):\n    for w in result.warnings:\n        print(w)\n",
            "def _build_x(outcome):\n    return list(outcome.activation_errors)\n",
            "def _render_x(outcome):\n    return outcome.worktree_failures\n",
            "def _render_x(outcome):\n    return len(outcome.drifted_paths)\n",
            "def _print_x(outcome):\n    return outcome.surface_repair_messages\n",
            "def _render_x(outcome, errors):\n    pass\n",
            "def _build_x(outcome, *, effective_success):\n    pass\n",
        ],
    )
    def test_rule_2_presentation_assembles_messages(self, mutation: str) -> None:
        assert find_message_assembly_violations(mutation)

    def test_rule_2_non_presentation_functions_are_out_of_scope(self) -> None:
        source = "def upgrade(outcome):\n    outcome.result.warnings.append('x')\n"
        assert find_message_assembly_violations(source) == []

    @pytest.mark.parametrize(
        "mutation",
        [
            "def emit_x(outcome):\n    console.print(outcome.result.errors)\n",
            "def emit_x(outcome):\n    for w in outcome.result.warnings:\n        print(w)\n",
            "def emit_x(outcome, verbose):\n    console.print(len(outcome.drifted_paths))\n",
            'def emit_x(outcome):\n    console.print(getattr(outcome.result, "errors", []))\n',
        ],
    )
    def test_rule_2_a_function_that_takes_the_outcome_and_prints_is_a_presentation_function(self, mutation: str) -> None:
        assert presentation_function_names(mutation) == {"emit_x"}
        assert find_message_assembly_violations(mutation)

    @pytest.mark.parametrize(
        "twin",
        [
            "def helper(outcome):\n    return outcome.result.errors\n",  # takes the outcome but prints nothing
            "def emit_x(result):\n    console.print(result.errors)\n",  # prints but takes no outcome
            "def emit_x(outcome):\n    log.print(outcome.result.errors)\n",  # not the console
            'def emit_x(outcome):\n    console.print(getattr(outcome, "kind"))\n',
        ],
    )
    def test_rule_2_the_structural_anchor_needs_both_the_outcome_parameter_and_a_print(self, twin: str) -> None:
        assert find_message_assembly_violations(twin) == []

    @pytest.mark.parametrize(
        "mutation",
        [
            'def _render_x(outcome):\n    return getattr(outcome, "warnings")\n',
            'def _build_x(outcome):\n    return getattr(outcome.result, "errors", [])\n',
            'def _print_x(outcome):\n    return getattr(outcome, "drifted_paths", ())\n',
        ],
    )
    def test_rule_2_getattr_of_a_message_attribute_is_reported(self, mutation: str) -> None:
        assert any("getattr" in violation for violation in find_message_assembly_violations(mutation))

    def test_rule_2_getattr_of_anything_else_passes(self) -> None:
        twin = 'def _render_x(outcome):\n    return getattr(outcome, "kind")\n'
        assert find_message_assembly_violations(twin) == []

    @pytest.mark.parametrize(
        "replacement",
        [
            "raise typer.Exit(1)",
            "raise typer.Exit(code)",
            "raise typer.Exit()",
            "raise typer.Exit(outcome.result.success)",
            "sys.exit(outcome.exit_code)",
            "raise SystemExit(outcome.exit_code)",
            "raise SystemExit",
            "os._exit(outcome.exit_code)",
        ],
    )
    def test_rule_3_command_exit_must_be_the_outcome_exit_code(self, replacement: str) -> None:
        mutated = _COMPLIANT_COMMAND.replace("raise typer.Exit(outcome.exit_code)", replacement)
        assert find_exit_site_violations(mutated)

    @pytest.mark.parametrize(
        "extra_exit",
        ["raise typer.Exit(2)", "raise SystemExit(2)", "raise SystemExit", "sys.exit(2)", "os._exit(2)"],
    )
    def test_rule_3_a_second_exit_after_the_finalizer_is_reported(self, extra_exit: str) -> None:
        mutated = _COMPLIANT_COMMAND + f"    {extra_exit}\n"
        assert find_exit_site_violations(mutated)

    @pytest.mark.parametrize(
        "exit_statement",
        [
            "raise SystemExit(1)",
            "sys.exit(1)",
            "os._exit(1)",
            "raise typer.Exit(1)",
        ],
    )
    def test_rule_3_presentation_function_with_any_kind_of_exit_is_reported(self, exit_statement: str) -> None:
        mutated = _COMPLIANT_COMMAND + f"\ndef _render_y(outcome):\n    {exit_statement}\n"
        assert any("presentation function exits" in violation for violation in find_exit_site_violations(mutated))

    @pytest.mark.parametrize(
        "guard",
        [
            "raise typer.Exit(outcome.exit_code)",  # unconditional
            "if ready:\n        raise typer.Exit(outcome.exit_code)",  # tests something else
            "if outcome.exit_code != 0:\n        pass\n    else:\n        raise typer.Exit(outcome.exit_code)",  # wrong branch
            "if outcome.exit_code != 0:\n        if ready:\n            raise typer.Exit(outcome.exit_code)",  # not directly under
            "for _ in range(1):\n        raise typer.Exit(outcome.exit_code)",
        ],
    )
    def test_rule_3_the_outcome_exit_must_sit_directly_under_a_test_of_the_exit_code(self, guard: str) -> None:
        mutated = _COMPLIANT_COMMAND.replace("if outcome.exit_code != 0:\n        raise typer.Exit(outcome.exit_code)", guard)
        assert any("not directly under a test of outcome.exit_code" in violation for violation in find_exit_site_violations(mutated))

    def test_rule_3_other_tests_of_the_exit_code_still_guard_the_exit(self) -> None:
        for test in ("outcome.exit_code", "outcome.exit_code > 0", "bool(outcome.exit_code)", "ready and outcome.exit_code != 0"):
            twin = _COMPLIANT_COMMAND.replace("outcome.exit_code != 0", test)
            assert find_exit_site_violations(twin) == [], test

    @pytest.mark.parametrize(
        "assignment",
        [
            "outcome.exit_code = 0",
            "outcome.exit_code += 1",
            "outcome.exit_code: int = 0",
            "result.exit_code, other = 0, 1",
            "for outcome.exit_code in (0,):\n        pass",
            'setattr(outcome, "exit_code", 0)',
        ],
    )
    def test_rule_3_assigning_an_exit_code_in_the_command_module_is_reported(self, assignment: str) -> None:
        in_command = _COMPLIANT_COMMAND + f"    {assignment}\n"
        elsewhere = _COMPLIANT_COMMAND + f"\ndef helper(outcome, result):\n    {assignment}\n"
        for mutated in (in_command, elsewhere):
            assert find_exit_code_assignments(mutated)
            assert find_exit_site_violations(mutated)

    def test_rule_3_reading_or_naming_an_exit_code_is_not_an_assignment(self) -> None:
        twin = _COMPLIANT_COMMAND + "\ndef helper(outcome):\n    code = outcome.exit_code\n    exit_code = 1\n    return code, exit_code\n"
        assert find_exit_code_assignments(twin) == []

    def test_rule_3_presentation_function_that_exits_is_reported(self) -> None:
        mutated = _COMPLIANT_COMMAND + "\ndef _render_y(outcome):\n    raise typer.Exit(outcome.exit_code)\n"
        assert find_exit_site_violations(mutated)

    def test_rule_3_missing_finalizer_call_is_reported(self) -> None:
        assert find_exit_site_violations("def upgrade():\n    pass\n")

    def test_rule_3_derive_call_sites(self) -> None:
        finalizer = f"{_FINALIZER_SUFFIX}"
        call = "def f(outcome):\n    outcome.derive_exit_code()\n"
        assert find_derive_site_violations({finalizer: call}) == []
        assert find_derive_site_violations({finalizer: call, "specify_cli/cli/commands/upgrade.py": call})
        assert find_derive_site_violations({"specify_cli/cli/commands/upgrade.py": call})
        assert find_derive_site_violations({finalizer: "def f():\n    pass\n"})

    @pytest.mark.parametrize(
        "body",
        [
            "self.exit_code = 0 if self.result.success else 1\n        return self.exit_code",
            "self.exit_code = 0 if self.kind in SUCCESS_KINDS and self.effective_success else 1\n        return self.exit_code",
            "self.exit_code = compute(self)\n        return self.exit_code",
            "self.exit_code = 1\n        return self.exit_code",
            "self.exit_code = 0 if self.kind in SUCCESS_KINDS else 1\n        return self.committed",
        ],
    )
    def test_rule_4_exit_code_reads_more_than_the_kind(self, body: str) -> None:
        source = f"class UpgradeOutcome:\n    def derive_exit_code(self):\n        {body}\n"
        assert find_exit_derivation_violations(source)

    @pytest.mark.parametrize(
        "body",
        [
            "_ = self.kind\n        self.exit_code = 1\n        return self.exit_code",
            "_ = self.kind\n        self.exit_code = 0\n        return self.exit_code",
            "_ = self.kind\n        self.exit_code = int(False)\n        return self.exit_code",
            "_ = self.kind\n        self.exit_code: int = 1\n        return self.exit_code",
            "_ = self.kind\n        self.exit_code = 0 if self.kind in SUCCESS_KINDS else 1\n        self.exit_code = 1\n        return self.exit_code",
        ],
    )
    def test_rule_4_the_stored_exit_code_must_be_computed_from_the_kind(self, body: str) -> None:
        source = f"class UpgradeOutcome:\n    def derive_exit_code(self):\n        {body}\n"
        assert any("value that does not read self.kind" in violation for violation in find_exit_derivation_violations(source))

    def test_rule_4_an_exit_code_that_is_never_stored_is_reported(self) -> None:
        source = "class UpgradeOutcome:\n    def derive_exit_code(self):\n        return 0 if self.kind in SUCCESS_KINDS else 1\n"
        assert any("never assigns self.exit_code" in violation for violation in find_exit_derivation_violations(source))

    def test_rule_4_an_annotated_assignment_computed_from_the_kind_passes(self) -> None:
        body = "self.exit_code: int = 0 if self.kind in SUCCESS_KINDS else 1\n        return self.exit_code"
        source = f"class UpgradeOutcome:\n    def derive_exit_code(self):\n        {body}\n"
        assert find_exit_derivation_violations(source) == []

    def test_rule_4_missing_function_is_reported(self) -> None:
        assert find_exit_derivation_violations("class UpgradeOutcome:\n    pass\n")

    def test_authority_parse_reads_the_closing_constants_at_run_time(self) -> None:
        reworded = '_CLOSING_NO_OP = "Nothing left to do for this project."\n_CLOSING_FAILED = "Upgrade failed."\n'
        fragments = closing_fragments(closing_constants(reworded))
        assert "nothing left to do for this project." in fragments
        leak = 'def _render_x(outcome):\n    console.print("Nothing left to do for this project.")\n'
        assert find_closing_text_leaks(leak, fragments)
        assert closing_constants("X = 1\n") == {}
