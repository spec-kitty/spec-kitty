"""Shared ``.pyc`` corruption constructors for the #4124/#4130 bytecode suites.

Both ``tests/specify_cli/test_bytecode_heal.py`` (the heal-and-retry half)
and ``tests/specify_cli/cli/commands/test_bytecode_doctor.py`` (the
read-only detection half) need to build a ``.pyc`` with an intact header
Python's import machinery would trust, but a body that fails to unmarshal
-- the interrupted-write shape from #4124. They independently grew their
own copies of the same two byte constructors; this module is the single
source so the two suites cannot drift apart.
"""

from __future__ import annotations

import marshal
from pathlib import Path

_HEADER_SIZE = 16


def corrupt_truncated_body(pyc: Path) -> None:
    """Intact header, truncated/garbage body -- the #4124 field signature."""
    data = pyc.read_bytes()
    pyc.write_bytes(data[:_HEADER_SIZE] + b"\x00" * 8)


def corrupt_non_code_body(pyc: Path) -> None:
    """Intact header; body unmarshals cleanly to a non-code object."""
    data = pyc.read_bytes()
    pyc.write_bytes(data[:_HEADER_SIZE] + marshal.dumps(b"not-a-code-object"))
