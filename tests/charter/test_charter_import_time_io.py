"""Single-source driver + import-time-I/O regression guard for charter (WP02, #2669).

Covers (T006):

1. **RED-first single-source driver** — a synthetic mission-type YAML injected
   via a monkeypatched ``MissionTypeRepository.default`` root (C-010 test
   seam) must flow through to ``PackContext.from_config``'s default
   ``activated_mission_types`` set. Before T008, ``pack_context.py`` derives
   its default from a hardcoded ``_BUILTIN_MISSION_TYPE_IDS`` literal that
   ignores the accessor entirely, so this test is genuinely RED until the
   Roster B lazy-derivation lands.

2. **Import-time-I/O regression guard (green-stays-green)** — importing the
   two "hot" charter modules (``charter.activation.mission_type_profiles``,
   ``charter.activation.pack_context``) must trigger AT MOST ONE cached read of the
   doctrine ``mission_types/`` directory, and a second read anywhere in the
   same process must trigger ZERO further reads (NFR-001 / SC-005). The
   bound is ``<=1``, not a literal zero: importing either hot module first
   runs ``charter/__init__.py`` (the package init any submodule import
   executes), which eagerly imports ``charter.activation.activations`` as part of its
   public re-export surface — and ``charter.activation.activations.ALLOWED_MISSION_TYPES``
   is a module-scope value derived from the accessor (the C-012 carve-out —
   it must stay an importable frozenset VALUE for the unowned
   ``test_activation_registry_schema.py``, so it cannot be made lazy without
   also breaking the symbol-level dead-code gate's static-definition
   requirement, see ``charter/activations.py``'s own docstring note above
   ``ALLOWED_MISSION_TYPES``). So the ONE read every hot-module import
   inherits is exactly that carve-out's read, fired once and then satisfied
   by ``builtin_mission_type_ids``'s process-wide ``functools.cache``
   (NFR-002) for the rest of the process — proven by the second assertion
   below. Run in a subprocess so the spy observes a genuine fresh import,
   not a module already cached in this test session's ``sys.modules``.

3. **New-factory import-time-I/O bound (NFR-004, mission
   ``up-mission-type-seam-01KZY1JB`` WP03)** — ``resolve_layered_mission_types``
   (``charter.offering.missions.mission_type_repository``, FR-001) must never be
   called at module scope in any ``charter.*`` module. At this WP's point in
   the mission sequence nothing calls it yet (WP04 wires the first caller),
   so the bound asserted here is exactly zero calls, checked via
   ``resolve_layered_mission_types.cache_info()`` (hits + misses) rather than
   a spy -- the ``functools.cache`` wrapper already tracks total invocations,
   so no extra instrumentation is needed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

import charter.offering
from charter.activation.pack_context import PackContext
from charter.offering.missions.mission_type_repository import (
    MissionTypeRepository,
    builtin_mission_type_ids,
    resolve_layered_mission_types,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SHIPPED_MISSION_TYPES_DIR = (
    Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions" / "mission_types"
)

_SYNTHETIC_ANALYSIS_YAML = (
    "schema_version: 1\n"
    "id: analysis\n"
    'display_name: "Analysis"\n'
    "action_sequence:\n"
    "  - specify\n"
    "  - plan\n"
)

_MINIMAL_CONFIG = """\
vcs:
  type: git
agents:
  available:
    - claude
"""


@pytest.fixture(autouse=True)
def _clear_builtin_mission_type_ids_cache() -> Iterator[None]:
    """Reset the process-wide ``functools.cache`` before and after each test.

    Mirrors the C-010 seam fixture in
    ``tests/charter_offering/missions/test_builtin_mission_type_ids.py`` — a
    monkeypatched root must not leak a cached value into another test
    (including other modules under ``-n auto``).
    """
    builtin_mission_type_ids.cache_clear()
    resolve_layered_mission_types.cache_clear()
    yield
    builtin_mission_type_ids.cache_clear()
    resolve_layered_mission_types.cache_clear()


def _write_config(project_root: Path, content: str) -> None:
    kittify = project_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _patch_default_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Monkeypatch ``MissionTypeRepository.default`` to load from *root* (C-010)."""

    def _fake_default(cls: type[MissionTypeRepository]) -> MissionTypeRepository:
        return cls(root)

    monkeypatch.setattr(MissionTypeRepository, "default", classmethod(_fake_default))


