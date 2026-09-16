"""Mode detection with precedence: charter override > explicit flag > environment > parent process.

Source-of-truth: kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/research.md R-001
Spec refs:       FR-016, C-013

Compatibility shim notice
--------------------------
This module is scheduled for retirement.  It is retained through spec-kitty 3.2.x because
``gate.py``, ``retrospective_terminus.py``, and test code import ``detect`` and
``ModeResolutionError`` directly from here.

**Retirement plan:**
- Deprecation target: spec-kitty 3.3.0
- Follow-up issue: https://github.com/spec-kitty/spec-kitty/issues/TBD
  (Issue title: "Retire retrospective.config + mode shim modules")
- Rationale: ``gate.py`` and ``_internal_runtime/retrospective_terminus.py`` import
  ``detect`` from here; migrating those callers requires cross-cutting changes to the
  gate API and integration tests that are out of scope for WP06.

New code should import ``ModeResolutionError`` from ``specify_cli.retrospective.mode``
(this module) until the retirement issue is resolved.  The ``detect()`` function will
move to ``specify_cli.retrospective.policy`` in a future WP.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Literal, cast

from ruamel.yaml import YAML as _YAML
from ruamel.yaml.error import YAMLError as _YAMLError

from charter.bundle import CHARTER_MD
from specify_cli.retrospective.schema import Mode, ModeSourceSignal

# ---------------------------------------------------------------------------
# Optional psutil — import lazily so a missing psutil does not crash the module.
# ---------------------------------------------------------------------------

psutil: ModuleType | None
try:
    import psutil as _psutil
except ImportError:
    psutil = None
else:
    psutil = _psutil

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

NON_INTERACTIVE_PARENTS: frozenset[str] = frozenset(
    {
        "github-actions",
        "gitlab-runner",
        "cron",
        "launchd",
        "systemd",
        "Runner.Listener",  # GitHub Actions runner process name on the runner host
        "agent-harness",
    }
)

#: Allowed values for the SPEC_KITTY_MODE environment variable.
_ALLOWED_ENV_VALUES: frozenset[str] = frozenset({"autonomous", "human_in_command"})


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ModeResolutionError(Exception):
    """Raised when the charter file exists but is malformed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_parent_name() -> str | None:
    """Return the name of the parent process, or None on any failure.

    Wraps psutil so that:
    - a missing psutil dependency → None (no signal)
    - any runtime error (permissions, zombie process, etc.) → None
    """
    if psutil is None:
        return None
    try:
        name: str = str(psutil.Process(os.getppid()).name())
        return name
    except Exception:  # noqa: BLE001
        return None


