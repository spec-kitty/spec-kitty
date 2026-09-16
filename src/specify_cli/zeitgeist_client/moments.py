"""#190: per-developer moment settings — the off switch, the filters, and
the rate ceiling that decide which Zeitgeist status moments reach agent
context ("Moments in agent context", Robert 2026-08-26: "there needs to be a
way to filter or unsubscribe because some people will find this annoying").

Three facts fix this module's shape:

**Filtering is the reader's business.** The relay stays a per-team firehose
(``zeitgeist/managed.py`` fans every accepted frame out to every subscriber
of the frame's scope); nothing here is ever sent upstream. What this module
produces is a *predicate* over already-received :class:`~.live_frame.LiveFrame`
objects, which ``filtered_stream.FilteredStream`` applies client-side before a
frame is delivered — the exact seam Priivacy-ai/spec-kitty#190 names
("applied client-side in the stream client").

**Team awareness by default.** Unconfigured agents receive team moments,
including unfamiliar missions and moments without a mission. Explicit ``mine``
restricts delivery to locally known or configured missions; this is a checkout
proxy, never an assignment or ownership claim. Invalid modes fail closed to off.

**One setting, two files.** Global preferences live in ``~/.kittify/config.toml``
and repository preferences in ``<repo>/.kittify/config.toml``. Both scopes can
narrow delivery: modes choose ``off < mine < team``, allowlists intersect, and
rate ceilings choose the lower configured value. Repository content cannot
widen an explicit developer-global restriction.

Nothing here performs network I/O, so this module sits outside the egress
consent boundary by construction; and nothing here reads a credential —
mode/filters/rate are preference state, never auth state.
"""

from __future__ import annotations

import time
import tomllib

from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import tomli_w
from spec_kitty_events.zeitgeist_attrs import VOLATILE_EVENT_TYPES

from kernel.paths import get_kittify_home


class MomentsMode(StrEnum):
    """How much of the team's moment stream an agent surface may deliver.

    ``off``  — nothing; the MCP server refuses to start (#190 item 3).
    ``mine`` — moments about locally known or explicitly configured missions.
    ``team`` — everything the team's relay carries (the default).
    """

    OFF = "off"
    MINE = "mine"
    TEAM = "team"


#: Team awareness is the default; explicit preferences may narrow it.
DEFAULT_AGENTS_MODE = MomentsMode.TEAM

#: #190 item 4: "at most N moments per minute surfaced to an agent (default
#: small)". Small enough that a chatty team cannot flood an agent's context,
#: large enough that one developer's normal work is never summarised away.
DEFAULT_RATE_PER_MINUTE = 10

CONFIG_FILENAME = "config.toml"
REPO_CONFIG_DIRNAME = ".kittify"

#: The TOML table every aspect lives under, in both config files.
CONFIG_SECTION = "moments"

_WINDOW_S = 60.0


class MomentsDisabled(Exception):
    """Raised when a moment surface starts against ``[moments] agents =
    "off"``. Carries the human line its caller reports — one sentence, never
    a traceback — plus the config file that decided it."""

    def __init__(self, settings: MomentSettings) -> None:
        super().__init__(
            f"Zeitgeist moments to agents are switched off "
            f'([moments] agents = "{settings.agents.value}" per {settings.agents_source}); '
            "run `spec-kitty moments on` to re-enable."
        )
        self.settings = settings


