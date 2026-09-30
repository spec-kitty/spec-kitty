"""Parity oracle primitives for the ``runtime_bridge`` characterization suite.

Mission ``runtime-bridge-degod-01KX8M1C`` (#2531), WP01 — the BLOCKING safety
net that every extraction WP (WP03-WP10) re-runs as its acceptance gate. See
``kitty-specs/runtime-bridge-degod-01KX8M1C/contracts/parity-oracle.md`` for
the authoritative contract; this module implements it verbatim.

This module owns three concerns, corresponding to contract sections:

* **Equality contract** (``canonical`` / ``assert_parity``) — the
  MASK / PATH-NORMALIZE / STABLE partition over ``Decision.to_dict()``.
* **Capture-and-assert side-effect isolation** (``capture_side_effects``,
  ``SideEffectCapture``) — binding equality on recorded payloads, not mere
  stubbing.
* **Coverage-floor bookkeeping** (``capture_decision_sites``,
  ``capture_guard_calls``, ``CoverageLedger``, ``assert_coverage_floor_met``)
  — a *checkable count* of the 29 ``Decision(...)`` sites and the guard
  branches, each tallied from its owning public entry, so a hollow oracle
  (one that drives zero/few sites) cannot pass silently.

Nothing here stubs ``next_step`` / ``get_or_start_run`` — the runtime planner
is the logic under test (WP01 safeguard). All capture wrappers call through
to the real implementation and only *observe* the call.

**Scope of the guarantee (read before over-trusting a green oracle).** Every
assertion compares two independent runs of the *current* code; there are no
stored golden baselines. This oracle therefore catches: non-determinism,
coverage-floor regressions, and binding-equality breaks in the captured side
effects. It does NOT, on its own, catch a *consistent* behavior change across
an extraction (both runs shift identically). The compensating control is that
every extraction WP (WP03–WP10) ALSO re-runs the full existing runtime test
suite (``tests/next/*``, ``tests/integration/test_*_runtime_walk.py``, …),
which pins specific decide_next / query / answer outputs. Treat this oracle as
the coverage-floor + determinism + side-effect-payload guarantee layered ON TOP
of that suite, not as a standalone golden characterization.
"""

from __future__ import annotations

import contextlib
import inspect
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

    from runtime.next.decision import Decision

# ---------------------------------------------------------------------------
# §Equality contract — canonical(decision, repo_root) / assert_parity
# ---------------------------------------------------------------------------

# MASK: dropped before compare, but None-vs-present is preserved (a kind-shape
# change must not be blinded). These are ULIDs / wall-clock timestamps that
# differ on every real run by construction.
_MASKED_FIELDS: frozenset[str] = frozenset({"timestamp", "run_id", "decision_id"})

# PATH-NORMALIZE: relativized to *each run's own* repo_root. ``reason`` is the
# non-obvious carrier (contract §Equality contract) — it embeds feature_dir /
# exc paths as free text, not a bare path value, so it is normalized via
# substring replacement rather than Path.relative_to.
_PATH_VALUE_FIELDS: frozenset[str] = frozenset({"workspace_path"})
_FREE_TEXT_PATH_FIELDS: frozenset[str] = frozenset({"reason"})

# ``prompt_file`` is a PATH-NORMALIZE field per the contract, but — unlike
# ``workspace_path`` — it does NOT live under repo_root. Every prompt writer
# roots its output at the shared, per-repo prompt namespace
# ``<tempdir>/spec-kitty-prompts/<sha256(repo_root)[:16]>/`` (see
# ``runtime.next._tmp_namespace``), which sits OUTSIDE the mission repo, so
# relativizing to repo_root leaves it untouched and two independent runs
# diverge on it. Its run-local noise is (a) that ``<tempdir>/…/<hash>`` prefix
# and (b) the ``mkstemp`` random suffix on composed markers
# (``spec-kitty-composed-<action>-<rand>.md``). The STABLE semantic carrier is
# the basename stem: ``spec-kitty-next-<agent>-<mission>-<action>[-<wp>]`` for
# the deterministic writer, ``spec-kitty-composed-<action>`` for the marker. We
# collapse (a)+(b) and keep the stem — so a genuine routing change (a different
# action/wp → a different stem) still diverges and is caught.
_PROMPT_FILE_FIELDS: frozenset[str] = frozenset({"prompt_file"})
# Matches a composed marker's mkstemp random suffix so it can be stripped. NB:
# this also strips a trailing ``-<6–12 alnum>`` token from any future composed
# action name that happens to end that way; safe for today's enum actions
# (plan/tasks/specify/review/accept/…) — revisit if composed action names grow
# a literal random-looking trailing segment.
_COMPOSED_MARKER_RANDOM_RE = re.compile(r"^(spec-kitty-composed-.+?)-[A-Za-z0-9_]{6,12}\.md$")
_PROMPT_TOKEN = "<PROMPT>"

