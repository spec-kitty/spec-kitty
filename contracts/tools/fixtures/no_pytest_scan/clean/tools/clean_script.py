"""A clean control: it may talk about the test runner in prose and still reach nothing."""

from __future__ import annotations

import subprocess
import sys

IGNORED_CACHE_DIRECTORY = ".pytest_cache"  # a directory name is not an invocation
HYPHENATED = "pytest-free"


def main() -> int:
    # Prose in a comment: the check never imports the test runner.
    return subprocess.run([sys.executable, "-c", "print('ok')"], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
