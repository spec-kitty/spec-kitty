package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/** The fenced list under the README's "Artifact read allowlist" heading equals {@link ArtifactAllowlist#PATTERNS}, entry for entry and in order. */
class ArtifactAllowlistReadmeParityTest {

  private static final String HEADING = "## Artifact read allowlist";

  private static String readme() throws IOException {
    return Files.readString(AllowlistReadmeParityTest.README, StandardCharsets.UTF_8);
  }

  @Test
  void theReadmeListEqualsTheConstant() throws IOException {
    assertThat(AllowlistReadmeParityTest.fencedAllowlist(readme(), HEADING)).containsExactlyElementsOf(ArtifactAllowlist.PATTERNS);
  }

  @Test
  void anEntryAddedToOneSideOnlyIsCaught() throws IOException {
    List<String> withExtra = new ArrayList<>(ArtifactAllowlist.PATTERNS);
    withExtra.add(".kittify/config.yaml");
    assertThat(AllowlistReadmeParityTest.fencedAllowlist(readme(), HEADING)).isNotEqualTo(withExtra);
    String edited = readme().replace("kitty-specs/ (names only)\nkitty-specs/<mission>/meta.json", "kitty-specs/ (names only)\n.git/HEAD\nkitty-specs/<mission>/meta.json");
    assertThat(edited).isNotEqualTo(readme());
    assertThat(AllowlistReadmeParityTest.fencedAllowlist(edited, HEADING)).isNotEqualTo(ArtifactAllowlist.PATTERNS);
  }

  @Test
  void theStatusAllowlistStillNamesNoArtifact() throws IOException {
    assertThat(AllowlistReadmeParityTest.fencedAllowlist(readme())).containsExactlyElementsOf(Allowlist.PATTERNS);
    assertThat(Allowlist.PATTERNS).noneMatch(pattern -> pattern.contains("<path>"));
  }
}
