"""Derived consumer census (#6173, mission derived-consumer-census-01M4V5P5).

The single authority for "which test module consumes which ``src/**`` or
``packs/**`` path" — the data from which ``gate_selection.GROUP_MODULE_FANOUT``
is derived and against which ``tests/architectural/test_consumer_census_routing.py``
fires when a consumer is unrouted.

It replaces the drift-prone *hand-curated module sets* in the fan-out: a new test
module that reads a mission-step prompt, imports ``cli/commands/lifecycle.py``, or
loads an ``expected-artifacts.yaml`` manifest shows up here automatically, instead
of staying invisible until it reddens ``main`` (the #6166 class).

Two detection halves, because a pure grep misses the consumers that matter most:

* **static** — each test file's imports (including dynamic
  ``importlib.import_module("...")`` string literals) resolved to their ``src/**``
  files, plus repo-relative ``src/**``/``packs/**`` path string-literals. This is
  how ``tests/agent`` is seen to consume ``cli/commands/lifecycle.py`` (a dynamic
  import — a plain AST ``import`` scan misses it).
* **runtime** — the resolver-driven pack reads a grep never sees: the
  package-default ``MissionTemplateRepository`` / ``MissionTypeRepository`` and the
  dossier ``ManifestRegistry`` are exercised under an ``open`` audit hook, and the
  ``packs/**`` files they open are attributed to every test module whose tests
  import that surface. This is how ``tests/next`` is seen to consume the
  ``mission-steps`` prompt it resolves through the CLI without ever naming its path
  (the canonical #6156 case), and ``tests/*dossier*`` the ``expected-artifacts.yaml``
  that ``index_feature`` loads.

Module attribution reuses ``gate_selection`` (the one routing authority): a test
file is attributed to the modules ``_modules_for_test_paths`` maps it to, and the
module universe is ``_registry_module_names()`` — both read the registry/router at
runtime, so a module-set change (e.g. #6164) flows through without editing a module
list (NFR-002). The runtime half is NOT open-ended, though: it replays a fixed set of
resolver surfaces (``_RESOLVER_SURFACES``), so a reader that resolves pack content
outside those surfaces is not seen until a surface is added for it (tracked in #6214).
The census is deterministic and offline (NFR-003): sorted output, no network.

Regenerate with ``python scripts/ci/consumer_census.py --write``; check drift with
``--check``.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Put the repo root on sys.path so ``scripts.ci.gate_selection`` resolves whether this
# module is imported (pytest / ``-m``, repo root already on path — a no-op then) or run
# directly as ``python scripts/ci/consumer_census.py`` (only scripts/ci is on path).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.gate_selection import (  # noqa: E402 — needs the sys.path bootstrap above
    DEFAULT_REGISTRY_PATH,
    DEFAULT_ROUTER_PATH,
    FANOUT_GROUPS,
    Router,
    _modules_for_test_paths,
    _registry_module_names,
    load_router,
    select_gates,
)

__all__ = [
    "CENSUS_PATH",
    "ConsumedPath",
    "build_census",
    "load_census",
    "main",
    "unrouted_pack_consumers",
]

CENSUS_PATH = _REPO_ROOT / ".github" / "ci-consumer-census.json"

_SCHEMA_VERSION = 1

# Top-level src packages (the layout under ``src/``). A dotted import whose head
# is one of these resolves to a file under ``src/<dotted-as-path>``.
_SRC_TOP_PACKAGES = frozenset({"specify_cli", "charter", "kernel", "glossary", "runtime", "mission_runtime"})

# Provenance vocabulary (data-model.md).
_STATIC_IMPORT = "static-import"
_RUNTIME = "runtime"

# The mission-pack-content domain: every consumed path under here is in scope, so a
# NEW unrouted pack sub-tree is recorded and reds the routing gate (the whole point).
_PACK_DOMAIN_PREFIX = "packs/built-in/missions/"


# ---------------------------------------------------------------------------
# Runtime resolver surfaces: (label, import signatures, runner).
#
# A surface's runner exercises a package-default resolver entry point under the
# ``open`` audit hook; the ``packs/**`` files it opens are attributed to every
# test module whose tests REFERENCE one of the surface's entry-point names (a
# called function / class / module attribute in the test AST — a far more precise
# signal than merely importing the package, which many tests do for unrelated
# symbols). The entry-point name set is a stable list of the resolver-surface
# functions/classes — NOT a per-module list — so the drift-prone "which modules
# consume" half stays fully derived (the static scan answers it from real call
# sites). Each runner is self-validating: a surface that opens zero ``packs/**``
# paths fails the build (a renamed/retired entry point reds), so a stale surface
# can never silently drop a consumer.
# ---------------------------------------------------------------------------
def _run_template_repository_surface() -> None:
    """Enumerate + read every built-in mission's command/content templates,
    mission config, action index/guidelines — the mission-step prompts and
    per-type templates/mission.yaml/actions the ``next``/runtime/charter
    resolver surfaces read at tier 6."""
    from charter.offering.missions import MissionTemplateRepository

    repo = MissionTemplateRepository.default()
    missions_root = repo.default_missions_root()
    for mission in repo.list_missions():
        repo.get_mission_config(mission)
        for name in repo.list_command_templates(mission):
            repo.get_command_template(mission, name)
        for name in repo.list_content_templates(mission):
            repo.get_content_template(mission, name)
        for action in repo.list_command_templates(mission):
            repo.get_action_index(mission, action)
            repo.get_action_guidelines(mission, action)
        # mission-runtime.yaml: read by runtime.next.runtime_bridge at resolve time;
        # read it here so a mission-runtime edit routes to the runtime consumers.
        runtime_yaml = missions_root / mission / "mission-runtime.yaml"
        if runtime_yaml.is_file():
            runtime_yaml.read_text(encoding="utf-8")


def _run_mission_type_surface() -> None:
    """Load every built-in mission type (reads ``mission_types/*.yaml`` and
    resolves each type's builtin step projection — the ``charter`` type surface)."""
    from charter.offering.missions.mission_type_repository import MissionTypeRepository

    MissionTypeRepository.default.cache_clear()
    MissionTypeRepository.default().load_all()


def _run_dossier_manifest_surface() -> None:
    """Load every built-in mission type's expected-artifacts manifest — the
    ``packs/built-in/missions/<type>/expected-artifacts.yaml`` the dossier
    indexer opens through ``index_feature`` without a test ever naming it."""
    from charter.offering.missions.mission_type_repository import MissionTypeRepository
    from specify_cli.dossier.manifest import ManifestRegistry

    for mission_type in MissionTypeRepository.default().ids():
        ManifestRegistry.load_manifest(mission_type, repo_root=_REPO_ROOT)


def _run_profile_surface() -> None:
    """Load every shipped ``packs/built-in/missions/<type>/governance-profile.yaml``
    (the ``MissionTypeProfileRepository`` surface — ``missions``/``charter`` tests
    resolve mission-type profiles against the real pack)."""
    from charter.activation.mission_type_profile_repository import MissionTypeProfileRepository

    MissionTypeProfileRepository.for_project(_REPO_ROOT).all()


def _run_step_contract_surface() -> None:
    """Resolve every built-in step contract (the ``MissionStepRepository`` surface:
    reads ``packs/built-in/missions/built_in_step_contracts/**`` and the
    ``mission-steps`` step.yaml set) across every mission type and step."""
    from charter.offering.missions.mission_step_repository import MissionStepRepository
    from charter.offering.missions.mission_type_repository import MissionTypeRepository
    from charter.offering.missions.repository import MissionTemplateRepository

    step_repo = MissionStepRepository.default()
    template_repo = MissionTemplateRepository.default()
    for mission_type in MissionTypeRepository.default().ids():
        for step in template_repo.list_command_templates(mission_type):
            step_repo.resolve(mission_type, step)


# Each surface is ``(label, entrypoint_names, runner, owned_groups)``:
#
# * ``entrypoint_names`` — a test module drives the surface (and so consumes the
#   pack sub-trees it opens) iff a test file in it REFERENCES one of these names (a
#   called function/class/attribute — a precise signal, unlike a bare package
#   import). Grounded in the real call sites (grep over ``tests/``).
# * ``owned_groups`` — the FANOUT_GROUPS this surface is responsible for. The audit
#   hook sees every ``packs/**`` open, including incidental ones a surface makes
#   outside its concern (e.g. ``MissionTypeRepository`` resolves each type's
#   ``mission-steps/<step>/step.yaml`` projection — a ``mission_pack_content`` read,
#   not the ``mission_type_definitions`` the type surface is about). Scoping each
#   surface's captured paths to its owned groups' globs stops that cross-contamination
#   (so a ``MissionTypeRepository`` referencer is attributed ``mission_types`` only,
#   not the prompts the projection happened to touch).
_RESOLVER_SURFACES: tuple[tuple[str, frozenset[str], object, frozenset[str]], ...] = (
    (
        "template_repository",
        frozenset(
            {
                "resolve_command",
                "resolve_template",
                "resolve_configured_template",
                "get_command_template",
                "get_content_template",
                "get_action_index",
                "get_action_guidelines",
                "get_mission_config",
                "list_command_templates",
                "list_content_templates",
                "compose_template_with_workflow",
                "agent_commands",
                "prompt_builder",
                "runtime_bridge",
                "build_prompt",
            }
        ),
        _run_template_repository_surface,
        frozenset({"mission_pack_content"}),
    ),
    (
        "mission_type_repository",
        frozenset(
            {
                "MissionTypeRepository",
                "builtin_mission_type_ids",
                "resolve_layered_mission_types",
                "load_layered_mission_types",
            }
        ),
        _run_mission_type_surface,
        frozenset({"mission_type_definitions"}),
    ),
    (
        "dossier_manifest",
        frozenset(
            {
                "index_feature",
                "load_manifest",
                "ManifestRegistry",
                "ExpectedArtifactManifest",
                "_load_expected_artifact_manifest",
                "_expected_artifacts_path",
            }
        ),
        _run_dossier_manifest_surface,
        frozenset({"mission_manifest"}),
    ),
    (
        "profile",
        frozenset({"MissionTypeProfileRepository", "mission_type_profiles", "resolve_profile"}),
        _run_profile_surface,
        frozenset({"mission_pack_content"}),
    ),
    (
        "step_contract",
        frozenset({"MissionStepRepository", "MissionStepContract", "step_contract", "resolve_step"}),
        _run_step_contract_surface,
        frozenset({"mission_pack_content"}),
    ),
)


# ---------------------------------------------------------------------------
# The ``open`` audit hook. One process-wide hook appends to ``_CAPTURE`` while a
# capture is active; it is a no-op otherwise, so it is safe to add once and leave
# installed across repeated ``build_census`` calls in one test process.
# ---------------------------------------------------------------------------
_CAPTURE: list[str] | None = None
_HOOK_INSTALLED = False
_PACKS_ROOT = str(_REPO_ROOT / "packs") + "/"


def _audit_open_hook(event: str, args: tuple[object, ...]) -> None:
    if event != "open" or _CAPTURE is None or not args:
        return
    raw = args[0]
    if not isinstance(raw, (str, bytes, Path)):
        return
    try:
        resolved = str(Path(raw if isinstance(raw, (str, Path)) else raw.decode()).resolve())
    except (OSError, ValueError, UnicodeDecodeError):
        return
    if resolved.startswith(_PACKS_ROOT):
        _CAPTURE.append(str(Path(resolved).relative_to(_REPO_ROOT).as_posix()))


def _ensure_hook() -> None:
    global _HOOK_INSTALLED
    if not _HOOK_INSTALLED:
        sys.addaudithook(_audit_open_hook)
        _HOOK_INSTALLED = True


def _reset_resolver_caches() -> None:
    """Clear the resolver/repository memoization so a capture re-opens the pack.

    The pack loaders memoize (``MissionTypeRepository.default``, the manifest and
    mission-step caches, …) so a SECOND ``build_census`` in one process would open
    zero files and the capture would see nothing — breaking reproducibility. Each
    clear is best-effort (a renamed cache API must not crash the build; the
    zero-paths self-check still catches a genuinely broken surface).
    """
    import contextlib

    with contextlib.suppress(Exception):
        from charter.offering.missions.mission_type_repository import (
            MissionTypeRepository,
            builtin_mission_type_ids,
        )

        MissionTypeRepository.default.cache_clear()
        MissionTypeRepository.cache_clear()
        builtin_mission_type_ids.cache_clear()
    with contextlib.suppress(Exception):
        from charter.offering.missions.mission_step_repository import MissionStepRepository

        MissionStepRepository.cache_clear()
    with contextlib.suppress(Exception):
        from specify_cli.dossier.manifest import ManifestRegistry

        ManifestRegistry.clear_cache()
    with contextlib.suppress(Exception):
        # The deep one: shipped-YAML parses (manifests, governance-profiles, mission
        # types, step contracts) are memoized by path+mtime (#5526). Markdown prompts
        # are read with read_text and re-open each time, but the YAML surfaces would
        # open nothing on a second build without this clear.
        from charter.offering import yaml_utils

        yaml_utils._SHIPPED_DOCUMENT_MEMO.clear()


def _capture_surface(runner: object) -> frozenset[str]:
    """Run ``runner`` with the audit capture active; return opened ``packs/**`` paths.

    Caches are reset first so repeated builds in one process re-open the pack
    (reproducibility — NFR-003)."""
    global _CAPTURE
    _ensure_hook()
    _reset_resolver_caches()
    _CAPTURE = []
    try:
        runner()  # type: ignore[operator]
    finally:
        captured = frozenset(_CAPTURE or ())
        _CAPTURE = None
    return captured


# ---------------------------------------------------------------------------
# Static scan.
# ---------------------------------------------------------------------------
def _dotted_to_src_file(dotted: str) -> str | None:
    """Resolve a dotted module name to its ``src/**`` file, or ``None``."""
    head = dotted.split(".", 1)[0]
    if head not in _SRC_TOP_PACKAGES:
        return None
    rel = dotted.replace(".", "/")
    module_py = _REPO_ROOT / "src" / f"{rel}.py"
    if module_py.is_file():
        return f"src/{rel}.py"
    pkg_init = _REPO_ROOT / "src" / rel / "__init__.py"
    if pkg_init.is_file():
        return f"src/{rel}/__init__.py"
    return None


class _TestFileScan:
    """The static facts a test file yields: imported dotted modules (incl. dynamic
    ``importlib`` string literals), the ``src/**`` files they resolve to, and every
    referenced name (for resolver-entry-point matching).

    Deliberately NOT recorded: bare ``packs/**`` path string literals. A pack path
    appearing as a string in a test is far more often test DATA (an example edit
    path, a routing assertion, a fixture) than genuine content consumption — and
    genuine content consumption is caught by the runtime resolver capture. Recording
    literals also made the census's own CI-tooling tests (which name example pack
    paths) spurious ``ci``-module consumers (self-referential churn). The three #6166
    pins are static-import (lifecycle.py) + runtime (prompt, manifest), never literal.
    """

    def __init__(self) -> None:
        self.imports: set[str] = set()
        self.src_files: set[str] = set()
        self.names: set[str] = set()


def _scan_test_file(path: Path) -> _TestFileScan:
    scan = _TestFileScan()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return scan

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                scan.imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            scan.imports.add(node.module)
            # ``from pkg import name`` may import a SUBMODULE (e.g.
            # ``from specify_cli.cli.commands import lifecycle``) — resolve
            # ``pkg.name`` too, else the lifecycle.py consumer is missed (#6161).
            for alias in node.names:
                scan.imports.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Name):
            scan.names.add(node.id)
        elif isinstance(node, ast.Attribute):
            scan.names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Dotted module string (dynamic import target, e.g.
            # importlib.import_module("specify_cli.cli.commands.lifecycle")).
            value = node.value
            if "." in value and " " not in value and "/" not in value:
                src_file = _dotted_to_src_file(value)
                if src_file is not None:
                    scan.imports.add(value)
                    scan.src_files.add(src_file)

    for dotted in scan.imports:
        src_file = _dotted_to_src_file(dotted)
        if src_file is not None:
            scan.src_files.add(src_file)
    return scan


def _iter_test_files(repo_root: Path) -> Iterator[Path]:
    yield from sorted((repo_root / "tests").rglob("*.py"))


# ---------------------------------------------------------------------------
# Sub-tree bucketing: keep ONE representative concrete path per structural
# sub-tree per module, so the artifact stays small and router-independent while
# every recorded ``path`` is a real file the gate can route with ``select_modules``.
# ---------------------------------------------------------------------------
def _subtree_bucket(rel: str) -> str:
    """A router-independent structural key grouping paths that share a sub-tree."""
    parts = rel.split("/")
    prefix = "packs/built-in/missions/"
    if rel.startswith(prefix):
        tail = parts[3:]
        if tail and tail[0] in ("mission-steps", "mission_types", "built_in_step_contracts"):
            return f"{prefix}{tail[0]}"
        if len(tail) >= 2:
            # <type>/<leaf>[/...]: collapse the type so every type shares a bucket.
            return f"{prefix}*/{tail[1]}"
        return rel
    return rel


def _dedupe_by_subtree(paths: Iterable[str]) -> list[str]:
    """One representative concrete path per sub-tree, chosen lexicographically."""
    representative: dict[str, str] = {}
    for rel in sorted(paths):
        bucket = _subtree_bucket(rel)
        representative.setdefault(bucket, rel)
    return sorted(representative.values())


class ConsumedPath:
    """A single ``(path, provenance, via)`` census entry for a module."""

    __slots__ = ("path", "provenance", "via")

    def __init__(self, path: str, provenance: str, via: str) -> None:
        self.path = path
        self.provenance = provenance
        self.via = via

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "provenance": self.provenance, "via": self.via}


