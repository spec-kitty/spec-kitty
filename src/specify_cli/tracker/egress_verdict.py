"""The single tracker-egress verdict: one local consent channel, one named destination (#3108).

**One function decides whether tracker data may leave the machine.**
:func:`tracker_egress_verdict` reads the project's own committed ``tracker.egress`` key and a
caller-supplied :class:`EgressDestination` into one :class:`TrackerEgressVerdict`. Both the
gates that raise and the diagnostic surfaces call this same function, so the enforced answer
and the reported answer cannot disagree.

**The hosted destination was removed with the hosted surface (#6164).** This module used to
answer for a ``HOSTED_SERVICE`` destination too (the operator's authenticated SaaS session,
narrowed-only by the local key); that transport was removed from open-core, so only the
local-subprocess consent channel remains. The ``tracker.egress`` key still gates the kept
``beads``/``fp`` local providers.

**The project's own committed ``tracker.egress`` key** in ``.kittify/config.yaml``:
``absent`` / ``refused`` / ``permitted`` / ``fault``. Decoded by :func:`_resolve_channel2`
from :class:`~specify_cli.tracker.config.TrackerProjectConfig`.

Polarity at ``LOCAL_SUBPROCESS`` is two-way, and this is deliberate
--------------------------------------------------------------------

``EgressDestination.LOCAL_SUBPROCESS`` (``beads``/``fp``): the key is **two-way** --
``refused`` refuses, and ``permitted`` grants. The subprocess spawn is exactly the leak the
key exists to gate: issue fields travel into an executable the operator configured
machine-globally, so only an explicit committed grant decides, and absence refuses (inability
to determine consent is never consent).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from specify_cli.tracker.config import (
    EGRESS_ABSENT,
    EGRESS_PERMITTED,
    EGRESS_REFUSED,
    TrackerConfigError,
    load_tracker_config,
)

__all__: list[str] = []


class EgressDestination(enum.Enum):
    """The closed, caller-supplied set of transports a tracker-egress verdict is asked about.

    ``tracker_egress_verdict`` never derives this value -- it is a required, keyword-only
    parameter at every call site.
    """

    #: An executable named by the operator's own **machine-global** tracker credential file
    #: (``tracker/factory.py`` -- the ``command`` key, defaulting to ``bd``/``fp``), invoked
    #: with issue fields (title, body, labels, assignees) as ``argv``. spec-kitty's hosted
    #: service is not involved anywhere on this path.
    LOCAL_SUBPROCESS = "local_subprocess"


#: The legal Channel-2 values, built from the imported constants -- never a re-spelled literal.
_LEGAL_CHANNEL2_VALUES: Final[frozenset[str]] = frozenset({EGRESS_REFUSED, EGRESS_PERMITTED})


class _UnreadableConfigType:
    """Sentinel for "the project's tracker config could not be read at all" (unreadable file,
    unreadable enclosing directory, unparseable YAML) -- distinct from a present ``null``
    (which decodes to ``None``, a legitimate fault *value* to quote verbatim) and distinct from
    :data:`~specify_cli.tracker.config.EGRESS_ABSENT` (the key was simply missing from a config
    that *was* readable).

    Reachable from :attr:`TrackerEgressVerdict.channel2_raw` -- a log line may render it, so it
    carries a legible ``__repr__`` rather than the illegible default ``<object object at ...>``
    a bare ``object()`` would print.
    """

    def __repr__(self) -> str:
        return "<tracker config unreadable>"


#: The single instance of :class:`_UnreadableConfigType`.
_UNREADABLE: Final = _UnreadableConfigType()

CHANNEL_2: Final = "channel_2"

#: Channel-2's state vocabulary. ``EGRESS_REFUSED`` / ``EGRESS_PERMITTED`` are imported from
#: ``tracker/config.py``, never re-spelled: that module exports them as the single canonical
#: spelling precisely so a second spelling here cannot drift from ``egress_fault``'s idea of
#: what is legal.
CHANNEL2_ABSENT: Final = "absent"
CHANNEL2_FAULT: Final = "fault"


@dataclass(frozen=True, slots=True)
class TrackerEgressVerdict:
    """The one value object both the enforcing gates and diagnostics read.

    No ``binding_kind`` field, and no binding-kind derivation anywhere in this module: the
    caller states :attr:`destination`; the verdict never reads
    :class:`~specify_cli.tracker.config.TrackerProjectConfig.provider` to guess it.
    """

    #: The enforced answer, for the destination asked about. Never derived a second way anywhere
    #: else -- every raise site reads this field and nothing else to decide whether to refuse.
    refused: bool

    #: Which channel refuses -- populated only when the verdict actually refuses; empty when it
    #: permits. Only one channel remains, so this is ``{CHANNEL_2}`` or empty.
    refusing_channels: frozenset[str]

    #: Echoed back so a renderer cannot mislabel a row and a test can assert the enforced and
    #: reported verdicts were asked about the same destination.
    destination: EgressDestination

    #: One of :data:`CHANNEL2_ABSENT`, ``EGRESS_REFUSED`` (``"refused"``), ``EGRESS_PERMITTED``
    #: (``"permitted"``), or :data:`CHANNEL2_FAULT`.
    channel2_state: str

    #: The raw value read from the project's own ``tracker.egress`` key -- verbatim, for a fault
    #: message to quote. :data:`~specify_cli.tracker.config.EGRESS_ABSENT` when the key was
    #: missing or no config was read.
    channel2_raw: object

    #: The single composed operator-facing message. No raise site composes its own text --
    #: every one uses this field unchanged.
    message: str

    #: Ordered remedies. Empty when the verdict permits. **Raise sites must render these
    #: alongside `message`, never `message` alone**: at ``LOCAL_SUBPROCESS`` the grant remedy
    #: lives only here, not folded into `message`.
    remedies: tuple[str, ...]


def _resolve_channel2(root: Path) -> tuple[str, object]:
    """Decode Channel 2 from *root*'s committed tracker config. Reads the file exactly once.

    Never raises: an unreadable or unparseable ``.kittify/config.yaml`` is itself a fault, not
    a crash. Catches ``OSError`` alongside ``TrackerConfigError`` because the pre-check ahead
    of ``load_tracker_config``'s own guarded open/parse block calls ``Path.exists()``, which
    re-raises rather than swallows a ``PermissionError`` -- an unreadable *enclosing directory*
    would otherwise propagate straight out of a function that must never raise.
    """
    try:
        config = load_tracker_config(root)
    except (TrackerConfigError, OSError):
        return CHANNEL2_FAULT, _UNREADABLE

    raw = config.egress
    if raw is EGRESS_ABSENT:
        return CHANNEL2_ABSENT, raw
    if isinstance(raw, str) and raw in _LEGAL_CHANNEL2_VALUES:
        return raw, raw
    # Deliberate, not an incidental fallthrough: this also covers a string that
    # ``tracker/config.py`` might one day add to its own legal values without this module being
    # updated to match -- an unmapped-here value refuses rather than silently permitting.
    return CHANNEL2_FAULT, raw


def _fault_message(destination: EgressDestination, raw: object) -> str:
    """Compose the fault message: names the offending value verbatim.

    Names both legal values by their exact on-disk spelling, so an operator fixes a typo
    without reading source.
    """
    offending = "the project's tracker configuration could not be read" if raw is _UNREADABLE else repr(raw)
    return (
        f"tracker.egress is set to {offending}, which is not a legal value; refusing tracker "
        f"egress to {destination.value} (legal values are {EGRESS_REFUSED!r} and {EGRESS_PERMITTED!r})"
    )


def _refused_message(destination: EgressDestination) -> str:
    """Compose the plain ``refused`` message."""
    return (
        f"tracker.egress is recorded as {EGRESS_REFUSED!r} in this project's own "
        f".kittify/config.yaml; refusing tracker egress to {destination.value}"
    )


def _permit_message(destination: EgressDestination) -> str:
    """Compose the Channel-2 grant message (``LOCAL_SUBPROCESS`` + ``permitted`` only)."""
    return (
        f"tracker egress to {destination.value} is permitted by tracker.egress: "
        f"{EGRESS_PERMITTED!r}, recorded in this project's own .kittify/config.yaml"
    )


_LOCAL_GRANT_REMEDY: Final = (
    "record `tracker.egress: permitted` in this project's own .kittify/config.yaml"
)


def tracker_egress_verdict(
    root: Path | None, *, destination: EgressDestination, identifiers: str
) -> TrackerEgressVerdict:
    """Decide whether tracker data may leave the machine for *destination*. Never raises.

    ``destination`` is required and keyword-only -- there is no default, so no call site can
    inherit a polarity silently. ``identifiers`` stays a required parameter so a transport that
    did not declare what it can put on the wire cannot quietly skip the declaration, even
    though the local channel no longer renders it into messages.

    At ``LOCAL_SUBPROCESS`` the project's own ``tracker.egress`` key decides: ``permitted``
    grants; ``refused``, an illegal value, or an unreadable config refuse; absence refuses too,
    with the grant recorded as the remedy -- spawning a machine-global executable with mission
    data needs an explicit yes, and inability to determine consent is never consent.
    """
    del identifiers  # required declaration only, since Channel 1 retired

    if root is None:
        return TrackerEgressVerdict(
            refused=True,
            refusing_channels=frozenset({CHANNEL_2}),
            destination=destination,
            channel2_state=CHANNEL2_ABSENT,
            channel2_raw=EGRESS_ABSENT,
            message=(
                "no project root could be resolved, so no tracker.egress decision can be read; "
                f"refusing tracker egress to {destination.value}"
            ),
            remedies=(),
        )

    channel2_state, channel2_raw = _resolve_channel2(root)

    if channel2_state == EGRESS_PERMITTED:
        return TrackerEgressVerdict(
            refused=False,
            refusing_channels=frozenset(),
            destination=destination,
            channel2_state=channel2_state,
            channel2_raw=channel2_raw,
            message=_permit_message(destination),
            remedies=(),
        )

    if channel2_state == CHANNEL2_FAULT:
        message = _fault_message(destination, channel2_raw)
    elif channel2_state == EGRESS_REFUSED:
        message = _refused_message(destination)
    else:
        message = (
            f"no tracker.egress key is recorded in this project's own .kittify/config.yaml; "
            f"refusing tracker egress to {destination.value}"
        )
    return TrackerEgressVerdict(
        refused=True,
        refusing_channels=frozenset({CHANNEL_2}),
        destination=destination,
        channel2_state=channel2_state,
        channel2_raw=channel2_raw,
        message=message,
        remedies=(_LOCAL_GRANT_REMEDY,) if channel2_state == CHANNEL2_ABSENT else (),
    )
