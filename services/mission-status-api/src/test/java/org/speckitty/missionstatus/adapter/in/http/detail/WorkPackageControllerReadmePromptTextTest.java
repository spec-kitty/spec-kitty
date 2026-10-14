package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

/**
 * AC-9.4: the service README has a section "Prompt text" that names the exception to the leak projection and its guard, and that contains the
 * strings {@code includePrompt} and {@code Host and Origin}. The revert rows are the two negative controls: the same check on a copy without
 * the section, and on a copy of the section without either string, is red.
 */
class WorkPackageControllerReadmePromptTextTest {

  private static final Path README = Path.of("README.md");
  private static final String HEADING = "## Prompt text";

  private static String read() {
    try {
      return Files.readString(README, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** The text of the section: from its heading to the next heading of the same level, or null when there is none. */
  static String section(String readme) {
    int start = readme.indexOf("\n" + HEADING + "\n");
    if (start < 0) {
      return null;
    }
    int from = start + 1;
    int next = readme.indexOf("\n## ", from + HEADING.length());
    return next < 0 ? readme.substring(from) : readme.substring(from, next);
  }

  /** True when the README holds the section and the section holds both strings. */
  static boolean sectionIsComplete(String readme) {
    String section = section(readme);
    return section != null && section.contains("includePrompt") && section.contains("Host and Origin");
  }

  @Test
  void theReadmeHasThePromptTextSectionWithTheParameterAndTheGuard() {
    String section = section(read());

    assertThat(section).as("the '## Prompt text' section").isNotNull();
    assertThat(section).contains("includePrompt").contains("Host and Origin").contains("promptMarkdown");
    assertThat(sectionIsComplete(read())).isTrue();
  }

  @Test
  void theSectionIsOnlyThePromptTextSectionAndNoOtherHeadingIsInsideIt() {
    String section = section(read());

    assertThat(section).doesNotContain("\n## ").doesNotContain("\n# ");
    assertThat(section.lines().count()).isLessThan(30);
  }

  @Test
  void aReadmeWithoutTheSectionOrWithoutEitherStringIsRed() {
    String readme = read();
    String section = section(readme);

    assertThat(sectionIsComplete(readme.replace(section, ""))).as("section deleted").isFalse();
    assertThat(sectionIsComplete(readme.replace(section, section.replace("Host and Origin", "the filter")))).as("Host and Origin deleted").isFalse();
    assertThat(sectionIsComplete(readme.replace(section, section.replace("includePrompt", "the parameter")))).as("includePrompt deleted").isFalse();
    assertThat(sectionIsComplete(readme.replace(HEADING, "## Something else"))).as("heading renamed").isFalse();
  }
}
