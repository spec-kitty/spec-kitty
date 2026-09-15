from __future__ import annotations

import ast
import functools
import hashlib
import hmac
import json
import os
import secrets
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from filelock import FileLock


_BANNED_CALLS = {
    ("datetime", "now"): "datetime.now()",
    ("datetime", "utcnow"): "datetime.utcnow()",
    ("datetime", "today"): "datetime.today()",
    ("datetime", "datetime", "now"): "datetime.datetime.now()",
    ("datetime", "datetime", "utcnow"): "datetime.datetime.utcnow()",
    ("datetime", "datetime", "today"): "datetime.datetime.today()",
    ("date", "today"): "date.today()",
    ("datetime", "date", "today"): "datetime.date.today()",
    ("time", "time"): "time.time()",
}

_ALIASABLE_CLOCK_PATHS = set(_BANNED_CALLS) | {
    ("datetime",),
    ("datetime", "datetime"),
    ("date",),
    ("datetime", "date"),
    ("time",),
}

_AliasMap = dict[tuple[str, ...], tuple[str, ...] | None]
_ValueMap = dict[tuple[str, ...], ast.expr]
_ClassInitializers = dict[tuple[str, ...], ast.FunctionDef | ast.AsyncFunctionDef]
_SHADOWED_PATH = ("<shadowed>",)
_SETUP_METHOD_NAMES = {"setup", "setup_method", "setup_class", "setUp", "setUpClass"}
_MODULE_SETUP_NAMES = {"setup_module", "setup_function", "setUpModule"}
_SCAN_CACHE_VERSION = 3
_SCAN_CACHE_LOCK_TIMEOUT_S = 600.0
_SCAN_CACHE_AUTHORITY_KEY_NAME = "authority.key"
_SCAN_CACHE_AUTHORITY_KEY_BYTES = 32


@dataclass(frozen=True, order=True)
class WallClockAssertionViolation:
    path: Path
    line: int
    call: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.call}"


@dataclass
class _ImportAliasMetrics:
    module_visits: int = 0
    parsed_files: int = 0


def find_wall_clock_assertion_violations(paths: Iterable[Path]) -> list[WallClockAssertionViolation]:
    """Find direct wall-clock reads inside pytest assert expressions."""
    python_paths = sorted({Path(p) for p in paths if Path(p).suffix == ".py"})
    sources = {path: path.read_text(encoding="utf-8") for path in python_paths}
    return _find_wall_clock_assertion_violations_from_sources(python_paths, sources)


def _find_wall_clock_assertion_violations_from_sources(
    python_paths: list[Path],
    sources: Mapping[Path, str],
) -> list[WallClockAssertionViolation]:
    violations: list[WallClockAssertionViolation] = []
    trees = {
        path: ast.parse(sources[path], filename=str(path))
        for path in python_paths
    }
    import_aliases = _collect_import_aliases(python_paths, _trees=trees)
    conftest_fixture_aliases, conftest_module_aliases = _collect_conftest_aliases(
        python_paths,
        import_aliases,
        _trees=trees,
    )
    for path in python_paths:
        visitor = _WallClockAssertionVisitor(
            path,
            import_aliases,
            conftest_fixture_aliases.get(path, {}),
            conftest_module_aliases.get(path, {}),
        )
        visitor.visit(trees[path])
        violations.extend(visitor.violations)
    return sorted(violations)


def find_wall_clock_assertion_violations_cached(
    paths: Iterable[Path],
    cache_root: Path,
    *,
    config_paths: Iterable[Path] = (),
) -> list[WallClockAssertionViolation]:
    """Share one content-addressed scan safely across pytest processes."""
    python_paths = sorted({Path(p) for p in paths if Path(p).suffix == ".py"})
    sources = {path: path.read_text(encoding="utf-8") for path in python_paths}
    digest = _wall_clock_scan_digest(python_paths, sources, config_paths)
    cache_root.mkdir(parents=True, exist_ok=True)
    result_path = cache_root / f"{digest}.json"
    lock_path = cache_root / "scan.lock"
    with FileLock(str(lock_path), timeout=_SCAN_CACHE_LOCK_TIMEOUT_S):
        authority_key = _load_or_create_wall_clock_scan_authority_key(cache_root)
        cached = _read_wall_clock_scan_cache(result_path, digest, authority_key)
        if cached is not None:
            return cached
        violations = _find_wall_clock_assertion_violations_from_sources(python_paths, sources)
        _write_wall_clock_scan_cache(result_path, digest, violations, authority_key)
        return violations