_ROOT_TOKEN = "<REPO_ROOT>"
_PRESENT_TOKEN = "<PRESENT>"


def _normalize_prompt_file(value: str | None) -> str | None:
    """Collapse the run-local noise in a ``prompt_file`` path.

    Drops the volatile ``<tempdir>/spec-kitty-prompts/<hash>/`` prefix by
    reducing to the basename, then strips the ``mkstemp`` random suffix from a
    composed marker (``spec-kitty-composed-<action>-<rand>.md`` →
    ``spec-kitty-composed-<action>.md``). The deterministic
    ``spec-kitty-next-…`` writer already produces a stable basename, so it is
    left as-is under the ``<PROMPT>/`` token. Returns ``None`` unchanged so a
    kind-shape change (prompt present vs absent) is never blinded.
    """
    if value is None:
        return None
    name = Path(str(value)).name
    match = _COMPOSED_MARKER_RANDOM_RE.match(name)
    if match:
        name = f"{match.group(1)}.md"
    return f"{_PROMPT_TOKEN}/{name}"


def _normalize_path_value(value: str | None, repo_root: Path) -> str | None:
    """Relativize a bare path-shaped field to ``repo_root``."""
    if value is None:
        return None
    text = str(value)
    for candidate_root in _root_variants(repo_root):
        if text == candidate_root:
            return _ROOT_TOKEN
        prefix = candidate_root.rstrip("/") + "/"
        if text.startswith(prefix):
            return f"{_ROOT_TOKEN}/{text[len(prefix) :]}"
    return text


def _normalize_free_text(value: str | None, repo_root: Path) -> str | None:
    """Collapse every occurrence of ``repo_root`` (any spelling) inside free text."""
    if value is None:
        return None
    text = str(value)
    for candidate_root in _root_variants(repo_root):
        if candidate_root:
            text = text.replace(candidate_root, _ROOT_TOKEN)
    return text


def _root_variants(repo_root: Path) -> list[str]:
    """Return the raw and resolved string spellings of ``repo_root``.

    Temp dirs are frequently accessed through a symlinked path (e.g. macOS
    ``/tmp`` -> ``/private/tmp``); both spellings must collapse identically or
    the normalizer under-collapses and the oracle self-blinds in the other
    direction (falsely reports a parity break on pure path noise).
    """
    variants = {str(repo_root)}
    with contextlib.suppress(OSError):
        variants.add(str(repo_root.resolve()))
    # Longest first so a resolved-root prefix match wins over a shorter raw one.
    return sorted(variants, key=len, reverse=True)


def _normalize_origin(origin: Any, repo_root: Path) -> Any:
    if not isinstance(origin, dict):
        return origin
    normalized = dict(origin)
    if "mission_path" in normalized:
        normalized["mission_path"] = _normalize_path_value(normalized["mission_path"], repo_root)
    # origin.mission_tier is explicitly STABLE (contract §Equality contract) —
    # left untouched.
    return normalized


def canonical(decision: Decision, repo_root: Path) -> dict[str, Any]:
    """Return ``decision.to_dict()`` masked/normalized per the equality contract.

    * MASK ``timestamp`` / ``run_id`` / ``decision_id`` -> ``<PRESENT>`` when
      not ``None``, else ``None`` (None-vs-present is preserved).
    * PATH-NORMALIZE ``workspace_path`` / ``reason`` / ``origin.mission_path``
      relative to *this run's* ``repo_root``.
    * PROMPT-NORMALIZE ``prompt_file`` — a PATH-NORMALIZE field the contract
      lists, but it lives OUTSIDE ``repo_root`` (shared prompt namespace), so
      it is collapsed to its stable basename stem via
      :func:`_normalize_prompt_file` rather than relativized.
    * STABLE: every other field compares as-is (kind, agent, mission
      identity, state, action, wp_id, step_id, guard_failures [content AND
      order], progress, question/options, is_query, origin.mission_tier, …).
    """
    raw = decision.to_dict()
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _MASKED_FIELDS:
            out[key] = _PRESENT_TOKEN if value is not None else None
        elif key in _PROMPT_FILE_FIELDS:
            out[key] = _normalize_prompt_file(value)
        elif key in _PATH_VALUE_FIELDS:
            out[key] = _normalize_path_value(value, repo_root)
        elif key in _FREE_TEXT_PATH_FIELDS:
            out[key] = _normalize_free_text(value, repo_root)
        elif key == "origin":
            out[key] = _normalize_origin(value, repo_root)
        else:
            out[key] = value
    return out