def _read_charter_mode(repo_root: Path) -> str | None:
    """Parse the charter file for a mode declaration.

    The charter is a Markdown file at ``.kittify/charter/charter.md``.
    We look for a YAML frontmatter block (between ``---`` delimiters at the
    start of the file) that contains a ``mode:`` key.

    No existing charter loader exposes a programmatic API for reading the
    mode policy field — the ``charter.activation.context`` module is a prompt-rendering
    surface, not a structured data reader.  We therefore implement a minimal
    frontmatter parser here, consistent with the approach described in the
    WP04 spec (T017).

    FR-005c note (``doctrine-charter-split-unification``): the retrospective
    **policy** now resolves yaml-first from ``charter.yaml``
    ``governance.retrospective`` (see :func:`~specify_cli.retrospective.policy.
    resolve_policy`).  ``mode:`` is deliberately NOT part of that flip: it is a
    top-level frontmatter key with no counterpart in
    :class:`~charter.activation.schemas.RetrospectiveGovernance`, whose keys mirror
    ``policy._KNOWN_KEYS`` exactly.  Minting a ``governance`` home for ``mode:``
    is a schema change (FR-005a scope), not a resolver change, so this reader
    stays frontmatter-only until that block exists.  The charter path constant
    is nevertheless imported directly from ``charter.bundle.CHARTER_MD``
    (WP06 T003 / #3163), not redeclared or reached through a sibling
    module's private alias.

    Returns:
        ``"autonomous"`` or ``"human_in_command"`` if the charter declares a
        mode; ``None`` if the charter is absent or has no ``mode:`` key.

    Raises:
        ModeResolutionError: if the charter file exists but its frontmatter
            is malformed (YAML parse error or structurally invalid).
    """
    charter_path = repo_root / CHARTER_MD
    if not charter_path.exists():
        return None  # No charter — no signal; fall through.

    try:
        raw = charter_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is a ValueError subclass, NOT an OSError
        # subclass -- non-UTF-8 bytes previously escaped uncaught here as a
        # raw crash instead of the contracted ModeResolutionError
        # (landing-fold follow-up to #3163, second-round adversarial
        # review: fold 214a06de9 fixed the sibling charter.yaml reader in
        # retrospective/policy.py but missed this frontmatter reader).
        raise ModeResolutionError(
            f"Charter at {charter_path} could not be read as UTF-8: {exc}"
        ) from exc

    # Attempt to extract YAML frontmatter (lines between first two ``---``).
    if not raw.startswith("---"):
        # No frontmatter block; treat as "no mode declaration" (not malformed).
        return None

    # Find the closing ``---``.
    lines = raw.splitlines()
    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break

    if close_idx is None:
        # Opened ``---`` but never closed — treat as malformed.
        raise ModeResolutionError(
            f"Charter at {charter_path} has an unclosed YAML frontmatter block."
        )

    frontmatter_text = "\n".join(lines[1:close_idx])

    # Parse with ruamel.yaml in safe mode.
    try:
        yaml = _YAML(typ="safe")
        data = yaml.load(frontmatter_text)
    except (_YAMLError, Exception) as exc:  # noqa: BLE001
        raise ModeResolutionError(
            f"Charter at {charter_path} has a malformed YAML frontmatter: {exc}"
        ) from exc

    if data is None:
        # Empty frontmatter — no mode declaration.
        return None

    if not isinstance(data, dict):
        raise ModeResolutionError(
            f"Charter at {charter_path} has a frontmatter that is not a YAML mapping."
        )

    raw_mode = data.get("mode")
    if raw_mode is None:
        return None  # No ``mode:`` key — no signal; fall through.

    mode_str = str(raw_mode).strip()
    if mode_str not in _ALLOWED_ENV_VALUES:
        raise ModeResolutionError(
            f"Charter at {charter_path} declares an invalid mode value: {mode_str!r}. "
            f"Allowed: {sorted(_ALLOWED_ENV_VALUES)}"
        )

    return mode_str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect(
    *,
    repo_root: Path,
    explicit_flag: Literal["autonomous", "human_in_command"] | None = None,
    env: Mapping[str, str] | None = None,
    parent_process_name: str | None = None,
) -> Mode:
    """Resolve mode with precedence: charter > flag > env > parent.

    All inputs are injectable for testability.  Production callers pass only
    ``repo_root`` and rely on ambient env / parent-process detection.

    Precedence (first signal that produces a definite value wins):

    1. **Charter override** — ``.kittify/charter/charter.md`` YAML frontmatter
       ``mode:`` key.  Sovereign; no runtime invocation can override it.
       Missing charter or missing ``mode:`` key → fall through silently.
       Malformed charter → raises :exc:`ModeResolutionError`.

    2. **Explicit flag** — ``explicit_flag`` parameter.

    3. **Environment** — ``SPEC_KITTY_MODE`` env var.  Allowed values:
       ``autonomous`` | ``human_in_command``; anything else is skipped.

    4. **Parent process** — ``parent_process_name`` parameter, or
       ``psutil.Process(os.getppid()).name()`` when not supplied.  Names in
       :data:`NON_INTERACTIVE_PARENTS` → autonomous; anything else →
       human_in_command (conservative default).

    Args:
        repo_root: Absolute path to the repository root.
        explicit_flag: Operator-supplied mode flag, or ``None``.
        env: Mapping to use as the environment (defaults to ``os.environ``).
        parent_process_name: Override the parent process name detection (for
            testing).  When ``None``, the function calls
            ``psutil.Process(os.getppid()).name()`` (best-effort).

    Returns:
        A :class:`~specify_cli.retrospective.schema.Mode` carrying the resolved
        value and a populated ``source_signal`` with non-empty ``evidence``.

    Raises:
        ModeResolutionError: if the charter exists but is malformed.
    """
    # ------------------------------------------------------------------
    # Layer 1 — Charter override
    # ------------------------------------------------------------------
    charter_mode = _read_charter_mode(repo_root)
    # _read_charter_mode raises ModeResolutionError on malformed charter;
    # returns None on absent/silent charter.
    if charter_mode is not None:
        # The clause id recorded as evidence is the frontmatter ``mode:`` key
        # with the value appended, giving reviewers a traceable string.
        evidence = f"mode-policy:{charter_mode}"
        return Mode(
            value=cast(Literal["autonomous", "human_in_command"], charter_mode),
            source_signal=ModeSourceSignal(
                kind="charter_override",
                evidence=evidence,
            ),
        )

    # ------------------------------------------------------------------
    # Layer 2 — Explicit flag
    # ------------------------------------------------------------------
    if explicit_flag is not None:
        return Mode(
            value=explicit_flag,
            source_signal=ModeSourceSignal(
                kind="explicit_flag",
                evidence=str(explicit_flag),
            ),
        )

    # ------------------------------------------------------------------
    # Layer 3 — Environment variable
    # ------------------------------------------------------------------
    effective_env: Mapping[str, str] = env if env is not None else os.environ
    env_value = effective_env.get("SPEC_KITTY_MODE", "").strip()
    if env_value in _ALLOWED_ENV_VALUES:
        return Mode(
            value=cast(Literal["autonomous", "human_in_command"], env_value),
            source_signal=ModeSourceSignal(
                kind="environment",
                evidence="SPEC_KITTY_MODE",
            ),
        )

    # ------------------------------------------------------------------
    # Layer 4 — Parent process (conservative default: HiC when in doubt)
    # ------------------------------------------------------------------
    name: str | None = (
        parent_process_name if parent_process_name is not None else _detect_parent_name()
    )
    if name is not None and name in NON_INTERACTIVE_PARENTS:
        return Mode(
            value="autonomous",
            source_signal=ModeSourceSignal(
                kind="parent_process",
                evidence=name,
            ),
        )

    # Conservative default: human_in_command.
    # evidence captures the resolved name when available ("default-no-signal"
    # when no name could be determined) so the audit trail is always non-empty.
    evidence = name if name is not None else "default-no-signal"
    return Mode(
        value="human_in_command",
        source_signal=ModeSourceSignal(
            kind="parent_process",
            evidence=evidence,
        ),
    )