def _wall_clock_scan_digest(
    paths: list[Path],
    sources: Mapping[Path, str],
    config_paths: Iterable[Path],
) -> str:
    # File-integrity identity, not charter content hashing.
    digest = hashlib.sha256()  # noqa: TID251
    digest.update(f"wall-clock-scan-v{_SCAN_CACHE_VERSION}\0".encode())
    all_paths = [*paths, *sorted({Path(path) for path in config_paths})]
    root = (
        Path(os.path.commonpath([str(path.parent) for path in all_paths]))
        if all_paths
        else Path(".")
    )
    for path in all_paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = str(path.resolve(strict=False))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path in sources:
            digest.update(sources[path].encode("utf-8"))
        elif path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def _read_wall_clock_scan_cache(
    result_path: Path,
    digest: str,
    authority_key: bytes,
) -> list[WallClockAssertionViolation] | None:
    if not result_path.is_file():
        return None
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != _SCAN_CACHE_VERSION:
            return None
        if payload.get("digest") != digest or not isinstance(payload.get("violations"), list):
            return None
        expected_authenticator = _wall_clock_scan_result_authenticator(
            digest,
            payload["violations"],
        )
        if payload.get("result_sha256") != expected_authenticator:
            return None
        expected_authority = _wall_clock_scan_authority(
            digest,
            payload["violations"],
            authority_key,
        )
        authority = payload.get("authority_hmac_sha256")
        if not isinstance(authority, str) or not hmac.compare_digest(authority, expected_authority):
            return None
        violations: list[WallClockAssertionViolation] = []
        for row in payload["violations"]:
            if not isinstance(row, dict):
                return None
            path = row.get("path")
            line = row.get("line")
            call = row.get("call")
            if (
                not isinstance(path, str)
                or not isinstance(line, int)
                or isinstance(line, bool)
                or line <= 0
                or not isinstance(call, str)
            ):
                return None
            violations.append(WallClockAssertionViolation(Path(path), line, call))
        return sorted(violations)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _write_wall_clock_scan_cache(
    result_path: Path,
    digest: str,
    violations: list[WallClockAssertionViolation],
    authority_key: bytes,
) -> None:
    rows = [
        {"path": str(violation.path), "line": violation.line, "call": violation.call}
        for violation in violations
    ]
    payload = {
        "version": _SCAN_CACHE_VERSION,
        "digest": digest,
        "violations": rows,
        "result_sha256": _wall_clock_scan_result_authenticator(digest, rows),
        "authority_hmac_sha256": _wall_clock_scan_authority(digest, rows, authority_key),
    }
    temporary = result_path.with_name(f"{result_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, result_path)
    finally:
        temporary.unlink(missing_ok=True)


def _wall_clock_scan_result_authenticator(digest: str, rows: object) -> str:
    """Bind cached result rows to their version and source-input digest."""
    canonical = json.dumps(
        {"version": _SCAN_CACHE_VERSION, "digest": digest, "violations": rows},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()  # noqa: TID251


def _wall_clock_scan_authority(digest: str, rows: object, authority_key: bytes) -> str:
    """Authenticate result rows with authority held outside the result document."""
    canonical = json.dumps(
        {"version": _SCAN_CACHE_VERSION, "digest": digest, "violations": rows},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    # Cache-integrity HMAC, not charter content hashing.
    return hmac.new(authority_key, canonical, hashlib.sha256).hexdigest()  # noqa: TID251


def _load_or_create_wall_clock_scan_authority_key(cache_root: Path) -> bytes:
    """Return the cross-process cache authority key, replacing malformed keys."""
    key_path = cache_root / _SCAN_CACHE_AUTHORITY_KEY_NAME
    try:
        key = key_path.read_bytes()
    except FileNotFoundError:
        key = b""
    if len(key) == _SCAN_CACHE_AUTHORITY_KEY_BYTES:
        return key

    key = secrets.token_bytes(_SCAN_CACHE_AUTHORITY_KEY_BYTES)
    temporary = key_path.with_name(f"{key_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(key)
        os.replace(temporary, key_path)
    finally:
        temporary.unlink(missing_ok=True)
    return key


def find_test_python_paths(root: Path) -> list[Path]:
    """Return every Python file under the test tree, including helper modules."""
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _collect_import_aliases(
    paths: list[Path],
    *,
    _metrics: _ImportAliasMetrics | None = None,
    _trees: Mapping[Path, ast.Module] | None = None,
) -> dict[str, _AliasMap]:
    if not paths:
        return {}
    root = Path(os.path.commonpath([str(path.parent) for path in paths]))
    module_names = {path: _module_names(path, root) for path in paths}
    trees: dict[Path, ast.Module]
    if _trees is None:
        trees = {
            path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in paths
        }
        if _metrics is not None:
            _metrics.parsed_files += len(trees)
    else:
        trees = dict(_trees)
    module_paths = {
        module_name: path
        for path, names in module_names.items()
        for module_name in names
    }
    dependents: dict[Path, set[Path]] = {path: set() for path in paths}
    for dependent_path, tree in trees.items():
        for dependency_name in _imported_module_names(tree):
            dependency_path = module_paths.get(dependency_name)
            if dependency_path is not None and dependency_path != dependent_path:
                dependents[dependency_path].add(dependent_path)

    import_aliases: dict[str, _AliasMap] = {}
    exports_by_path: dict[Path, _AliasMap] = {}
    queue = deque(paths)
    queued = set(paths)
    visits = 0
    visit_limit = max(32, len(paths) * 16)
    while queue:
        path = queue.popleft()
        queued.remove(path)
        visits += 1
        if visits > visit_limit:
            raise RuntimeError(
                f"Wall-clock import alias propagation did not converge after {visit_limit} module visits."
            )
        if _metrics is not None:
            _metrics.module_visits += 1
        visitor = _WallClockAssertionVisitor(path, import_aliases)
        visitor.visit(trees[path])
        exports = _module_exports(visitor.scopes[0])
        if exports_by_path.get(path) == exports:
            continue
        exports_by_path[path] = exports
        for module_name in module_names[path]:
            import_aliases[module_name] = exports
        for dependent in dependents[path]:
            if dependent not in queued:
                queue.append(dependent)
                queued.add(dependent)
    return import_aliases


def _imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(
                f"{node.module}.{alias.name}"
                for alias in node.names
                if alias.name != "*"
            )
    return names


def _module_names(path: Path, root: Path) -> set[str]:
    try:
        relative = path.with_suffix("").relative_to(root)
    except ValueError:
        return set()
    parts = relative.parent.parts if relative.name == "__init__" else relative.parts
    if not parts:
        return set()
    names = {".".join(parts)}
    if root.name:
        names.add(".".join((root.name, *parts)))
    return names


def _module_exports(scope: _AliasMap) -> _AliasMap:
    return {
        path: source
        for path, source in scope.items()
        if source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS
    }


def _collect_conftest_aliases(
    paths: list[Path],
    import_aliases: dict[str, _AliasMap],
    *,
    _trees: Mapping[Path, ast.Module] | None = None,
) -> tuple[dict[Path, _AliasMap], dict[Path, _AliasMap]]:
    conftest_fixture_aliases: dict[Path, _AliasMap] = {}
    conftest_module_aliases: dict[Path, _AliasMap] = {}
    for path in paths:
        if path.name != "conftest.py":
            continue
        tree = (
            _trees[path]
            if _trees is not None
            else ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
        visitor = _WallClockAssertionVisitor(path, import_aliases)
        visitor.visit(tree)
        conftest_fixture_aliases[path] = visitor.fixture_return_aliases()
        conftest_module_aliases[path] = visitor.autouse_module_aliases

    fixture_aliases_by_path: dict[Path, _AliasMap] = {}
    module_aliases_by_path: dict[Path, _AliasMap] = {}
    for path in paths:
        fixture_aliases: _AliasMap = {}
        module_aliases: _AliasMap = {}
        for conftest_path in conftest_fixture_aliases:
            if conftest_path.parent == path.parent or conftest_path.parent in path.parent.parents:
                fixture_aliases.update(conftest_fixture_aliases[conftest_path])
                module_aliases.update(conftest_module_aliases[conftest_path])
        if fixture_aliases:
            fixture_aliases_by_path[path] = fixture_aliases
        if module_aliases:
            module_aliases_by_path[path] = module_aliases
    return fixture_aliases_by_path, module_aliases_by_path


def format_wall_clock_assertion_violations(
    violations: Iterable[WallClockAssertionViolation],
) -> str:
    rendered = "\n".join(f"  - {violation.render()}" for violation in violations)
    return (
        "Wall-clock reads are not allowed inside test assertions.\n"
        "Inject a stable `now=`/clock into production code and assert against that fixed value.\n"
        "For genuine freshness-window checks, capture bounds before/after the action and keep the wall-clock calls out of the assert expression.\n"
        f"{rendered}"
    )


def _wall_clock_calls(
    assert_node: ast.Assert,
    scopes: list[_AliasMap],
) -> list[tuple[ast.Call, str]]:
    visitor = _AssertCallVisitor(scopes)
    visitor.visit(assert_node.test)
    if assert_node.msg is not None:
        visitor.visit(assert_node.msg)
    return visitor.calls


class _AssertCallVisitor(ast.NodeVisitor):
    def __init__(self, scopes: list[_AliasMap]) -> None:
        self.scopes = [*scopes, {}]
        self.calls: list[tuple[ast.Call, str]] = []

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.NamedExpr):
            self.visit(node.func.value)
            self._add_assignment_aliases([node.func.target], node.func.value)
            raw_path = _attribute_path(node.func.target)
        else:
            raw_path = _attribute_path(node.func)
            self.visit(node.func)

        if raw_path and _normalize_alias(raw_path, self.scopes) in _BANNED_CALLS:
            self.calls.append((node, f"{'.'.join(raw_path)}()"))

        for arg in node.args:
            self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._add_assignment_aliases([node.target], node.value)

    def visit_If(self, node: ast.If) -> None:
        if _is_static_false(node.test) or _is_type_checking_name(node.test, self.scopes):
            for statement in node.orelse:
                self.visit(statement)
            return
        if _is_static_true(node.test):
            for statement in node.body:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *(default for default in node.args.kw_defaults if default is not None)):
            self.visit(default)
        local_scope: _AliasMap = {(name,): None for name in _argument_names(node.args)}
        local_scope.update(_arguments_default_aliases(node.args, self.scopes))
        self.scopes.append(local_scope)
        try:
            self.visit(node.body)
        finally:
            self.scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension([node.elt], node.generators)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension([node.elt], node.generators)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension([node.elt], node.generators)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension([node.key, node.value], node.generators)

    def _add_assignment_aliases(self, targets: list[ast.expr], value: ast.expr) -> None:
        _add_assignment_aliases(self.scopes, lambda _: self.scope, targets, value)

    def _visit_comprehension(
        self,
        result_nodes: list[ast.expr],
        generators: list[ast.comprehension],
    ) -> None:
        local_scope: _AliasMap = {}
        self.scopes.append(local_scope)
        for generator in generators:
            self.visit(generator.iter)
            for target_path in _assignment_target_paths(generator.target):
                _set_shadow(local_scope, target_path)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self.scopes.pop()


class _WallClockAssertionVisitor(ast.NodeVisitor):
    def __init__(
        self,
        path: Path,
        import_aliases: dict[str, _AliasMap] | None = None,
        external_fixture_aliases: _AliasMap | None = None,
        external_module_aliases: _AliasMap | None = None,
    ) -> None:
        self.path = path
        self.import_aliases = import_aliases or {}
        self.external_fixture_aliases = external_fixture_aliases or {}
        self.violations: list[WallClockAssertionViolation] = []
        self.scopes: list[_AliasMap] = [external_module_aliases.copy() if external_module_aliases else {}]
        self.global_names_stack: list[set[str]] = []
        self.propagate_global_stack: list[bool] = []
        self.defer_function_scans = True
        self.deferred_functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.deferred_classes: list[tuple[str, list[ast.FunctionDef | ast.AsyncFunctionDef], set[str]]] = []
        self.local_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.value_literals: _ValueMap = {}
        self.class_initializers: _ClassInitializers = {}
        self.autouse_fixtures: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.autouse_module_aliases: _AliasMap = {}
        self.fixtures: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.module_usefixtures: set[str] = set()

    def fixture_return_aliases(self) -> _AliasMap:
        aliases: _AliasMap = {}
        for fixture_name in self.fixtures:
            aliases.update(self._fixture_return_aliases(fixture_name, set()))
        return aliases

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit_Module(self, node: ast.Module) -> None:
        for statement in node.body:
            self.visit(statement)
        self._scan_deferred_functions()

    def visit_Assert(self, node: ast.Assert) -> None:
        for call, call_name in _wall_clock_calls(node, self.scopes):
            self.violations.append(
                WallClockAssertionViolation(
                    path=self.path,
                    line=getattr(call, "lineno", node.lineno),
                    call=call_name,
                )
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            parts = tuple(alias.name.split("."))
            module_name = ".".join(parts)
            if module_name in self.import_aliases:
                target_path = (alias.asname,) if alias.asname else parts
                self._add_module_import_aliases(target_path, self.import_aliases[module_name])
            elif parts and parts[0] in {"datetime", "time", "typing", "pytest"}:
                self._set_alias((alias.asname or parts[0],), parts)
            else:
                self._set_shadow((alias.asname or parts[0],))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    self._set_alias((alias.asname or alias.name,), ("typing", "TYPE_CHECKING"))
                elif alias.name != "*":
                    self._set_shadow((alias.asname or alias.name,))
            return
        if node.module == "pytest":
            for alias in node.names:
                if alias.name in {"fixture", "mark", "param"}:
                    self._set_alias((alias.asname or alias.name,), ("pytest", alias.name))
                elif alias.name != "*":
                    self._set_shadow((alias.asname or alias.name,))
            return
        if node.module and self._has_from_import_aliases(node.module, node.names):
            self._add_from_import_aliases(node.module, node.names)
            return
        if node.module not in {"datetime", "time"}:
            for alias in node.names:
                if alias.name == "*":
                    self._set_shadow(("datetime",))
                    self._set_shadow(("date",))
                    self._set_shadow(("time",))
                else:
                    self._set_shadow((alias.asname or alias.name,))
            return
        for alias in node.names:
            if alias.name == "*":
                _add_star_import_aliases(self.scope, node.module)
                continue
            self._set_alias((alias.asname or alias.name,), (node.module, alias.name))

    def _add_module_import_aliases(self, target_path: tuple[str, ...], exports: _AliasMap) -> None:
        existing_descendants = {
            alias_path: source
            for alias_path, source in self.scope.items()
            if len(alias_path) > len(target_path) and alias_path[: len(target_path)] == target_path and source is not None
        }
        self._set_shadow(target_path)
        for alias_path, source in existing_descendants.items():
            self._set_alias(alias_path, source)
        for export_path, export_source in exports.items():
            if export_source is not None:
                self._set_alias((*target_path, *export_path), export_source)

    def _add_from_import_aliases(self, module_name: str, aliases: list[ast.alias]) -> None:
        exports = self.import_aliases.get(module_name, {})
        for alias in aliases:
            if alias.name == "*":
                for export_path, source in exports.items():
                    if source is not None:
                        self._set_alias(export_path, source)
                continue
            target_name = alias.asname or alias.name
            source = exports.get((alias.name,))
            if source is not None:
                self._set_alias((target_name,), source)
                continue
            descendant_exports = {
                export_path[1:]: export_source
                for export_path, export_source in exports.items()
                if len(export_path) > 1 and export_path[0] == alias.name and export_source is not None
            }
            if descendant_exports:
                for export_path, export_source in descendant_exports.items():
                    self._set_alias((target_name, *export_path), export_source)
                continue
            imported_module = self.import_aliases.get(f"{module_name}.{alias.name}")
            if imported_module is not None:
                self._add_module_import_aliases((target_name,), imported_module)
                continue
            self._set_shadow((target_name,))

    def _has_from_import_aliases(self, module_name: str, aliases: list[ast.alias]) -> bool:
        return module_name in self.import_aliases or any(
            alias.name != "*" and f"{module_name}.{alias.name}" in self.import_aliases for alias in aliases
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if _attribute_path(target) == ("pytestmark",):
                self.module_usefixtures.update(_pytestmark_usefixture_names(node.value, self.scopes))
        self._record_value_literals(node.targets, node.value)
        self._add_assignment_aliases(node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            self._shadow_targets([node.target])
            return
        self._record_value_literals([node.target], node.value)
        self._add_assignment_aliases([node.target], node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._shadow_targets([node.target])

    def visit_For(self, node: ast.For) -> None:
        self._visit_for(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with(node)

    def _visit_for(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        self._shadow_targets([node.target])
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._shadow_targets([item.optional_vars])
        for statement in node.body:
            self.visit(statement)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._add_assignment_aliases([node.target], node.value)

    def visit_Call(self, node: ast.Call) -> None:
        _record_setattr_alias(self.scopes, self._scope_for_target, node)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if _is_static_false(node.test) or _is_type_checking_name(node.test, self.scopes):
            for statement in node.orelse:
                self.visit(statement)
            return
        if _is_static_true(node.test):
            for statement in node.body:
                self.visit(statement)
            return
        self.visit(node.test)
        self._visit_unknown_branch(node.body)
        self._visit_unknown_branch(node.orelse)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.defer_function_scans:
            self._set_shadow((node.name,))
            self.local_functions[node.name] = node
            self._record_function_return_alias(node)
            if node.name in _MODULE_SETUP_NAMES:
                _propagate_module_setup_aliases(node, self.scopes)
            self._record_fixture(node)
            if _is_autouse_fixture(node, self.scopes):
                self.autouse_fixtures.append(node)
            self.deferred_functions.append(node)
            return
        self._set_shadow((node.name,))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self.defer_function_scans:
            self._set_shadow((node.name,))
            self.local_functions[node.name] = node
            self._record_function_return_alias(node)
            if node.name in _MODULE_SETUP_NAMES:
                _propagate_module_setup_aliases(node, self.scopes)
            self._record_fixture(node)
            if _is_autouse_fixture(node, self.scopes):
                self.autouse_fixtures.append(node)
            self.deferred_functions.append(node)
            return
        self._set_shadow((node.name,))

    def _scan_function_def(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        fixture_aliases: _AliasMap = {}
        if _is_test_function(node):
            fixture_aliases = self._fixture_aliases_for_function(node, set())
        self._visit_function_scope(node, bind_name=True, local_aliases=fixture_aliases)
        if not _is_test_function(node):
            self._record_function_return_alias(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.defer_function_scans:
            self._set_shadow((node.name,))
            return

        self._set_shadow((node.name,))
        class_usefixtures = _usefixture_names(node.decorator_list, self.scopes)
        deferred_methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

        self.scopes.append({})
        for statement in node.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                self._set_shadow((statement.name,))
                deferred_methods.append(statement)
                continue
            self.visit(statement)
        class_aliases = {path: source for path, source in self.scope.items() if source is not None}
        self.scopes.pop()

        for path, source in class_aliases.items():
            self._set_alias((node.name, *path), source)
        init_method = _class_init_method(deferred_methods)
        if init_method is not None:
            self.class_initializers[(node.name,)] = init_method
        self.deferred_classes.append((node.name, deferred_methods, class_usefixtures))

    def _scan_deferred_functions(self) -> None:
        self.defer_function_scans = False
        for fixture in self.autouse_fixtures:
            before = self.scopes[0].copy()
            self._propagate_fixture_node_aliases(fixture, set())
            self._record_autouse_module_aliases(before)
        for function in self.deferred_functions:
            self._scan_function_def(function)
        for class_name, methods, class_usefixtures in self.deferred_classes:
            base_class_aliases = _module_class_aliases(self.scopes[0], class_name)
            for method in methods:
                if method.name in _SETUP_METHOD_NAMES:
                    base_class_aliases.update(_method_instance_aliases(method, self.scopes, base_class_aliases))
            class_fixture_methods = _class_fixture_methods(methods, self.scopes)
            autouse_fixture_methods = [
                method for method in methods if _is_autouse_fixture(method, self.scopes)
            ]
            for method in methods:
                class_aliases = base_class_aliases.copy()
                fixture_aliases: _AliasMap = {}
                if _is_test_function(method):
                    requested_fixtures = class_usefixtures | _usefixture_names(method.decorator_list, self.scopes)
                    for fixture_method in autouse_fixture_methods:
                        class_aliases.update(
                            _method_instance_aliases(
                                fixture_method,
                                self.scopes,
                                class_aliases,
                                stop_at_yield=True,
                            )
                        )
                    for fixture_name in requested_fixtures:
                        requested_fixture_method = class_fixture_methods.get(fixture_name)
                        if requested_fixture_method is not None:
                            class_aliases.update(
                                _method_instance_aliases(
                                    requested_fixture_method,
                                    self.scopes,
                                    class_aliases,
                                    stop_at_yield=True,
                                )
                            )
                    fixture_aliases = self._fixture_aliases_for_function(method, class_usefixtures)
                self._visit_function_scope(
                    method,
                    bind_name=False,
                    class_aliases=class_aliases,
                    local_aliases=fixture_aliases,
                )
        self.defer_function_scans = True

    def _record_autouse_module_aliases(self, before: _AliasMap) -> None:
        for path, source in self.scopes[0].items():
            if source is not None and before.get(path) != source:
                self.autouse_module_aliases[path] = source

    def _visit_function_scope(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        bind_name: bool,
        class_aliases: dict[tuple[str, ...], tuple[str, ...]] | None = None,
        local_aliases: _AliasMap | None = None,
    ) -> None:
        if bind_name:
            self._set_shadow((node.name,))
        local_shadows: _AliasMap = {(name,): None for name in _function_bound_names(node)}
        local_shadows.update(_function_default_aliases(node, self.scopes))
        if _is_test_function(node):
            local_shadows.update(
                _parametrize_aliases(
                    node.decorator_list,
                    self.scopes,
                    self.value_literals,
                    self.class_initializers,
                )
            )
        if class_aliases:
            for self_name in _method_self_names(node):
                for path, source in class_aliases.items():
                    local_shadows[(self_name, *path)] = source
        if local_aliases:
            local_shadows.update(local_aliases)
        self.scopes.append(local_shadows)
        self.global_names_stack.append(_function_global_names(node))
        self.propagate_global_stack.append(bind_name and node.name in _MODULE_SETUP_NAMES)
        for statement in node.body:
            self.visit(statement)
        self.propagate_global_stack.pop()
        self.global_names_stack.pop()
        self.scopes.pop()

    def _add_assignment_aliases(self, targets: list[ast.expr], value: ast.expr) -> None:
        _add_assignment_aliases(self.scopes, self._scope_for_target, targets, value)
        _add_call_result_aliases_from_functions(
            self.scopes,
            self._scope_for_target,
            targets,
            value,
            self.local_functions,
            self.class_initializers,
        )
        _add_call_result_aliases_from_class_initializers(
            self.scopes,
            self._scope_for_target,
            targets,
            value,
            self.class_initializers,
        )

    def _record_function_return_alias(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for alias_path, source in _function_result_aliases(
            node,
            self.scopes,
            (node.name,),
            include_yields=False,
            class_initializers=self.class_initializers,
        ).items():
            if source is not None:
                self._set_alias(alias_path, source)

    def _record_fixture(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for fixture_name in _fixture_names(node, self.scopes):
            self.fixtures[fixture_name] = node

    def _fixture_aliases_for_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        extra_fixture_names: set[str],
    ) -> _AliasMap:
        fixture_argument_names = _argument_names(node.args)
        fixture_names = (
            fixture_argument_names
            | _usefixture_names(node.decorator_list, self.scopes)
            | self.module_usefixtures
            | extra_fixture_names
        )
        for fixture_name in sorted(fixture_names):
            self._propagate_fixture_aliases(fixture_name, set())

        aliases: _AliasMap = {}
        for fixture_name in sorted(fixture_argument_names):
            aliases.update(self._fixture_return_aliases(fixture_name, set()))
        return aliases

    def _propagate_fixture_aliases(self, fixture_name: str, active_fixtures: set[int]) -> None:
        fixture = self.fixtures.get(fixture_name)
        if fixture is not None:
            self._propagate_fixture_node_aliases(fixture, active_fixtures)

    def _propagate_fixture_node_aliases(
        self,
        fixture: ast.FunctionDef | ast.AsyncFunctionDef,
        active_fixtures: set[int],
    ) -> None:
        fixture_id = id(fixture)
        if fixture_id in active_fixtures:
            return
        active_fixtures.add(fixture_id)
        for dependency_name in _argument_names(fixture.args):
            self._propagate_fixture_aliases(dependency_name, active_fixtures)
        _propagate_module_setup_aliases(
            fixture,
            self.scopes,
            self._fixture_setup_aliases(fixture, active_fixtures),
            stop_at_yield=True,
        )
        active_fixtures.remove(fixture_id)

    def _fixture_setup_aliases(
        self,
        fixture: ast.FunctionDef | ast.AsyncFunctionDef,
        active_fixtures: set[int],
    ) -> _AliasMap:
        aliases = _fixture_param_aliases(
            fixture,
            self.scopes,
            self.value_literals,
            self.class_initializers,
        )
        aliases.update(self._fixture_argument_aliases(fixture, active_fixtures))
        return aliases

    def _fixture_argument_aliases(
        self,
        fixture: ast.FunctionDef | ast.AsyncFunctionDef,
        active_fixtures: set[int],
    ) -> _AliasMap:
        aliases: _AliasMap = {}
        for dependency_name in _argument_names(fixture.args):
            aliases.update(self._fixture_return_aliases(dependency_name, active_fixtures))
        return aliases

    def _fixture_return_aliases(self, fixture_name: str, active_fixtures: set[int]) -> _AliasMap:
        fixture = self.fixtures.get(fixture_name)
        if fixture is None:
            return {
                path: source
                for path, source in self.external_fixture_aliases.items()
                if path[:1] == (fixture_name,) and source is not None
            }
        fixture_id = id(fixture)
        if fixture_id in active_fixtures:
            return {}
        active_fixtures.add(fixture_id)
        local_aliases = _function_default_aliases(fixture, self.scopes)
        local_aliases.update(
            _fixture_param_aliases(
                fixture,
                self.scopes,
                self.value_literals,
                self.class_initializers,
            )
        )
        local_aliases.update(self._fixture_argument_aliases(fixture, active_fixtures))
        aliases = _function_result_aliases(
            fixture,
            self.scopes,
            (fixture_name,),
            include_yields=True,
            initial_aliases=local_aliases,
            class_initializers=self.class_initializers,
        )
        active_fixtures.remove(fixture_id)
        return aliases

    def _shadow_targets(self, targets: list[ast.expr]) -> None:
        for target in targets:
            for target_path in _assignment_target_paths(target):
                self._set_shadow(target_path)

    def _record_value_literals(self, targets: list[ast.expr], value: ast.expr) -> None:
        if not self.defer_function_scans or len(self.scopes) != 1:
            return
        for target in targets:
            target_path = _attribute_path(target)
            if not target_path:
                continue
            if isinstance(value, ast.Tuple | ast.List):
                self.value_literals[target_path] = value
            else:
                self.value_literals.pop(target_path, None)

    def _set_alias(self, target_path: tuple[str, ...], source: tuple[str, ...]) -> None:
        _set_alias(self.scope, target_path, source)

    def _set_shadow(self, target_path: tuple[str, ...]) -> None:
        _set_shadow(self.scope, target_path)

    def _scope_for_target(self, target_path: tuple[str, ...]) -> _AliasMap:
        if (
            self.global_names_stack
            and self.propagate_global_stack
            and self.propagate_global_stack[-1]
            and len(target_path) == 1
            and target_path[0] in self.global_names_stack[-1]
        ):
            return self.scopes[0]
        return self.scope

    def _visit_unknown_branch(self, statements: list[ast.stmt]) -> None:
        branch_scope: _AliasMap = {}
        self.scopes.append(branch_scope)
        for statement in statements:
            self.visit(statement)
        self.scopes.pop()
        _merge_clock_aliases(self.scope, branch_scope)


def _add_star_import_aliases(
    aliases: _AliasMap,
    module: str | None,
) -> None:
    if module == "time":
        aliases[("time",)] = ("time", "time")
    elif module == "datetime":
        aliases[("datetime",)] = ("datetime", "datetime")
        aliases[("date",)] = ("datetime", "date")


def _module_class_aliases(
    module_scope: _AliasMap,
    class_name: str,
) -> dict[tuple[str, ...], tuple[str, ...]]:
    return {
        alias_path[1:]: source
        for alias_path, source in module_scope.items()
        if len(alias_path) > 1 and alias_path[0] == class_name and source is not None
    }


def _class_fixture_methods(
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    scopes: list[_AliasMap],
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    fixtures: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for method in methods:
        for fixture_name in _fixture_names(method, scopes):
            fixtures[fixture_name] = method
    return fixtures


def _merge_clock_aliases(target: _AliasMap, source: _AliasMap) -> None:
    for path, alias_source in source.items():
        if alias_source is not None:
            _set_alias(target, path, alias_source)


def _fixture_names(node: ast.FunctionDef | ast.AsyncFunctionDef, scopes: list[_AliasMap]) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        if not _is_fixture_decorator(decorator, scopes):
            continue
        names.add(_fixture_decorator_name(decorator) or node.name)
    return names


def _is_autouse_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef, scopes: list[_AliasMap]) -> bool:
    for decorator in node.decorator_list:
        if not _is_fixture_decorator(decorator, scopes):
            continue
        if not isinstance(decorator, ast.Call):
            continue
        for keyword in decorator.keywords:
            if keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                return True
    return False


def _is_fixture_decorator(decorator: ast.expr, scopes: list[_AliasMap]) -> bool:
    path = _attribute_path(decorator.func) if isinstance(decorator, ast.Call) else _attribute_path(decorator)
    return _normalize_alias(path, scopes) in {("fixture",), ("pytest", "fixture")}


def _fixture_decorator_name(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    for keyword in decorator.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _usefixture_names(decorators: list[ast.expr], scopes: list[_AliasMap]) -> set[str]:
    names: set[str] = set()
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if _normalize_alias(_attribute_path(decorator.func), scopes) != ("pytest", "mark", "usefixtures"):
            continue
        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.add(arg.value)
    return names


def _pytestmark_usefixture_names(node: ast.expr, scopes: list[_AliasMap]) -> set[str]:
    if isinstance(node, ast.Call):
        return _usefixture_names([node], scopes)
    if isinstance(node, ast.Tuple | ast.List):
        names: set[str] = set()
        for element in node.elts:
            names.update(_pytestmark_usefixture_names(element, scopes))
        return names
    return set()


def _parametrize_aliases(
    decorators: list[ast.expr],
    scopes: list[_AliasMap],
    value_literals: _ValueMap,
    class_initializers: _ClassInitializers,
) -> _AliasMap:
    aliases: _AliasMap = {}
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if _normalize_alias(_attribute_path(decorator.func), scopes) != ("pytest", "mark", "parametrize"):
            continue
        argnames_node = _call_arg_or_keyword(decorator, 0, "argnames")
        argvalues_node = _call_arg_or_keyword(decorator, 1, "argvalues")
        if argnames_node is None or argvalues_node is None:
            continue
        argnames = _parametrize_argnames(argnames_node)
        if not argnames:
            continue
        for row in _parametrize_rows(argvalues_node, len(argnames), scopes, value_literals):
            for name, value in zip(argnames, row, strict=False):
                aliases.update(_expression_aliases_for_target((name,), value, scopes, class_initializers))
    return aliases


def _fixture_param_aliases(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
    value_literals: _ValueMap,
    class_initializers: _ClassInitializers,
) -> _AliasMap:
    aliases: _AliasMap = {}
    for decorator in node.decorator_list:
        if not _is_fixture_decorator(decorator, scopes) or not isinstance(decorator, ast.Call):
            continue
        params_node = _call_arg_or_keyword(decorator, -1, "params")
        if params_node is None:
            continue
        for row in _parametrize_rows(params_node, 1, scopes, value_literals):
            if row:
                aliases.update(_expression_aliases_for_target(("request", "param"), row[0], scopes, class_initializers))
    return aliases


def _call_arg_or_keyword(call: ast.Call, index: int, name: str) -> ast.expr | None:
    if index >= 0 and len(call.args) > index:
        return call.args[index]
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _parametrize_argnames(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        separator = "," if "," in node.value else None
        return [name.strip() for name in node.value.split(separator) if name.strip()]
    if isinstance(node, ast.Tuple | ast.List):
        names: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                names.append(element.value)
        return names
    return []


def _parametrize_rows(
    node: ast.expr,
    arity: int,
    scopes: list[_AliasMap],
    value_literals: _ValueMap,
) -> list[list[ast.expr]]:
    resolved_node = _resolve_value_literal(node, value_literals)
    if not isinstance(resolved_node, ast.Tuple | ast.List):
        return []
    rows: list[list[ast.expr]] = []
    for element in resolved_node.elts:
        pytest_param_values = _pytest_param_values(element, scopes)
        if pytest_param_values is not None:
            rows.append(pytest_param_values[:arity])
        elif arity == 1:
            rows.append([element])
        elif isinstance(element, ast.Tuple | ast.List):
            rows.append(list(element.elts)[:arity])
    return rows


def _resolve_value_literal(node: ast.expr, value_literals: _ValueMap) -> ast.expr:
    return value_literals.get(_attribute_path(node), node)


def _pytest_param_values(node: ast.expr, scopes: list[_AliasMap]) -> list[ast.expr] | None:
    if not isinstance(node, ast.Call):
        return None
    if _normalize_alias(_attribute_path(node.func), scopes) != ("pytest", "param"):
        return None
    return list(node.args)


def _propagate_module_setup_aliases(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
    local_aliases: _AliasMap | None = None,
    *,
    stop_at_yield: bool = False,
) -> None:
    global_names = _function_global_names(node)
    collector = _ModuleSetupAliasCollector(scopes, global_names, local_aliases)
    for statement in (_setup_phase_body(node.body) if stop_at_yield else node.body):
        collector.visit(statement)


def _setup_phase_body(statements: list[ast.stmt]) -> list[ast.stmt]:
    setup_statements: list[ast.stmt] = []
    for statement in statements:
        if any(isinstance(node, ast.Yield | ast.YieldFrom) for node in ast.walk(statement)):
            break
        setup_statements.append(statement)
    return setup_statements


class _ModuleSetupAliasCollector(ast.NodeVisitor):
    def __init__(self, scopes: list[_AliasMap], global_names: set[str], local_aliases: _AliasMap | None = None) -> None:
        self.global_names = global_names
        self.scopes = [*scopes, local_aliases.copy() if local_aliases else {}]
        self.local_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.local_helper_aliases: dict[str, str] = {}
        self.active_helpers: set[str] = set()

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_helper_aliases(node.targets, node.value)
        _add_assignment_aliases(self.scopes, self._scope_for_target, node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            _add_assignment_aliases(self.scopes, self._scope_for_target, [node.target], node.value)

    def visit_If(self, node: ast.If) -> None:
        if _is_static_false(node.test) or _is_type_checking_name(node.test, self.scopes):
            for statement in node.orelse:
                self.visit(statement)
            return
        if _is_static_true(node.test):
            for statement in node.body:
                self.visit(statement)
            return
        self.visit(node.test)
        self._visit_unknown_branch(node.body)
        self._visit_unknown_branch(node.orelse)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.local_helpers[node.name] = node
        _set_alias(self.scope, (node.name,), (node.name,))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.local_helpers[node.name] = node
        _set_alias(self.scope, (node.name,), (node.name,))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        del node

    def visit_Call(self, node: ast.Call) -> None:
        _record_setattr_alias(self.scopes, self._scope_for_target, node)
        helper_name = self._local_helper_alias_name(_raw_called_name(node))
        if helper_name is None:
            helper_name = self._local_helper_name(_called_name(node, self.scopes))
        if helper_name is None or helper_name not in self.local_helpers or helper_name in self.active_helpers:
            self.generic_visit(node)
            return
        helper = self.local_helpers[helper_name]
        bindings = _call_argument_bindings(helper, node)
        if bindings is None:
            self.generic_visit(node)
            return
        call_scope = _function_call_scope(helper, bindings, self.scopes)
        self.active_helpers.add(helper_name)
        original_global_names = self.global_names
        self.global_names = self.global_names | _function_global_names(helper)
        self.scopes.append(call_scope)
        try:
            for statement in helper.body:
                self.visit(statement)
        finally:
            self.scopes.pop()
            self.global_names = original_global_names
            self.active_helpers.remove(helper_name)

    def _scope_for_target(self, target_path: tuple[str, ...]) -> _AliasMap:
        if len(target_path) == 1 and target_path[0] in self.global_names:
            return self.scopes[0]
        if len(target_path) > 1 and self._is_module_attribute_target(target_path):
            return self.scopes[0]
        return self.scope

    def _is_module_attribute_target(self, target_path: tuple[str, ...]) -> bool:
        root_path = target_path[:1]
        if root_path in self.scope:
            return False
        return target_path[0] in self.global_names or any(path[:1] == root_path for path in self.scopes[0])

    def _record_helper_aliases(self, targets: list[ast.expr], value: ast.expr) -> None:
        source = _attribute_path(value)
        helper_name = source[0] if len(source) == 1 and source[0] in self.local_helpers else None
        for target in targets:
            target_path = _attribute_path(target)
            if len(target_path) == 1:
                if helper_name is None:
                    self.local_helper_aliases.pop(target_path[0], None)
                else:
                    self.local_helper_aliases[target_path[0]] = helper_name

    def _local_helper_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        return self.local_helper_aliases.get(name, name)

    def _local_helper_alias_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        return self.local_helper_aliases.get(name)

    def _visit_unknown_branch(self, statements: list[ast.stmt]) -> None:
        branch_scope: _AliasMap = {}
        self.scopes.append(branch_scope)
        for statement in statements:
            self.visit(statement)
        self.scopes.pop()
        _merge_clock_aliases(self.scope, branch_scope)

def _add_assignment_aliases(
    scopes: list[_AliasMap],
    scope_for_target: Callable[[tuple[str, ...]], _AliasMap],
    targets: list[ast.expr],
    value: ast.expr,
) -> None:
    if len(targets) == 1 and isinstance(targets[0], ast.Tuple | ast.List) and isinstance(value, ast.Tuple | ast.List):
        for target, element in zip(targets[0].elts, value.elts, strict=False):
            _add_assignment_aliases(scopes, scope_for_target, [target], element)
        return

    source = _alias_source(value, scopes)
    if source not in _ALIASABLE_CLOCK_PATHS:
        for target in targets:
            for target_path in _assignment_target_paths(target):
                target_scope = scope_for_target(target_path)
                _set_shadow(target_scope, target_path)
                _add_inline_field_aliases(target_scope, target_path, value, scopes)
                _add_call_result_field_aliases(target_scope, target_path, value, scopes)
        return
    for target in targets:
        target_path = _attribute_path(target)
        if target_path:
            _set_alias(scope_for_target(target_path), target_path, source)


def _add_call_result_aliases_from_functions(
    scopes: list[_AliasMap],
    scope_for_target: Callable[[tuple[str, ...]], _AliasMap],
    targets: list[ast.expr],
    value: ast.expr,
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    class_initializers: _ClassInitializers,
) -> None:
    if not isinstance(value, ast.Call):
        return
    helper_name = _called_name(value, scopes)
    raw_helper_name = _raw_called_name(value)
    if helper_name is None and raw_helper_name is not None and (raw_helper_name,) not in scopes[-1]:
        helper_name = raw_helper_name
    if helper_name is None:
        return
    helper = functions.get(helper_name)
    if helper is None:
        return
    bindings = _call_argument_bindings(helper, value)
    if bindings is None:
        return
    call_scope = _function_call_scope(helper, bindings, scopes)
    for target in targets:
        target_path = _attribute_path(target)
        if not target_path:
            continue
        target_scope = scope_for_target(target_path)
        for alias_path, source in _function_result_aliases(
            helper,
            scopes,
            target_path,
            include_yields=False,
            initial_aliases=call_scope,
            class_initializers=class_initializers,
        ).items():
            if source is not None:
                _set_alias(target_scope, alias_path, source)


def _add_call_result_aliases_from_class_initializers(
    scopes: list[_AliasMap],
    scope_for_target: Callable[[tuple[str, ...]], _AliasMap],
    targets: list[ast.expr],
    value: ast.expr,
    class_initializers: _ClassInitializers,
) -> None:
    if not isinstance(value, ast.Call):
        return
    for target in targets:
        target_path = _attribute_path(target)
        if not target_path:
            continue
        target_scope = scope_for_target(target_path)
        for alias_path, source in _constructor_field_aliases(value, scopes, class_initializers).items():
            if source is not None:
                _set_alias(target_scope, (*target_path, *alias_path), source)


def _record_setattr_alias(
    scopes: list[_AliasMap],
    scope_for_target: Callable[[tuple[str, ...]], _AliasMap],
    node: ast.Call,
) -> None:
    targets_and_value = _setattr_targets_and_value(node)
    if targets_and_value is None:
        return
    target_paths, value = targets_and_value
    for target_path in target_paths:
        target_scope = scope_for_target(target_path)
        aliases = _expression_aliases_for_target(target_path, value, scopes)
        if not aliases:
            _set_shadow(target_scope, target_path)
            continue
        for alias_path, source in aliases.items():
            if source is not None:
                _set_alias(target_scope, alias_path, source)


def _setattr_targets_and_value(node: ast.Call) -> tuple[list[tuple[str, ...]], ast.expr] | None:
    func_path = _attribute_path(node.func)
    if func_path == ("setattr",) or (len(func_path) >= 2 and func_path[-1] == "setattr"):
        args = node.args
    else:
        return None
    if len(args) >= 3 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, str):
        target_root = _attribute_path(args[0])
        if target_root:
            return [(*target_root, args[1].value)], args[2]
    if len(func_path) >= 2 and len(args) >= 2 and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        target_paths = _dotted_target_paths(args[0].value)
        if target_paths:
            return target_paths, args[1]
    return None


def _dotted_target_paths(value: str) -> list[tuple[str, ...]]:
    parts = tuple(part for part in value.split(".") if part)
    if len(parts) < 2:
        return []
    return [parts[index:] for index in range(len(parts) - 1)]


def _expression_aliases_for_target(
    target_path: tuple[str, ...],
    value: ast.expr,
    scopes: list[_AliasMap],
    class_initializers: _ClassInitializers | None = None,
) -> _AliasMap:
    aliases: _AliasMap = {}
    source = _alias_source(value, scopes)
    if _is_clock_source(source):
        aliases[target_path] = source
    for field_path, field_source in _call_field_aliases(value, scopes).items():
        if field_source is not None:
            aliases[(*target_path, *field_path)] = field_source
    for field_path, field_source in _call_result_field_aliases(value, scopes).items():
        if field_source is not None:
            aliases[(*target_path, *field_path)] = field_source
    if class_initializers is not None:
        for field_path, field_source in _constructor_field_aliases(value, scopes, class_initializers).items():
            if field_source is not None:
                aliases[(*target_path, *field_path)] = field_source
    return aliases


def _add_inline_field_aliases(
    aliases: _AliasMap,
    target_path: tuple[str, ...],
    value: ast.expr,
    scopes: list[_AliasMap],
) -> None:
    for field_path, source in _call_field_aliases(value, scopes).items():
        if source is not None:
            _set_alias(aliases, (*target_path, *field_path), source)


def _add_call_result_field_aliases(
    aliases: _AliasMap,
    target_path: tuple[str, ...],
    value: ast.expr,
    scopes: list[_AliasMap],
) -> None:
    for field_path, source in _call_result_field_aliases(value, scopes).items():
        if source is not None:
            _set_alias(aliases, (*target_path, *field_path), source)


def _set_alias(scope: _AliasMap, target_path: tuple[str, ...], source: tuple[str, ...]) -> None:
    scope[target_path] = source


def _set_shadow(scope: _AliasMap, target_path: tuple[str, ...]) -> None:
    for alias_path in list(scope):
        if len(alias_path) > len(target_path) and alias_path[: len(target_path)] == target_path:
            del scope[alias_path]
    scope[target_path] = None


def _normalize_alias(
    path: tuple[str, ...],
    scopes: list[_AliasMap],
) -> tuple[str, ...]:
    for scope in reversed(scopes):
        for index in range(len(path), 0, -1):
            prefix = path[:index]
            if prefix not in scope:
                continue
            replacement = scope[prefix]
            if replacement is None:
                return _SHADOWED_PATH
            return replacement + path[index:]
    return path


def _alias_source(node: ast.expr, scopes: list[_AliasMap]) -> tuple[str, ...]:
    if (
        isinstance(node, ast.Call)
        and _attribute_path(node.func) in {("staticmethod",), ("classmethod",)}
        and len(node.args) == 1
    ):
        return _normalize_alias(_attribute_path(node.args[0]), scopes)
    if isinstance(node, ast.Lambda):
        source = _lambda_call_source(node, scopes)
        return source or _SHADOWED_PATH
    if isinstance(node, ast.Call):
        source = _normalize_alias(_attribute_path(node.func), scopes)
        if source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS:
            return source
    return _normalize_alias(_attribute_path(node), scopes)


def _lambda_call_source(node: ast.Lambda, scopes: list[_AliasMap]) -> tuple[str, ...] | None:
    local_scope: _AliasMap = {(name,): None for name in _argument_names(node.args)}
    local_scope.update(_arguments_default_aliases(node.args, scopes))
    lambda_scopes = [*scopes, local_scope]
    if isinstance(node.body, ast.Call):
        source = _normalize_alias(_attribute_path(node.body.func), lambda_scopes)
        if source in _BANNED_CALLS:
            return source
    return None


def _call_field_aliases(node: ast.expr, scopes: list[_AliasMap]) -> _AliasMap:
    if not isinstance(node, ast.Call):
        return {}
    aliases: _AliasMap = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        source = _alias_source(keyword.value, scopes)
        if source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS:
            aliases[(keyword.arg,)] = source
    return aliases


def _call_result_field_aliases(node: ast.expr, scopes: list[_AliasMap]) -> _AliasMap:
    if not isinstance(node, ast.Call):
        return {}
    raw_path = _attribute_path(node.func)
    path = _normalize_alias(raw_path, scopes)
    if not raw_path:
        return {}
    aliases: _AliasMap = {}
    prefixes = [raw_path]
    if path and path != _SHADOWED_PATH and path != raw_path:
        prefixes.append(path)
    for scope in scopes:
        for alias_path, source in scope.items():
            if source is None:
                continue
            if source not in _ALIASABLE_CLOCK_PATHS and source not in _BANNED_CALLS:
                continue
            for prefix in prefixes:
                if len(alias_path) > len(prefix) and alias_path[: len(prefix)] == prefix:
                    aliases[alias_path[len(prefix) :]] = source
    return aliases


def _constructor_field_aliases(
    node: ast.expr,
    scopes: list[_AliasMap],
    class_initializers: _ClassInitializers,
) -> _AliasMap:
    if not isinstance(node, ast.Call):
        return {}
    init_method = _class_initializer_for_call(node, scopes, class_initializers)
    if init_method is None:
        return {}
    call_scope = _initializer_call_scope(init_method, node, scopes)
    if call_scope is None:
        return {}
    aliases: _AliasMap = dict(_method_instance_aliases(init_method, scopes, {}, initial_aliases=call_scope))
    return aliases


def _class_initializer_for_call(
    node: ast.Call,
    scopes: list[_AliasMap],
    class_initializers: _ClassInitializers,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    raw_path = _attribute_path(node.func)
    normalized_path = _normalize_alias(raw_path, scopes)
    for path in (raw_path, normalized_path):
        init_method = class_initializers.get(path)
        if init_method is not None:
            return init_method
    return None


def _is_clock_source(source: tuple[str, ...] | None) -> bool:
    return source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS


def _expression_clock_source(node: ast.expr, scopes: list[_AliasMap]) -> tuple[str, ...] | None:
    visitor = _AssertCallVisitor(scopes)
    visitor.visit(node)
    if not visitor.calls:
        return None
    call, _ = visitor.calls[0]
    return _normalize_alias(_attribute_path(call.func), scopes)


def _is_static_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_static_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_type_checking_name(node: ast.AST, scopes: list[_AliasMap]) -> bool:
    return _normalize_alias(_attribute_path(node), scopes) == ("typing", "TYPE_CHECKING")


def _is_test_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.name.startswith("test_")


@lru_cache(maxsize=32_768)
def _function_bound_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = _argument_names(node.args)
    visitor = _FunctionBindingVisitor()
    for statement in node.body:
        visitor.visit(statement)
    names.update(visitor.names - visitor.global_names - visitor.nonlocal_names)
    return names


@lru_cache(maxsize=32_768)
def _function_global_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    visitor = _FunctionBindingVisitor()
    for statement in node.body:
        visitor.visit(statement)
    return visitor.global_names


def _function_default_aliases(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
) -> _AliasMap:
    return _arguments_default_aliases(node.args, scopes)


def _arguments_default_aliases(
    arguments: ast.arguments,
    scopes: list[_AliasMap],
) -> _AliasMap:
    aliases: _AliasMap = {}
    positional_args = (*arguments.posonlyargs, *arguments.args)
    default_offset = len(positional_args) - len(arguments.defaults)
    for arg, default in zip(positional_args[default_offset:], arguments.defaults, strict=False):
        source = _alias_source(default, scopes)
        if source in _ALIASABLE_CLOCK_PATHS:
            aliases[(arg.arg,)] = source

    for arg, kw_default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        if kw_default is None:
            continue
        source = _alias_source(kw_default, scopes)
        if source in _ALIASABLE_CLOCK_PATHS:
            aliases[(arg.arg,)] = source
    return aliases


def _function_return_alias(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
    *,
    include_yields: bool = False,
) -> tuple[str, ...] | None:
    visitor = _FunctionReturnAliasVisitor(scopes, node, include_yields=include_yields)
    for statement in node.body:
        visitor.visit(statement)
    return visitor.source


def _function_result_aliases(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
    target_prefix: tuple[str, ...],
    *,
    include_yields: bool,
    initial_aliases: _AliasMap | None = None,
    class_initializers: _ClassInitializers | None = None,
) -> _AliasMap:
    visitor = _FunctionReturnAliasVisitor(
        scopes,
        node,
        include_yields=include_yields,
        initial_aliases=initial_aliases,
        class_initializers=class_initializers,
    )
    for statement in node.body:
        visitor.visit(statement)

    aliases: _AliasMap = {}
    if visitor.source in _ALIASABLE_CLOCK_PATHS or visitor.source in _BANNED_CALLS:
        aliases[target_prefix] = visitor.source
    for alias_path, source in visitor.inline_result_aliases.items():
        if source is not None:
            aliases[(*target_prefix, *alias_path)] = source
    if visitor.result_path:
        for scope in visitor.scopes:
            for alias_path, source in scope.items():
                if (
                    source is not None
                    and (source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS)
                    and len(alias_path) > len(visitor.result_path)
                    and alias_path[: len(visitor.result_path)] == visitor.result_path
                ):
                    aliases[(*target_prefix, *alias_path[len(visitor.result_path) :])] = source
    return aliases


class _FunctionReturnAliasVisitor(ast.NodeVisitor):
    def __init__(
        self,
        scopes: list[_AliasMap],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        include_yields: bool,
        initial_aliases: _AliasMap | None = None,
        class_initializers: _ClassInitializers | None = None,
    ) -> None:
        local_scope: _AliasMap = {(name,): None for name in _function_bound_names(node)}
        local_scope.update(_function_default_aliases(node, scopes))
        if initial_aliases:
            local_scope.update(initial_aliases)
        self.scopes = [*scopes, local_scope]
        self.include_yields = include_yields
        self.source: tuple[str, ...] | None = None
        self.result_path: tuple[str, ...] | None = None
        self.inline_result_aliases: _AliasMap = {}
        self.class_initializers = class_initializers or {}

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            return
        self._record_result(node.value)

    def visit_Yield(self, node: ast.Yield) -> None:
        if not self.include_yields or node.value is None:
            return
        self._record_result(node.value)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        if self.include_yields:
            self._record_result(node.value)

    def _record_result(self, node: ast.expr) -> None:
        self.inline_result_aliases.update(_call_field_aliases(node, self.scopes))
        self.inline_result_aliases.update(_constructor_field_aliases(node, self.scopes, self.class_initializers))
        expression_source = _expression_clock_source(node, self.scopes)
        if expression_source is not None:
            self.source = expression_source
            return
        source = _alias_source(node, self.scopes)
        if source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS:
            self.source = source
        raw_path = _attribute_path(node)
        path = _normalize_alias(raw_path, self.scopes)
        if path and path != _SHADOWED_PATH:
            self.result_path = path
        elif raw_path:
            self.result_path = raw_path

    def visit_Assign(self, node: ast.Assign) -> None:
        _add_assignment_aliases(self.scopes, lambda _: self.scope, node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            _add_assignment_aliases(self.scopes, lambda _: self.scope, [node.target], node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        _add_assignment_aliases(self.scopes, lambda _: self.scope, [node.target], node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        del node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        del node

    def visit_Lambda(self, node: ast.Lambda) -> None:
        del node

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        _set_shadow(self.scope, (node.name,))
        self.scopes.append({})
        for statement in node.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            self.visit(statement)
        class_aliases = {path: source for path, source in self.scope.items() if source is not None}
        self.scopes.pop()
        for path, source in class_aliases.items():
            _set_alias(self.scope, (node.name, *path), source)


def _call_argument_bindings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    call: ast.Call,
) -> dict[str, ast.expr] | None:
    positional_params = (*function.args.posonlyargs, *function.args.args)
    if len(call.args) > len(positional_params):
        return None

    bindings = {param.arg: arg for param, arg in zip(positional_params, call.args, strict=False)}
    keyword_param_names = {param.arg for param in (*function.args.args, *function.args.kwonlyargs)}
    for keyword in call.keywords:
        if keyword.arg is None or keyword.arg not in keyword_param_names or keyword.arg in bindings:
            return None
        bindings[keyword.arg] = keyword.value
    return bindings


def _function_call_scope(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    bindings: dict[str, ast.expr],
    scopes: list[_AliasMap],
) -> _AliasMap:
    call_scope: _AliasMap = {(name,): None for name in _function_bound_names(function)}
    call_scope.update(_function_default_aliases(function, scopes))
    for name, value in bindings.items():
        source = _alias_source(value, scopes)
        if source in _ALIASABLE_CLOCK_PATHS:
            _set_alias(call_scope, (name,), source)
        else:
            _set_shadow(call_scope, (name,))
    return call_scope


def _initializer_call_scope(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    call: ast.Call,
    scopes: list[_AliasMap],
) -> _AliasMap | None:
    positional_params = (*function.args.posonlyargs, *function.args.args)
    user_params = positional_params[1:]
    if len(call.args) > len(user_params):
        return None

    bindings = {param.arg: arg for param, arg in zip(user_params, call.args, strict=False)}
    keyword_param_names = {param.arg for param in (*user_params, *function.args.kwonlyargs)}
    for keyword in call.keywords:
        if keyword.arg is None or keyword.arg not in keyword_param_names or keyword.arg in bindings:
            return None
        bindings[keyword.arg] = keyword.value
    return _function_call_scope(function, bindings, scopes)


def _class_init_method(
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for method in methods:
        if method.name == "__init__":
            return method
    return None


def _method_self_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    positional_args = (*node.args.posonlyargs, *node.args.args)
    if positional_args:
        names.add(positional_args[0].arg)
    if node.args.vararg is not None:
        names.add(node.args.vararg.arg)
    return names


def _method_instance_aliases(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scopes: list[_AliasMap],
    class_aliases: dict[tuple[str, ...], tuple[str, ...]],
    *,
    stop_at_yield: bool = False,
    initial_aliases: _AliasMap | None = None,
) -> dict[tuple[str, ...], tuple[str, ...]]:
    self_names = _method_self_names(node)
    aliases: dict[tuple[str, ...], tuple[str, ...]] = {}
    if not self_names:
        return aliases

    collector = _MethodInstanceAliasCollector(scopes, class_aliases, self_names, node, initial_aliases)
    for statement in (_setup_phase_body(node.body) if stop_at_yield else node.body):
        collector.visit(statement)
    return collector.aliases


class _MethodInstanceAliasCollector(ast.NodeVisitor):
    def __init__(
        self,
        scopes: list[_AliasMap],
        class_aliases: dict[tuple[str, ...], tuple[str, ...]],
        self_names: set[str],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        initial_aliases: _AliasMap | None = None,
    ) -> None:
        self.self_names = self_names
        self.aliases: dict[tuple[str, ...], tuple[str, ...]] = {}
        self.local_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.local_helper_aliases: dict[str, str] = {}
        self.active_helpers: set[str] = set()
        local_scope: _AliasMap = {(name,): None for name in _function_bound_names(node)}
        for self_name in self_names:
            for path, source in class_aliases.items():
                local_scope[(self_name, *path)] = source
        if initial_aliases:
            local_scope.update(initial_aliases)
        self.scopes = [*scopes, local_scope]

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_helper_aliases(node.targets, node.value)
        self._record_instance_aliases(node.targets, node.value)
        _add_assignment_aliases(self.scopes, lambda _: self.scope, node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        self._record_instance_aliases([node.target], node.value)
        _add_assignment_aliases(self.scopes, lambda _: self.scope, [node.target], node.value)

    def visit_If(self, node: ast.If) -> None:
        if _is_static_false(node.test) or _is_type_checking_name(node.test, self.scopes):
            for statement in node.orelse:
                self.visit(statement)
            return
        if _is_static_true(node.test):
            for statement in node.body:
                self.visit(statement)
            return
        self.visit(node.test)
        self._visit_unknown_branch(node.body)
        self._visit_unknown_branch(node.orelse)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.local_helpers[node.name] = node
        _set_alias(self.scope, (node.name,), (node.name,))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.local_helpers[node.name] = node
        _set_alias(self.scope, (node.name,), (node.name,))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        del node

    def visit_Lambda(self, node: ast.Lambda) -> None:
        del node

    def visit_Call(self, node: ast.Call) -> None:
        self._record_setattr_instance_alias(node)
        _record_setattr_alias(self.scopes, lambda _: self.scope, node)
        helper_name = self._local_helper_alias_name(_raw_called_name(node))
        if helper_name is None:
            helper_name = self._local_helper_name(_called_name(node, self.scopes))
        if helper_name is None or helper_name not in self.local_helpers or helper_name in self.active_helpers:
            self.generic_visit(node)
            return
        helper = self.local_helpers[helper_name]
        bindings = _call_argument_bindings(helper, node)
        if bindings is None:
            self.generic_visit(node)
            return
        call_scope = _function_call_scope(helper, bindings, self.scopes)
        helper_self_names = self._helper_self_names(bindings)
        self.active_helpers.add(helper_name)
        original_self_names = self.self_names
        self.self_names = self.self_names | helper_self_names
        self.scopes.append(call_scope)
        try:
            for statement in helper.body:
                self.visit(statement)
        finally:
            self.scopes.pop()
            self.self_names = original_self_names
            self.active_helpers.remove(helper_name)

    def _record_setattr_instance_alias(self, node: ast.Call) -> None:
        targets_and_value = _setattr_targets_and_value(node)
        if targets_and_value is None:
            return
        target_paths, value = targets_and_value
        for target_path in target_paths:
            if len(target_path) <= 1 or target_path[0] not in self.self_names:
                continue
            instance_path = target_path[1:]
            source = _alias_source(value, self.scopes)
            if source in _ALIASABLE_CLOCK_PATHS:
                self.aliases[instance_path] = source
            else:
                self.aliases.pop(instance_path, None)

    def _record_instance_aliases(self, targets: list[ast.expr], value: ast.expr) -> None:
        if len(targets) == 1 and isinstance(targets[0], ast.Tuple | ast.List) and isinstance(value, ast.Tuple | ast.List):
            for target, element in zip(targets[0].elts, value.elts, strict=False):
                self._record_instance_aliases([target], element)
            return

        source = _alias_source(value, self.scopes)
        for target in targets:
            target_path = _attribute_path(target)
            if len(target_path) <= 1 or target_path[0] not in self.self_names:
                continue
            instance_path = target_path[1:]
            if source in _ALIASABLE_CLOCK_PATHS:
                self.aliases[instance_path] = source
            else:
                self.aliases.pop(instance_path, None)

    def _record_helper_aliases(self, targets: list[ast.expr], value: ast.expr) -> None:
        source = _attribute_path(value)
        helper_name = source[0] if len(source) == 1 and source[0] in self.local_helpers else None
        for target in targets:
            target_path = _attribute_path(target)
            if len(target_path) == 1:
                if helper_name is None:
                    self.local_helper_aliases.pop(target_path[0], None)
                else:
                    self.local_helper_aliases[target_path[0]] = helper_name

    def _local_helper_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        return self.local_helper_aliases.get(name, name)

    def _local_helper_alias_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        return self.local_helper_aliases.get(name)

    def _visit_unknown_branch(self, statements: list[ast.stmt]) -> None:
        branch_scope: _AliasMap = {}
        self.scopes.append(branch_scope)
        for statement in statements:
            self.visit(statement)
        self.scopes.pop()
        _merge_clock_aliases(self.scope, branch_scope)

    def _helper_self_names(
        self,
        bindings: dict[str, ast.expr],
    ) -> set[str]:
        helper_self_names: set[str] = set()
        self_paths = {(name,) for name in self.self_names}
        for helper_arg, call_arg in bindings.items():
            if _attribute_path(call_arg) in self_paths:
                helper_self_names.add(helper_arg)
        return helper_self_names


class _FunctionBindingVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        del node

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            _add_bound_target_names(target, self.names)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        _add_bound_target_names(node.target, self.names)
        if node.value is not None:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        _add_bound_target_names(node.target, self.names)
        self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        self._visit_for(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with(node)

    def _visit_for(self, node: ast.For | ast.AsyncFor) -> None:
        _add_bound_target_names(node.target, self.names)
        self.visit(node.iter)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                _add_bound_target_names(item.optional_vars, self.names)
        for statement in node.body:
            self.visit(statement)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        _add_bound_target_names(node.target, self.names)
        self.visit(node.value)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.names.add(node.name)
        for statement in node.body:
            self.visit(statement)


def _argument_names(arguments: ast.arguments) -> set[str]:
    names = {
        arg.arg
        for arg in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _add_bound_target_names(target: ast.expr, names: set[str]) -> None:
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            _add_bound_target_names(element, names)


def _assignment_target_paths(target: ast.expr) -> list[tuple[str, ...]]:
    if isinstance(target, ast.Tuple | ast.List):
        paths: list[tuple[str, ...]] = []
        for element in target.elts:
            paths.extend(_assignment_target_paths(element))
        return paths
    target_path = _attribute_path(target)
    if target_path:
        return [target_path]
    return []


def _called_name(node: ast.Call, scopes: list[_AliasMap]) -> str | None:
    path = _normalize_alias(_attribute_path(node.func), scopes)
    if path == _SHADOWED_PATH:
        return None
    if len(path) == 1:
        return path[0]
    return None


def _raw_called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.NamedExpr):
        target_path = _attribute_path(current.target)
        if target_path:
            return target_path + tuple(reversed(parts))
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))
    return tuple(reversed(parts))


# ---------------------------------------------------------------------------
# Whole-module call-ban entry point (mission kernel-clock-single-door, WP01b,
# FR-012(b) / SC-001 / C-008).
#
# This is a NEW, independent entry point -- it does NOT widen
# ``find_wall_clock_assertion_violations`` above (which stays assert-scoped,
# used by the conftest collection-time gate and its own 124-test support
# suite). Widening that visitor to flag every banned call anywhere in a
# module would turn the legitimate freshness-bounds idiom
# ``before = datetime.now(UTC)`` / ``after = datetime.now(UTC)`` (bounds
# captured OUTSIDE an assert, then compared inside one) into a false
# positive and red-flag ``tests/_support/test_wall_clock_assertions.py``.
#
# Deliberately independent of ``_WallClockAssertionVisitor``'s pytest
# fixture/parametrize/autouse-propagation machinery: that machinery exists
# to resolve what a pytest *assertion* aliases to, given fixtures injected
# by the test framework -- none of that applies to scanning arbitrary
# production/test module bodies for banned calls. This visitor instead
# reuses only the shared, stateless primitives (``_BANNED_CALLS``,
# ``_ALIASABLE_CLOCK_PATHS``, ``_set_alias``/``_set_shadow``,
# ``_normalize_alias``, ``_attribute_path``, ``_add_assignment_aliases``,
# ``_function_bound_names``/``_function_default_aliases``,
# ``_add_star_import_aliases``) with a plain lexical-scope stack (module +
# one nested scope per function/class body).
#
# HONEST LIMITS (disclosed, not silently patched over):
#   * Cross-statement receiver binding is resolved only within a function's
#     (or the module's) own local alias map -- an alias assigned in one
#     function is invisible in another, and comprehension/lambda-local
#     targets are not separately scoped (they fall through to the enclosing
#     scope). This mirrors ordinary Python scoping closely enough for real
#     call-site shapes; it does not attempt full closure/global resolution.
#   * ``getattr(kernel.clock, "datetime").now()`` yields no attribute chain
#     for ``_attribute_path`` to walk (the receiver is a ``Call`` node, not
#     an ``Attribute``/``Name`` chain) and is an accepted, disclosed
#     residual -- contrived, and it carries no ``datetime`` import for the
#     import-ban to catch either.
#
# THE CRITICAL FIX (plan Sec 1.3): resolving the door re-export
# (``from kernel.clock import datetime; datetime.now()``) requires knowing
# the door module's own dotted name as it would appear in an importer's
# ``from <name> import ...`` statement. Deriving that name via a single
# ``os.path.commonpath`` over a scan spanning ``src/`` + ``tests/`` +
# ``scripts/`` (as ``_collect_import_aliases`` above does for the
# assert-gate, which only ever scans one test tree) collapses the door's
# path to ``src.kernel.clock`` -- a string no real ``from kernel.clock
# import ...`` statement's module name ever equals, silently defeating the
# re-export resolution. ``anchored_module_name`` instead anchors ``src/**``
# at ``src/`` (so ``src/kernel/clock.py`` resolves to ``kernel.clock``)
# before falling back to the repository root for anything else
# (``tests/**``, ``scripts/**``).
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
DOOR_FILE = SRC_ROOT / "kernel" / "clock.py"


def anchored_module_name(path: Path) -> str | None:
    """Resolve ``path``'s dotted module name, anchored at its own source root.

    Tries the ``src/`` anchor first (so anything under ``src/`` resolves
    relative to ``src/``, never to a wider root that would also cover
    ``tests/``/``scripts/``), then falls back to the repository root. Returns
    ``None`` for a path outside both anchors (e.g. package ``__init__``
    resolving to an empty name).
    """
    resolved = path.resolve()
    for anchor in (SRC_ROOT, REPO_ROOT):
        try:
            relative = resolved.with_suffix("").relative_to(anchor)
        except ValueError:
            continue
        parts = relative.parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else None
    return None


def door_module_name() -> str:
    """The single door's own dotted module name (``kernel.clock``)."""
    name = anchored_module_name(DOOR_FILE)
    if name is None:
        raise RuntimeError(f"the kernel.clock door file is not resolvable under {SRC_ROOT} or {REPO_ROOT}")
    return name


@functools.lru_cache(maxsize=1)
def _door_exports() -> _AliasMap:
    """The clock-aliasable names ``kernel.clock`` re-exports (e.g. ``datetime``, ``date``).

    Parses the REAL, already-landed ``src/kernel/clock.py`` (WP01a), reading
    ONLY its top-level ``Import``/``ImportFrom`` statements -- deliberately
    NOT ``_WallClockAssertionVisitor`` (tried first; reverted): that visitor's
    function-return-alias propagation (designed so an assert on a *helper
    function* wrapping a wall-clock read is still flagged) walks
    ``now_utc_iso``'s body, sees its ``datetime.now(UTC).isoformat()``
    return expression, and records ``now_utc_iso`` ITSELF as an alias for
    the banned ``datetime.now()`` call -- exactly backwards for a producer
    that is supposed to be safe to call anywhere. A door export, for this
    engine's purposes, is exactly its own module-level import statements;
    the door's helper FUNCTIONS (``now_utc_iso``, and later producers) are
    never aliased here, only its re-exported stdlib names.

    Keeps only the exports whose source is itself a clock-callable path
    (``_ALIASABLE_CLOCK_PATHS``/``_BANNED_CALLS``) -- a door re-export of a
    non-clock-callable name (e.g. ``UTC``, ``timedelta``) is correctly
    dropped: re-exporting a type never creates a sanctioned ``.now()`` path.
    """
    tree = ast.parse(DOOR_FILE.read_text(encoding="utf-8"), filename=str(DOOR_FILE))
    exports: _AliasMap = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"datetime", "time"}:
            for alias in node.names:
                if alias.name == "*":
                    continue
                source = (node.module, alias.name)
                if source in _ALIASABLE_CLOCK_PATHS or source in _BANNED_CALLS:
                    exports[(alias.asname or alias.name,)] = source
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = tuple(alias.name.split("."))
                if parts in _ALIASABLE_CLOCK_PATHS or parts in _BANNED_CALLS:
                    exports[(alias.asname or parts[0],)] = parts
    return exports


@dataclass(frozen=True, order=True)
class WallClockCallViolation:
    """One banned wall-clock call site found by :func:`find_wall_clock_call_violations`.

    Carries no ``path`` -- the caller already knows which file it parsed
    ``tree`` from (mirrors the ``(tree, module_name)`` signature: this
    function is a pure AST-in, violations-out engine; filesystem walking and
    path bookkeeping are the caller's concern, same division of labour as
    ``test_kernel_no_doctrine_import.py``'s own ``_scan_file``).

    ``suggestion`` is the SC-001 message-mapping guidance (WP15): the
    ``kernel.clock`` producer this call site should migrate to. Computed by
    :func:`_suggested_producer` from the banned call's canonical family
    (``.now``/``.utcnow`` vs ``date.today`` vs ``time.time()``) plus, for the
    ``.now``/``.utcnow`` family, the immediately-chained
    ``.isoformat()``/``.strftime(<literal>)`` call the flagged call feeds
    into, when one is present at the call site.
    """

    line: int
    call: str
    suggestion: str


def find_wall_clock_call_violations(tree: ast.AST, module_name: str) -> list[WallClockCallViolation]:
    """Find every banned wall-clock call (``.now``/``.utcnow``/``.today``/``time.time()``) in ``tree``.

    Unlike :func:`find_wall_clock_assertion_violations`, this walks the
    WHOLE module -- not just ``assert`` expressions -- and resolves the
    door's re-exported ``datetime``/``date`` names as aliases of the real
    stdlib types (the re-export-bypass form FR-012(b)/SC-001 requires this
    gate to catch).

    ``module_name`` must be the caller's own :func:`anchored_module_name`
    result for the file ``tree`` was parsed from. When it equals
    :func:`door_module_name`, this returns ``[]`` unconditionally: the door
    itself is the one sanctioned holder of these calls (see
    ``src/kernel/clock.py``'s ``now_utc_iso``), and it is scanned by the
    caller like any other file -- the self-exemption lives here, in the
    shared engine, rather than being left to every caller to remember.
    """
    if module_name == door_module_name():
        return []
    visitor = _WholeModuleClockVisitor()
    visitor.visit(tree)
    return sorted(visitor.violations)


#: SC-001 message-mapping (WP15): canonical banned-call family -> suggested
#: kernel.clock producer. Keyed on the CANONICAL (alias-resolved) path, not
#: the as-written receiver text, so ``dt.time()``/``time.time()`` and
#: ``d.now()``/``datetime.now()`` map identically regardless of aliasing.
_EPOCH_CALL: tuple[str, ...] = ("time", "time")
_DATE_TODAY_CALLS: frozenset[tuple[str, ...]] = frozenset({("date", "today"), ("datetime", "date", "today")})
_NOW_FAMILY_CALLS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("datetime", "now"),
        ("datetime", "datetime", "now"),
        ("datetime", "utcnow"),
        ("datetime", "datetime", "utcnow"),
    }
)
_EPOCH_SUGGESTION = "kernel.clock.now_epoch()"
_DATE_TODAY_SUGGESTION = "kernel.clock.now_utc().date() (or an adjudicated naive-local fix per FR-011)"
_GENERIC_NOW_SUGGESTION = (
    "kernel.clock.now_utc() (or now_utc_iso()/now_utc_stamp()/"
    "now_utc_compact_stamp()/now_utc_seconds() for a specific serialization contract)"
)
_UNKNOWN_CALL_SUGGESTION = "the matching kernel.clock producer"

#: The two on-disk stamp contracts the door's producers own (C-003); a
#: ``.strftime(<literal>)`` chained directly onto the flagged call is only
#: mapped when the literal matches one of these EXACTLY -- any other format
#: string falls back to :data:`_GENERIC_NOW_SUGGESTION` rather than guessing.
_STRFTIME_PRODUCER_SUGGESTIONS: dict[str, str] = {
    "%Y-%m-%dT%H:%M:%SZ": "kernel.clock.now_utc_stamp()",
    "%Y%m%dT%H%M%SZ": "kernel.clock.now_utc_compact_stamp()",
}


def _isoformat_producer_suggestion(outer_call: ast.Call) -> str:
    """``.now(...).isoformat(timespec="seconds")`` -> ``now_utc_seconds()``; else ``now_utc_iso()``."""
    for keyword in outer_call.keywords:
        if keyword.arg == "timespec" and isinstance(keyword.value, ast.Constant) and keyword.value.value == "seconds":
            return "kernel.clock.now_utc_seconds()"
    return "kernel.clock.now_utc_iso()"


def _strftime_producer_suggestion(outer_call: ast.Call) -> str | None:
    """``.now(...).strftime(<literal format>)`` -> the matching stamp producer, if the format is recognized."""
    if not outer_call.args:
        return None
    fmt_arg = outer_call.args[0]
    if isinstance(fmt_arg, ast.Constant) and isinstance(fmt_arg.value, str):
        return _STRFTIME_PRODUCER_SUGGESTIONS.get(fmt_arg.value)
    return None


class _WholeModuleClockVisitor(ast.NodeVisitor):
    """Whole-module banned-call scanner. See the module-level engine docstring above."""

    def __init__(self) -> None:
        self.scopes: list[_AliasMap] = [{}]
        self.violations: list[WallClockCallViolation] = []
        #: Ancestor stack (root-to-current), maintained by the overridden
        #: :meth:`visit` below -- exists ONLY so :meth:`_chained_attribute_call`
        #: can look one/two levels up from a flagged call to detect an
        #: immediately-chained ``.isoformat()``/``.strftime(...)`` for the
        #: SC-001 message-mapping suggestion. Nothing else in this visitor
        #: reads it.
        self._parent_stack: list[ast.AST] = []

    @property
    def scope(self) -> _AliasMap:
        return self.scopes[-1]

    def visit(self, node: ast.AST) -> None:
        self._parent_stack.append(node)
        try:
            super().visit(node)
        finally:
            self._parent_stack.pop()

    def _chained_attribute_call(self, call_node: ast.Call) -> tuple[str, ast.Call] | None:
        """If ``call_node`` is immediately followed by ``.<attr>(...)``, return ``(attr, outer_call)``."""
        stack = self._parent_stack
        if len(stack) < 3 or stack[-1] is not call_node:
            return None
        parent, grandparent = stack[-2], stack[-3]
        if (
            isinstance(parent, ast.Attribute)
            and parent.value is call_node
            and isinstance(grandparent, ast.Call)
            and grandparent.func is parent
        ):
            return parent.attr, grandparent
        return None

    def _suggested_producer(self, call_node: ast.Call, canonical: tuple[str, ...]) -> str:
        """SC-001 message mapping: the kernel.clock producer this violation should migrate to."""
        if canonical == _EPOCH_CALL:
            return _EPOCH_SUGGESTION
        if canonical in _DATE_TODAY_CALLS:
            return _DATE_TODAY_SUGGESTION
        if canonical in _NOW_FAMILY_CALLS:
            chained = self._chained_attribute_call(call_node)
            if chained is not None:
                attr_name, outer_call = chained
                if attr_name == "isoformat":
                    return _isoformat_producer_suggestion(outer_call)
                if attr_name == "strftime":
                    stamp_suggestion = _strftime_producer_suggestion(outer_call)
                    if stamp_suggestion is not None:
                        return stamp_suggestion
            return _GENERIC_NOW_SUGGESTION
        return _UNKNOWN_CALL_SUGGESTION

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            parts = tuple(alias.name.split("."))
            dotted = ".".join(parts)
            target_path = (alias.asname,) if alias.asname else parts
            if dotted == door_module_name():
                self._bind_door_export(target_path)
            elif parts and parts[0] in {"datetime", "time"}:
                _set_alias(self.scope, (alias.asname or parts[0],), parts)
            else:
                _set_shadow(self.scope, (alias.asname or parts[0],))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == door_module_name():
            self._bind_from_door_import(node.names)
            return
        if node.module not in {"datetime", "time"}:
            for alias in node.names:
                if alias.name == "*":
                    _set_shadow(self.scope, ("datetime",))
                    _set_shadow(self.scope, ("time",))
                else:
                    _set_shadow(self.scope, (alias.asname or alias.name,))
            return
        for alias in node.names:
            if alias.name == "*":
                _add_star_import_aliases(self.scope, node.module)
                continue
            _set_alias(self.scope, (alias.asname or alias.name,), (node.module, alias.name))

    def _bind_door_export(self, target_path: tuple[str, ...]) -> None:
        _set_shadow(self.scope, target_path)
        for export_path, export_source in _door_exports().items():
            if export_source is not None:
                _set_alias(self.scope, (*target_path, *export_path), export_source)

    def _bind_from_door_import(self, aliases: list[ast.alias]) -> None:
        exports = _door_exports()
        for alias in aliases:
            if alias.name == "*":
                for export_path, source in exports.items():
                    if source is not None:
                        _set_alias(self.scope, export_path, source)
                continue
            target_name = alias.asname or alias.name
            source = exports.get((alias.name,))
            if source is not None:
                _set_alias(self.scope, (target_name,), source)
            else:
                _set_shadow(self.scope, (target_name,))

    def visit_Assign(self, node: ast.Assign) -> None:
        _add_assignment_aliases(self.scopes, lambda _target: self.scope, node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            _add_assignment_aliases(self.scopes, lambda _target: self.scope, [node.target], node.value)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        _add_assignment_aliases(self.scopes, lambda _target: self.scope, [node.target], node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        raw_path = _attribute_path(node.func)
        canonical = _normalize_alias(raw_path, self.scopes) if raw_path else ()
        if raw_path and canonical in _BANNED_CALLS:
            # Mirrors `_AssertCallVisitor.visit_Call` above: `_BANNED_CALLS`
            # membership (via the normalized/alias-resolved path) is the
            # ban CHECK, but the reported `call` text is the literal,
            # as-written receiver -- e.g. `d.now()` for the variable-split
            # form, not the canonical `datetime.now()` it resolves to. This
            # is what makes the violation message greppable against the
            # actual source line. `suggestion` (SC-001) is keyed on the
            # CANONICAL path instead, so an aliased/variable-split call still
            # gets the correct producer recommendation.
            self.violations.append(
                WallClockCallViolation(
                    line=node.lineno,
                    call=f"{'.'.join(raw_path)}()",
                    suggestion=self._suggested_producer(node, canonical),
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_like(node)

    def _visit_function_like(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
            self.visit(default)
        local_scope: _AliasMap = {(name,): None for name in _function_bound_names(node)}
        local_scope.update(_function_default_aliases(node, self.scopes))
        self.scopes.append(local_scope)
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        self.scopes.append({})
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.scopes.pop()
