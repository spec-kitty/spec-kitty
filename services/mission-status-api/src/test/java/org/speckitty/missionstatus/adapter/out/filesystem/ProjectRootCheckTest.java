package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ProjectRootCheckTest {

  @Test
  void anAbsentValueIsRefusedAsUnset() {
    assertThat(ProjectRootCheck.refusal(null)).hasValueSatisfying(m -> assertThat(m).contains("project root unset"));
  }

  @Test
  void aBlankValueIsRefusedAsUnset() {
    assertThat(ProjectRootCheck.refusal("   ")).hasValueSatisfying(m -> assertThat(m).contains("project root unset"));
  }

  @Test
  void aValueThatIsNotADirectoryIsRefusedNamingTheKeyAndNeverTheOperatingSystemMessage(@TempDir Path dir) throws Exception {
    Path file = Files.writeString(dir.resolve("a-file"), "x");

    assertThat(ProjectRootCheck.refusal(file.toString()))
        .hasValueSatisfying(m -> assertThat(m).contains("mission-status.project-root").contains("not a directory").doesNotContain("No such"));
    assertThat(ProjectRootCheck.refusal(dir.resolve("missing").toString()))
        .hasValueSatisfying(m -> assertThat(m).contains("mission-status.project-root").contains("not a directory"));
  }

  @Test
  void aValueThatIsNotAPathAtAllIsRefusedLikeANonDirectory() {
    assertThat(ProjectRootCheck.refusal("bad\0path")).hasValueSatisfying(m -> assertThat(m).contains("not a directory"));
  }

  @Test
  void anExistingDirectoryIsAccepted(@TempDir Path dir) {
    assertThat(ProjectRootCheck.refusal(dir.toString())).isEmpty();
  }
}