def assert_parity(before: Decision, after: Decision, repo_root: Path) -> None:
    """Assert ``canonical(before, root) == canonical(after, root)``.

    Both decisions are canonicalized against the *same* ``repo_root`` — this
    is the contract's own definition (§Equality contract: ``assert_parity
    (before, after, repo_root) == canonical(before, root) == canonical
    (after, root)``). For decisions produced under two *different* per-run
    roots (the reason-normalizer meta-test), call :func:`canonical` directly
    with each decision's own root and compare the results.
    """
    canon_before = canonical(before, repo_root)
    canon_after = canonical(after, repo_root)
    if canon_before != canon_after:
        diff_keys = sorted(k for k in (set(canon_before) | set(canon_after)) if canon_before.get(k) != canon_after.get(k))
        details = "\n".join(f"  {k}: before={canon_before.get(k)!r} after={canon_after.get(k)!r}" for k in diff_keys)
        raise AssertionError(f"parity break — canonical Decision diverged on fields: {diff_keys}\n{details}")


# ---------------------------------------------------------------------------
# §Coverage — Decision-site reach tracking (traceback-based, ground truth)
# ---------------------------------------------------------------------------


@contextmanager
def capture_decision_sites(monkeypatch: pytest.MonkeyPatch, bridge_module: Any) -> Iterator[list[int]]:
    """Record the ``runtime_bridge.py`` line number of every ``Decision(...)`` call.

    All 29 ``Decision(...)`` construction sites live in ``runtime_bridge.py``
    and reference the same module-global ``Decision`` name (imported once at
    module scope). Patching that name to a thin recording subclass intercepts
    every site without stubbing any decision *logic* — the real
    ``__post_init__`` validation (the ``kind='step'`` prompt-file contract,
    including ``InvalidStepDecision``) still runs unchanged via
    ``super().__post_init__()``.

    Recording happens *before* delegating to the real ``__post_init__`` so
    sites that go on to raise ``InvalidStepDecision`` are still counted as
    reached (the call site did fire; the ensuing catch-and-reblock at another
    site is a *separate*, also-recorded, construction).
    """
    real_decision = bridge_module.Decision
    bridge_file = str(Path(inspect.getfile(bridge_module)))
    sites: list[int] = []

    # ``real_decision`` is resolved at runtime from the bridge module, so mypy
    # sees it as ``Any`` and rejects subclassing it. The subclass is genuinely
    # required (a recording ``__post_init__`` that still delegates to the real
    # validation) and cannot be expressed statically — narrowly scoped, safe.
    class _SpyDecision(real_decision):  # type: ignore[misc,valid-type]
        def __post_init__(self) -> None:
            for frame_info in inspect.stack()[1:]:
                if str(Path(frame_info.filename)) == bridge_file:
                    sites.append(frame_info.lineno)
                    break
            super().__post_init__()

    monkeypatch.setattr(bridge_module, "Decision", _SpyDecision)
    yield sites


# ---------------------------------------------------------------------------
# §Coverage — guard branch reach tracking
# ---------------------------------------------------------------------------


@dataclass
class GuardCall:
    fn: str  # "cli" | "composed"
    step_id_or_action: str
    mission: str | None
    legacy_step_id: str | None
    failures: list[str]


_CLI_GUARD_KNOWN_STEPS: frozenset[str] = frozenset({"specify", "plan", "tasks_outline", "tasks_packages", "tasks_finalize", "implement", "review"})
_RESEARCH_GUARD_KNOWN_ACTIONS: frozenset[str] = frozenset({"scoping", "methodology", "gathering", "synthesis", "output"})
_DOCUMENTATION_GUARD_KNOWN_ACTIONS: frozenset[str] = frozenset({"discover", "audit", "design", "generate", "validate", "publish", "accept"})
_SOFTWARE_DEV_GUARD_KNOWN_ACTIONS: frozenset[str] = frozenset({"specify", "plan", "implement", "review"})


