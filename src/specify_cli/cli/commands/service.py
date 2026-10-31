"""``spec-kitty service``: fetch, vendor, inspect and stop the pinned service binaries (#6590).

The operator surface of ``kitty-specs/pinned-service-binaries-01M64N66/contracts/cli-surface.md``:

* ``fetch`` -- fetch and verify the host build of each pinned service in scope (the jar when
  the host has no native build) into the cache (FR-010). ``--all`` means every pinned service
  the CLI launches (ADR 2026-10-29-1 D-6: the read service is pinned for CI conformance only,
  so it is fetched only when named with ``--service``). Exit 0, or 1 on a refusal.
* ``vendor`` -- the only path that rewrites ``pins/<service>.source.yaml`` (FR-013), through
  :mod:`specify_cli.services.vendor`; ``--check`` verifies the lockfile instead. Exit 0, 1 on a
  refusal, 2 on a usage error. A bump writes only the ``pins/`` of the spec-kitty source
  checkout this CLI runs from, and only when invoked inside it; anywhere else it is a usage error.
* ``status`` -- the pin, the cache state of each pinned asset and the running instance. It only
  reads: it never starts a service, never writes and never evicts (a cached copy that does not
  verify is reported ``corrupt`` and left in place, like ``make sync-services --check``). Exit 0.
* ``stop`` -- stop this clone's instance (FR-009) through :class:`ServiceLauncher`. Exit 0 when
  it stopped or none was running, 1 on a refusal or an instance that could not be confirmed.

``--service`` defaults to ``write-service``. The pin is always the CLI's own
(:func:`specify_cli.services.resolution.pins_dir`), never one in the user's project. No output
ever carries the endpoint token.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from kernel.git_topology import GitTopologyError, NotAGitRepositoryError, git_common_dir
from kernel.service_artifacts import ASSET_DIR_ENV, ServiceArtifactError, cached_path, default_cache_root, fetch_asset, verify_asset
from kernel.service_hosts import host_target, select_build
from kernel.service_pin import KNOWN_SERVICES, PINS_DIR, ServiceAsset, ServicePin, ServiceTarget
from specify_cli.core.paths import locate_project_root
from specify_cli.services import ServiceRefusal, find_pin, resolution
from specify_cli.services.client import ServiceClient, ServiceUnreachable
from specify_cli.services.launcher import ServiceLauncher, StopOutcome
from specify_cli.services.policies import policy_for
from specify_cli.services.vendor import VENDOR_COMMIT_REQUIRED, VENDOR_USAGE, VendorError, check_pin, vendor_pin
from specify_cli.status import EndpointFileError, EndpointRefusalCode, endpoint_file_path, read_endpoint_file, repository_id
from specify_cli.version_utils import get_version

app = typer.Typer(name="service", help="Fetch, vendor, inspect and stop the pinned service binaries.", no_args_is_help=True)

DEFAULT_SERVICE = "write-service"
NO_PIN_MESSAGE = "No service is pinned in this spec-kitty version yet."
_DIGEST_PREFIX = 12
_USAGE_EXIT = 2
_REFUSAL_EXIT = 1
#: Vendor refusals that are about the invocation, not the release: exit 2.
_VENDOR_USAGE_CODES = frozenset({VENDOR_USAGE, VENDOR_COMMIT_REQUIRED})
_SERVICE_HELP = f"The service: one of {', '.join(sorted(KNOWN_SERVICES))}."
_JSON_HELP = "Print JSON."
_VERIFIED = "verified"
_MISSING = "missing"
_CORRUPT = "corrupt"
_HEALTHY = "healthy"
_STALE = "stale"
_ABSENT = "absent"

ServiceOption = Annotated[str, typer.Option("--service", help=_SERVICE_HELP)]
JsonOption = Annotated[bool, typer.Option("--json", help=_JSON_HELP)]


def _repo_root() -> Path:
    """The project the command runs for: the spec-kitty project root, else the working directory."""
    return locate_project_root() or Path.cwd()


def _usage(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(_USAGE_EXIT)


def _check_service(service: str) -> None:
    if service not in KNOWN_SERVICES:
        raise _usage(f"unknown --service {service!r}; {_SERVICE_HELP}")


def _emit_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _refuse(refusal: ServiceRefusal, *, as_json: bool) -> typer.Exit:
    """Print *refusal* (message, remedy and code) and return the exit to raise."""
    if as_json:
        _emit_json({"error": refusal.to_dict()})
    else:
        typer.echo(str(refusal), err=True)
    return typer.Exit(_REFUSAL_EXIT)


def _pinned(services: Sequence[str]) -> list[tuple[str, Path]]:
    """``(service, lockfile)`` for each service in *services* that this spec-kitty version pins."""
    found = [(service, find_pin(service)) for service in services]
    return [(service, path) for service, path in found if path is not None]


def _load(path: Path) -> ServicePin:
    pin: ServicePin = resolution.load_pin(path)
    return pin


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #


def _fetch_target(pin: ServicePin) -> tuple[ServiceTarget, ServiceAsset]:
    """The host's native build, else the jar (``kernel.service_hosts.select_build``); otherwise resolution's refusal."""
    build = select_build(pin, host_target())
    if build is None:
        raise resolution.no_build_refusal(pin)
    return build.target, build.asset


def _artifact_refusal(pin: ServicePin, asset: ServiceAsset, exc: ServiceArtifactError) -> ServiceRefusal:
    configured = os.environ.get(ASSET_DIR_ENV)
    return resolution.artifact_refusal(pin, asset, exc, cache_root=default_cache_root(), asset_dir=Path(configured) if configured else None)


def _fetch_one(path: Path, offline: bool) -> dict[str, Any]:
    pin = _load(path)
    target, asset = _fetch_target(pin)
    try:
        fetched = fetch_asset(pin, asset, offline=offline)
    except ServiceArtifactError as exc:
        raise _artifact_refusal(pin, asset, exc) from exc
    return {
        "service": pin.service,
        "tag": pin.tag,
        "commit": pin.commit,
        "assets": [{"target": target.value, "name": asset.name, "state": _VERIFIED, "path": str(fetched), "sha256": asset.sha256}],
    }


def _print_fetched(entry: dict[str, Any]) -> None:
    for asset in entry["assets"]:
        typer.echo(f"{entry['service']} {entry['tag']} {asset['target']}: {asset['path']} (sha256 {asset['sha256'][:_DIGEST_PREFIX]})")


@app.command()
def fetch(
    service: ServiceOption = DEFAULT_SERVICE,
    all_services: Annotated[bool, typer.Option("--all", help="Every pinned service this CLI launches (the CI-only read service only with --service).")] = False,
    offline: Annotated[bool, typer.Option("--offline", help="Never download: use the cache or SPEC_KITTY_SERVICE_ASSET_DIR only.")] = False,
    as_json: JsonOption = False,
) -> None:
    """Fetch and verify the pinned build of a service for this host into the cache."""
    _check_service(service)
    services = sorted(name for name in KNOWN_SERVICES if policy_for(name).launchable) if all_services else [service]
    pinned = _pinned(services)
    if not pinned:
        _no_pin(as_json)
        return
    try:
        entries = [_fetch_one(path, offline) for _, path in pinned]
    except ServiceRefusal as refusal:
        raise _refuse(refusal, as_json=as_json) from None
    if as_json:
        _emit_json({"services": entries})
        return
    for entry in entries:
        _print_fetched(entry)


def _no_pin(as_json: bool) -> None:
    if as_json:
        _emit_json({"services": [], "message": NO_PIN_MESSAGE})
    else:
        typer.echo(NO_PIN_MESSAGE)


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def _cache_state(pin: ServicePin, asset: ServiceAsset) -> str:
    """``verified``, ``missing`` or ``corrupt``, by reading only: a copy that does not verify is reported, never evicted."""
    path = cached_path(pin, asset, default_cache_root())
    if verify_asset(path, asset):
        return _VERIFIED
    return _CORRUPT if path.is_symlink() or path.exists() else _MISSING


def _asset_states(pin: ServicePin) -> list[dict[str, str]]:
    rows = [(target.value, asset) for target, asset in sorted(pin.assets.items(), key=lambda item: item[0].value)]
    rows += sorted(pin.extras.items())
    return [{"target": target, "name": asset.name, "state": _cache_state(pin, asset)} for target, asset in rows]


@dataclass(frozen=True)
class InstanceState:
    """The running instance as ``status`` sees it; never carries the token."""

    state: str
    instance_id: str | None = None
    port: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {"state": self.state, "instance_id": self.instance_id, "port": self.port}


def instance_state(service: str, repo_root: Path) -> InstanceState:
    """Read the endpoint file and ask one handshake; starts nothing.

    ``healthy`` when the published instance answers as itself for this clone, ``stale`` when a
    file is published but nothing (or something else) answers, ``absent`` otherwise.
    """
    if not policy_for(service).launchable:
        return InstanceState(_ABSENT)
    try:
        git_common = git_common_dir(repo_root)
        endpoint = read_endpoint_file(endpoint_file_path(git_common))
    except GitTopologyError:
        return InstanceState(_ABSENT)
    except EndpointFileError as exc:
        return InstanceState(_ABSENT if exc.error_code == EndpointRefusalCode.MISSING.value else _STALE)
    try:
        handshake = ServiceClient(endpoint).handshake()
    except ServiceUnreachable:
        return InstanceState(_STALE, endpoint.instance_id, endpoint.port)
    healthy = handshake.instance_id == endpoint.instance_id and handshake.repository_id == repository_id(git_common)
    return InstanceState(_HEALTHY if healthy else _STALE, endpoint.instance_id, endpoint.port)


def _status_entry(path: Path, repo_root: Path) -> dict[str, Any]:
    pin = _load(path)
    return {
        "service": pin.service,
        "tag": pin.tag,
        "commit": pin.commit,
        "assets": _asset_states(pin),
        "instance": instance_state(pin.service, repo_root).to_dict(),
    }


def _print_status(entry: dict[str, Any]) -> None:
    typer.echo(f"{entry['service']}: {entry['tag']} ({entry['commit'][:_DIGEST_PREFIX]})")
    for asset in entry["assets"]:
        typer.echo(f"  {asset['target']}: {asset['state']} ({asset['name']})")
    instance = entry["instance"]
    detail = f" (instance {instance['instance_id']}, port {instance['port']})" if instance["instance_id"] else ""
    typer.echo(f"  instance: {instance['state']}{detail}")


@app.command()
def status(service: ServiceOption = DEFAULT_SERVICE, as_json: JsonOption = False) -> None:
    """Show the pin, the cache state and the running instance of a service (reads only: starts, writes and evicts nothing)."""
    _check_service(service)
    repo_root = _repo_root()
    pinned = _pinned([service])
    if not pinned:
        _no_pin(as_json)
        return
    try:
        entries = [_status_entry(path, repo_root) for _, path in pinned]
    except ServiceRefusal as refusal:
        # status exits 0 (it reports); an invalid pin is reported, not refused.
        _refuse(refusal, as_json=as_json)
        return
    if as_json:
        _emit_json({"services": entries})
        return
    for entry in entries:
        _print_status(entry)


# --------------------------------------------------------------------------- #
# stop
# --------------------------------------------------------------------------- #


_STOP_WORDS = {StopOutcome.STOPPED: "stopped", StopOutcome.NOT_RUNNING: "not running", StopOutcome.FORCED: "forced"}


@app.command()
def stop(service: ServiceOption = DEFAULT_SERVICE) -> None:
    """Stop this clone's running instance of a service."""
    _check_service(service)
    if not policy_for(service).launchable:
        typer.echo(f"not running: the CLI never launches {service}")
        return
    warnings: list[str] = []
    try:
        outcome = ServiceLauncher(warn=warnings.append).stop(service, _repo_root())
    except NotAGitRepositoryError as exc:
        typer.echo(f"cannot stop {service}: {exc.path} is not inside a git repository", err=True)
        raise typer.Exit(_REFUSAL_EXIT) from None
    except GitTopologyError as exc:
        typer.echo(f"cannot stop {service}: {exc}", err=True)
        raise typer.Exit(_REFUSAL_EXIT) from None
    except EndpointFileError as exc:
        typer.echo(f"{exc}\nError code: {exc.error_code}.", err=True)
        raise typer.Exit(_REFUSAL_EXIT) from None
    if outcome is StopOutcome.UNCONFIRMED:
        typer.echo("unconfirmed: " + " ".join(warnings), err=True)
        raise typer.Exit(_REFUSAL_EXIT)
    typer.echo(_STOP_WORDS[outcome])