# ---------------------------------------------------------------------------
# The census build — orchestrated from small, individually-testable phases.
# ---------------------------------------------------------------------------
def _group_globs(router: Router, groups: Iterable[str]) -> tuple[str, ...]:
    """The router filter globs of a set of groups, flattened."""
    return tuple(pattern for group in groups for pattern in router.filters.get(group, ()))


def _attribute_test_files(
    repo_root: Path, router: Router, registry: Path | None, modules: frozenset[str]
) -> tuple[dict[str, frozenset[str]], dict[str, _TestFileScan]]:
    """Map each test file to its owning modules (per the routing authority) and
    statically scan it. Only files that map to >=1 module are kept — an unrouted
    tree cannot force any module selection.

    ``_modules_for_test_paths`` re-reads the registry YAML per call and its answer
    depends only on a path's DIRECTORY, so owner resolution is memoized per
    directory (~550 dirs vs ~4000 files).
    """
    owners_by_dir: dict[str, frozenset[str]] = {}
    file_modules: dict[str, frozenset[str]] = {}
    file_scans: dict[str, _TestFileScan] = {}
    for test_path in _iter_test_files(repo_root):
        rel = test_path.relative_to(repo_root).as_posix()
        directory = rel.rsplit("/", 1)[0]
        owners = owners_by_dir.get(directory)
        if owners is None:
            owners = _modules_for_test_paths([rel], router=router, registry_path=registry, modules=modules)
            owners_by_dir[directory] = owners
        if not owners:
            continue
        file_modules[rel] = owners
        file_scans[rel] = _scan_test_file(test_path)
    return file_modules, file_scans


