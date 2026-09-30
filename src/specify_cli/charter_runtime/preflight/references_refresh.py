"""References-parity boundary auto-refresh completion (#2777, FR-011, WP06).

The boundary auto-refresh reconciler (``preflight.runner._attempt_auto_refresh``)
runs ``spec-kitty charter sync`` -> ``spec-kitty charter synthesize`` ->
``spec-kitty charter bundle validate``. None of those three steps recompiles
the *compiled* references catalog embedded in ``.kittify/charter/charter.yaml``
(``catalog.references`` -- the direct successor of the retired stand-alone
``references.yaml`` file; see ``charter.activation.compiler._build_catalog_dict``'s
docstring: "Mirrors the retired ``references.yaml`` body"). Only
``spec-kitty charter generate`` recompiles that section, so a project whose
``.kittify/config.yaml`` activation changed without an intervening
``generate`` run cannot self-heal that drift through the boundary's existing
three-step sequence.

This module is WP04's ``refresh_references_if_needed`` extension point,
implemented: :func:`refresh_references_if_needed` runs a *targeted*
``generate`` -- but only when the freshness causes that triggered the heal
name the references-parity layer (:func:`is_references_parity_cause`), never
unconditionally (T024).

What "references-parity cause" means today (mapping note)
-----------------------------------------------------------
Pre-consolidate-charter-bundle, "references-parity" meant a dedicated
config<->``references.yaml``/graph activation-parity check
(``_activation_parity_drift_reason``). That check is retired outright
(``freshness/computer.py`` module docstring, #2759): once freshness reads
``charter.yaml`` directly, activation lives INSIDE the same file the
content-hash comparison already covers, so the *stand-alone* file/graph
divergence it used to detect cannot exist anymore. The freshness computer's
only three check names are ``charter_source``, ``synced_bundle``, and
``synthesized_drg`` (``preflight.runner._LAYER_ORDER``) -- there is no
literal ``"references_parity"`` cause string anywhere in the runner. The
``synthesized_drg`` layer is the modern proxy: it is the ONLY layer whose
staleness stems from ``charter.yaml``'s own derived-content hash (the same
content ``generate`` recomputes), and it is reachable stale independently of
``charter_source``/``synced_bundle`` (e.g. a project whose synthesis manifest
declares ``built_in_only: true`` reports ``synthesized_drg="built_in_only"``,
a PASS state, even while ``charter_source``/``synced_bundle`` are themselves
stale/invalid) -- so gating on ``synthesized_drg`` alone is a real,
non-degenerate condition, not a rubber stamp.

NFR-006 (curated charter.md untouched)
-----------------------------------------------------------
``generate`` is safe to invoke here as-is: ``charter.activation.compiler.
write_compiled_charter`` only ever refreshes ``charter.yaml``'s DERIVED
``catalog``/``metadata`` sections (round-tripped so authored
``governance``/``directives``/activation/``overrides`` survive
byte-for-byte) and NEVER writes ``charter.md`` (data-model.md Landmine 3,
the #2772 preservation contract). No "references-only" mode is needed in
``generate.py`` -- the existing command already satisfies the preservation
contract structurally.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from charter.activation.charter_yaml_io import read_catalog_field

from .runner import SYNTHESIZED_DRG_LAYER

__all__ = ["refresh_references_if_needed"]

_logger = logging.getLogger(__name__)

#: The freshness-check name that stands in for "references-parity drift" —
#: see the module docstring's mapping note. Sourced from
#: ``preflight.runner.SYNTHESIZED_DRG_LAYER`` (the runner's own
#: ``_LAYER_ORDER`` authority) rather than re-declared here, so a rename of
#: the layer name cannot silently desync this cause-matching from the
#: runner's actual layer set — see this module's binding test,
#: ``test_references_parity_cause_name_is_a_runner_layer``.
_REFERENCES_PARITY_CAUSE_NAME = SYNTHESIZED_DRG_LAYER

#: Targeted-generate timeout — mirrors ``preflight.runner``'s refresh-step
#: default (the whole boundary sequence budgets 30s/step; this hook fires
#: once, after that sequence already succeeded).
_GENERATE_TIMEOUT_SECS = 30.0

_GENERATE_CMD_PREFIX: tuple[str, ...] = ("spec-kitty", "charter", "generate")

#: The label ``charter``'s ``_emit_error`` prefixes to a non-JSON error line.
_RICH_ERROR_LINE = re.compile(r"^(?:Unexpected error|Error):")


@dataclass(frozen=True)
class ReferencesRefreshOutcome:
    """Outcome of one targeted ``generate`` invocation.

    Carries "did it succeed", not just "was it attempted", so a genuine
    ``generate`` failure cannot be reported as success. Only three states
    are reachable (enforced in ``__post_init__``): not attempted, succeeded,
    or failed (optionally with a *detail*).

    Attributes:
        attempted: ``True`` iff *cause* named the references-parity layer
            and a targeted ``generate`` subprocess was actually spawned.
            ``False`` for a true no-op (non-references-parity cause).
        succeeded: ``True`` iff the subprocess exited 0. Always ``False``
            when ``attempted`` is ``False``.
        detail: A short excerpt naming why the targeted ``generate`` failed
            (see :func:`_extract_failure_detail`) when ``attempted and not
            succeeded``; ``None`` otherwise.

    A plain object is always truthy, so ``if refresh_references_if_needed(...):``
    would read a not-attempted or failed outcome as success; ``__bool__``
    refuses that coercion so callers must check the named fields.
    """

    attempted: bool
    succeeded: bool
    detail: str | None

    def __post_init__(self) -> None:
        # Three reachable states: not attempted, succeeded, failed (+ detail).
        if (self.succeeded and not self.attempted) or (self.detail is not None and not (self.attempted and not self.succeeded)):
            raise ValueError(
                "impossible ReferencesRefreshOutcome: succeeded requires attempted, "
                f"and detail is only valid on a failed attempt (attempted={self.attempted}, "
                f"succeeded={self.succeeded}, detail={self.detail!r})"
            )

    def __bool__(self) -> NoReturn:
        raise TypeError("ReferencesRefreshOutcome has no truth value -- check .attempted/.succeeded explicitly")


def is_references_parity_cause(cause: str) -> bool:
    """Return True iff *cause* names the references-parity layer.

    ``cause`` is the comma-joined, sorted set of freshness-check names that
    triggered the boundary heal (``preflight.runner._attempt_auto_refresh``'s
    ``stale_cause``). See the module docstring's mapping note for why
    ``synthesized_drg`` is the references-parity signal.
    """
    causes = {name for name in cause.split(",") if name}
    return _REFERENCES_PARITY_CAUSE_NAME in causes


def _read_catalog_mission_and_template_set(
    repo_root: Path,
) -> tuple[str | None, str | None]:
    """Best-effort read of the existing charter.yaml's ``catalog.mission``/
    ``catalog.template_set``.

    Used so the targeted refresh recompiles for the SAME mission/template
    set the project already uses, rather than silently defaulting to
    ``generate``'s hardcoded ``"software-dev"`` fallback (which only applies
    when ``--no-from-interview`` is passed and no ``--mission-type`` is
    given). Returns ``(None, None)`` when ``charter.yaml`` is absent,
    unparseable, or missing a ``catalog`` section — callers then fall back
    to ``generate``'s own defaults rather than failing the refresh.

    Both fields are read through the single shared ``catalog.<field>``
    reader (``charter.activation.charter_yaml_io.read_catalog_field``,
    Finding B / #4993) rather than a second, ad-hoc ``YAML(typ="safe")``
    parse of ``charter.yaml`` — the parser-drift risk this fold removes.
    """
    mission = read_catalog_field(repo_root, "mission")
    template_set = read_catalog_field(repo_root, "template_set")
    return (
        mission if isinstance(mission, str) and mission else None,
        template_set if isinstance(template_set, str) and template_set else None,
    )


def _build_generate_command(repo_root: Path) -> list[str]:
    """Build the targeted ``charter generate`` argv.

    ``--no-from-interview`` is always passed: activation is sourced from
    ``.kittify/config.yaml``'s ``activated_*`` fields, never from interview
    answers (``compile_charter``'s docstring, FR-001/FR-002), so skipping
    the interview read avoids requiring ``answers.yaml`` to exist for this
    background heal while not losing any activation fidelity. The existing
    mission/template_set are threaded through explicitly (when readable) so
    a project on a non-default mission type is not silently recompiled
    against ``generate``'s ``"software-dev"`` fallback. ``--json`` makes a
    failure carry its message in a machine-readable ``error`` field instead
    of rich-wrapped prose (see :func:`_extract_failure_detail`).
    """
    mission, template_set = _read_catalog_mission_and_template_set(repo_root)
    cmd = [*_GENERATE_CMD_PREFIX, "--no-from-interview", "--json"]
    if mission:
        cmd.extend(["--mission-type", mission])
    if template_set:
        cmd.extend(["--template-set", template_set])
    return cmd


def _json_error_field(stdout: str) -> str | None:
    """The ``error`` string of ``generate --json``'s failure payload, if any."""
    for candidate in (stdout, *reversed(stdout.splitlines())):
        try:
            payload = json.loads(candidate)
        except ValueError:
            continue
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, str) and error.strip():
            return error.strip()
    return None


def _unwrapped_error_paragraph(stream: str) -> str | None:
    """The last ``Error: ...`` paragraph of *stream*, re-joined onto one line.

    rich hard-wraps at 80 columns when stdout is not a TTY, so the message
    continues on the following lines; the last physical line alone is a
    fragment.
    """
    lines = [line.strip() for line in stream.splitlines() if line.strip()]
    starts = [i for i, line in enumerate(lines) if _RICH_ERROR_LINE.match(line)]
    return " ".join(lines[starts[-1] :]) if starts else None


def _extract_failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    """Short excerpt naming why the targeted ``generate`` failed.

    Preference order: the ``error`` field of ``generate --json``'s payload;
    an unwrapped ``Error: ...`` paragraph (either stream, stdout first, so a
    stray stderr warning cannot outrank the real error); the last non-empty
    ``stderr`` line, else the last non-empty ``stdout`` line.
    """
    stdout, stderr = completed.stdout or "", completed.stderr or ""
    json_error = _json_error_field(stdout)
    if json_error:
        return json_error
    for stream in (stdout, stderr):
        paragraph = _unwrapped_error_paragraph(stream)
        if paragraph:
            return paragraph
    for stream in (stderr, stdout):
        lines = [line for line in stream.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return f"generate exited {completed.returncode} with no captured output"


def refresh_references_if_needed(repo_root: Path, cause: str) -> ReferencesRefreshOutcome:
    """Recompile ``charter.yaml``'s references catalog for references-parity drift.

    True no-op (``ReferencesRefreshOutcome(attempted=False, succeeded=False,
    detail=None)``, no subprocess spawned) unless
    :func:`is_references_parity_cause` accepts *cause*. When it does, runs a
    targeted ``spec-kitty charter generate`` against *repo_root* and reports
    the subprocess's actual outcome, so a genuine ``generate`` failure is
    never reported as success.

    Never raises: an ``OSError``/``TimeoutExpired`` spawning the subprocess
    is reported as ``attempted=True, succeeded=False`` (the same failure
    shape as a non-zero exit) rather than propagated — matching this whole
    package's "MUST NOT raise on filesystem or subprocess errors" contract
    (``preflight.runner`` module docstring). Callers (``preflight.runner
    ._attempt_auto_refresh``) decide what a failed attempt means for the
    overall preflight result; this function only reports the outcome.

    Args:
        repo_root: Repository root the boundary heal ran against.
        cause: Comma-joined freshness-check names that triggered the heal.

    Returns:
        A :class:`ReferencesRefreshOutcome` describing whether a targeted generate was
        attempted and, if so, whether it succeeded.
    """
    if not is_references_parity_cause(cause):
        return ReferencesRefreshOutcome(attempted=False, succeeded=False, detail=None)

    cmd = _build_generate_command(repo_root)
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GENERATE_TIMEOUT_SECS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _logger.debug(
            "references-parity refresh: `%s` invocation failed",
            " ".join(cmd),
            exc_info=True,
        )
        return ReferencesRefreshOutcome(
            attempted=True,
            succeeded=False,
            detail=f"`{' '.join(cmd)}` invocation failed: {exc}",
        )

    if completed.returncode == 0:
        return ReferencesRefreshOutcome(attempted=True, succeeded=True, detail=None)
    return ReferencesRefreshOutcome(
        attempted=True,
        succeeded=False,
        detail=_extract_failure_detail(completed),
    )