def classify_guard_branch(call: GuardCall) -> str:
    """Return a stable branch-id string for a captured guard call.

    Branch granularity matches the WP's own vocabulary: the ``elif`` arm
    selected by ``step_id``/``action`` (+ ``mission`` family for the composed
    guard, + ``legacy_step_id`` for the ``tasks`` 4-way union), not the
    individual artifact-presence checks nested inside an arm.
    """
    if call.fn == "cli":
        step_id = call.step_id_or_action
        if step_id in _CLI_GUARD_KNOWN_STEPS:
            return f"cli:{step_id}"
        return "cli:fallthrough_unrecognized"

    mission = call.mission or "software-dev"
    action = call.step_id_or_action
    if mission == "research":
        if action in _RESEARCH_GUARD_KNOWN_ACTIONS:
            return f"composed:research:{action}"
        return "composed:research:fail_closed_default"
    if mission == "documentation":
        if action in _DOCUMENTATION_GUARD_KNOWN_ACTIONS:
            return f"composed:documentation:{action}"
        return "composed:documentation:fail_closed_default"
    # software-dev (default family)
    if action == "tasks":
        if call.legacy_step_id == "tasks_outline":
            return "composed:software-dev:tasks_outline"
        if call.legacy_step_id == "tasks_packages":
            return "composed:software-dev:tasks_packages"
        # legacy_step_id in {"tasks_finalize", None} -> the terminal union arm.
        return "composed:software-dev:tasks_union"
    if action in _SOFTWARE_DEV_GUARD_KNOWN_ACTIONS:
        return f"composed:software-dev:{action}"
    return "composed:software-dev:fallthrough_unrecognized"


@contextmanager
def capture_guard_calls(monkeypatch: pytest.MonkeyPatch, bridge_module: Any) -> Iterator[list[GuardCall]]:
    """Record every ``_check_cli_guards`` / ``_check_composed_action_guard`` call.

    Both are wrapped as call-through spies (never stubbed): the real guard
    logic always runs; only the (selector, returned failures) tuple is
    recorded, keyed by which of the two guard functions fired.
    """
    calls: list[GuardCall] = []
    real_cli = bridge_module._check_cli_guards
    real_composed = bridge_module._check_composed_action_guard

    def _cli_spy(
        step_id: str,
        feature_dir: Path,
        *,
        mission_family: str | None = None,
        repo_root: Path | None = None,
        owned: Any | None = None,
    ) -> list[str]:
        result: list[str] = list(
            real_cli(
                step_id,
                feature_dir,
                mission_family=mission_family,
                repo_root=repo_root,
                owned=owned,
            )
        )
        calls.append(GuardCall("cli", step_id, None, None, list(result)))
        return result

    def _composed_spy(
        action: str,
        feature_dir: Path,
        *,
        mission: str = "software-dev",
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: Any | None = None,
    ) -> list[str]:
        result: list[str] = list(
            real_composed(
                action,
                feature_dir,
                mission=mission,
                legacy_step_id=legacy_step_id,
                repo_root=repo_root,
                owned=owned,
            )
        )
        calls.append(GuardCall("composed", action, mission, legacy_step_id, list(result)))
        return result

    monkeypatch.setattr(bridge_module, "_check_cli_guards", _cli_spy)
    monkeypatch.setattr(bridge_module, "_check_composed_action_guard", _composed_spy)
    yield calls


# ---------------------------------------------------------------------------
# §Side-effect isolation — CAPTURE-and-assert (binding, not a stub)
# ---------------------------------------------------------------------------


class _RecordingProxy:
    """Transparent forwarding proxy that records every method call it forwards.

    Used to capture-and-assert binding payloads on emitters/loggers without
    changing their behavior: every call is forwarded to the real target and
    its (method_name, args, kwargs) is appended to ``sink`` in order.
    """

    def __init__(self, target: Any, sink: list[tuple[str, tuple[Any, ...], dict[str, Any]]]) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_sink", sink)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_target"), name)
        if not callable(attr):
            return attr
        sink = object.__getattribute__(self, "_sink")

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            result = attr(*args, **kwargs)
            sink.append((name, args, kwargs))
            return result

        return _wrapped


