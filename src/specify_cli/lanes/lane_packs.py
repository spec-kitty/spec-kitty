"""Place the pinned packs trees into a new lane checkout from the local cache (#7577, FR-012).

A repository that pins its pack trees (``packs/<name>.source.yaml``) instead of
committing them gives a fresh lane checkout no tree, so the lane's own CLI and pack
tests fail with ``BuiltInPackMissing``. :func:`place_pinned_packs` places each pinned
tree the lane lacks with the same two functions ``make sync-packs`` runs
(``fetch_to_cache`` then ``place_pack``), which re-hash the tree against the pin, and
**offline only** (operator ruling, decision ``01M774QJP2HZ0A2A8KQ05MQCRS``): a cold
cache leaves the lane without the tree and yields a remedy line, never a fetch and
never an error. The pack set is the pin files the lane carries, so a repository with
none (every consumer project) is untouched.

The pack functions are imported lazily through the ``charter.packs`` facade, keeping
the ``specify_cli -> charter`` direction and the facade seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.pack_tiers import pin_filename

__all__ = ["LanePacksResult", "place_pinned_packs"]

_PACKS_DIR = "packs"
#: An unexpected error's text is cut to this length so one remedy line stays one line.
_REASON_LIMIT = 160


@dataclass(frozen=True)
class LanePacksResult:
    """Which pinned trees were placed into a lane, and which were left out and why."""

    placed: tuple[str, ...] = ()
    skipped: tuple[tuple[str, str], ...] = ()
    """``(pack name, bounded reason)``: a ``PACK_*`` code, or a cut error text."""

    def remedy_lines(self, lane: Path) -> tuple[str, ...]:
        """One line per pack left out, naming the lane to run ``make sync-packs`` in."""
        return tuple(f"{_PACKS_DIR}/{name} not placed in the lane ({reason}); run `make sync-packs` in {lane}" for name, reason in self.skipped)


def place_pinned_packs(lane: Path) -> LanePacksResult:
    """Place every pinned pack tree *lane* lacks from the verified local cache, offline.

    A tree already present is left untouched (never re-placed). A pack whose pin
    cannot be read, whose cache entry is missing or fails its digest, or whose
    placement fails is reported in :attr:`LanePacksResult.skipped`; nothing raises
    for a pack-level failure.
    """
    placed: list[str] = []
    skipped: list[tuple[str, str]] = []
    for name in _pinned_pack_names(lane / _PACKS_DIR):
        dest = lane / _PACKS_DIR / name
        if dest.exists():
            continue
        reason = _place_one(lane / _PACKS_DIR / pin_filename(name), dest)
        if reason is None:
            placed.append(name)
        else:
            skipped.append((name, reason))
    return LanePacksResult(placed=tuple(placed), skipped=tuple(skipped))


def _pinned_pack_names(packs_dir: Path) -> list[str]:
    """The pack names whose pin file sits in *packs_dir*, sorted (empty when there is none)."""
    if not packs_dir.is_dir():
        return []
    suffix = pin_filename("")
    return sorted(path.name[: -len(suffix)] for path in packs_dir.glob(pin_filename("*")) if path.is_file() and len(path.name) > len(suffix))


def _place_one(pin_path: Path, dest: Path) -> str | None:
    """Place one pinned tree at *dest*; return ``None`` on success, else a bounded reason."""
    from charter.packs import PACK_PIN_INVALID, PackPinError, PackSyncError, fetch_to_cache, load_pack_pin, place_pack

    try:
        pin = load_pack_pin(pin_path)
        place_pack(fetch_to_cache(pin, offline=True), dest, pin)
    except PackSyncError as exc:
        return str(exc.code)
    except PackPinError:
        return str(PACK_PIN_INVALID)
    except (OSError, ValueError) as exc:
        return _bounded(f"{type(exc).__name__}: {exc}")
    return None


def _bounded(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= _REASON_LIMIT else flat[: _REASON_LIMIT - 3] + "..."
