package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

/**
 * D-31 and FR-018: the README states that the artifact routes and the Work Package index need a UTF-8 locale for file names. The sentence
 * must hold the three literals {@code UTF-8 locale}, {@code sun.jnu.encoding} and {@code LC_ALL}; the README test of the work package that
 * owns the file asserts the same three.
 */
class ArtifactControllerReadmeLocaleTest {

  private static String readme() throws IOException {
    return Files.readString(Path.of("README.md"), StandardCharsets.UTF_8);
  }

  @Test
  void theReadmeHoldsTheLocaleSentenceWithItsThreeLiterals() throws IOException {
    String readme = readme();

    assertThat(readme).contains("UTF-8 locale").contains("sun.jnu.encoding").contains("LC_ALL");
  }

  @Test
  void theThreeLiteralsAreInOneSentenceThatNamesBothRoutes() throws IOException {
    String sentence =
        java.util.Arrays.stream(readme().split("(?<=[.!?])\\s+"))
            .filter(candidate -> candidate.contains("UTF-8 locale") && candidate.contains("sun.jnu.encoding") && candidate.contains("LC_ALL"))
            .findFirst()
            .orElseThrow(() -> new AssertionError("no sentence holds the three literals"));

    assertThat(sentence).contains("artifact").contains("Work Package");
  }

  @Test
  void theWrongPhrasingIsNotWhatTheTestAccepts() {
    assertThat("UTF-8 file-name locale").doesNotContain("UTF-8 locale");
  }
}
