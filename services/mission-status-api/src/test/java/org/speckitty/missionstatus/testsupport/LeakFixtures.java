package org.speckitty.missionstatus.testsupport;

import java.util.List;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/** The patterns of {@code contracts/tools/leak_patterns.py}, source for source, compiled through the one translating entry point. */
final class LeakFixtures {

  private static final String EMAIL =
      "(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+"
          + "|(?<![\\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\\w@-]|\\.[A-Za-z0-9])";
  private static final String EMAIL_ANCHORED =
      "[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+" + "|(?<![\\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\\w@-]|\\.[A-Za-z0-9])";

  private LeakFixtures() {}

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
}