def _capture_scoped_surfaces(router: Router) -> dict[str, frozenset[str]]:
    """Run each resolver surface under the audit hook; return the ``packs/**`` paths
    it opens SCOPED to its owned FANOUT_GROUPS (so an incidental out-of-concern read —
    e.g. the type repo's ``step.yaml`` projection — does not cross-contaminate). A
    surface that opens zero paths in its owned groups fails the build loud (a
    renamed/retired entry point reds)."""
    surface_paths: dict[str, frozenset[str]] = {}
    for label, _names, runner, owned_groups in _RESOLVER_SURFACES:
        captured = _capture_surface(runner)
        owned_globs = _group_globs(router, owned_groups)
        scoped = frozenset(p for p in captured if any(fnmatch.fnmatch(p, g) for g in owned_globs))
        if not scoped:
            raise RuntimeError(
                f"consumer_census: resolver surface {label!r} opened zero packs/** paths in its "
                f"owned groups {sorted(owned_groups)} — the entry point is renamed/retired or the "
                "pack/router changed; the runtime capture would silently drop a consumer. "
                "Fix the surface runner or its owned_groups."
            )
        surface_paths[label] = scoped
    return surface_paths


class _DomainRecorder:
    """Records (module, path, provenance) consumption scoped to the INDIRECT-CONSUMPTION
    FAN-OUT DOMAIN and to consumption base routing misses.

    Domain: any mission-pack-content path (``packs/built-in/missions/**`` — so a NEW
    unrouted pack sub-tree is still recorded and reds the gate), plus a ``src/**`` path
    a FANOUT_GROUPS glob names (today ``cli_lifecycle`` -> lifecycle.py). A module's own
    src imports and general cross-module src imports are out of scope (base routing
    covers the former; fanning out every cross-module import is the deferred #6166
    command-module class, not this mission).

    Base-routing filter: a (module, path) is recorded only when base routing (src
    groups + the tests-only mirror, WITHOUT the fan-out) does NOT already select the
    module — i.e. only genuine indirect consumption the fan-out must cover.
    """

    def __init__(self, router: Router, registry: Path | None, modules: frozenset[str]) -> None:
        self._router = router
        self._registry = registry
        self._modules = modules
        self._fanout_globs = _group_globs(router, FANOUT_GROUPS)
        self._base_cache: dict[str, frozenset[str]] = {}
        self.raw: dict[str, dict[tuple[str, str], str]] = {m: {} for m in sorted(modules)}

    def _base_select(self, path: str) -> frozenset[str]:
        cached = self._base_cache.get(path)
        if cached is None:
            selection = select_gates([path], router=self._router)
            if selection.unmatched_src:
                cached = self._modules
            else:
                test = _modules_for_test_paths([path], router=self._router, registry_path=self._registry, modules=self._modules)
                cached = (selection.matched_groups & self._modules) | test
            self._base_cache[path] = cached
        return cached

    def _in_domain(self, path: str) -> bool:
        if path.startswith(_PACK_DOMAIN_PREFIX):
            return True
        return any(fnmatch.fnmatch(path, pattern) for pattern in self._fanout_globs)

    def record(self, module: str, path: str, provenance: str, via: str) -> None:
        if module not in self.raw or not self._in_domain(path) or module in self._base_select(path):
            return
        self.raw[module].setdefault((path, provenance), via)


