package org.speckitty.missionstatus.domain.redaction;

import java.util.List;

/**
 * The leak patterns of {@code contracts/tools/leak_patterns.py}, written inline (the real {@code leak-patterns.json} is read by the
 * adapter, not here). Sources are compiled through {@link LeakClasses#compile(String)}, the one place the Unicode flag is applied.
 */
final class InlineLeakClasses {

  private InlineLeakClasses() {}

  static final String EMAIL =
      "(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+"
          + "|(?<![\\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\\w@-]|\\.[A-Za-z0-9])";

  static final String EMAIL_ANCHORED =
      "[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+" + "|(?<![\\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\\w@-]|\\.[A-Za-z0-9])";

  /** Python's patterns, source for source. */
  static LeakClasses python() {
    return new LeakClasses(
        List.of(
            LeakClasses.compile("^(?:/|~/|[A-Za-z]:[\\\\/])"),
            LeakClasses.compile("(?:^|/)(?:home|Users)/[^/\\s]+/"),
            LeakClasses.compile("[A-Za-z]:\\\\Users\\\\")),
        List.of(
            LeakClasses.compile("(?<![\\w.~-])/(?:home|Users|root)/[^\\s/]+"),
            LeakClasses.compile("(?<![\\w.~-])/(?:tmp|var/tmp|var/folders)/\\S"),
            LeakClasses.compile("[A-Za-z]:\\\\Users\\\\[^\\s\\\\]+")),
        LeakClasses.compile(EMAIL),
        LeakClasses.compile(EMAIL_ANCHORED),
        List.of(
            LeakClasses.compile("(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,}"),
            LeakClasses.compile("(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{40,}"),
            LeakClasses.compile("(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"),
            LeakClasses.compile("-{5}BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-{5}")));
  }

  /** An obviously fake GitHub-token-shaped canary, assembled from fragments so that no scanner reads this file as a secret. */
  static String fakeGithubToken() {
    return "gh" + "p_" + "A".repeat(36);
  }

  static String fakeAwsKeyId() {
    return "AK" + "IA" + "B".repeat(16);
  }
}
