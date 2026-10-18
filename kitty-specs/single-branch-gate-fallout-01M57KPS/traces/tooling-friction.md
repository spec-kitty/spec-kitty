# Tooling friction — single-branch-gate-fallout

Tooling touched: `spec-kitty agent mission create/setup-plan/finalize-tasks`, `spec-commit`, `agent decision`, pytest (out-of-matrix e2e), the acceptance-jvm Cucumber harness.

- **[2026-10-18][specify] Cucumber-JVM cannot run in the cloud session.** The session ships JDK 21 and `acceptance-jvm/build.gradle` needs a Java 25 toolchain (README "Cloud sessions"). Workaround: a shell port of the scenario-6 builder (`MissionLifecycle.planSingleBranchMission` + `advance`) drives the same CLI commands. The nightly `acceptance-bdd` lane remains the authoritative run.
- **[2026-10-18][specify] Shallow clone hides the #5939 commits.** `git show 6af1d49bf9` failed until `git fetch --deepen=300 origin main`. Workaround.
- **[2026-10-18][specify] `spec-commit` of the decisions dir also commits `index.json.lock`.** Seen in other missions too (20 tracked `.lock` files). Candidate gap: noise, not harmful.