def _record_consumption(
    recorder: _DomainRecorder,
    file_modules: dict[str, frozenset[str]],
    file_scans: dict[str, _TestFileScan],
    surface_paths: dict[str, frozenset[str]],
) -> None:
    """Record static (imports + path literals) and runtime (resolver-surface) consumption."""
    for rel, owners in file_modules.items():
        scan = file_scans[rel]
        for module in owners:
            for src_file in scan.src_files:
                recorder.record(module, src_file, _STATIC_IMPORT, rel)
    for label, entrypoint_names, _runner, _owned in _RESOLVER_SURFACES:
        captured = surface_paths[label]
        for rel, owners in file_modules.items():
            if not (file_scans[rel].names & entrypoint_names):
                continue
            for module in owners:
                for packs_path in captured:
                    recorder.record(module, packs_path, _RUNTIME, f"{rel} [{label}]")


def _assemble_modules(raw: dict[str, dict[tuple[str, str], str]]) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Dedupe by sub-tree (one representative concrete path per bucket per
    (module, provenance)) and sort for deterministic output."""
    out_modules: dict[str, dict[str, list[dict[str, str]]]] = {}
    for module in sorted(raw):
        entries = raw[module]
        if not entries:
            continue
        by_prov: dict[str, dict[str, str]] = {}
        for (path, provenance), via in entries.items():
            by_prov.setdefault(provenance, {})[path] = via
        consumes = [
            {"path": path, "provenance": provenance, "via": by_prov[provenance][path]}
            for provenance in sorted(by_prov)
            for path in _dedupe_by_subtree(by_prov[provenance])
        ]
        consumes.sort(key=lambda e: (e["path"], e["provenance"], e["via"]))
        if consumes:
            out_modules[module] = {"consumes": consumes}
    return out_modules


def build_census(
    *,
    repo_root: Path = _REPO_ROOT,
    router: Router | None = None,
    registry_path: Path | None = None,
) -> dict[str, object]:
    """Build the consumer census (deterministic, offline).

    Returns the artifact mapping (schema in data-model.md). Reused by the CLI
    (``--write``/``--check``), by ``test_consumer_census.py`` and by the
    derived-vs-hand analysis in ``gate_selection.derive_group_module_fanout``.
    """
    router = router or load_router(DEFAULT_ROUTER_PATH)
    registry = registry_path or DEFAULT_REGISTRY_PATH
    modules = _registry_module_names(registry)

    file_modules, file_scans = _attribute_test_files(repo_root, router, registry, modules)
    surface_paths = _capture_scoped_surfaces(router)
    recorder = _DomainRecorder(router, registry, modules)
    _record_consumption(recorder, file_modules, file_scans, surface_paths)

    return {
        "schema_version": _SCHEMA_VERSION,
        "description": (
            "Derived consumer census (#6173): per test module, the src/** and packs/** "
            "paths its tests consume (static import/read + runtime resolver capture). "
            "Regenerate with `python scripts/ci/consumer_census.py --write`."
        ),
        "generated_by": "scripts/ci/consumer_census.py",
        "modules": _assemble_modules(recorder.raw),
    }


def load_census(path: Path = CENSUS_PATH) -> dict[str, object]:
    """Load the committed census artifact."""
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def unrouted_pack_consumers(census: dict[str, object], *, router: Router | None = None) -> list[tuple[str, str]]:
    """Every census ``(module, pack-path)`` whose path matches NO fan-out group glob.

    A mission-pack-content path a test consumes but that no FANOUT_GROUPS glob routes
    is an UNROUTED consumer: an edit to it selects zero fan-out modules, so the
    consuming module runs in no per-PR shard and the break surfaces on ``main``
    later (the #6166 class). The routing gate asserts this list is empty; a planted
    pack path under an un-globbed sub-tree makes it non-empty (the gate's teeth).

    Only ``packs/built-in/missions/**`` paths are checked — src consumers are routed
    by base src-group routing, outside this fan-out concern.
    """
    router = router or load_router()
    fanout_globs = tuple(pattern for group in FANOUT_GROUPS for pattern in router.filters.get(group, ()))
    modules = census.get("modules", {})
    if not isinstance(modules, dict):
        return []
    unrouted: list[tuple[str, str]] = []
    for module, data in sorted(modules.items()):
        if not isinstance(data, dict):
            continue
        for entry in data.get("consumes", ()):
            path = entry.get("path") if isinstance(entry, dict) else None
            if not path or not path.startswith(_PACK_DOMAIN_PREFIX):
                continue
            if not any(fnmatch.fnmatch(path, pattern) for pattern in fanout_globs):
                unrouted.append((module, path))
    return unrouted


def _serialize(census: dict[str, object]) -> str:
    return json.dumps(census, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/check the derived consumer census (#6173).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="Regenerate and write the census artifact.")
    group.add_argument("--check", action="store_true", help="Fail if the committed artifact is stale.")
    args = parser.parse_args(argv)

    census = build_census()
    serialized = _serialize(census)

    if args.write:
        CENSUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CENSUS_PATH.write_text(serialized, encoding="utf-8")
        print(f"wrote {CENSUS_PATH.relative_to(_REPO_ROOT)} ({len(census['modules'])} modules)")  # type: ignore[arg-type]
        return 0

    if args.check:
        if not CENSUS_PATH.is_file():
            print(f"census artifact missing: {CENSUS_PATH}", file=sys.stderr)
            return 1
        committed = CENSUS_PATH.read_text(encoding="utf-8")
        if committed != serialized:
            print(
                "consumer census is stale — run `python scripts/ci/consumer_census.py --write`",
                file=sys.stderr,
            )
            return 1
        print("consumer census is up to date")
        return 0

    # Default: print a summary.
    for module in sorted(census["modules"]):  # type: ignore[call-overload]
        consumes = census["modules"][module]["consumes"]  # type: ignore[index]
        print(f"{module}: {len(consumes)} consumed path(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
