package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class CaseSensitiveHostTest {

  private static Path report() {
    return ScratchDirs.create().resolve("reports").resolve("not-run.txt");
  }

  @Test
  void onACaseInsensitiveHostTheCasePairFixtureIsLeftOutAndTheLineIsWritten() throws IOException {
    Path report = report();

    assertThat(CaseSensitiveHost.comparable("artifacts-sort/artifacts-sort", false, report)).isFalse();

    assertThat(Files.readAllLines(report)).containsExactly("not run: case-insensitive file system: artifacts-sort/artifacts-sort");
  }

  @Test
  void onACaseInsensitiveHostEveryOtherFixtureIsStillCompared() {
    Path report = report();

    assertThat(CaseSensitiveHost.comparable("artifacts-populated/artifacts-populated", false, report)).isTrue();

    assertThat(report).doesNotExist();
  }

  @Test
  void onACaseSensitiveHostNothingIsLeftOutAndNothingIsWritten() {
    Path report = report();

    assertThat(CaseSensitiveHost.comparable("artifacts-sort/artifacts-sort", true, report)).isTrue();

    assertThat(report).doesNotExist();
  }

  @Test
  void theProbeAgreesWithTheFileSystemItRanOn() throws IOException {
    Path dir = ScratchDirs.create();
    Files.createFile(dir.resolve("Probe"));

    assertThat(CaseSensitiveHost.isCaseSensitive()).isEqualTo(!Files.exists(dir.resolve("probe")));
  }
}
