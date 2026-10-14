package org.speckitty.missionstatus.domain.redaction;

/**
 * Obviously fake leak-shaped values, assembled from fragments so that no scanner reads this file as a secret. The patterns that
 * judge them are never written out here: tests load them from the generated {@code leak-patterns.json} through
 * {@code LeakPatternsFile.load()}, the one source.
 */
final class FakeLeakValues {

  private FakeLeakValues() {}

  /** An obviously fake GitHub-token-shaped canary. */
  static String fakeGithubToken() {
    return "gh" + "p_" + "A".repeat(36);
  }

  static String fakeAwsKeyId() {
    return "AK" + "IA" + "B".repeat(16);
  }
}
