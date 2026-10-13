package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * AC-10b: the fenced allowlist in the service README equals {@link Allowlist#PATTERNS}, entry for entry and in order. The test parses
 * the one fence under the "Read allowlist" heading; a path pattern added to the constant without the README, or the reverse, is red.
 */
class AllowlistReadmeParityTest {

  static final Path README = Path.of("README.md");

  /** The lines of the one fenced block under the "Read allowlist" heading. */
  static List<String> fencedAllowlist(String readme) {
    List<String> lines = readme.lines().toList();
    int heading = -1;
    for (int i = 0; i < lines.size(); i++) {
      if (lines.get(i).strip().equalsIgnoreCase("## Read allowlist")) {
        heading = i;
        break;
      }
    }
    assertThat(heading).as("the README has a '## Read allowlist' heading").isGreaterThanOrEqualTo(0);
    List<String> entries = new ArrayList<>();
    boolean inside = false;
    int fences = 0;
    for (int i = heading + 1; i < lines.size(); i++) {
      String line = lines.get(i);
      if (!inside && line.startsWith("## ")) {
        break;
      }
      if (line.startsWith("```")) {
        if (inside) {
          break;
        }
        inside = true;
        fences++;
        continue;
      }
      if (inside && !line.isBlank()) {
        entries.add(line.strip());
      }
    }
    assertThat(fences).as("one fenced list under the heading").isEqualTo(1);
    return entries;
  }

  private static String readme() throws IOException {
    return Files.readString(README, StandardCharsets.UTF_8);
  }

  @Test
  void theReadmeFenceEqualsTheAllowlistConstantEntryForEntryAndInOrder() throws IOException {
    assertThat(fencedAllowlist(readme())).containsExactlyElementsOf(Allowlist.PATTERNS);
  }

  @Test
  void aPatternAddedToTheConstantWithoutTheReadmeIsRed() throws IOException {
    List<String> constantWithExtra = new ArrayList<>(Allowlist.PATTERNS);
    constantWithExtra.add("kitty-specs/<mission>/tasks/WP01.md");
    assertThat(fencedAllowlist(readme())).isNotEqualTo(constantWithExtra);
  }

  @Test
  void anEntryAddedToTheReadmeWithoutTheConstantIsRed() throws IOException {
    String edited = readme().replaceFirst("```\n", "```\nkitty-specs/<mission>/tasks/WP01.md\n");
    assertThat(fencedAllowlist(edited)).isNotEqualTo(Allowlist.PATTERNS);
  }

  @Test
  void aReorderedReadmeIsRed() throws IOException {
    List<String> reordered = new ArrayList<>(fencedAllowlist(readme()));
    java.util.Collections.reverse(reordered);
    assertThat(reordered).isNotEqualTo(Allowlist.PATTERNS);
  }

  @Test
  void theReadmeStatesTheResidualToctouAndNamesNoHostPath() throws IOException {
    String text = readme();
    assertThat(text).containsIgnoringCase("final path component");
    assertThat(text).containsIgnoringCase("intermediate");
    assertThat(text).doesNotContain("/home/").doesNotContain("/Users/");
  }
}
