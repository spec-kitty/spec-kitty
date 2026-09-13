"""Guard the consolidated runtime emitter seam (ADR 2026-09-06-2).

Three regressions mission ``dead-port-disposition-01M1VRA2`` closed must stay
closed by construction (contracts ``emitter-seam.md`` S7-S8 and
``decision-log-flush.md`` F7):

1. a second class named ``RuntimeEventEmitter`` under ``src/runtime/next/``
   (the concrete duplicate that shadowed the canonical Protocol);
2. any import of the deleted ``runtime.next.event_emitter`` module;
3. an engine-facing reference to the plain seam in the bridge -- handing the
   flush target or the composition emitter ``ctx.sync_emitter`` instead of
   ``ctx.emitter_for_engine`` bypasses the decision-log wrapper and silently
   drops decision events.

The guard reads source text only; it must never import the runtime.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_ADR = "docs/adr/3.x/2026-09-06-2-runtime-event-emitter-disposition.md"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_NEXT = _REPO_ROOT / "src" / "runtime" / "next"
_BRIDGE = _RUNTIME_NEXT / "runtime_bridge.py"
_CANONICAL_SEAM = "src/runtime/next/_internal_runtime/events.py"
_THIS_FILE = Path(__file__).resolve()

_SEAM_CLASS_RE = re.compile(r"^class RuntimeEventEmitter\b", re.MULTILINE)
_DELETED_MODULE_IMPORT_RE = re.compile(r"runtime\.next\.event_emitter\b|from runtime\.next import event_emitter\b")

# Engine-facing bridge call sites that must receive the decision-log-wrapping
# ``ctx.emitter_for_engine``; passing the plain seam reintroduces the bypass.
_BRIDGE_BYPASS_NEEDLES = ("flush(ctx.sync_emitter)", "sync_emitter=ctx.sync_emitter")

# The ADR's headline scope boundary: "no live producer is wired". A second
# call site of this name under src/ would be exactly that -- a producer
# registering itself -- so the invariant is "this text appears in exactly
# one file", not "this text never appears" (the definition and its own
# illustrative comment both live in the canonical seam module).
#
# THIS GATE IS A TRIPWIRE, NOT A PROHIBITION -- and it has a planned exit.
# The ADR's ADR-BLOCKED list bound *Mission B* (`dead-port-disposition`),
# which is merged and closed; it is not a standing ban on ever wiring a
# producer. Wiring one is exactly what E3 (spec-kitty#3929) is for. E3 took
# that exit: the one planned production registration site is the status
# seam's ``ensure_zeitgeist_moment_handlers``, which registers
# ``specify_cli.events.runtime_moments.RuntimeMomentProducer``. The gate stays
# and still catches an *unplanned* third site.
_PLANNED_PRODUCER_REGISTRATION_SITE = "src/specify_cli/status/adapters.py"
_ALLOWED_REGISTRATION_SITES: tuple[str, ...] = (_CANONICAL_SEAM, _PLANNED_PRODUCER_REGISTRATION_SITE)

# Matched as a regex, not a bare substring, so ``name (args)`` and stray
# whitespace do not slip past; ``_registration_sites`` additionally resolves
# ``from ... import register_runtime_emitter_factory as _alias`` so an
# aliased import tail -- a common way to keep the public name out of a
# producer's namespace -- cannot register invisibly.
_REGISTRATION_NAME = "register_runtime_emitter_factory"
_REGISTRATION_CALL_RE = re.compile(rf"\b{_REGISTRATION_NAME}\s*\(")
_REGISTRATION_ALIAS_RE = re.compile(rf"\b{_REGISTRATION_NAME}\s+as\s+(\w+)")


def _py_files(root: Path) -> list[Path]:
    """Every ``.py`` file under ``root``, skipping virtualenvs and this guard."""
    return [p for p in sorted(root.rglob("*.py")) if ".venv" not in p.parts and p.resolve() != _THIS_FILE]


def _relative(path: Path) -> str:
    """Repo-relative posix path; falls back to the absolute path for a file outside the repo (a scratch copy)."""
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _seam_class_definitions(root: Path) -> list[str]:
    return [_relative(p) for p in _py_files(root) if _SEAM_CLASS_RE.search(p.read_text(encoding="utf-8"))]


def _deleted_module_importers(*roots: Path) -> list[str]:
    files = [p for root in roots for p in _py_files(root)]
    return [_relative(p) for p in files if _DELETED_MODULE_IMPORT_RE.search(p.read_text(encoding="utf-8"))]


def _bridge_bypass_hits(bridge_source: str, needle: str) -> list[int]:
    calls = [node for node in ast.walk(ast.parse(bridge_source)) if isinstance(node, ast.Call)]
    if needle.startswith("flush"):
        return [
            call.lineno
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "flush"
            and any(ast.unparse(arg) == "ctx.sync_emitter" for arg in [*call.args, *(kw.value for kw in call.keywords if kw.arg == "target")])
        ]
    return [call.lineno for call in calls if any(kw.arg == "sync_emitter" and ast.unparse(kw.value) == "ctx.sync_emitter" for kw in call.keywords)]


def _bridge_function(source: str, name: str) -> ast.FunctionDef:
    """Require the production entry point, rather than matching its mention."""
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert [node.name for node in functions] == [name], f"missing or duplicate bridge function {name}; see {_ADR}"
    return functions[0]


def _registration_call_in(source: str) -> bool:
    """True if ``source`` calls the registry -- directly or via an alias."""
    if _REGISTRATION_CALL_RE.search(source):
        return True
    return any(re.search(rf"\b{re.escape(alias)}\s*\(", source) for alias in _REGISTRATION_ALIAS_RE.findall(source))


def _registration_sites(root: Path) -> list[str]:
    return [_relative(p) for p in _py_files(root) if _registration_call_in(p.read_text(encoding="utf-8"))]


def test_exactly_one_runtime_event_emitter_class() -> None:
    """S7: exactly one ``RuntimeEventEmitter`` lives under ``src/runtime/next/``."""
    assert _seam_class_definitions(_RUNTIME_NEXT) == [_CANONICAL_SEAM], f"one canonical seam class only ({_CANONICAL_SEAM}); see {_ADR}"


def test_deleted_event_emitter_module_is_not_imported() -> None:
    """S7: ``runtime.next.event_emitter`` was deleted and must not be referenced."""
    offenders = _deleted_module_importers(_REPO_ROOT / "src", _REPO_ROOT / "tests")
    assert offenders == [], f"runtime.next.event_emitter was deleted; see {_ADR}: {offenders}"


def test_bridge_obtains_seam_only_through_factory() -> None:
    """S8: the bridge imports ``runtime_emitter_for_mission`` by name and never constructs a concrete class."""
    source = _BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "runtime.next._internal_runtime.events"
        and any(alias.name == "runtime_emitter_for_mission" and alias.asname is None for alias in node.names)
        for node in tree.body
    ), f"bridge must import the canonical factory by name; see {_ADR}"
    for name in ("_dn_bootstrap", "answer_decision_via_runtime"):
        assignments = [
            node
            for node in ast.walk(_bridge_function(source, name))
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "sync_emitter" for target in node.targets)
        ]
        assert [ast.unparse(node.value.func) if isinstance(node.value, ast.Call) else None for node in assignments] == ["runtime_emitter_for_mission"], (
            f"{name} must construct its seam once through the factory; see {_ADR}"
        )
    assert not any(isinstance(node, ast.Call) and ast.unparse(node.func) == "RuntimeEventEmitter" for node in ast.walk(tree)), (
        f"bridge must not construct the Protocol; see {_ADR}"
    )


@pytest.mark.parametrize("needle", _BRIDGE_BYPASS_NEEDLES)
def test_bridge_never_hands_engine_paths_the_plain_seam(needle: str) -> None:
    """F7: no engine-facing bridge call site receives the plain ``ctx.sync_emitter``."""
    source = _BRIDGE.read_text(encoding="utf-8")
    function_name = "_dn_decision_materialize" if needle.startswith("flush") else "_dn_composition_dispatch"
    calls = [node for node in ast.walk(_bridge_function(source, function_name)) if isinstance(node, ast.Call)]
    if needle.startswith("flush"):
        targets = [
            ast.unparse(call.args[0]) if call.args else next((ast.unparse(kw.value) for kw in call.keywords if kw.arg == "target"), None)
            for call in calls
            if isinstance(call.func, ast.Attribute) and call.func.attr == "flush"
        ]
    else:
        targets = [
            next((ast.unparse(kw.value) for kw in call.keywords if kw.arg == "sync_emitter"), None)
            for call in calls
            if isinstance(call.func, ast.Name) and call.func.id == "_advance_run_state_after_composition"
        ]
    assert targets == ["ctx.emitter_for_engine"], f"{function_name} must pass the wrapped emitter exactly once; see {_ADR}"
    hits = _bridge_bypass_hits(source, needle)
    assert hits == [], (
        f"{needle!r} at {_relative(_BRIDGE)}:{hits} reintroduces the decision-log bypass fixed by {_ADR}; engine-facing calls must use ctx.emitter_for_engine"
    )


def test_only_events_module_registers_the_runtime_emitter_factory() -> None:
    """ADR scope boundary: "no live producer is wired". The only file under
    ``src/`` that calls the registry is the seam's own module -- both the
    ``def`` and its illustrative registration-example comment live there.

    Removal trigger: E3 (spec-kitty#3929) wires a real producer. That is the
    boundary's planned exit, not a violation -- add the producer module to
    ``_ALLOWED_REGISTRATION_SITES`` rather than deleting this gate, which
    still catches an unplanned second registration site."""
    assert _registration_sites(_REPO_ROOT / "src") == list(_ALLOWED_REGISTRATION_SITES), (
        f"a registration site was added outside {list(_ALLOWED_REGISTRATION_SITES)}. If this is E3 "
        f"(spec-kitty#3929) wiring the planned producer, add it to _ALLOWED_REGISTRATION_SITES; "
        f"otherwise it is an unplanned live producer -- see {_ADR}"
    )


# --- helper self-checks (the guard's own branches, exercised on synthetic trees) ---


def test_seam_class_scan_reports_duplicates(tmp_path: Path) -> None:
    canonical = tmp_path / "src/runtime/next/_internal_runtime/events.py"
    duplicate = tmp_path / "src/runtime/next/event_emitter.py"
    for path in (canonical, duplicate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class RuntimeEventEmitter:\n    pass\n", encoding="utf-8")
    (tmp_path / "src/runtime/next/other.py").write_text("class RuntimeEventEmitterSpy:\n    pass\n", encoding="utf-8")
    hits = [p.relative_to(tmp_path).as_posix() for p in _py_files(tmp_path) if _SEAM_CLASS_RE.search(p.read_text(encoding="utf-8"))]
    assert hits == [_CANONICAL_SEAM, "src/runtime/next/event_emitter.py"]


def test_registration_site_scan_flags_a_second_site(tmp_path: Path) -> None:
    """Non-vacuity proof for ``test_only_events_module_registers_the_runtime_emitter_factory``:
    a synthetic tree with a second registration site must report both files,
    proving the scan actually detects a live producer rather than trivially
    passing on any input."""
    canonical = tmp_path / "src/runtime/next/_internal_runtime/events.py"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("def register_runtime_emitter_factory(factory):\n    ...\n", encoding="utf-8")
    producer = tmp_path / "src/runtime/next/_internal_runtime/some_producer.py"
    producer.write_text("register_runtime_emitter_factory(MyProducer.for_mission)\n", encoding="utf-8")
    hits = [p.relative_to(tmp_path).as_posix() for p in _py_files(tmp_path) if _registration_call_in(p.read_text(encoding="utf-8"))]
    assert hits == [_CANONICAL_SEAM, "src/runtime/next/_internal_runtime/some_producer.py"]


@pytest.mark.parametrize(
    "tail",
    [
        pytest.param("register_runtime_emitter_factory(P.for_mission)\n", id="direct"),
        pytest.param("register_runtime_emitter_factory (P.for_mission)\n", id="space-before-paren"),
        pytest.param(
            "from runtime.next._internal_runtime.events import register_runtime_emitter_factory as _reg\n_reg(P.for_mission)\n",
            id="aliased-import",
        ),
    ],
)
def test_registration_scan_catches_the_evasive_registration_forms(tail: str) -> None:
    """A producer that keeps the public name out of its namespace, or that
    merely spaces the call oddly, still registers a live producer -- the scan
    must see all three shapes, not just the obvious one."""
    assert _registration_call_in(tail)


def test_registration_scan_ignores_a_bare_mention_without_a_call() -> None:
    """Prose and imports that never call the registry are not sites."""
    assert not _registration_call_in("# see register_runtime_emitter_factory for the seam\n")
    assert not _registration_call_in("from runtime.next._internal_runtime.events import register_runtime_emitter_factory\n")


def test_relative_falls_back_to_absolute_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path / "runtime_bridge.py"
    assert _relative(_BRIDGE) == "src/runtime/next/runtime_bridge.py"
    assert _relative(outside) == outside.as_posix()


def test_deleted_module_regex_matches_both_import_forms() -> None:
    assert _DELETED_MODULE_IMPORT_RE.search("from runtime.next.event_emitter import RuntimeEventEmitter")
    assert _DELETED_MODULE_IMPORT_RE.search("from runtime.next import event_emitter")
    assert _DELETED_MODULE_IMPORT_RE.search("from runtime.next._internal_runtime.events import RuntimeEventEmitter") is None


@pytest.mark.parametrize("needle", _BRIDGE_BYPASS_NEEDLES)
def test_bridge_bypass_scan_locates_reintroduced_lines(needle: str) -> None:
    fixed = "def run(ctx):\n    buffer.flush(ctx.emitter_for_engine)\n    dispatch(sync_emitter=ctx.emitter_for_engine)\n"
    assert _bridge_bypass_hits(fixed, needle) == []
    reintroduced = fixed.replace("ctx.emitter_for_engine", "ctx.sync_emitter")
    assert _bridge_bypass_hits(reintroduced, needle) == [2 if needle.startswith("flush") else 3]


@pytest.mark.parametrize(
    ("before", "after", "guard"),
    [
        ("sync_emitter = runtime_emitter_for_mission(", "sync_emitter = NullEmitter.for_mission(", "factory"),
        ("sync_emitter = runtime_emitter_for_mission(", "unrelated = runtime_emitter_for_mission(", "factory"),
        ("buffer.flush(ctx.emitter_for_engine)", "buffer.flush(\n            ctx.sync_emitter\n        )", "flush"),
        ("buffer.flush(ctx.emitter_for_engine)", "buffer.discard()", "flush"),
        ("buffer.flush(ctx.emitter_for_engine)", "buffer.flush(target=ctx.sync_emitter)", "flush"),
        ("buffer.flush(ctx.emitter_for_engine)", "buffer.flush(ctx.emitter_for_engine); buffer.flush(ctx.emitter_for_engine)", "flush"),
        ("sync_emitter=ctx.emitter_for_engine", "sync_emitter = ctx.sync_emitter", "composition"),
        ("_advance_run_state_after_composition(\n", "replacement_advance(\n", "composition"),
    ],
)
def test_bridge_guards_reject_semantic_mutations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, before: str, after: str, guard: str) -> None:
    """Mutate real call sites: imports/comments cannot substitute for a call."""
    source = _BRIDGE.read_text(encoding="utf-8")
    assert before in source
    mutant = tmp_path / "runtime_bridge.py"
    mutant.write_text(source.replace(before, after), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "_BRIDGE", mutant)
    with pytest.raises(AssertionError):
        if guard == "factory":
            test_bridge_obtains_seam_only_through_factory()
        else:
            test_bridge_never_hands_engine_paths_the_plain_seam("flush(ctx.sync_emitter)" if guard == "flush" else "sync_emitter=ctx.sync_emitter")


@pytest.mark.parametrize("target", ["\n            ctx.emitter_for_engine,\n        ", "target=ctx.emitter_for_engine"])
def test_bridge_guards_accept_equivalent_call_formatting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """Formatting and positional-to-keyword changes preserve the seam contract."""
    source = _BRIDGE.read_text(encoding="utf-8")
    rewritten = source.replace("buffer.flush(ctx.emitter_for_engine)", f"buffer.flush({target})").replace(
        "sync_emitter=ctx.emitter_for_engine", "sync_emitter = ctx.emitter_for_engine"
    )
    bridge = tmp_path / "runtime_bridge.py"
    bridge.write_text(rewritten, encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "_BRIDGE", bridge)
    test_bridge_obtains_seam_only_through_factory()
    for needle in _BRIDGE_BYPASS_NEEDLES:
        test_bridge_never_hands_engine_paths_the_plain_seam(needle)