@dataclass
class SideEffectCapture:
    """Binding-equality capture of every side effect the WP names.

    Each list holds ``(method_name, args, kwargs)`` tuples in call order,
    except ``retrospective_calls`` which holds the raw kwargs dict passed to
    ``_run_retrospective_learning_capture`` (the actual retrospective gate
    reachable from ``decide_next_via_runtime`` — see module docstring note on
    ``_rich_hic_prompt`` unreachability) and ``append_event_calls`` /
    ``write_snapshot_calls`` / ``read_snapshot_calls`` which hold the raw
    ``(args, kwargs)`` passed to the IC-02 engine mutations.
    """

    sync_emitter_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    coord_commit_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    retrospective_calls: list[dict[str, Any]] = field(default_factory=list)
    append_event_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    write_snapshot_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    read_snapshot_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)


@contextmanager
def capture_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    bridge_module: Any,
    engine_module: Any,
) -> Iterator[SideEffectCapture]:
    """Capture-and-assert every side effect named in contract §Side-effect isolation.

    All wrappers call through to the real implementation (never stub) and
    record binding payloads:

    * the ``decide_next`` sync emitter (bridge:2556) and its answer-path twin
      (bridge:3410) — distinguished by call order (the sync emitter used by
      ``decide_next_via_runtime`` is always constructed before the one used
      by ``answer_decision_via_runtime`` within a single harness run; each
      harness run only ever drives ONE public entry, so at most one of the
      two sinks is populated per run).
    * the coord-branch ``DecisionGitLog`` commit at bridge:2563 and its
      answer-path twin at bridge:3427 (same distinguishing rule).
    * the retrospective gate (``_run_retrospective_learning_capture``).
    * the engine mutations relocated in IC-02: ``_append_event`` /
      ``_write_snapshot`` / ``_read_snapshot`` (module-level in
      ``_internal_runtime.engine``, patched at the source module so both
      module-level and function-local ``from ... import`` call sites in
      ``runtime_bridge.py`` observe the spy).
    """
    capture = SideEffectCapture()

    # decide_next's own sync emitter (bridge:2556) vs the answer-path's
    # (bridge:3410) share one production factory. A single harness call
    # only ever drives one public entry, so route by an explicit "current
    # sink" toggle the harness sets before invoking the entry.
    active_sink_holder = {"sync": capture.sync_emitter_calls, "coord": capture.coord_commit_calls}

    real_factory = bridge_module.runtime_emitter_for_mission

    def _factory_spy(**kwargs: Any) -> Any:
        emitter = real_factory(**kwargs)
        return _RecordingProxy(emitter, active_sink_holder["sync"])

    monkeypatch.setattr(bridge_module, "runtime_emitter_for_mission", _factory_spy)

    real_wrap = bridge_module._wrap_with_decision_git_log

    def _wrap_spy(emitter: Any, mission_slug: str, repo_root: Path, **kwargs: Any) -> Any:
        wrapped = real_wrap(emitter, mission_slug, repo_root, **kwargs)
        return _RecordingProxy(wrapped, active_sink_holder["coord"])

    monkeypatch.setattr(bridge_module, "_wrap_with_decision_git_log", _wrap_spy)

    real_retro = bridge_module._run_retrospective_learning_capture

    def _retro_spy(**kwargs: Any) -> None:
        capture.retrospective_calls.append(dict(kwargs))
        real_retro(**kwargs)

    monkeypatch.setattr(bridge_module, "_run_retrospective_learning_capture", _retro_spy)

    real_append_event = engine_module._append_event
    real_write_snapshot = engine_module._write_snapshot
    real_read_snapshot = engine_module._read_snapshot

    def _append_event_spy(*args: Any, **kwargs: Any) -> Any:
        capture.append_event_calls.append((args, kwargs))
        return real_append_event(*args, **kwargs)

    def _write_snapshot_spy(*args: Any, **kwargs: Any) -> Any:
        capture.write_snapshot_calls.append((args, kwargs))
        return real_write_snapshot(*args, **kwargs)

    def _read_snapshot_spy(*args: Any, **kwargs: Any) -> Any:
        capture.read_snapshot_calls.append((args, kwargs))
        return real_read_snapshot(*args, **kwargs)

    monkeypatch.setattr(engine_module, "_append_event", _append_event_spy)
    monkeypatch.setattr(engine_module, "_write_snapshot", _write_snapshot_spy)
    monkeypatch.setattr(engine_module, "_read_snapshot", _read_snapshot_spy)

    yield capture