# ---------------------------------------------------------------------------
# 1. RED-first single-source driver
# ---------------------------------------------------------------------------


class TestDefaultActivationSetIsSingleSourced:
    """``PackContext`` has no default activation set for mission types (WP04).

    This class originally pinned "the default activation set, when the
    ``mission_type_activations`` key is absent, single-sources from the WP01
    ``MissionTypeRepository`` accessor rather than a hardcoded literal." WP04
    retired the default-on-absence behavior entirely -- ``pack_context.py`` no
    longer references ``MissionTypeRepository``/``builtin_mission_type_id_set``
    at all. The final WP04 re-architecture then made construction TOTAL: an
    absent key resolves to ``frozenset()`` (never the all-four backfill, never
    a raise), with the fail-closed moved to the mission-create boundary (see
    ``tests/charter/test_pack_context.py::test_from_config_no_config_yaml_returns_empty_not_raise``).
    There is no "default set" for this accessor-swap contract to single-source.
    """

    def test_synthetic_accessor_type_does_not_create_an_implicit_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An absent ``mission_type_activations`` key resolves to an EMPTY set
        even when the ``MissionTypeRepository`` accessor root carries a
        synthetic type that used to leak into the old hardcoded-default
        fallback.

        Supersedes the pre-WP04
        ``test_default_activated_mission_types_includes_synthetic_type``: proves
        the retired backfill is not quietly reintroduced by an accessor-sourced
        type -- the absent key reads as ``frozenset()`` (absent != all-four),
        not the synthetic-inclusive roster, and construction does not raise.
        """
        mission_types_root = tmp_path / "mission_types"
        mission_types_root.mkdir()
        for shipped_yaml in _SHIPPED_MISSION_TYPES_DIR.glob("*.yaml"):
            shutil.copy(shipped_yaml, mission_types_root / shipped_yaml.name)
        (mission_types_root / "analysis.yaml").write_text(
            _SYNTHETIC_ANALYSIS_YAML, encoding="utf-8"
        )

        _patch_default_root(monkeypatch, mission_types_root)
        builtin_mission_type_ids.cache_clear()

        project_root = tmp_path / "project"
        _write_config(project_root, _MINIMAL_CONFIG)  # no mission_type_activations key

        ctx = PackContext.from_config(project_root)

        assert ctx.activated_mission_types == frozenset()


# ---------------------------------------------------------------------------
# 2. Import-time-I/O regression guard (green-stays-green)
# ---------------------------------------------------------------------------


_IMPORT_SPY_SCRIPT = textwrap.dedent(
    """\
    import sys

    from charter.offering.missions.mission_type_repository import (
        MissionTypeRepository,
        builtin_mission_type_id_set,
        resolve_layered_mission_types,
    )

    _calls: list[int] = []
    _orig_default = MissionTypeRepository.default.__func__

    def _spy(cls):
        _calls.append(1)
        return _orig_default(cls)

    MissionTypeRepository.default = classmethod(_spy)

    import charter.activation.mission_type_profiles  # noqa: F401
    import charter.activation.pack_context  # noqa: F401

    after_import = len(_calls)
    if after_import > 1:
        print(
            f"MissionTypeRepository.default() called {after_import} time(s) at import "
            "time -- expected at most 1 (the C-012 carve-out read inherited via the "
            "eager charter/__init__.py -> charter.activation.activations chain)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Second access anywhere in the same process (e.g. another charter module
    # deriving the same roster, or a runtime caller re-reading
    # ALLOWED_MISSION_TYPES) must be satisfied entirely by
    # ``builtin_mission_type_ids``'s process-wide ``functools.cache``
    # (NFR-002) -- zero FURTHER MissionTypeRepository.default() calls.
    builtin_mission_type_id_set()
    after_second_access = len(_calls)
    if after_second_access != after_import:
        print(
            f"MissionTypeRepository.default() called {after_second_access - after_import} "
            "additional time(s) on a second roster access -- the process-wide cache "
            "(NFR-002) is not preventing a repeat mission_types/ read",
            file=sys.stderr,
        )
        sys.exit(1)

    # WP03/NFR-004: the new layered-lookup factory (FR-001) must never be
    # called at module scope in any charter.* module. Nothing calls it yet
    # at this WP's point in the mission sequence (WP04 wires the first
    # caller), so the bound is exactly zero -- read straight off the
    # functools.cache wrapper's own call-count bookkeeping.
    layered_info = resolve_layered_mission_types.cache_info()
    layered_calls = layered_info.hits + layered_info.misses
    if layered_calls != 0:
        print(
            f"resolve_layered_mission_types() called {layered_calls} time(s) at "
            "import time -- expected 0 (NFR-004; nothing calls it yet at WP03's "
            "point in the mission sequence, WP04 wires the first caller)",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)
    """
)


def _subprocess_env_with_src_root() -> dict[str, str]:
    """Build a subprocess env that guarantees ``doctrine``/``charter`` import cleanly.

    ``sys.executable`` guarantees the *same interpreter*, but not the same
    import roots: pytest's ``pythonpath = src`` ini option mutates this
    process's ``sys.path`` in memory, and a child process spawned via
    ``subprocess.run`` does not inherit an in-memory ``sys.path`` mutation --
    only environment variables. In a local editable-install layout that gap
    is often invisible (the venv's site-packages happens to resolve
    ``doctrine``/``charter`` too), but is real whenever the running
    interpreter's site-packages does not carry an editable install for THIS
    checkout (e.g. a plain ``uv run`` environment, or a shared venv whose
    editable install points at a different checkout) -- then the subprocess
    raises ``ModuleNotFoundError`` before the I/O probe ever runs, instead
    of measuring anything. Propagate the ``src`` root this process actually
    resolved ``doctrine`` from, so the subprocess sees the same package
    regardless of what its own default ``sys.path`` would have produced.

    ``doctrine`` is now the CR-06 compatibility shim (``src/doctrine.py``, a
    single module, not a package) re-exporting ``charter.offering`` -- so
    ``charter.offering.__file__`` resolves directly to ``src/doctrine.py`` and its
    immediate ``.parent`` (not ``.parents[1]``) is the ``src`` root.
    """
    src_root = str(Path(charter.offering.__file__).resolve().parents[0])
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        os.pathsep.join([src_root, existing_pythonpath]) if existing_pythonpath else src_root
    )
    return env


class TestHotModulesTriggerZeroImportTimeIo:
    """Importing the two hot charter modules triggers at most 1 cached read.

    NFR-001's bound is ``<=1``, not a literal zero: importing either hot
    module runs ``charter/__init__.py`` first (the package init any
    submodule import executes), which eagerly imports ``charter.activation.activations``
    — whose ``ALLOWED_MISSION_TYPES`` is a module-scope value derived from
    the accessor (the C-012 carve-out, see ``charter/activations.py``). That
    carve-out read is the ONE this test bounds; it must never repeat (proven
    by the second-access assertion in ``_IMPORT_SPY_SCRIPT``), and no OTHER
    import-time read may occur.

    Runs in a subprocess so the spy observes a genuine fresh import — pytest
    collection has already imported both modules by the time this test body
    runs, so an in-process ``importlib.reload`` would not reliably surface a
    module-scope accessor call cached from an earlier import in the same
    session.
    """

    def test_import_charter_mission_type_profiles_and_pack_context_bounded_io(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", _IMPORT_SPY_SCRIPT],
            capture_output=True,
            text=True,
            check=False,
            env=_subprocess_env_with_src_root(),
        )

        # A non-zero exit with an unhandled traceback (e.g. ModuleNotFoundError
        # because the subprocess interpreter could not import 'doctrine' or
        # 'charter') is an environment/setup failure, NOT the unbounded-I/O
        # condition this test guards against -- the I/O probe in
        # _IMPORT_SPY_SCRIPT never even ran. Fail with a truthful message
        # instead of misattributing it to NFR-001.
        if result.returncode != 0 and "Traceback (most recent call last):" in result.stderr:
            pytest.fail(
                "subprocess failed to import charter/doctrine modules before "
                "the import-time-I/O probe could run -- this is an "
                "interpreter/environment setup failure (e.g. the spawned "
                "interpreter cannot import 'doctrine'/'charter'), NOT an "
                f"unbounded-I/O violation:\nstdout={result.stdout}\nstderr={result.stderr}"
            )

        assert result.returncode == 0, (
            "importing charter.activation.mission_type_profiles / charter.activation.pack_context "
            "triggered unbounded mission_types/ I/O (NFR-001, <=1 cached read "
            f"expected):\nstdout={result.stdout}\nstderr={result.stderr}"
        )