# --------------------------------------------------------------------------- #
# vendor
# --------------------------------------------------------------------------- #


def _protocol_versions(raw: str) -> tuple[int, ...]:
    try:
        versions = tuple(int(part) for part in raw.split(",") if part.strip())
    except ValueError:
        raise _usage(f"--protocol-versions must be comma-separated positive integers; got {raw!r}") from None
    if not versions or any(version < 1 for version in versions):
        raise _usage(f"--protocol-versions must be comma-separated positive integers; got {raw!r}")
    return versions


_VENDOR_REMEDY = "run `spec-kitty service vendor` from inside a spec-kitty/spec-kitty clone whose editable install this CLI is (`uv run spec-kitty ...` there)"


def _vendor_usage(why: str) -> typer.Exit:
    return _usage(f"{why}\nRemedy: {_VENDOR_REMEDY}.\nError code: {VENDOR_USAGE}.")


def _vendor_pins_dir() -> Path:
    """The ``pins/`` a bump may rewrite: the CLI's own source checkout's, and only when run inside it."""
    checkout: Path | None = resolution.source_checkout_root()
    if checkout is None:
        raise _vendor_usage("`service vendor` rewrites the pins of the spec-kitty source checkout it runs from, and this CLI is an installed package")
    if not Path.cwd().resolve().is_relative_to(checkout):
        raise _vendor_usage(f"`service vendor` rewrites only {checkout / PINS_DIR}, the pins of the source checkout this CLI runs from; run it inside {checkout}")
    return checkout / PINS_DIR


