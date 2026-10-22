# Tooling friction

- **[2026-10-22][setup] origin/main was force-updated under the clone.** Local `main` diverged by 50 commits from a rewritten origin. It was realigned with `reset --hard origin/main` (no local work). Afterwards the auto-mode classifier refused the next unrelated commands once. Workaround: rerun each separately.
- **[2026-10-22][setup] JDK 25 present but not on PATH.** Temurin 25 is at `/usr/lib/jvm/temurin-25`, while `java` on PATH is 21 (the profile export of #6325 did not reach this shell). It is not needed for this Python-only mission. Disposition: noted, no gap filed.
