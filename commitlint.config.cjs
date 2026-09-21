module.exports = {
  defaultIgnores: true,
  // spec-kitty auto-generates mission lifecycle commits that don't use
  // conventional-commit format. Ignore them rather than requiring every
  // planning command to produce a typed subject line.
  //
  // 2026-08-24 (#3705): the planning-phase pattern below never covered the
  // analysis and acceptance generators, so every mission that ran `accept` or
  // `agent mission record-analysis` wore commitlint failures for commits no
  // human authored. The escapees are already on main (`Accept <slug>`,
  // `Record acceptance commit for <slug>`, `Add analysis report for mission
  // <slug>`) because commitlint only lints commits in a PR range, so the
  // violation surfaces on whichever PR happens to carry them. Each pattern
  // below is anchored and matched against the real generator string:
  //   src/specify_cli/acceptance/__init__.py       "Accept {mission_slug}"
  //   src/specify_cli/acceptance/__init__.py       "Record acceptance commit for {mission_slug}"
  //   src/specify_cli/cli/commands/accept.py       "Finalize acceptance artifacts for {mission_slug}"
  //   .../agent/mission_record_analysis.py         "Add analysis report for mission {slug}"
  ignores: [
    (commit) =>
      /^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) /.test(
        commit
      ),
    (commit) => /^Add analysis report for mission \S/.test(commit),
    (commit) => /^Accept \S/.test(commit),
    (commit) => /^Record acceptance commit for \S/.test(commit),
    (commit) => /^Finalize acceptance artifacts for \S/.test(commit),
  ],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "build",
        "charter",
        "chore",
        "ci",
        "docs",
        "feat",
        "fix",
        "lint",
        "perf",
        "plan",
        "refactor",
        "revert",
        "spec",
        "style",
        "test",
      ],
    ],
    "type-case": [2, "always", "lower-case"],
    "type-empty": [2, "never"],
    "subject-empty": [2, "never"],
  },
};
