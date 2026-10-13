# Research: Acceptance scenario contract, per-PR check and nightly evidence

| # | Question | Finding | Source |
|---|----------|---------|--------|
| R1 | Does the `@wip` pass overwrite gating results? | Yes. Both passes run the same `test` task into `build/`; the second runs with `--rerun-tasks`, rewriting `build/cucumber-report/cucumber.json` and `build/test-results/test/`; Allure results accumulate in one folder. | `.github/workflows/ci-nightly.yml` acceptance-bdd job; `acceptance-jvm/build.gradle` L46-65 |
| R2 | How should a per-PR test reach scenario-only PRs? | `architectural-fast` has no path filter and runs on every PR; its roster is `special_tiers.architectural.fast_gate.roster` in `.github/ci-module-registry.yml`. Wiring the `scenarios`/`acceptance_jvm` groups to the heavy battery would run the whole battery and break `_DELIBERATELY_UNGATED_FILTER_GROUPS`. | `ci-router.yml` L796-830; `tests/architectural/test_workflow_coherence.py` L311-323 |
| R3 | Can the CLI version be read without running the CLI? | Yes: `CliUnderTest` builds `spec_kitty_cli-<version>-py3-none-any.whl`; the version is the second `-` field. | `CliUnderTest.java` L72-109 |
| R4 | Where can run metadata be written once per run? | A static `io.cucumber.java.BeforeAll` hook (Cucumber 7.20) in the glue package. | Cucumber 7 API |
| R5 | Can Allure's results folder be set per pass? | `allure-java` reads `allure.results.directory` from system properties. To be confirmed against the 2.29.1 jar during implementation. | allure-java `PropertiesUtils` |
| R6 | Is there a JDK 25 locally? | No: JDK 21 only; GitHub release assets are blocked. Verify Java in a scratch copy with toolchain 21; CI compiles with 25. | environment probe |
| R7 | What pins the nightly YAML? | Nothing pins the upload step today; `tests/architectural/_gate_coverage.load_spliced_workflow` is the canonical loader. | `tests/ci/test_nightly_escalation.py` L507-513 |