@dataclass(frozen=True)
class MomentSettings:
    """The effective moment preferences for one developer in one checkout.

    The four tuple-valued fields are allowlists: empty means "no restriction"
    (the mode alone governs), non-empty means "only these". ``agents_source``
    records where the effective mode came from — ``"default"``, the winning
    config file's path, or that path marked invalid when the stored value was
    unreadable — so ``status`` can say *why* rather than just *what*.

    ``blocked_filters`` names valid allowlists with no overlap across scopes.
    These admit nothing; an empty tuple alone would mean no restriction.

    ``invalid_filters`` names which of ``repos``/``missions``/``teammates``/
    ``kinds`` were PRESENT in the deciding config but not a list — the shape
    :func:`_string_list` quietly empties to the same tuple an unset key
    produces. That collapse is the bug this field exists to prevent: an unset
    filter means "no restriction" (intentional), but a malformed one means
    the developer asked for a restriction and typo'd it, so it must never
    read as "no restriction" too — :func:`frame_predicate` and
    :func:`allows_repo` fail that dimension closed (admit nothing) instead.

    ``kinds`` is spelled-correctly-but-wrong's other trap: it matches a
    frame's raw wire ``kind`` (:func:`event_kind`) — the volatile family name
    (``WPStatusChanged``, ``MissionCreated``, …; the full list is
    :data:`KNOWN_KIND_NAMES`) — never the dotted style #190's own text used
    (``wp.move``, ``mission.created``). A well-formed list of dotted or
    otherwise unknown strings is not ``invalid_filters`` material — it is
    valid TOML, so it settles into ``kinds`` normally — but it can never
    match anything, and :func:`frame_predicate` then fails every event
    closed. :func:`unknown_kind_names` is how ``moments status``
    (Priivacy-ai/spec-kitty#210) makes that silence visible.
    """

    agents: MomentsMode = DEFAULT_AGENTS_MODE
    repos: tuple[str, ...] = ()
    missions: tuple[str, ...] = ()
    teammates: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    rate_per_minute: int = DEFAULT_RATE_PER_MINUTE
    agents_source: str = "default"
    invalid_filters: frozenset[str] = frozenset()
    blocked_filters: frozenset[str] = frozenset()

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe projection (StrEnum members serialise as their values;
        ``invalid_filters`` as a sorted list — a frozenset is not JSON-safe).

        Adds ``kinds_unknown`` — the :func:`unknown_kind_names` among
        ``kinds`` — so a machine caller sees the same "this can never match"
        signal `spec-kitty moments status`'s human text does, without
        re-deriving it against :data:`KNOWN_KIND_NAMES` itself."""
        payload = asdict(self)
        payload["invalid_filters"] = sorted(self.invalid_filters)
        payload["blocked_filters"] = sorted(self.blocked_filters)
        payload["kinds_unknown"] = [] if "kinds" in self.invalid_filters else list(unknown_kind_names(self.kinds))
        return payload


def global_config_path(*, home: Path | None = None) -> Path:
    """The developer-global config file holding the default ``[moments]``
    table. ``home`` exists for callers that must pin the root (tests); the
    production door is :func:`kernel.paths.get_kittify_home`."""
    return (home if home is not None else get_kittify_home()) / CONFIG_FILENAME


def repo_config_path(project_root: Path) -> Path:
    """The per-repo override file inside ``project_root``."""
    return project_root / REPO_CONFIG_DIRNAME / CONFIG_FILENAME


def locate_repo_root(cwd: Path | None = None) -> Path | None:
    """The Spec Kitty checkout containing ``cwd``, or ``None`` when there is
    none. A Git checkout without the canonical ``.kittify`` marker is not a
    Spec Kitty checkout for this preference surface. Function-scoped import:
    the resolver drags in a large
    ``specify_cli.core`` graph no other reader of this module should pay for
    (same lazy-import discipline ``cli/commands/zeitgeist.py`` records)."""
    from specify_cli.core.paths import locate_project_root  # noqa: PLC0415

    project_root = locate_project_root(cwd if cwd is not None else Path.cwd())
    if project_root is None or not (project_root / REPO_CONFIG_DIRNAME).is_dir():
        return None
    return cast(Path, project_root)


def _read_section(path: Path) -> tuple[dict[str, Any], str | None]:
    """The ``[moments]`` table of one config file, plus a parse-error message
    when the file exists but ``tomllib`` could not read it.

    Returns ``({}, None)`` when there is no file, no table, or the file is
    unreadable for reasons unrelated to its content (missing, a directory,
    permission-denied) — those read as unset, the same tolerance
    ``credentials._read_all`` applies to its store.

    Returns ``({}, message)`` when the file exists but is not valid TOML: a
    syntax error ANYWHERE in the file — even outside ``[moments]`` — must not
    read as "this file said nothing", because that silently discards an
    explicit ``agents = "off"`` and every filter the file set, widening the
    effective mode to the ``team`` default (Priivacy-ai/spec-kitty#211). The
    caller fails that scope's mode closed instead."""
    try:
        with path.open("rb") as fh:
            document = tomllib.load(fh)
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return {}, None
    except tomllib.TOMLDecodeError as exc:
        return {}, str(exc)
    section = document.get(CONFIG_SECTION)
    return (dict(section) if isinstance(section, Mapping) else {}), None


def _coerce_mode(raw: Any, source: str) -> tuple[MomentsMode, str]:
    """A stored ``agents`` value as ``(mode, provenance)``. Anything but the
    three spelled modes fails CLOSED to ``off``: a mistyped value narrows the
    stream, it never widens it."""
    if isinstance(raw, str):
        try:
            return MomentsMode(raw.strip().lower()), source
        except ValueError:
            pass
    return MomentsMode.OFF, f"{source} (invalid value {raw!r}; failing closed to off)"


def _string_list(raw: Any) -> tuple[str, ...]:
    """A stored list-of-strings filter as stripped, de-duplicated, order-
    preserving strings. Validation lives in :func:`_malformed_filter_keys`;
    callers only ask this helper for the usable values."""
    if not isinstance(raw, (list, tuple)):
        return ()
    seen: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        value = entry.strip()
        if value and value not in seen:
            seen.append(value)
    return tuple(seen)


#: The four allowlist keys a config's ``[moments]`` table may set.
_FILTER_KEYS = ("repos", "missions", "teammates", "kinds")


def _malformed_filter_keys(merged: Mapping[str, Any]) -> frozenset[str]:
    """Which allowlist keys are present but unusable.

    A key that is absent means "no restriction". A present key with the wrong
    container, an empty list, a blank string, or a non-string entry means the
    developer attempted a restriction but typed it wrong; that dimension must
    fail closed instead of collapsing to "no restriction" and widening the
    stream.
    """
    malformed: set[str] = set()
    for key in _FILTER_KEYS:
        if key not in merged:
            continue
        raw = merged[key]
        if not isinstance(raw, (list, tuple)):
            malformed.add(key)
            continue
        if not raw:
            malformed.add(key)
            continue
        for entry in raw:
            if not isinstance(entry, str) or not entry.strip():
                malformed.add(key)
                break
    return frozenset(malformed)


_MODE_RANK = {
    MomentsMode.OFF: 0,
    MomentsMode.MINE: 1,
    MomentsMode.TEAM: 2,
}


def _parse_error_candidate(path: Path, message: str) -> tuple[MomentsMode, str]:
    """A config file that exists but failed to parse contributes a forced
    ``off`` candidate to :func:`_resolve_mode` — the file might have said
    ``agents = "off"`` or set a filter, and an unparseable file cannot be
    trusted to have said anything narrower, so the scope fails closed
    instead of being treated as absent (#211)."""
    return MomentsMode.OFF, f"{path} (unparseable: {message}; failing closed to off)"


def _resolve_mode(
    global_section: Mapping[str, Any],
    repo_section: Mapping[str, Any],
    *,
    global_error: str | None,
    repo_error: str | None,
    home: Path | None,
    project_root: Path | None,
) -> tuple[MomentsMode, str]:
    """Resolve ``agents`` narrow-only across global and repo config.

    Repo settings used to have unconditional precedence. For this per-developer
    switch, that lets a committed repo file re-enable moments for someone who
    globally opted out. Treat the two values as a lattice instead: choose the
    narrower mode by ``off < mine < team`` and report the source that won.

    A file that failed to parse (``global_error``/``repo_error`` set) always
    contributes ``off`` regardless of whatever ``agents`` value the other
    scope's file holds — see :func:`_parse_error_candidate`.
    """
    candidates: list[tuple[MomentsMode, str]] = []
    if global_error is not None:
        candidates.append(_parse_error_candidate(global_config_path(home=home), global_error))
    elif "agents" in global_section:
        candidates.append(_coerce_mode(global_section["agents"], str(global_config_path(home=home))))
    if project_root is not None:
        if repo_error is not None:
            candidates.append(_parse_error_candidate(repo_config_path(project_root), repo_error))
        elif "agents" in repo_section:
            candidates.append(_coerce_mode(repo_section["agents"], str(repo_config_path(project_root))))
    if not candidates:
        return DEFAULT_AGENTS_MODE, "default"
    return min(candidates, key=lambda candidate: _MODE_RANK[candidate[0]])


def _coerce_rate(raw: Any) -> int:
    """A stored ``rate_per_minute`` as a usable cap. Absent/negative/non-int
    falls back to the default; zero is honoured literally (surface no
    moments), since that is what a developer writing 0 asked for."""
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return DEFAULT_RATE_PER_MINUTE
    return int(raw)


def load_settings(
    *,
    project_root: Path | None = None,
    home: Path | None = None,
) -> MomentSettings:
    """The effective settings for one developer in one checkout: the global
    and repo ``[moments]`` tables combined without widening either scope.

    ``project_root=None`` discovers the checkout from the process working
    directory (:func:`locate_repo_root`); ``None`` found simply means no repo
    override exists. Both paths are optional parameters rather than globals
    so tests can pin them without touching the real home.
    """
    if project_root is None:
        project_root = locate_repo_root()
    global_section, global_error = _read_section(global_config_path(home=home))
    repo_section, repo_error = _read_section(repo_config_path(project_root)) if project_root is not None else ({}, None)

    invalid_filters = _malformed_filter_keys(global_section) | _malformed_filter_keys(repo_section)
    filters: dict[str, tuple[str, ...]] = {}
    blocked_filters: set[str] = set()
    for key in _FILTER_KEYS:
        configured = [_string_list(section[key]) for section in (global_section, repo_section) if key in section]
        values = configured[0] if configured else ()
        if len(configured) == 2:
            values = tuple(value for value in values if value in configured[1])
            if not values and key not in invalid_filters:
                blocked_filters.add(key)
        filters[key] = values
    rates = [_coerce_rate(section["rate_per_minute"]) for section in (global_section, repo_section) if "rate_per_minute" in section]
    mode, agents_source = _resolve_mode(
        global_section,
        repo_section,
        global_error=global_error,
        repo_error=repo_error,
        home=home,
        project_root=project_root,
    )
    return MomentSettings(
        agents=mode,
        repos=filters["repos"],
        missions=filters["missions"],
        teammates=filters["teammates"],
        kinds=filters["kinds"],
        rate_per_minute=min(rates) if rates else DEFAULT_RATE_PER_MINUTE,
        agents_source=agents_source,
        invalid_filters=invalid_filters,
        blocked_filters=frozenset(blocked_filters),
    )


def write_agents_mode(
    mode: MomentsMode,
    *,
    scope: str = "global",
    project_root: Path | None = None,
    home: Path | None = None,
) -> Path:
    """Persist ``[moments] agents = <mode>`` to the global or repo config
    file, preserving every other key in that file, and return the path
    written.

    The rewrite is whole-file (``tomllib`` in, ``tomli_w`` out): comments in
    a hand-edited config are not preserved. That is the accepted cost of one
    writer for both scopes — the alternative is a second TOML dependency for
    a table this CLI owns.
    """
    if scope == "repo":
        if project_root is None:
            raise ValueError("scope='repo' requires project_root")
        path = repo_config_path(project_root)
    elif scope == "global":
        path = global_config_path(home=home)
    else:
        raise ValueError(f"unknown scope {scope!r} (expected 'global' or 'repo')")
    try:
        with path.open("rb") as fh:
            document: dict[str, Any] = tomllib.load(fh)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        document = {}

    section = document.get(CONFIG_SECTION)
    section = dict(section) if isinstance(section, Mapping) else {}
    section["agents"] = mode.value
    document[CONFIG_SECTION] = section

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("wb") as fh:
        tomli_w.dump(document, fh)
    tmp_path.replace(path)  # atomic on POSIX and Windows (same volume)
    return path


def local_missions(project_root: Path | None) -> frozenset[str]:
    """The mission slugs this checkout resolves — the cheap, local stand-in
    for locally known missions, not developer assignment.

    Routed through :class:`~specify_cli.context.mission_resolver.FsMissionResolver`
    (the sanctioned mission-discovery boundary — a raw ``kitty-specs/`` walk
    here would bypass it), so exactly its semantics apply: identity-bearing
    missions only; legacy directories whose ``meta.json`` lacks a
    ``mission_id``, and non-directory entries, are invisible to it. A missing
    root yields the empty set.

    Under ``mine``, a checkout that resolves nothing therefore surfaces no
    moments beyond explicitly configured missions, never
    everything.
    """
    if project_root is None:
        return frozenset()

    from specify_cli.context.mission_resolver import FsMissionResolver  # noqa: PLC0415

    try:
        return frozenset(mission.mission_slug for mission in FsMissionResolver(project_root).all_missions())
    except OSError:
        # An unreadable checkout reads as "no known missions" — quiet, never
        # everything (the same tolerance _read_section applies to config).
        return frozenset()


# --- #190: the client-side predicate ----------------------------------------

#: Every volatile family name a ``kinds`` entry can actually match on the
#: wire — re-exported from :mod:`spec_kitty_events.zeitgeist_attrs` so a
#: ``[moments]`` config or its docs never has to spell the vocabulary a
#: second time (``WPStatusChanged``, ``MissionCreated``, ``PhaseEntered``, …,
#: not the dotted ``wp.move``/``mission.created`` style #190's own text
#: used). See :func:`unknown_kind_names`.
KNOWN_KIND_NAMES: frozenset[str] = VOLATILE_EVENT_TYPES


def event_kind(payload: Mapping[str, Any]) -> str | None:
    """An event payload's ``kind`` — the volatile vocabulary's event type
    (``WPStatusChanged``, ``MissionCreated``, …; the full list is
    :data:`KNOWN_KIND_NAMES`) — or ``None`` when absent."""
    kind = payload.get("kind")
    return kind if isinstance(kind, str) and kind else None


def unknown_kind_names(kinds: Iterable[str]) -> tuple[str, ...]:
    """Which entries of a configured ``kinds`` filter are not in
    :data:`KNOWN_KIND_NAMES`, order-preserving.

    A well-formed ``kinds`` list of dotted (``wp.move``) or otherwise unknown
    strings is not a shape :func:`_malformed_filter_keys` catches — it is
    valid TOML — so it settles into :attr:`MomentSettings.kinds` looking like
    an ordinary, active filter. It can never match a frame's wire
    :func:`event_kind`, though, so :func:`frame_predicate` fails every event
    closed and the developer sees zero moments with no error anywhere. This
    is the fail-closed direction Priivacy-ai/spec-kitty#210 asks to keep —
    just make the silence visible, which is `spec-kitty moments status`'s
    job (``cli/commands/moments.py``)."""
    return tuple(kind for kind in kinds if kind not in KNOWN_KIND_NAMES)


def event_actor(payload: Mapping[str, Any]) -> str | None:
    """An event payload's attested actor label (``actor.user`` — the identity
    the relay derives from the capability credential), or ``None``."""
    actor = payload.get("actor")
    if not isinstance(actor, Mapping):
        return None
    user = actor.get("user")
    return user if isinstance(user, str) and user else None


def event_mission(payload: Mapping[str, Any]) -> str | None:
    """The mission an event moment is about: the ``mission_slug`` attr the
    volatile codec rides on every mission-scoped family, falling back to the
    frame ``ref`` (that codec's aggregate field verbatim). ``None`` when the
    moment names no mission at all."""
    attrs = payload.get("attrs")
    if isinstance(attrs, Mapping):
        slug = attrs.get("mission_slug")
        if isinstance(slug, str) and slug:
            return slug
    ref = payload.get("ref")
    if isinstance(ref, str) and ref:
        return ref.split("/", 1)[0]
    return None


def frame_predicate(
    settings: MomentSettings,
    *,
    local_missions: Iterable[str] = (),
) -> Callable[[Any], bool]:
    """Build the client-side predicate ``filtered_stream.FilteredStream``
    applies to each received frame.

    Non-event frames (presence/focus/signal) always pass — the setting governs
    *moments*, never liveness. An event passes only when BOTH hold:

    * every configured filter admits it — ``kinds``, ``teammates``, and
      ``missions`` are allowlists that apply in every mode;
    * the mode admits it — ``team`` admits all, ``off`` admits nothing, and
      ``mine`` admits moments whose mission is one of this checkout's own
      (:data:`local_missions`) or of the configured ``missions``.

    An event that names no mission fails explicit ``mine``; the
    same moment passes ``team`` subject to the filters alone.

    A ``kinds``/``teammates``/``missions`` value present in config but not a
    list (e.g. a typo'd bare string, see ``settings.invalid_filters``) fails
    ITS dimension closed: every event is refused, never admitted, so a
    malformed allowlist narrows the stream to nothing instead of silently
    reading as "no restriction" and widening it (Priivacy-ai/spec-kitty#190
    squad follow-up, PR #201). ``repos`` is not one of these — it gates
    subscriptions, not frames — and is checked by :func:`allows_repo` instead.
    """
    kinds = frozenset(settings.kinds)
    teammates = frozenset(settings.teammates)
    configured_missions = frozenset(settings.missions)
    my_missions = configured_missions | frozenset(local_missions)
    predicate_relevant_invalid = (settings.invalid_filters | settings.blocked_filters) & {"kinds", "teammates", "missions"}

    def predicate(live_frame: Any) -> bool:
        if getattr(live_frame, "frame_type", None) != "event":
            return True
        if settings.agents is MomentsMode.OFF:
            return False
        if predicate_relevant_invalid:
            return False
        payload = getattr(live_frame, "payload", None)
        if not isinstance(payload, Mapping):
            return False
        if kinds:
            kind = event_kind(payload)
            if kind is None or kind not in kinds:
                return False
        if teammates:
            actor = event_actor(payload)
            if actor is None or actor not in teammates:
                return False
        mission = event_mission(payload)
        if configured_missions and (mission is None or mission not in configured_missions):
            return False
        # Explicit mine requires a locally known or configured mission.
        return not (settings.agents is MomentsMode.MINE and (mission is None or mission not in my_missions))

    return predicate


def allows_repo(settings: MomentSettings, store_key: str) -> bool:
    """Whether moments for the credential-store key ``store_key``
    (``host/owner/repo``) may be surfaced at all. An unset ``repos`` filter
    allows every repo this developer holds a credential for; a set one is an
    exact-match allowlist — the store key is the only repo identity a moment
    surface has, since one subscription is bound to exactly one credential.

    A ``repos`` value present in config but not a list fails closed here —
    every repo is refused, never every repo admitted — matching
    :func:`frame_predicate`'s treatment of the other three filters."""
    if "repos" in settings.invalid_filters | settings.blocked_filters:
        return False
    return not settings.repos or store_key in settings.repos


class MomentRateGate:
    """#190 item 4: at most ``limit_per_minute`` moments surfaced to an agent
    in any rolling 60-second window; everything beyond the cap is counted so
    the caller can summarise it as "+k more".

    One gate belongs to one agent session (one stdio server instance), not to
    one call — a client polling every two seconds must not earn a fresh quota
    each poll. The clock is injected so tests advance time instead of
    sleeping; ``time.monotonic`` is the production default (elapsed-time
    measurement, matching ``budget.py``'s idiom — never wall-clock datetimes).
    """

    def __init__(
        self,
        limit_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit_per_minute
        self._clock = clock
        self._window: deque[float] = deque()
        self._suppressed_since_read = 0

    def admit(self) -> bool:
        """Whether one more moment may surface right now. Rejected moments
        are counted, never queued — they are summarised, not delayed (#190:
        "the rest summarised")."""
        now = self._clock()
        while self._window and self._window[0] <= now - _WINDOW_S:
            self._window.popleft()
        if len(self._window) >= self._limit:
            self._suppressed_since_read += 1
            return False
        self._window.append(now)
        return True

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def suppressed(self) -> int:
        """Moments rejected since the last :meth:`take_summary`."""
        return self._suppressed_since_read

    def take_summary(self) -> str | None:
        """The "+k more" line for everything suppressed so far, or ``None``
        when nothing was; reading resets the counter so one watch call's
        report says what THAT call withheld, not the session's lifetime total."""
        count, self._suppressed_since_read = self._suppressed_since_read, 0
        if not count:
            return None
        return f"+{count} more moment{'s' if count != 1 else ''} withheld (agent rate cap: {self._limit}/min)"
