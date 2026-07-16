"""Plain-text ``{{ORG_NAME}}`` / ``{{LOCAL_PATH}}`` substitution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Plain-text substitution markers (not credentials; S105 false positive on "TOKEN").
ORG_NAME_PLACEHOLDER = "{{ORG_NAME}}"
LOCAL_PATH_PLACEHOLDER = "{{LOCAL_PATH}}"


@dataclass(frozen=True, slots=True)
class SubstituteError:
    """Leftover-token or I/O failure during substitution."""

    rule_id: str
    message: str


RULE_LEFTOVER_TOKENS = "substitute.leftover_tokens"


def substitute_tokens(
    destination: Path,
    org_name: str,
    local_path: str,
) -> SubstituteError | None:
    """Replace tokens in UTF-8 text files under *destination*.

    Undecodable (binary) files are left unchanged and are not scanned for
    leftovers. Returns an error if either token remains in any scanned text file.
    """
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        err = _substitute_file(path, org_name, local_path)
        if err is not None:
            return err
    return _assert_no_leftovers(destination)


def _substitute_file(path: Path, org_name: str, local_path: str) -> SubstituteError | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    replaced = text.replace(ORG_NAME_PLACEHOLDER, org_name).replace(
        LOCAL_PATH_PLACEHOLDER, local_path
    )
    if replaced != text:
        path.write_text(replaced, encoding="utf-8")
    return None


def _assert_no_leftovers(destination: Path) -> SubstituteError | None:
    offenders: list[str] = []
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if ORG_NAME_PLACEHOLDER in text or LOCAL_PATH_PLACEHOLDER in text:
            offenders.append(path.relative_to(destination).as_posix())
    if not offenders:
        return None
    sample = ", ".join(offenders[:5])
    more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
    return SubstituteError(
        rule_id=RULE_LEFTOVER_TOKENS,
        message=(
            f"Unfilled template tokens remain ({RULE_LEFTOVER_TOKENS}) in: "
            f"{sample}{more}"
        ),
    )