def _vendor_check(service: str, offline: bool) -> None:
    directory = resolution.pins_dir()
    if directory is None:
        typer.echo(f"{PINS_DIR}/{service}.source.yaml: this spec-kitty carries no pins directory", err=True)
        raise typer.Exit(_REFUSAL_EXIT)
    problems = check_pin(pins_dir=directory, service=service, online=not offline)
    if problems:
        for problem in problems:
            typer.echo(f"{PINS_DIR}/{service}.source.yaml: {problem}", err=True)
        raise typer.Exit(_REFUSAL_EXIT)
    typer.echo(f"{PINS_DIR}/{service}.source.yaml is sound{' (shape only, offline)' if offline else ''}.")


def _check_vendor_usage(check: bool, offline: bool, bump_options: Sequence[object]) -> None:
    if check and any(option is not None for option in bump_options):
        raise _usage("--check verifies the lockfile only; it cannot be combined with --tag, --repository, --commit, --protocol-versions or --asset-prefix.")
    if offline and not check:
        raise _usage("--offline applies to --check only; a bump needs the release.")


@app.command()
def vendor(
    service: ServiceOption = DEFAULT_SERVICE,
    tag: Annotated[str | None, typer.Option("--tag", help="The spec-kitty-events release tag to pin (service-vX.Y.Z).")] = None,
    repository: Annotated[
        str | None,
        typer.Option("--repository", help="The release repository (https:// or file://); default: the current pin's, else spec-kitty-events."),
    ] = None,
    commit: Annotated[
        str | None,
        typer.Option(
            "--commit",
            help="The commit the tag names. Required for a file:// repository (no git remote to ask); for https:// it must match the tag.",
        ),
    ] = None,
    protocol_versions: Annotated[
        str | None,
        typer.Option("--protocol-versions", help="Comma-separated protocol majors the build speaks (default 1); must match the release notes."),
    ] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Verify the lockfile instead of bumping it: shape rules, and online the release's SHA256SUMS. Writes nothing."),
    ] = False,
    offline: Annotated[bool, typer.Option("--offline", help="With --check: the shape rules only, no network.")] = False,
    asset_prefix: Annotated[
        str | None,
        typer.Option(
            "--asset-prefix",
            help="The release name prefix of this service's builds (<prefix>-<ver>-<target>, <prefix>-<ver>.jar); default: the service's known prefix.",
        ),
    ] = None,
) -> None:
    """Bump (or --check) pins/<service>.source.yaml from a spec-kitty-events release; the only way to change a pin."""
    _check_service(service)
    _check_vendor_usage(check, offline, (tag, repository, commit, protocol_versions, asset_prefix))
    if check:
        _vendor_check(service, offline)
        return
    if tag is None:
        raise _usage("pass --tag <service-vX.Y.Z> to bump the pin, or --check to verify it.")
    versions = _protocol_versions(protocol_versions or "1")
    pins_dir = _vendor_pins_dir()
    try:
        result = vendor_pin(
            pins_dir=pins_dir,
            service=service,
            tag=tag,
            repository=repository,
            commit=commit,
            protocol_versions=versions,
            asset_prefix_override=asset_prefix,
            core_version=get_version(),
        )
    except VendorError as exc:
        typer.echo(f"{exc.message}\nError code: {exc.code}.", err=True)
        raise typer.Exit(_USAGE_EXIT if exc.code in _VENDOR_USAGE_CODES else _REFUSAL_EXIT) from None
    pin = result.pin
    typer.echo(f"Pinned {PINS_DIR}/{service}.source.yaml to {pin.tag} ({pin.commit[:_DIGEST_PREFIX]}), {len(pin.assets)} build(s), {len(pin.extras)} extra(s).")
    if result.absent_targets:
        typer.echo(f"No build in this release for: {', '.join(target.value for target in result.absent_targets)}")
    if result.ignored:
        typer.echo(f"Ignored release files that are not pin assets: {', '.join(result.ignored)}")
