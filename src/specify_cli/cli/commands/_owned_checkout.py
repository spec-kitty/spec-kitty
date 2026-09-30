"""The ONE shared CLI owned-checkout surface (owned-checkout-lifecycle-authority WP08).

Every owned-capable command this WP wires (today: ``agent context resolve``)
validates ownership through this module instead of re-deriving the logic per
command. It owns:

* the ``--owned-checkout`` option declaration (:data:`OwnedCheckoutOption`,
  :func:`owned_checkout_option`);
* the single validation entry point (:func:`resolve_owned_or_adopt`, plus its
  refusal-rendering Typer-edge wrapper :func:`resolve_owned_or_refuse`) and
  :func:`refuse_owned_action`, which validate ownership exactly once per
  command invocation (NFR-002);
* typed refusal rendering (:func:`emit_owned_refusal`) and the four envelope
  builders each consuming command needs;
* the stale-repository-root-copy channel (R-12, R-16): :func:`stale_repository_root_copy`,
  :func:`stale_copy_payload` and :func:`echo_stale_copy_warning`.

**G2 status.** This module is G2's DESIGNATED sole CLI caller of
``resolve_owned_mission`` / ``adopt_owned_checkout``
(``contracts/architectural-gate.md``); the single-authority gate
(``tests/architectural/test_owned_checkout_single_authority.py``) enforces it
with an empty allowlist -- no other module calls either function.

**Envelope rule (occurrence map ``serialized_keys: do_not_change``).** Keys
this module adds to a command's JSON payload are ADDITIVE ONLY.
``stale_repository_root_copy`` is emitted only when the command holds an
``OwnedCheckout`` fact (explicit ``--owned-checkout`` or flagless adoption);
its value is ``null`` when the repository root holds no stale copy. The
non-owned payload of every consuming command stays byte-identical to today's
shape. WP09, WP13 and WP19 MUST follow this same convention for every
command they wire through this helper.

**G5 note.** The named ``CLI_CLAIM_INPUT_RULE``
(``tests/architectural/_owned_checkout_scan.py``) exempts a
``--owned-checkout`` parameter annotated with :data:`OwnedCheckoutOption`, or
with the help-preserving form
``Annotated[Path | None, owned_checkout_option(help=...)]``: it carries the
raw, unvalidated ``--owned-checkout`` input into the minter. Any other
spelling (an inline ``typer.Option("--owned-checkout", ...)``, or a renamed
parameter) is a G5 offender or a gate evasion.

**Cold-import boundary (#1461).** This module is imported by CLI command
modules that ``task_utils.support`` cold-imports; the minter functions and
topology sets from ``specify_cli.core.owned_mission`` (and the registry
reader from ``specify_cli.coordination.surface_resolver``) are therefore
imported lazily, inside the functions that use them, mirroring
``owned_mission.py``'s own lazy-import discipline.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Final, NoReturn

import typer
from rich.console import Console

from mission_runtime import ActionContextError, MissionTopology, OwnedCheckout, OwnedRefusalCode

from specify_cli.cli.json_contract import json_error

_stderr_console: Final = Console(stderr=True)

_ERROR_CODE_KEY: Final = "error_code"

OWNED_CHECKOUT_HELP: Final[str] = (
    "Run against an owned checkout: a linked checkout that owns this mission. Refuses the repository root checkout, lane worktrees and coordination worktrees."
)

# New flags use this alias directly; existing flags whose ``--help`` text is a
# committed golden fixture (``tasks.py:782,916``) use ``owned_checkout_option``
# instead, to keep that text byte-identical while still satisfying G5's
# ``CLI_CLAIM_INPUT_RULE``.
OwnedCheckoutOption = Annotated[Path | None, typer.Option("--owned-checkout", help=OWNED_CHECKOUT_HELP)]


def owned_checkout_option(help: str) -> object:  # noqa: A002 -- matches typer's own parameter name
    """Build a ``--owned-checkout`` option carrying a caller-supplied, help-preserving ``help`` string.

    Existing commands with a committed ``--help`` golden fixture use this
    instead of :data:`OwnedCheckoutOption` so their help text never changes;
    the returned option is still exempt from the G5 bare-``Path`` scan
    (``CLI_CLAIM_INPUT_RULE``) when used as
    ``Annotated[Path | None, owned_checkout_option(help=...)]``.
    """
    return typer.Option("--owned-checkout", help=help)


def resolve_owned_or_adopt(
    repository_root: Path,
    owned_claim: Path | None,
    handle: str | None,
    *,
    cwd: Path,
    allowed_topologies: frozenset[MissionTopology],
    target_override: str | None = None,
    discover_sole: bool = False,
) -> OwnedCheckout | None:
    """Validate ``--owned-checkout`` once, or adopt a flagless caller checkout.

    Validates ownership exactly once per command invocation (NFR-002); see
    the module docstring for this module's current G2 status.

    With an explicit ``owned_claim``, returns :func:`resolve_owned_mission`'s
    result (which raises :class:`ActionContextError` on any refusal, including
    ``OWNED_CHECKOUT_IS_REPOSITORY_ROOT`` for the repository root itself).
    ``target_override`` is forwarded on this explicit path only (WP13's
    ``finalize-tasks --target-branch`` and WP16's ``spec-commit`` both need
    it); flagless adoption never accepts an override -- the whole point of
    adoption is to accept the checkout's OWN stored target. ``discover_sole``
    (handle-less ``next``) is forwarded on the explicit path only: the sole
    mission is discovered inside the claimed checkout, after the single claim
    check (``OwnedMissionSelectionRequired`` for zero / several).
    Without ``owned_claim``, returns :func:`adopt_owned_checkout`'s result:
    a fact, or ``None`` when adoption does not apply (falls back to today's
    repository-root behaviour). ``adopt_owned_checkout`` itself raises
    ``ActionContextError("MISSION_CONTEXT_CONFLICT", ...)`` for the
    same-selector-different-identity case (US7-AS5); that typed error is left
    to propagate unchanged, never re-derived here.
    """
    from specify_cli.core.owned_mission import adopt_owned_checkout, resolve_owned_mission
    from specify_cli.core.paths import get_main_repo_root

    root = get_main_repo_root(repository_root).resolve()
    if owned_claim is not None:
        checkout = owned_claim if owned_claim.is_absolute() else cwd / owned_claim
        return resolve_owned_mission(
            root,
            checkout,
            handle,
            target_override=target_override,
            allowed_topologies=allowed_topologies,
            discover_sole=discover_sole,
        )
    return adopt_owned_checkout(root, cwd, handle, allowed_topologies=allowed_topologies)


def resolve_owned_or_refuse(
    repository_root: Path,
    owned_claim: Path | None,
    handle: str | None,
    *,
    cwd: Path,
    allowed_topologies: frozenset[MissionTopology],
    json_output: bool,
    envelope: Callable[[str, str], dict[str, object]],
    target_override: str | None = None,
) -> OwnedCheckout | None:
    """:func:`resolve_owned_or_adopt`, rendering any validation refusal through :func:`emit_owned_refusal`.

    The one Typer-edge entry point for commands that own no bespoke refusal
    plumbing (owned-checkout-lifecycle-authority WP16: ``move-task``,
    ``mark-status``, ``spec-commit``, ``check-prerequisites``): the raw
    ``--owned-checkout`` value goes straight into the minter here, a refusal
    prints the command's ``envelope`` and exits 1, and the caller receives
    only the validated fact (or ``None`` when neither the flag nor adoption
    applies). Validation runs exactly once per invocation (NFR-002).
    """
    try:
        return resolve_owned_or_adopt(
            repository_root,
            owned_claim,
            handle,
            cwd=cwd,
            allowed_topologies=allowed_topologies,
            target_override=target_override,
        )
    except ActionContextError as exc:
        emit_owned_refusal(exc, json_output=json_output, envelope=envelope)


def refuse_owned_action(
    repository_root: Path,
    owned_claim: Path,
    handle: str | None,
    *,
    action: str,
) -> NoReturn:
    """Refuse ``agent action implement`` / ``agent action review`` under ``--owned-checkout`` (FR-018/FR-020).

    WP09 owns the call-site wiring; this WP owns the function and its unit
    tests. With a ``handle``, validates through :func:`resolve_owned_mission`
    (``LIFECYCLE_OWNED_TOPOLOGIES``) so every invalid-path refusal code
    surfaces before the unconditional ``OWNED_ACTION_UNSUPPORTED`` refusal.
    Without one, validates only the claim and the repository-root refusal via
    :func:`resolve_owned_create_root` (the mission may not be resolvable yet).
    """
    from specify_cli.core.owned_mission import (
        LIFECYCLE_OWNED_TOPOLOGIES,
        resolve_owned_create_root,
        resolve_owned_mission,
    )
    from specify_cli.core.paths import get_main_repo_root

    root = get_main_repo_root(repository_root).resolve()
    if handle is not None and handle.strip():
        resolve_owned_mission(root, owned_claim, handle, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    else:
        resolve_owned_create_root(root, owned_claim)
    raise ActionContextError(
        OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED,
        f"'{action}' does not support --owned-checkout yet. "
        "Use 'spec-kitty next --owned-checkout <P>' or "
        "'spec-kitty agent tasks move-task --owned-checkout <P>' instead.",
    )


def _registered_owned_error_codes() -> frozenset[str]:
    """The full data-model.md Error code registry ``emit_owned_refusal`` accepts.

    ``OwnedRefusalCode`` already carries the four claim-primitive codes
    (``WORKTREE_INVOCATION_REFUSED``, ``OWNERSHIP_NESTED``, ``OWNERSHIP_FOREIGN``,
    ``OWNERSHIP_BROKEN_POINTER``) alongside every owned-checkout-specific code.
    Two further code families are accepted, each sourced from its single named
    module constant and never repeated here as a literal (WP02 review
    follow-up 2): ``WorktreeRegistryUnavailable.error_code``
    (``_require_not_mission_worktree``'s fail-closed registry-read refusal on
    the explicit ``--owned-checkout`` path), and the two pre-existing wire
    codes ``specify_cli.core.owned_mission.FEATURE_CONTEXT_UNRESOLVED`` /
    ``MISSION_CONTEXT_CONFLICT`` that ``resolve_owned_or_adopt`` can propagate.
    """
    from specify_cli.core.owned_mission import FEATURE_CONTEXT_UNRESOLVED, MISSION_CONTEXT_CONFLICT
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    return frozenset({member.value for member in OwnedRefusalCode}) | {
        WorktreeRegistryUnavailable.error_code,
        FEATURE_CONTEXT_UNRESOLVED,
        MISSION_CONTEXT_CONFLICT,
    }


class UnregisteredOwnedRefusalCode(RuntimeError):
    """Raised when ``emit_owned_refusal`` is asked to render an unregistered ``error_code``.

    A programming error in the caller, not a user-facing refusal (review
    cycle 1 finding 11): an ``assert`` would vanish under ``python -O``,
    silently dropping the "every emitted code is registered" guarantee and,
    on the rare path where it did fire, surfacing an uncaught
    ``AssertionError`` instead of a typed exception.
    """


def emit_owned_refusal(
    exc: ActionContextError,
    *,
    json_output: bool,
    envelope: Callable[[str, str], dict[str, object]],
) -> NoReturn:
    """Render one owned-checkout refusal through ``envelope`` and exit(1).

    JSON mode prints ``envelope(exc.code, str(exc))`` on stdout (adding a
    top-level ``error_code`` key when the envelope omits one -- additive
    only). Human mode prints ``Error: [<code>] <message>`` on **stderr**.
    ``exc.code`` is validated against :func:`_registered_owned_error_codes`
    first: an unregistered code is a programming error in the caller, not a
    user-facing refusal, so it raises :class:`UnregisteredOwnedRefusalCode`
    rather than rendering an un-auditable code.
    """
    registered = _registered_owned_error_codes()
    if exc.code not in registered:
        raise UnregisteredOwnedRefusalCode(f"emit_owned_refusal: unregistered owned refusal error_code {exc.code!r}")

    payload = envelope(exc.code, str(exc))
    if _ERROR_CODE_KEY not in payload:
        payload[_ERROR_CODE_KEY] = exc.code

    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        _stderr_console.print(f"Error: [{exc.code}] {exc}")
    raise typer.Exit(1)


def success_false_envelope(code: str, message: str) -> dict[str, object]:
    """``{"success": False, "error_code", "error"}`` -- for ``agent context resolve``."""
    return {"success": False, "error_code": code, "error": message}


def json_error_envelope(code: str, message: str) -> dict[str, object]:
    """``json_error`` plus a top-level ``error_code`` -- for ``agent tasks status``."""
    return {**json_error(code, message), "error_code": code}


def flat_error_envelope(code: str, message: str) -> dict[str, object]:
    """``{"error", "error_code"}`` -- for ``move-task`` and ``check-prerequisites``."""
    return {"error": message, "error_code": code}


def result_error_envelope(code: str, message: str) -> dict[str, object]:
    """``{"result": "error", "phase_complete": False, "error_code", "error"}`` -- for ``setup-plan``."""
    return {"result": "error", "phase_complete": False, "error_code": code, "error": message}


def stale_repository_root_copy(owned: OwnedCheckout) -> dict[str, str] | None:
    """Report R's stale copy of the owned mission, or ``None`` (R-12).

    Reads via the canonical pure composer
    ``specify_cli.missions._read_path_resolver.compose_meta_json_path`` (the
    same public meta.json composer ``next_cmd.py`` and
    ``mission_runtime.resolution.read_dir_for`` already use), never a
    hand-composed path -- review cycle 1 finding 3. That composer is pure
    string logic (mid8 extraction + the verbatim ``<slug>-<mid8>`` grammar),
    with **no git calls and no topology probing**; deliberately NOT the
    placement seam / ``resolve_artifact_surface`` (those call
    ``get_main_repo_root`` and canonicalise handles, which would break R-12's
    "no git calls" rule). Returns the copy descriptor only when both metas
    exist and carry the SAME ``mission_id``; a different id is US7-AS5's
    conflict, not a stale copy, and an absent/corrupt R-side meta means the
    copy's identity cannot be proven, so it is not reported either.
    """
    from specify_cli.mission_metadata import load_meta_or_empty
    from specify_cli.missions._read_path_resolver import compose_meta_json_path

    r_copy_dir = compose_meta_json_path(owned.repository_root, owned.mission_slug).parent
    r_meta = load_meta_or_empty(r_copy_dir)
    p_meta = load_meta_or_empty(owned.mission_dir)
    r_id = r_meta.get("mission_id")
    p_id = p_meta.get("mission_id")
    if not r_id or not p_id or r_id != p_id:
        return None
    return {"path": str(r_copy_dir), "mission_id": str(r_id)}


STALE_COPY_WARNING: Final[str] = "The repository root checkout holds a stale copy of mission {slug} at {path}; the owned checkout {owned_path} is authoritative."


def _stale_copy_warning_text(owned: OwnedCheckout, value: dict[str, str]) -> str:
    return STALE_COPY_WARNING.format(slug=owned.mission_slug, path=value["path"], owned_path=str(owned.owned_root))


def stale_copy_payload(owned: OwnedCheckout, *, warnings: list[str] | None = None) -> dict[str, object]:
    """``{"stale_repository_root_copy": value}``, appending the human text to ``warnings`` when both apply."""
    value = stale_repository_root_copy(owned)
    if value is not None and warnings is not None:
        warnings.append(_stale_copy_warning_text(owned, value))
    return {"stale_repository_root_copy": value}


def echo_stale_copy_warning(owned: OwnedCheckout) -> None:
    """Print the stale-copy human text on **stderr** when R holds a copy; otherwise do nothing."""
    value = stale_repository_root_copy(owned)
    if value is not None:
        _stderr_console.print(_stale_copy_warning_text(owned, value))


__all__ = [
    "OwnedCheckoutOption",
    "echo_stale_copy_warning",
    "emit_owned_refusal",
    "flat_error_envelope",
    "json_error_envelope",
    "owned_checkout_option",
    "refuse_owned_action",
    "resolve_owned_or_adopt",
    "resolve_owned_or_refuse",
    "result_error_envelope",
    "stale_copy_payload",
    "success_false_envelope",
]
