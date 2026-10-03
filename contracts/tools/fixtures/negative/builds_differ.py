"""Negative-case harness: ``bundle.py`` whose second build differs from the first, so ``BUILDS_DIFFER`` must be reported (FR-014, NFR-002).

The writer is wrapped so that the second call appends a line to the bundle it wrote; the first and second digests then differ.
Run as a bare script with the arguments of ``bundle.py`` (``--root``, ``--out``, ``--bundle-only`` ...). Standard library and the
sibling ``bundle`` module only; it never imports pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import bundle  # noqa: E402 -- the tools directory has to be on the path first


def main() -> int:
    real = bundle.write_bundle
    calls: list[int] = []

    def flaky(module: Path, out_dir: Path) -> Path:
        target = real(module, out_dir)
        calls.append(1)
        if len(calls) == 2:
            target.write_text(target.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
        return target

    return bundle.run(sys.argv[1:], writer=flaky)


if __name__ == "__main__":
    sys.exit(main())
