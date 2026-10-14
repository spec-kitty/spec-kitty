package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** {@link OwnedFilePatterns#isGlob} against the oracle's {@code is_glob_pattern}: any of {@code * ? [ {}; each case was run through Python. */
class OwnedFilePatternsTest {

  @Test
  void aPatternWithAGlobMetacharacterIsAGlob() {
    for (String glob : new String[] {"a*", "a?", "a[", "a{", "src/**", "src/feature/*.py", "\\*", "{a,b}", "[ab]"}) {
      assertThat(OwnedFilePatterns.isGlob(glob)).as(glob).isTrue();
    }
  }

  @Test
  void aLiteralPathIsNotAGlob() {
    for (String literal : new String[] {"a", "README.md", "", "src/app/main.py", "a]", "a}", "a.b", "a/b"}) {
      assertThat(OwnedFilePatterns.isGlob(literal)).as(literal).isFalse();
    }
  }
}
