"""FR-011 non-vacuous closed-by-construction gate (mission
``cli-error-surface-seam-01M2WJD2``, #4746/#2899, WP08/T028-T030).

Asserts the mission's capstone invariant, and only that invariant
(``contracts/error-envelope.md`` INV-4 + ``contracts/guarded-read-primitive.md``):

1. **Hook registration** — the global Typer error-presentation hook
   (``specify_cli._run_app_with_error_hook``, WP01) is wired into the real
   top-level ``main()`` entry point, and actually intercepts a
   ``GuardedReadError`` raised by a command.
2. **No unguarded raw read** — none of the in-scope command/reader modules
   (the corrected WP02-WP07 adoption list, per the binding squad amendment)
   reaches a raw file read/decode call (``open``, ``Path.read_text``,
   ``Path.read_bytes``, ``json.load``/``loads``, ``yaml.safe_load``, a local
   ``ruamel.yaml.YAML()`` instance's ``.load(...)``, ``tomllib.load``/
   ``loads``) outside :func:`kernel.guarded_read.read_guarded`, beyond a
   concrete, individually-justified, shrink-only baseline recorded in
   ``tests/architectural/_baselines.yaml`` under this test's own key.

Per DIRECTIVE_043 / charter Standing Order #5, a gate that cannot fail is
not a gate: ``test_gate_fails_when_hook_registration_removed``,
``test_gate_fails_when_hook_removed_from_invocation_path``, and
``test_gate_fails_when_unguarded_read_introduced`` are the non-vacuity
proof — each demonstrates the exact check above would have caught the
regression it targets.

The floor below is SCAN-DERIVED (run ``find_unguarded_raw_reads`` from
``_gate_guarded_read_callshape.py`` over the in-scope module list — see
this file's own history for the reproduction command), not assumed zero:
the hardened tree still carries 7 individually-justified raw reads that
legitimately do not route through the primitive (config reads that
degrade to a safe default rather than raising, and one legacy
size-capped read that predates the primitive). None of the 7 in-scope
command entry points named by the mission's user stories reach an
*unguarded* read that would surface a raw traceback.

**Known, documented, out-of-band residual (WP07) — NOT part of this
scan's raw-read-call detection, mentioned here per the WP08 binding
amendment's "account for it explicitly":**
``core/wps_manifest.py``'s ``WpsManifest.model_validate(raw)`` (inside
``_parse_wps_manifest``, itself covered by ``read_guarded``'s one-hop
exemption) can raise a bare ``pydantic.ValidationError`` for a
schema-invalid-but-syntactically-valid manifest. ``read_guarded``'s
``errors=`` tuple for this call site intentionally omits it —
``pydantic-core`` is a Rust extension type whose ``__new__`` cannot accept
``GuardedReadError``'s ``path``/``reason`` keyword-only constructor
contract (D3: "subclass, never flat-replace"), so re-parenting it is not
practical. See ``WpsManifestReadError``'s own docstring. This is not a
raw *read/decode call* (nothing in the callee set this gate scans for),
so it is invisible to Part (2)'s AST walker by construction; it is
recorded here, in prose, so a future reader does not mistake the gate's
silence on it for an oversight.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import typer

from kernel.errors import GuardedReadError
from tests.architectural._gate_guarded_read_callshape import find_unguarded_raw_reads

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SRC = Path(__file__).resolve().parents[2] / "src"
_ERROR_HOOK_NAME = "_run_app_with_error_hook"

# ---------------------------------------------------------------------------
# In-scope module universe (WP08 binding amendment — the corrected list; see
# tasks/WP08-construction-gate.md's squad amendment #1). Deliberately finite
# and named: the CLI command entry points WP02-WP07 hardened, plus the 7
# WP07 audit-tail readers. A repo-wide scan would flag pre-existing,
# out-of-mission-scope raw reads and produce a gate red for reasons this
# mission never touched.
# ---------------------------------------------------------------------------
_IN_SCOPE_MODULES: tuple[str, ...] = (
    "specify_cli/cli/commands/workflow.py",
    "specify_cli/cli/commands/mission_type.py",
    "specify_cli/cli/commands/accept.py",
    "specify_cli/cli/commands/agent/release.py",
    "specify_cli/release/payload.py",
    "specify_cli/cli/commands/intake.py",
    "specify_cli/intake/scanner.py",
    "specify_cli/cli/commands/lifecycle.py",
    "specify_cli/decisions/service.py",
    "specify_cli/merge/state.py",
    "specify_cli/review/baseline.py",
    "specify_cli/review/lock.py",
    "specify_cli/review/artifacts.py",
    "specify_cli/status/validate.py",
    "specify_cli/core/wps_manifest.py",
)

# ---------------------------------------------------------------------------
# Shrink-only floor (tests/architectural/_baselines.yaml ::
# test_cli_error_surface_seam.justified_raw_read_residuals). Each entry is
# ``"<module>::<function>"`` for a raw read/decode call this scan finds
# outside read_guarded's one-hop coverage, individually justified because it
# legitimately cannot route through the primitive. Growth beyond this exact
# set means either a NEW unguarded read (fix it) or a genuinely new
# exception (argue it here AND bump the YAML baseline in the same PR).
# ---------------------------------------------------------------------------
_JUSTIFIED_RESIDUALS: frozenset[str] = frozenset(
    {
        # .kittify/config.yaml reads with a graceful safe-default fallback on
        # ANY exception (see the surrounding `except Exception: return
        # DEFAULT`). read_guarded's contract is to RAISE a GuardedReadError
        # on failure; wrapping these would change behavior from "degrade to
        # a sane default" to "crash the command over an optional config
        # tweak" -- not a fix, a regression.
        "specify_cli/intake/scanner.py::load_max_brief_bytes",
        "specify_cli/intake/scanner.py::load_allow_cross_fs",
        # Hand-rolled guard (stat-before-open size cap, then read+decode)
        # that predates this mission's read_guarded primitive. Raises
        # IntakeFileMissingError/IntakeFileUnreadableError -- already a
        # kernel.errors.GuardedReadError subclass -- on every failure mode
        # read_guarded itself would catch. read_guarded's simple
        # open-then-parse API has no hook for the stat-based cap this
        # function enforces BEFORE opening the file, so it cannot be
        # expressed as a single read_guarded(...) call without dropping
        # that check.
        "specify_cli/intake/scanner.py::read_brief",
        # Parses already-captured subprocess STDOUT text (`capture.getvalue()`),
        # not a file on disk -- kernel.read_guarded operates on a Path and
        # does not apply. Malformed lines are skipped (`except
        # json.JSONDecodeError: continue`), never surfaced as a raw
        # traceback.
        "specify_cli/cli/commands/lifecycle.py::_create_mission_for_specify_json",
        # .kittify/config.yaml reads with a graceful degrade (falls through
        # to "no configured test command" / "no isolation strategy") on ANY
        # exception -- same class as the two intake reads above.
        "specify_cli/review/baseline.py::_get_test_command",
        "specify_cli/review/lock.py::_get_isolation_config",
        # Defensive plan.md scan (does plan.md mention any IC-## concern
        # heading?) that degrades to False on OSError. Not a mission
        # artifact whose corruption should abort the command -- an ordinary
        # heuristic read with a safe fallback, same class as the config
        # reads above.
        "specify_cli/core/wps_manifest.py::_plan_contains_implementation_concerns",
    }
)


def _read_hook_source(func: object) -> str:
    return inspect.getsource(func)  # type: ignore[arg-type]


def _source_calls_error_hook(source: str) -> bool:
    """True when *source* contains a call to the global error hook."""
    return f"{_ERROR_HOOK_NAME}(" in source


# ---------------------------------------------------------------------------
# Part (a) -- hook registration (INV-4)
# ---------------------------------------------------------------------------


def test_error_hook_is_wired_into_the_real_top_level_entry_point() -> None:
    """``main()`` (the real ``spec-kitty`` entry point) routes app invocation
    through the global error hook -- not a bespoke per-command emitter."""
    from specify_cli import main

    assert _source_calls_error_hook(_read_hook_source(main)), (
        f"`specify_cli.main` no longer calls `{_ERROR_HOOK_NAME}(...)`. INV-4 "
        "requires the hook be registered on the top-level app; a bespoke "
        "per-command emitter is not a substitute."
    )


def _make_throwaway_multi_command_app() -> typer.Typer:
    """A minimal multi-command app mirroring the real top-level app's shape
    closely enough for ``app()`` to behave identically (mirrors
    ``tests/specify_cli/test_error_hook.py``'s ``_make_app``): Typer
    collapses a SINGLE-command app to no-subcommand invocation, so at least
    two commands are needed for ``sys.argv``-based subcommand dispatch to
    exercise the same code path the real CLI uses."""
    app = typer.Typer()

    @app.command()
    def boom() -> None:
        raise GuardedReadError(path="bad.yaml", reason="workflow file is not valid")

    @app.command()
    def ok() -> None:
        print("fine")

    return app


def test_error_hook_actually_intercepts_a_guarded_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioral companion to the source check above: the hook function
    itself (not just a reference to its name) catches GuardedReadError and
    exits 1, per ``contracts/error-envelope.md``."""
    from specify_cli import _run_app_with_error_hook

    monkeypatch.setattr("sys.argv", ["prog", "boom"])
    app = _make_throwaway_multi_command_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Part (b) -- no unguarded raw read beyond the justified floor
# ---------------------------------------------------------------------------


def _scan_in_scope_modules() -> set[str]:
    violations: set[str] = set()
    for rel_path in _IN_SCOPE_MODULES:
        source = (_SRC / rel_path).read_text(encoding="utf-8")
        for func_name in find_unguarded_raw_reads(source):
            violations.add(f"specify_cli/{rel_path.split('specify_cli/', 1)[-1]}::{func_name}")
    return violations


def test_no_unguarded_raw_reads_beyond_the_justified_baseline() -> None:
    """Scan-derived: every raw read/decode call in the in-scope module list
    is either routed through ``kernel.guarded_read.read_guarded`` or is one
    of the 7 individually-justified residuals above. A NEW entry here is
    either a genuine regression (fix it) or a new legitimate exception
    (justify it above AND bump ``_baselines.yaml``)."""
    live = _scan_in_scope_modules()
    unexpected = live - _JUSTIFIED_RESIDUALS
    assert not unexpected, (
        "Unguarded raw read/decode call(s) found outside kernel.read_guarded, "
        f"not in the justified baseline: {sorted(unexpected)}. Either route "
        "the read through kernel.guarded_read.read_guarded, or add a "
        "`# justification:`-commented entry to `_JUSTIFIED_RESIDUALS` above "
        "and bump `_baselines.yaml::test_cli_error_surface_seam."
        "justified_raw_read_residuals` in the same PR."
    )


def test_in_scope_module_list_matches_reality() -> None:
    """Sanity: every named in-scope module must exist. A renamed/deleted
    module would otherwise silently drop out of the scan (an empty glob
    reads as "zero violations", which is a false green, not a real one)."""
    missing = [rel for rel in _IN_SCOPE_MODULES if not (_SRC / rel).is_file()]
    assert not missing, f"In-scope module(s) no longer exist at the named path: {missing}"


# ---------------------------------------------------------------------------
# Non-vacuity (DIRECTIVE_043 / charter Standing Order #5). Each test below
# proves ONE of the two checks above would have failed against the exact
# defect it targets -- not merely that "an exception was raised somewhere".
# ---------------------------------------------------------------------------


def test_gate_fails_when_hook_registration_removed() -> None:
    """Part (a) non-vacuity #1 (static): a `main()` whose body no longer
    calls the error hook is reported as unregistered by the exact check
    `test_error_hook_is_wired_into_the_real_top_level_entry_point` runs."""
    synthetic_main_without_hook = "def main() -> None:\n    app = _assemble_app()\n    app()\n"
    assert not _source_calls_error_hook(synthetic_main_without_hook), (
        "Non-vacuity failure: the hook-registration check did not detect a `main()` with the hook call removed -- it would pass a regressed tree."
    )


def test_gate_fails_when_hook_removed_from_invocation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Part (a) non-vacuity #2 (behavioral): invoking the SAME throwaway app
    WITHOUT going through `_run_app_with_error_hook` (simulating "hook
    registration removed" from the invocation path) lets GuardedReadError
    escape uncaught, instead of being rendered and exiting 1. This is the
    exact regression `test_error_hook_actually_intercepts_a_guarded_read_error`
    exists to catch."""
    monkeypatch.setattr("sys.argv", ["prog", "boom"])
    app = _make_throwaway_multi_command_app()

    with pytest.raises(GuardedReadError):
        # Bare invocation -- click's standalone_mode only intercepts click's
        # own exception types; a plain Python exception from inside a
        # command propagates through app() unchanged when nothing wraps it.
        app(standalone_mode=False)


def test_gate_fails_when_unguarded_read_introduced() -> None:
    """Part (b) non-vacuity: a synthetic in-scope-shaped command function
    with a bare, unwrapped `open()`+`json.loads()` read is reported by the
    SAME walker Part (b) uses -- naming the exact offending function, not
    just "an exception was raised"."""
    synthetic_source = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def load_widget_config(path: Path) -> dict:\n"
        "    with open(path, encoding='utf-8') as fh:\n"
        "        return json.loads(fh.read())\n"
    )

    violations = find_unguarded_raw_reads(synthetic_source)

    assert violations == ["load_widget_config"], (
        f"Non-vacuity failure: the walker did not flag the synthetic unguarded read (or flagged the wrong function). Got: {violations}"
    )


def test_gate_does_not_flag_a_correctly_guarded_read() -> None:
    """Control (proves the walker isn't simply flagging everything -- that
    would be vacuous in the OTHER direction): the sanctioned
    read_guarded(path, parse, ...) shape, decoder passed by bare name,
    reports zero violations."""
    synthetic_source = (
        "import json\n"
        "from kernel.guarded_read import read_guarded\n"
        "\n"
        "\n"
        "def _parse(content):\n"
        "    return json.loads(content)\n"
        "\n"
        "\n"
        "def load_widget_config(path):\n"
        "    return read_guarded(path, _parse, errors=(json.JSONDecodeError,))\n"
    )

    assert find_unguarded_raw_reads(synthetic_source) == []


def test_gate_does_not_flag_a_lambda_wrapped_guarded_read() -> None:
    """Control: the ``lambda content: helper(content, ...)`` indirection
    used by ``core/wps_manifest.py`` is also recognised as covered."""
    synthetic_source = (
        "import json\n"
        "from kernel.guarded_read import read_guarded\n"
        "\n"
        "\n"
        "def _parse_thing(content, extra):\n"
        "    return json.loads(content)\n"
        "\n"
        "\n"
        "def load_widget_config(path, extra):\n"
        "    return read_guarded(path, lambda content: _parse_thing(content, extra))\n"
    )

    assert find_unguarded_raw_reads(synthetic_source) == []
