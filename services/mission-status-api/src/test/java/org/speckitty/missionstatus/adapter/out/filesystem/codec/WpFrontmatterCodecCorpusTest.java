package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * AC-6.1 at the codec: every Work Package file of the committed corpus {@code wpm-01..28} decodes to the outcome class the table below
 * names, and the table agrees with the oracle's stored goldens (a file the oracle parsed is parsed here, one it skipped is rejected
 * here). The cases that need no file (22, a directory, and 23, a link) have no regular candidate.
 */
class WpFrontmatterCodecCorpusTest {

  private static final String PARSED = "parsed";

  /** The expected outcome per fixture: {@code parsed}, or the rejection class. Fixture {@code wpm-NN} is case NN of AC-6.1. */
  private static final Map<String, String> EXPECTED =
      Map.ofEntries(
          Map.entry("wpm-01", PARSED), Map.entry("wpm-02", PARSED), Map.entry("wpm-03", PARSED),
          Map.entry("wpm-04", "NO_FRONTMATTER"), Map.entry("wpm-05", "NO_CLOSING_DELIMITER"), Map.entry("wpm-06", "YAML_SYNTAX"),
          Map.entry("wpm-07", "DUPLICATE_KEY"), Map.entry("wpm-08", "NOT_A_MAPPING"), Map.entry("wpm-09", "VALIDATION"),
          Map.entry("wpm-10", "VALIDATION"), Map.entry("wpm-11", PARSED), Map.entry("wpm-12", PARSED), Map.entry("wpm-13", PARSED),
          Map.entry("wpm-14", PARSED), Map.entry("wpm-15", PARSED), Map.entry("wpm-16", "VALIDATION"), Map.entry("wpm-17", "VALIDATION"),
          Map.entry("wpm-18", "VALIDATION"), Map.entry("wpm-19", "VALIDATION"), Map.entry("wpm-20", "VALIDATION"), Map.entry("wpm-21", PARSED),
          Map.entry("wpm-24", "NOT_UTF8"), Map.entry("wpm-25", "NOT_UTF8"), Map.entry("wpm-26", "NOT_UTF8"),
          Map.entry("wpm-27", PARSED), Map.entry("wpm-28", PARSED));

  private static List<TreeFixture> corpus() {
    return ConformanceTree.detailFixtures().stream().filter(fixture -> fixture.tag().equals("wp-malformed-frontmatter")).toList();
  }

  private static List<Path> candidateFiles(TreeFixture fixture) throws IOException {
    Path tasks = fixture.dir().resolve("kitty-specs/alpha-mission/tasks");
    if (!Files.isDirectory(tasks)) {
      return List.of();
    }
    try (Stream<Path> entries = Files.list(tasks)) {
      return entries.filter(Files::isRegularFile).filter(path -> path.getFileName().toString().startsWith("WP")).sorted().toList();
    }
  }

  @SuppressWarnings("unchecked")
  private static boolean oracleParsed(TreeFixture fixture) {
    byte[] golden = ConformanceTree.golden(fixture, "get-work-package.json");
    return !((Map<String, Object>) CanonicalJson.parse(golden)).isEmpty();
  }

  @Test
  void theCorpusHoldsTwentyEightFixtures() {
    assertThat(corpus()).hasSize(28);
  }

  @Test
  void everyFileOfTheCorpusDecodesToItsNamedOutcome() throws IOException {
    List<String> failures = new ArrayList<>();
    int decoded = 0;
    for (TreeFixture fixture : corpus()) {
      String expected = EXPECTED.get(fixture.name());
      List<Path> files = candidateFiles(fixture);
      if (expected == null) {
        assertThat(files).as("%s has no regular candidate (provisioned or directory case)", fixture.name()).isEmpty();
        continue;
      }
      assertThat(files).as(fixture.name()).isNotEmpty();
      for (Path file : files) {
        FrontmatterResult result = WpFrontmatterCodec.decode(Files.readAllBytes(file));
        decoded++;
        String actual = result instanceof FrontmatterResult.Rejected rejected ? rejected.kind().name() : PARSED;
        if (!actual.equals(expected)) {
          failures.add(fixture.name() + "/" + file.getFileName() + ": " + actual + " but " + expected);
        }
      }
    }
    assertThat(failures).isEmpty();
    assertThat(decoded).as("control: files were decoded").isGreaterThanOrEqualTo(26);
  }

  @Test
  void theTableAgreesWithWhatTheOracleParsed() throws IOException {
    for (TreeFixture fixture : corpus()) {
      String expected = EXPECTED.get(fixture.name());
      if (expected == null) {
        assertThat(oracleParsed(fixture)).as("%s: the oracle serves nothing", fixture.name()).isFalse();
      } else {
        assertThat(oracleParsed(fixture)).as("%s: oracle parsed iff the codec does", fixture.name()).isEqualTo(expected.equals(PARSED));
      }
    }
  }

  @Test
  void theByteOrderMarkFixtureAndTheCrLfFixtureDecodeToTheSameMetadataAsThePlainOne() throws IOException {
    FrontmatterResult plain = decodeOf("wpm-01");
    assertThat(decodeOf("wpm-02")).isEqualTo(plain);
    FrontmatterResult.Parsed crlf = (FrontmatterResult.Parsed) decodeOf("wpm-03");
    assertThat(crlf.metadata()).isEqualTo(((FrontmatterResult.Parsed) plain).metadata());
    assertThat(crlf.body()).as("the body of a CRLF file has line feeds only").doesNotContain("\r");
  }

  private static FrontmatterResult decodeOf(String name) throws IOException {
    TreeFixture fixture = corpus().stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
    return WpFrontmatterCodec.decode(Files.readAllBytes(candidateFiles(fixture).get(0)));
  }
}
