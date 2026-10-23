"""Migration: retire stale documentation/research template copies (#5280).

``src/specify_cli/missions/{documentation,research}/templates/`` are older forks
of the canonical ``packs/built-in/missions/<type>/templates/``. Two shipped
migrations still copy them into projects: ``0.12.0_documentation_mission``
(the whole documentation tree, pre-2.x projects only) and
``0.9.2_research_mission_templates`` (``research/templates/task-prompt-template.md``,
any project with a ``.kittify/missions/research/`` directory). A third,
``0.6.7_ensure_missions``, copies the whole research tree too, but cannot apply
today (its ``can_apply`` needs a packaged ``software-dev`` mission directory). The
``2.0.6_consistency_sweep`` of an older build then moved such a copy into
``.kittify/overrides/missions/<type>/templates/`` (#6548), where it outranks the
pack copy at resolution tier 1. (``runtime/migrate.py`` now compares a project
mission copy with the package mission, so the sweep and ``spec-kitty migrate``
no longer move it.) The shipped migrations stay byte-identical
(DIRECTIVE_044), so their fork sources stay frozen in place, migration-only
(operator ruling 2026-10-22); this migration repairs what they wrote.

**Proof.** A file is treated as a stale copy only when its bytes (CRLF folded to
LF) hash to a version that file ever had in a ``missions/<type>/templates/`` fork
in a released build (:data:`KNOWN_FORK_SHA256`, which includes the frozen
version the two migrations copy today). Only the 15 fork template names are examined; any other
file in those directories is never read. A file whose hash is not in the set is
treated as the operator's edit: it is kept and named in a warning. A file equal to
the current pack copy is already current and is left alone silently.

**Two trees, two outcomes** (operator rulings 2026-10-22):

* ``.kittify/overrides/missions/<type>/templates/`` -- a proven stale copy is
  **removed**. The override tier exists only for customisations; once the copy is
  gone the canonical tier (global runtime or the packs copy) resolves, and no new
  snapshot is written that could drift again.
* ``.kittify/missions/<type>/templates/`` -- a proven stale copy is **replaced**
  with the pack copy of the same name. This legacy project-mission directory is
  expected to be complete: removing ``research/templates/task-prompt-template.md``
  would re-arm ``0.9.2_research_mission_templates`` (a ``skipped`` record never
  settles it), which would copy the fork back on the next upgrade. A fork-only
  name (``plan-template.md`` / ``spec-template.md``; packs renamed them
  ``<type>-plan-template.md`` / ``<type>-spec-template.md``) has no pack copy, so
  a proven stale one is removed.

Every removal goes through ``guard_destructive_removal`` and every replacement
through ``guard_destructive_overwrite``, each with the hash prover. No directory
is created or removed. A directory on either path that is a symlink (or not a
directory) is skipped with a warning, so nothing outside the project is touched.

**Tracked effect** (``clone_local_effect = False``). ``.kittify/missions`` and
``.kittify/overrides`` travel with the commit, so the default partition is right.
``apply()`` is idempotent: a second run finds only pack-identical or kept files.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from kernel.atomic import atomic_write
from specify_cli.asset_preservation import guard_destructive_overwrite, guard_destructive_removal
from specify_cli.runtime.home import get_package_asset_root
from specify_cli.tool_surface.operations import OwnershipProof

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MISSION_TYPES: tuple[str, ...] = ("documentation", "research")
_TEMPLATES = "templates"
_LEGACY_TREE: tuple[str, ...] = (".kittify", "missions")
_OVERRIDE_TREE: tuple[str, ...] = (".kittify", "overrides", "missions")

#: Every released version of each fork template: its whole history on ``main``
#: at ``src/specify_cli/missions/<type>/templates/<name>`` (or its earlier home
#: ``.kittify/missions/<type>/templates/<name>``), plus the two ``task-prompt``
#: versions only the ``v1.0.3`` tag (``1.x-maintenance``) shipped, as SHA-256 of the bytes with
#: CRLF folded to LF. Keyed ``<type>/<path under templates/>``. Frozen: the
#: forks are frozen too (``tests/runtime/test_frozen_migration_template_sources.py``
#: pins that each current fork hash is in this set).
KNOWN_FORK_SHA256: dict[str, frozenset[str]] = {
    "documentation/divio/explanation-template.md": frozenset(
        {
            "62b594f31bee903b722a236056731bd18a88d9e8000118e87f756ed3015767e7",
            "fe810f3091a941c11f32df0ff0ede27446607468b3e9e373fac03b7b4af45c7a",
        }
    ),
    "documentation/divio/howto-template.md": frozenset(
        {
            "3e28e151173b325fff82a74cc9776d396d9b5fed09877561b2a6725ae1d5554e",
            "bad57e533f97024b369970e3712cf6fff6d57bfba75578d5bf70fcef9de44671",
        }
    ),
    "documentation/divio/reference-template.md": frozenset(
        {
            "33ad6e668847415a3813e145c8ffccb615e3e54effb67ba5d86e337154f2eb06",
            "883d08403f7915bf37633e7d25be8b47ff7225fa5354e9ee176c8e32fd39adf6",
        }
    ),
    "documentation/divio/tutorial-template.md": frozenset(
        {
            "64ad64956ddd2bb7b5eaa9e19682ca543445a098825789d17c1254d9ecfdb662",
            "e43f2cf966f9147b8e0d4d8729a944b398b3e50002ebede90dbb4789c8db4056",
        }
    ),
    "documentation/plan-template.md": frozenset(
        {
            "02088b60642aae5354f98b38ea12759189b7378ca1410ab976909b555553482c",
            "30dd3ad12352b4526684442a75a3645a44d918cff2ae8412707a9458bf035db3",
            "3109c5bc2ed07970ac8c644d755a12e37b4b8e6ef9ee107b69e36571b584ac75",
            "402fec9c26e87df39d78264915dda5db6a60e3d529390ddc989a3469daf6ec88",
            "8dc2d6dd32045dd2bc8c56eb4982cb367925352a6893d0c045b37cea13457d5e",
        }
    ),
    "documentation/release-template.md": frozenset(
        {
            "856b61fe0e7735a3c7103e1bcf242f5064326ed971edbb5aa3b5f6c4f04cf437",
            "d452ca449cb04d7678e1524773fbfb2d68d85f561a6ccbf2138ca025443ae73d",
        }
    ),
    "documentation/spec-template.md": frozenset(
        {
            "98cebd2cfab3d35d5bcb3bcd34083fe8e02be52e08fd3543e67fad5d0e19083c",
            "ba82d8cc3c38e50d6fe0e1abb78b1b32ef0e62c3b61af2ba9fc15d52db1b1132",
            "cfbf3d095fd3225d0f426e25582ffa60058fe1a63e57f34581ef3cb507cff37a",
            "d43fff182ae5ecbcdbab743734824c0795aa5af9488b4ee4a136626fbb591961",
        }
    ),
    "documentation/task-prompt-template.md": frozenset(
        {
            "0e05bb4136f36d0f91b992853bd4e47b5271894650efef94f5faa2933deb7eba",
            "16a6b08b4a1bf77ee73c58c6cce80ef9219e1cefc814d514e868ed06e5391cde",
            "203e3ec2ae63d3760a2a67ed280b4d9a23d2b2018c92852ed2ce46a4fd3a7db8",
            "2e17673d167bf13d6799602eca403f90856f913c6ed2f017690e07d81356e272",
            "448b57f73e4fd36bce06bee4a05ad398f747fe53d3e92512d7806cf00959a3a1",
            "6ff27f35f0b5cc1a8b787f73d2f35142d7a36913cf52ebdc7ce42d81657a9548",
            "9820e114509156e1495f5f5c721b373c9950c72d66250c17907d342d5bfce153",
            "98d3f8e0e3628592a7dd3b4645c3bbe7ad7f13396746a82fc1033e095086b0c7",
            "a24794f28e2dd7af0f0310522e19800136654b91082a71071aea624a6cd7390c",
            "c82e2c1f33cb363d31ea5728b790da8b73a6ed92b38b4d768b3afef37d2d52b1",
            "c8b0c33a02b4f37e27576757e8e49fa7a4b383819338f56379fd73010e3779e3",
            "d764d53db598d8c6f2992c422c77c3ad2df417dcc37d323a041f0027403ce410",
            "dffb50232bb076034beea174d588c581668b9f9c6cd3cda6903f95b75a2525ea",
            "e17fc3d339f8c8708af81cb9e94eb7e32d7ccf68c4a0b0599044c31678659d38",
            "e535e6269a2d58f98f868f55368ae37385686de84d0021ce205b57c02d66dcde",
            "eb46020554c7840845e2233c8f2c7c4ebdce009db2d2fed095026b29a1502c6e",
        }
    ),
    "documentation/tasks-template.md": frozenset(
        {
            "09a68ff734f0158aaa8a9832f775fc53932a171f10656c74f0d186e6e4e18ab1",
            "9735d55c770ef79c073614eaf5dee0f2011ccdc5cb1616e76ad937b65798efbd",
            "c593367877686a5e312ca05ad550dc52b33f8407433df52b81415fef5cbc9ce2",
            "d993e239b42ee75f86d5e4fdac26a0c06e1e84325478ec168637b166a82f97ea",
            "eaa08544c484100e6f4448370ad80face005e644ffb0754f09d10af7c1678cae",
        }
    ),
    "research/data-model-template.md": frozenset(
        {
            "d9115c00810c62874f1b456e3811827a14a94e2d8f770f30906ea41fc697d0c5",
            "fdcb09e829e2e967c34c20c4ae722b9ca00636c3be41c830293152e667d843a6",
        }
    ),
    "research/plan-template.md": frozenset(
        {
            "15f0c4bdd8b1cbccf9f032e849491925e9f50acdc8b0cd68602baf472377fa2b",
            "3850d398e77d85550218d07c7dfc02d2365ee2031fe276ed44245d557719bb4c",
            "3c6bc2be02d879b3397e075a7d3770bcca23fcdf15e54cd77d08ae5176aec857",
            "e8ce4ea2b3158c9daf9f4cfbf5d65377466a6972a51e9782fde86f8becef1a34",
        }
    ),
    "research/research-template.md": frozenset(
        {
            "3104d75be3c6112572c332c1362bfe8a8370b77a60da85304ec0e66ca384edbd",
            "582fe34c36d8cd779c07670a6b580ee3b9a10ba88e0ff60437026d9e8dfaaefc",
            "cd0deebe9e0fc0a4132416f59e95f530786fde482af008d7c1b5b3a35e18613a",
        }
    ),
    "research/spec-template.md": frozenset(
        {
            "16c845b94c48c67506e0a729ac5608357e971cb4078476e6211b862ba8168eae",
            "d9489b6847736a80b375cec09b708664e4c1229a880c8e346802f769e89b6bce",
            "f97386004b06661d8b1d6a20ab0040d3b27f109187e828158be78ba003f79b72",
        }
    ),
    "research/task-prompt-template.md": frozenset(
        {
            "16516fec8152f991be0d37b1b072bf38ab6849c87edc5b69edacb90c44b9276a",
            "171b795651f75fcca4a08a62e58cb1fc8efd5948e4368c690b870f389924d39b",
            "2d911d14001e1646729c0c88fa452e6459a2673aa6b2e03b4d14d7164cb09d99",
            "455a90e561f6020608395765f8bc851d4c7bff6350038efe0b549f5d953af9e6",
            "51e1745f1e8541ebc58cde8a9317fb0305c3da4261f4be267d5cd76068a7f951",
            "59accb807169400538f9a6c193df8799c09c8d36985b9597a42341005daf7830",
            "71ef1e31437fc2f6fa02709134026b8e6e63e8ed5de78bfb95f7c4e323ebf53e",
            "797c66a88747731291a5a37d38d03f8f65f950bd4f33c3bbf1e9134ae43ec161",
            "7dc1e8357b532b13fbd4b642ee46233abe35f14ccf2d0988bf6a774f2ee539a4",
            "a427393ed8dea5fcfd06918dbe45801456e84c084777c4f1547eb08211e64a21",
            "b60c2df2da0a74c51196209263125550140364194da82cac5662db2044862e5a",
            "e75ed3a1ad46528796deccf100b2bd59334471ec4ac456fcbe323ee1d4734051",
            "edc13271ae7d8dfc0d2445dc036e761ae82469712ae670a1e727f7202d1a81c2",
        }
    ),
    "research/tasks-template.md": frozenset(
        {
            "18499583e8724f3a9585bfdbdc7f40d9672f9a45ebb8448bc8e9c26c1db7c40f",
            "237b0954d3a87bc7f073c9a0037f231a068cec7db3e493f08c19de3e84c5689a",
            "4d22bc713080654d4d956809ce36d78d33c5b30557a94e1702acea6b92194cf4",
            "8fd0354620d3dc8ba6e2c78d3ac076adcb3e88d1440bad93eac44c65891c5e8e",
        }
    ),
}


def _fingerprint(content: bytes) -> str:
    """SHA-256 of *content* with CRLF folded to LF (a Windows checkout is not an edit)."""
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()  # noqa: TID251 - file-integrity check against shipped template bytes, not charter semantic hashing


def kept_warning(rel: str) -> str:
    """Warning for a fork-named file that differs from every shipped version."""
    return f"Kept {rel}: it differs from every version Spec Kitty shipped, so it is treated as your edit. Delete it to use the template Spec Kitty ships now."


def skipped_tree_warning(rel: str) -> str:
    """Warning for a directory on the scanned path that is a symlink or not a directory."""
    return f"Stale mission template cleanup skipped {rel}: it is a symlink or not a directory; nothing there was changed"


@dataclass(frozen=True)
class _Candidate:
    """One fork-named file in a scanned templates directory."""

    path: Path
    key: str  # "<type>/<path under templates/>"
    in_overrides: bool


class _KnownForkProver:
    """Prove a file is an unedited stale fork copy from :data:`KNOWN_FORK_SHA256`."""

    def __init__(self, key: str) -> None:
        self._known = KNOWN_FORK_SHA256[key]

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        if path.is_symlink() or not path.is_file():
            return None
        try:
            fingerprint = _fingerprint(path.read_bytes())
        except OSError:
            return None
        if fingerprint not in self._known:
            return None
        return OwnershipProof("canonical_content", f"known-fork:{_rel(path, project_path)}")


def _rel(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


def _real_dir(project_path: Path, parts: tuple[str, ...]) -> tuple[Path | None, str | None]:
    """Return ``project/parts`` when every component is a real directory.

    Returns ``(None, None)`` when a component is absent (nothing to do) and
    ``(None, rel)`` naming the first component that is a symlink or not a
    directory, which is refused.
    """
    current = project_path
    for part in parts:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return None, _rel(current, project_path)
        if not current.exists():
            return None, None
    return current, None


def _scan(project_path: Path) -> tuple[list[_Candidate], list[str]]:
    """Return the fork-named files present, plus warnings for refused directories."""
    candidates: list[_Candidate] = []
    refused: list[str] = []
    for tree, in_overrides in ((_LEGACY_TREE, False), (_OVERRIDE_TREE, True)):
        for mission_type in MISSION_TYPES:
            for key in KNOWN_FORK_SHA256:
                if not key.startswith(f"{mission_type}/"):
                    continue
                name_parts = tuple(key.split("/")[1:])
                parent, refused_rel = _real_dir(project_path, (*tree, mission_type, _TEMPLATES, *name_parts[:-1]))
                if refused_rel is not None and refused_rel not in refused:
                    refused.append(refused_rel)
                if parent is None:
                    continue
                path = parent / name_parts[-1]
                if path.exists() or path.is_symlink():
                    candidates.append(_Candidate(path=path, key=key, in_overrides=in_overrides))
    return candidates, refused


def _pack_copy(key: str) -> Path | None:
    """The pack template a fork file corresponds to, or ``None`` for a fork-only name."""
    mission_type, _, rel = key.partition("/")
    pack = get_package_asset_root() / mission_type / _TEMPLATES / rel
    return pack if pack.is_file() else None


def _is_current(candidate: _Candidate, pack: Path | None) -> bool:
    """True when the file already equals the pack copy (nothing to repair)."""
    if pack is None or candidate.path.is_symlink() or not candidate.path.is_file():
        return False
    try:
        return _fingerprint(candidate.path.read_bytes()) == _fingerprint(pack.read_bytes())
    except OSError:
        return False


def _iter_pending(candidates: list[_Candidate]) -> Iterator[tuple[_Candidate, Path | None]]:
    """Yield each candidate that differs from its pack copy, with that copy."""
    for candidate in candidates:
        pack = _pack_copy(candidate.key)
        if not _is_current(candidate, pack):
            yield candidate, pack


@MigrationRegistry.register
class RetireStaleMissionTemplateForksMigration(BaseMigration):
    """Remove or replace stale documentation/research template fork copies (#5280)."""

    migration_id = "4.0.0rc8_retire_stale_mission_template_forks"
    description = "Replace stale documentation/research template copies with the shipped templates"
    target_version = "4.0.0rc8"

    def detect(self, project_path: Path) -> bool:
        """True when a fork-named file differs from its pack copy, or a scanned directory is refused."""
        candidates, refused = _scan(project_path)
        if refused:
            return True
        try:
            return next(_iter_pending(candidates), None) is not None
        except FileNotFoundError:
            # No shipped templates to compare against: report the work so
            # ``can_apply`` refuses it visibly instead of a silent not-needed.
            return bool(candidates)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 -- the package asset root is project-independent
        """Refuse (a skip, retried later) when the shipped templates cannot be located."""
        try:
            get_package_asset_root()
        except FileNotFoundError as exc:
            return False, f"Could not locate the shipped mission templates: {exc}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove or replace each proven stale copy; keep and name every other file."""
        candidates, refused = _scan(project_path)
        changes: list[str] = []
        warnings = [skipped_tree_warning(rel) for rel in refused]
        errors: list[str] = []
        for candidate, pack in _iter_pending(candidates):
            try:
                outcome = _repair(project_path, candidate, pack, dry_run=dry_run)
            except OSError as exc:
                errors.append(f"Could not repair {_rel(candidate.path, project_path)}: {exc}")
                continue
            if outcome.startswith("Kept "):
                warnings.append(outcome)
            else:
                changes.append(outcome)
        return MigrationResult(success=not errors, changes_made=changes, warnings=warnings, errors=errors)


def _repair(project_path: Path, candidate: _Candidate, pack: Path | None, *, dry_run: bool) -> str:
    """Repair one candidate; return a change line, or a ``Kept ...`` warning."""
    rel = _rel(candidate.path, project_path)
    prover = _KnownForkProver(candidate.key)
    if candidate.in_overrides or pack is None:
        verdict = guard_destructive_removal(candidate.path, project_path, prover=prover, dry_run=dry_run)
        return verdict.diagnostic if verdict.owned else kept_warning(rel)
    overwrite = guard_destructive_overwrite(
        candidate.path,
        project_path,
        replacement_substantive=True,
        authorized=False,
        prover=prover,
    )
    if not overwrite.proceed:
        return kept_warning(rel)
    if dry_run:
        return f"Would replace stale {rel} with the shipped template"
    atomic_write(candidate.path, pack.read_bytes())
    return f"Replaced stale {rel} with the shipped template"