# ``answer_decision_via_runtime`` builds ONE sync emitter (bridge:3410) and ONE
# coord wrap (bridge:3427) per call, recorded into the SAME sync_emitter_calls /
# coord_commit_calls sinks as decide_next_via_runtime; the two are distinguished
# by *which entry the harness ran*, not by a runtime toggle — so there is no
# separate answer-path sink.


# ---------------------------------------------------------------------------
# §Side-effect isolation — binding-equality canonicalization (payload level)
# ---------------------------------------------------------------------------

# Run-local identifiers embedded in the captured payloads that must be masked
# so a cross-run comparison is binding on WHAT was emitted/committed, not on
# per-run ids. ULIDs (Crockford base32, 26 chars); 32-hex run/event ids; UUIDs;
# ISO-8601 timestamps; and CPython object addresses (for any payload object
# whose repr falls back to ``<object at 0x…>``).
_ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
_HEX_ID_RE = re.compile(r"\b[0-9a-f]{32}\b")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+\-]\d{2}:\d{2})?")
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")
# The query path bootstraps a throwaway run under a global
# ``tempfile.mkdtemp(prefix="spec-kitty-query-run-")`` dir — outside repo_root
# and the per-run tmp base — so its random suffix must be masked too.
_EPHEMERAL_RUN_RE = re.compile(r"spec-kitty-query-run-[A-Za-z0-9_]+")


def _canonical_effect_payload(call: Any, repo_root: Path) -> str:
    """Return a run-local-noise-masked ``repr`` of one captured side-effect call.

    The payload (event dicts, snapshot objects, run-dir paths) is reduced to a
    string with run-local paths relativized and every run-local id / timestamp /
    object address masked, so two independent runs of the same fixture (or a
    pre- vs post-extraction run) compare equal iff the emitted/committed content
    is behaviorally identical — a change to WHAT is emitted diverges here.

    Paths are relativized against the per-run **temp base** (``repo_root.parent``,
    the ``tmp_path_factory`` dir), not just ``repo_root``: a pre-advanced fixture
    resolves the engine's run dir via its copied ``feature-runs.json`` to the
    frozen-snapshot subtree (``<base>/snapshot/…``), a sibling of the driven
    ``<base>/run`` — both live under the base, whose only run-local component is
    the per-run ``_a0`` / ``_b0`` suffix that must collapse identically.
    """
    text = repr(call)
    roots = set(_root_variants(repo_root)) | set(_root_variants(repo_root.parent))
    for root in sorted(roots, key=len, reverse=True):
        if root:
            text = text.replace(root, _ROOT_TOKEN)
    text = _EPHEMERAL_RUN_RE.sub("spec-kitty-query-run-<RID>", text)
    text = _UUID_RE.sub("<UUID>", text)
    text = _ISO_TS_RE.sub("<TS>", text)
    text = _HEX_ID_RE.sub("<HEXID>", text)
    text = _ULID_RE.sub("<ULID>", text)
    text = _ADDR_RE.sub("<ADDR>", text)
    return text


def canonical_side_effects(capture: SideEffectCapture, repo_root: Path) -> dict[str, list[str]]:
    """Canonicalize every captured side-effect sink for binding-equality compare.

    Returns one masked-``repr`` list per sink — sync emitter, coord-branch
    commit, and the IC-02 engine mutations (``_append_event`` / ``_write_snapshot``
    / ``_read_snapshot``) plus the retrospective gate. The test asserts these
    dicts are equal across the two independent runs, so a refactor that changes
    the emitted/committed payloads (not just the method-call sequence) is caught
    — the binding-equality the contract §Side-effect isolation commissions.
    """
    return {
        "sync_emitter": [_canonical_effect_payload(c, repo_root) for c in capture.sync_emitter_calls],
        "coord_commit": [_canonical_effect_payload(c, repo_root) for c in capture.coord_commit_calls],
        "append_event": [_canonical_effect_payload(c, repo_root) for c in capture.append_event_calls],
        "write_snapshot": [_canonical_effect_payload(c, repo_root) for c in capture.write_snapshot_calls],
        "read_snapshot": [_canonical_effect_payload(c, repo_root) for c in capture.read_snapshot_calls],
        "retrospective": [_canonical_effect_payload(c, repo_root) for c in capture.retrospective_calls],
    }


# ---------------------------------------------------------------------------
# §Coverage floor — checkable count, binding
# ---------------------------------------------------------------------------

