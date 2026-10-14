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

  /** AC-11.3: the README states the read scope of each of the eleven entries added by the amendment of FR-011. */
  @Test
  void eachNewReadmeEntryStatesItsReadScope() throws IOException {
    List<String> entries = fencedAllowlist(readme());
    assertThat(entries).hasSize(22);
    assertThat(entries.subList(11, 22)).allSatisfy(entry -> assertThat(entry).containsAnyOf("scope AUTHORED", "scope ARTIFACT"));
    assertThat(entries.subList(0, 11)).as("the existing entries keep their text").allSatisfy(entry -> assertThat(entry).doesNotContain("scope "));
  }

  /** AC-11.3: the sentence that lists what is never opened is the narrower truth now. */
  @Test
  void theNeverOpenedSentenceNoLongerNamesThePlanningFilesTheTasksOrArtifacts() throws IOException {
    String text = readme();
    int start = text.indexOf("Nothing else is opened");
    assertThat(start).as("the README still has the 'Nothing else is opened' sentence").isGreaterThanOrEqualTo(0);
    int end = text.indexOf("`<read-dir>`", start);
    assertThat(end).isGreaterThan(start);
    String sentence = text.substring(start, end);
    assertThat(sentence).doesNotContain("tasks/*.md").doesNotContain("spec.md").doesNotContain("plan.md").doesNotContainIgnoringCase("artifact").doesNotContain("WP frontmatter");
    assertThat(sentence).contains("status.json").contains("config.toml").contains("meta.json");
  }

  @Test
  void theSentenceCheckIsRedForTheOldWording() {
    String old = "Nothing else is opened: never `tasks/*.md`, `spec.md`, `plan.md`, artifacts, WP frontmatter, `status.json`. `<read-dir>` is";
    int start = old.indexOf("Nothing else is opened");
    String sentence = old.substring(start, old.indexOf("`<read-dir>`", start));
    assertThat(sentence).contains("tasks/*.md").contains("spec.md");
  }
}
