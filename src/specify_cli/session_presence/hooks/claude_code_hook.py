"""ClaudeCodeHookRegistrar — manages lifecycle hooks in .claude/settings.json.

Reads the existing settings.json (if any), merges the spec-kitty hook entry
for a given lifecycle event (``SessionStart`` or ``Stop``) idempotently, and
writes the result back atomically.  All unrelated keys and hook entries are
preserved.

Contract (from contracts/settings-json-hook.md):

Target structure after ``register()``::

    {
      "hooks": {
        "<event_key>": [
          {
            "hooks": [
              {"type": "command", "command": "<cmd>"}
            ]
          }
        ]
      }
    }

Edge cases handled:
- File absent → treated as ``{}`` → ``register()`` creates it.
- File exists but contains invalid JSON or non-object JSON → original content is
  copied to ``settings.json.invalid*`` before ``register()`` creates a valid
  structure.
- File exists with other entries for the same event → all preserved.
- ``unregister()`` on a file where the command is not present → no-op, no
  write performed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from kernel.errors import GuardedReadError
from kernel.text_decode import decode_unambiguous
from specify_cli.asset_preservation.backup import backup_before_overwrite
from specify_cli.core.utils import write_text_within_directory
from ..writers.markdown_rules import (
    PreparedPresenceFile,
    _atomic_write,
    observe_presence_path,
    presence_state,
    read_presence_bytes,
)

__all__ = [
    "ClaudeCodeHookRegistrar",
    "SESSION_START_EVENT",
    "SettingsNotDecodableError",
    "STOP_EVENT",
]


class SettingsNotDecodableError(GuardedReadError):
    """Raised when ``.claude/settings.json`` bytes cannot be provably decoded.

    Provable means a byte-order mark or strict UTF-8 (see
    ``kernel.text_decode.decode_unambiguous``, D1/D6, #4940). Anything else
    (a single-byte code page such as cp1252, an ambiguous heuristic guess) is
    refused rather than reinterpreted, so the file is never silently
    overwritten by a lint-only reconstruction that loses the operator's
    permissions, env, and hook entries.
    """

    def __init__(self, *, path: str) -> None:
        reason = f"{path} is not valid UTF-8 and has no byte-order mark; re-save it as UTF-8"
        super().__init__(reason, path=path, reason=reason)


_SETTINGS_PATH = ".claude/settings.json"
_SETTINGS_PATH_PARTS = (".claude", "settings.json")
SESSION_START_EVENT = "SessionStart"
STOP_EVENT = "Stop"
_logger = logging.getLogger(__name__)


class ClaudeCodeHookRegistrar:
    """Read/merge/write ``.claude/settings.json`` for one lifecycle hook event.

    ``event_key`` selects the hook event this registrar manages
    (``"SessionStart"`` by default, or ``"Stop"``).  All writes are atomic: a
    sibling temp file is written and then swapped into place with
    ``os.replace()``.
    """

    def __init__(self, event_key: str = SESSION_START_EVENT) -> None:
        self._event_key = event_key
        # Set by ``_load`` for the path it just decoded, consumed by ``_save``
        # on the same instance to decide whether a byte backup is required
        # before the UTF-8 rewrite (D6). Keyed by string path since a
        # registrar may be asked about more than one settings path in
        # principle, though in practice there is exactly one.
        self._source_encoding_by_path: dict[str, str] = {}

    @property
    def settings_relative_path(self) -> str:
        """Canonical physical settings path shared by lifecycle events."""
        return _SETTINGS_PATH

    def prepare_commands(self, project_root: Path, commands: tuple[tuple[str, str], ...]) -> PreparedPresenceFile:
        """Validate and merge the complete automatic hook batch without recovery."""
        observations = observe_presence_path(project_root, _SETTINGS_PATH)
        state = presence_state(observations[-1])
        if state.kind not in ("file", "absent"):
            raise ValueError("Claude settings destination is not a regular file")
        path = project_root / _SETTINGS_PATH
        if state.kind == "file":
            raw = read_presence_bytes(path)
            decoded = decode_unambiguous(raw)
            if decoded is None:
                raise SettingsNotDecodableError(path=str(path))
            text, _source_encoding = decoded
            data = json.loads(text)
        else:
            raw = b""
            data = {}
        if not isinstance(data, dict):
            raise ValueError("Expected Claude settings JSON object")
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("Expected Claude hooks object")
        changed = False
        for event, command in commands:
            entries = hooks.setdefault(event, [])
            _validate_hook_entries(entries)
            registrar = ClaudeCodeHookRegistrar(event)
            present = any(hook.get("type") == "command" and hook.get("command") == command for hook in registrar._iter_command_hooks(entries))
            if not present:
                entries.append({"hooks": [{"type": "command", "command": command}]})
                changed = True
        desired = (json.dumps(data, indent=2) + "\n").encode() if changed else raw
        return PreparedPresenceFile(_SETTINGS_PATH, state, desired, reason="Prepare lifecycle hooks")

    def apply_prepared(self, project_root: Path, prepared: PreparedPresenceFile) -> None:
        """Write the previously validated final settings bytes once.

        When the on-disk source was not plain UTF-8, the original bytes are
        backed up (byte-exact, via ``backup_before_overwrite``) immediately
        before the rewrite (D6). The source encoding is re-derived from the
        current bytes rather than threaded from ``prepare_commands`` because
        a prepared batch crosses a registrar-instance boundary
        (``ClaudeCodeWriter.prepare_batch`` / ``apply_prepared`` each
        construct their own ``ClaudeCodeHookRegistrar``); re-reading is the
        smallest correct seam. A file that has become undecodable since it
        was prepared (a benign race) refuses rather than losing it.
        """
        if prepared.path != _SETTINGS_PATH:
            raise ValueError("Prepared settings belong to another owner")
        if not prepared.changed:
            return
        path = project_root / prepared.path
        if path.exists():
            decoded = decode_unambiguous(read_presence_bytes(path))
            if decoded is None:
                raise SettingsNotDecodableError(path=str(path))
            if decoded[1] != "utf-8":
                backup_before_overwrite(path)
        _atomic_write(path, prepared.content.decode("utf-8"), root=project_root, expected=prepared.before)

    def _settings_path(self, project_root: Path) -> Path:
        root = project_root.expanduser().resolve()
        path = root.joinpath(*_SETTINGS_PATH_PARTS)
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            msg = "Claude settings path escapes project root"
            raise ValueError(msg) from exc
        return path

    def _event_entries(self, data: dict[str, object]) -> list[object] | None:
        hooks_section = data.get("hooks")
        if not isinstance(hooks_section, dict):
            return None
        entries = hooks_section.get(self._event_key)
        if not isinstance(entries, list):
            return None
        return entries

    def _iter_command_hooks(self, entries: list[object]) -> list[dict[str, object]]:
        command_hooks: list[dict[str, object]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_hooks = entry.get("hooks")
            if not isinstance(entry_hooks, list):
                continue
            command_hooks.extend(hook for hook in entry_hooks if isinstance(hook, dict))
        return command_hooks

    def _read_settings_text(self, path: Path) -> tuple[str, str] | None:
        """Read and decode *path* via the shared proof-only rule (D1/D6).

        Returns ``None`` only when the file is absent, including the benign
        race where it disappears between an earlier ``exists()`` check and
        this read. Any other read failure propagates (it is not this
        function's job to swallow a real I/O error into an empty result --
        that is exactly the #4940 bug class). Raises
        :class:`SettingsNotDecodableError` when the bytes cannot be proven to
        be a supported encoding.
        """
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None
        decoded = decode_unambiguous(raw)
        if decoded is None:
            raise SettingsNotDecodableError(path=str(path))
        return decoded

    def _load(self, path: Path, *, preserve_invalid: bool = False) -> dict[str, object]:
        """Load JSON object from *path*, returning ``{}`` on absence or invalid data.

        When ``preserve_invalid`` is true, existing malformed/non-object content
        is copied to a sibling ``.invalid`` backup before callers overwrite the
        settings file.  Backup failures are re-raised to prevent silent data loss.

        The bytes are decoded only when a BOM or strict UTF-8 proves the
        encoding (D6); anything else raises :class:`SettingsNotDecodableError`
        rather than being silently discarded as ``{}``. The proven source
        encoding is remembered for this instance/path so :meth:`_save` knows
        whether a pre-write byte backup is required.
        """
        if not path.exists():
            return {}
        result = self._read_settings_text(path)
        if result is None:
            return {}
        text, source_encoding = result
        self._source_encoding_by_path[str(path)] = source_encoding
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if preserve_invalid:
                self._preserve_invalid(path, text)
            return {}
        if not isinstance(data, dict):
            if preserve_invalid:
                self._preserve_invalid(path, text)
            return {}
        return data

    def _preserve_invalid(self, path: Path, text: str) -> None:
        """Copy invalid settings content to a sibling backup before overwrite."""
        backup = path.parent / f"{path.name}.invalid.{uuid4().hex}"
        write_text_within_directory(backup, text, root=path.parent)
        _logger.warning("Preserved invalid Claude settings JSON at %s", backup)

    def _save(self, path: Path, data: dict[str, object]) -> None:
        """Write *data* as JSON to *path* atomically.

        When the most recent ``_load`` of *path* on this instance proved a
        source encoding other than plain UTF-8, the original bytes are
        backed up first (byte-exact, ``backup_before_overwrite``) so the
        re-encode to UTF-8 never loses the operator's original file.  Backup
        failures are re-raised to prevent silent data loss, per the same
        contract as ``_preserve_invalid``.
        """
        source_encoding = self._source_encoding_by_path.get(str(path))
        if source_encoding is not None and source_encoding != "utf-8" and path.exists():
            backup_before_overwrite(path)
        write_text_within_directory(
            path,
            json.dumps(data, indent=2) + "\n",
            root=path.parent,
        )

    def is_registered(self, project_root: Path, command: str) -> bool:
        """Return ``True`` when *command* is present in any entry for the event."""
        data = self._load(self._settings_path(project_root))
        entries = self._event_entries(data)
        if entries is None:
            return False
        return any(hook.get("type") == "command" and hook.get("command") == command for hook in self._iter_command_hooks(entries))

    def register(self, project_root: Path, command: str, matcher: str | None = None) -> None:
        """Add *command* as a hook entry for the configured event (idempotent).

        If the command is already registered, returns immediately without
        writing.  Otherwise appends a new entry and writes atomically.

        ``matcher`` (e.g. ``"Edit|Write"``) is included on the entry when given,
        as required by tool-scoped events such as ``PostToolUse``. Lifecycle
        events (``SessionStart``/``Stop``) take no matcher and pass ``None``.
        """
        if self.is_registered(project_root, command):
            return
        path = self._settings_path(project_root)
        data = self._load(path, preserve_invalid=True)
        # Ensure hooks → <event_key> list exists, then append.
        hooks_section = data.get("hooks")
        if not isinstance(hooks_section, dict):
            hooks_section = {}
            data["hooks"] = hooks_section
        entries = hooks_section.get(self._event_key)
        if not isinstance(entries, list):
            entries = []
            hooks_section[self._event_key] = entries
        entry: dict[str, object] = {"hooks": [{"type": "command", "command": command}]}
        if matcher is not None:
            entry = {"matcher": matcher, **entry}
        entries.append(entry)
        self._save(path, data)

    def unregister(self, project_root: Path, command: str) -> None:
        """Remove the spec-kitty *command* entry from the configured event hooks.

        Preserves all other entries and keys.  If the command is not present,
        returns without writing.  If removal empties the list, the key is kept
        with an empty list (never deleted).
        """
        path = self._settings_path(project_root)
        data = self._load(path)
        entries = self._event_entries(data)
        if entries is None:
            return

        new_entries: list[object] = []
        found = False
        for entry in entries:
            if not isinstance(entry, dict):
                new_entries.append(entry)
                continue
            entry_hooks = entry.get("hooks")
            if not isinstance(entry_hooks, list):
                new_entries.append(entry)
                continue
            # Filter out the specific command hook from this entry's hooks list.
            filtered: list[object] = [h for h in entry_hooks if not (isinstance(h, dict) and h.get("type") == "command" and h.get("command") == command)]
            if len(filtered) < len(entry_hooks):
                found = True
            new_entry: dict[str, object] = {**entry, "hooks": filtered}
            new_entries.append(new_entry)

        if not found:
            # Command was not present — no-op, do not write.
            return

        hooks_section = data.get("hooks")
        if not isinstance(hooks_section, dict):
            msg = "Expected hooks section to be a dict"
            raise TypeError(msg)
        hooks_section[self._event_key] = new_entries
        self._save(path, data)


def _validate_hook_entries(entries: object) -> None:
    if not isinstance(entries, list):
        raise ValueError("Expected Claude event entries list")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            raise ValueError("Expected Claude event entry with hooks list")
        for hook in entry["hooks"]:
            if not isinstance(hook, dict) or not isinstance(hook.get("type"), str):
                raise ValueError("Expected typed Claude hook object")
            if hook["type"] == "command" and not isinstance(hook.get("command"), str):
                raise ValueError("Expected Claude command string")