#: The 29 ``Decision(...)`` construction line numbers in
#: ``src/runtime/next/runtime_bridge.py`` on unmodified source (grep-verified,
#: WP01 T004). 19 blocked / 4 step / 4 query / 1 terminal / 1 decision_required.
KNOWN_DECISION_SITES: frozenset[int] = frozenset(
    {
        2545,
        2592,
        2639,
        2715,
        2733,
        2754,
        2846,
        2893,
        2936,
        2965,
        3015,  # decide_next_via_runtime (11)
        3095,
        3121,
        3147,
        3184,  # query_current_state's 4 builders
        3468,
        3496,
        3515,
        3536,  # _build_wp_iteration_decision (4)
        3582,
        3597,
        3629,
        3659,
        3684,
        3701,
        3718,
        3760,
        3778,
        3798,  # _map_runtime_decision (10)
    }
)

assert len(KNOWN_DECISION_SITES) == 29, "site inventory drifted from the 29-site contract count"


@dataclass
class CoverageLedger:
    """Accumulates reach evidence across every fixture in the ledger.

    ``sites_reached`` / ``guard_branches_reached`` are the ground-truth
    tallies (populated from :func:`capture_decision_sites` /
    :func:`capture_guard_calls` output) — the coverage floor is asserted
    directly off these sets, never off a fixture *count* (a hollow harness
    that runs many fixtures but reaches few sites must still fail).
    """

    sites_reached: set[int] = field(default_factory=set)
    guard_branches_reached: set[str] = field(default_factory=set)
    fixtures_run: list[str] = field(default_factory=list)

    def record(self, fixture_id: str, sites: list[int], guard_calls: list[GuardCall]) -> None:
        self.fixtures_run.append(fixture_id)
        self.sites_reached.update(sites)
        for call in guard_calls:
            self.guard_branches_reached.add(classify_guard_branch(call))


def assert_coverage_floor_met(
    ledger: CoverageLedger,
    *,
    site_floor: int,
    branch_floor: int,
    known_sites: frozenset[int] = KNOWN_DECISION_SITES,
) -> None:
    """The binding, checkable-count coverage-floor assertion (T004/T006).

    Raises ``AssertionError`` — not a soft warning — when either tally is
    below its floor. A hollow oracle (one that drives fixtures but reaches
    few/no Decision sites or guard branches) MUST fail here; this is what
    makes "green on unmodified source" a meaningful proof rather than a
    tautology (WP01 Safeguards).
    """
    reached_known_sites = ledger.sites_reached & known_sites
    unreached_known_sites = known_sites - ledger.sites_reached
    unknown_sites = ledger.sites_reached - known_sites  # would indicate drift; surfaced, not silently dropped

    assert len(reached_known_sites) >= site_floor, (
        f"coverage floor NOT met: {len(reached_known_sites)}/{len(known_sites)} known Decision "
        f"sites reached (floor={site_floor}). Unreached sites: {sorted(unreached_known_sites)}. "
        f"Fixtures run: {ledger.fixtures_run}"
    )
    assert len(ledger.guard_branches_reached) >= branch_floor, (
        f"coverage floor NOT met: {len(ledger.guard_branches_reached)} guard branches reached "
        f"(floor={branch_floor}). Reached: {sorted(ledger.guard_branches_reached)}. "
        f"Fixtures run: {ledger.fixtures_run}"
    )
    if unknown_sites:  # pragma: no cover - defensive; would mean KNOWN_DECISION_SITES drifted
        raise AssertionError(
            f"Decision(...) construction observed at line(s) {sorted(unknown_sites)} not present in "
            "KNOWN_DECISION_SITES — the site inventory has drifted from source and must be refreshed."
        )


# ---------------------------------------------------------------------------
# §NFR-006 — timing seed
# ---------------------------------------------------------------------------


@dataclass
class TimedResult:
    value: Any
    duration_seconds: float


def timed_call(fn: Any, *args: Any, **kwargs: Any) -> TimedResult:
    """Run ``fn`` once and record wall-clock duration.

    WP01 seeds this on the fixture matrix (unmodified-source baseline); WP10
    asserts the "after" side stays within noise of this baseline (NFR-006).
    """
    start = time.perf_counter()
    value = fn(*args, **kwargs)
    duration = time.perf_counter() - start
    return TimedResult(value=value, duration_seconds=duration)
