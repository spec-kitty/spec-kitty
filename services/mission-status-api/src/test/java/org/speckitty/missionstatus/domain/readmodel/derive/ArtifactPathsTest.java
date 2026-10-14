package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

/** The artifact-path rule of {@code contracts/mission-status/schemas/ArtifactPath.yaml}, one owner for the index, the cycles and the routes (D-111). */
class ArtifactPathsTest {

  private static final Path SCHEMA = Path.of("../../contracts/mission-status/schemas/ArtifactPath.yaml");

  @Test
  void aCleanRelativePathIsValid() {
    for (String path : List.of("spec.md", "tasks/WP01-example.md", "notes/with space.md", "a+b", "%2e%2e", ".hidden", "home/x", "caf\u00e9/\u00fc.md", "user@host.md", "a.b/c.d", "...", "a..b", "tasks/WP01-x/review-cycle-1.md")) {
      assertThat(ArtifactPaths.isValid(path)).as(path).isTrue();
    }
  }

  @Test
  void theRefusedShapesAreEachRefused() {
    List<String> refused =
        List.of(
            "",
            "/abs",
            "a//b",
            "a/",
            "/",
            "a\\b",
            "a\u0000b",
            "a\nb",
            "a\rb",
            "a\u000bb",
            "a\u000cb",
            "a\u001cb",
            "a\u001db",
            "a\u001eb",
            "a\u0085b",
            "a\u2028b",
            "a\u2029b",
            "~/x",
            "C:x",
            "c:/x",
            "z:",
            ".",
            "..",
            "a/./b",
            "a/../b",
            "../x",
            "./x",
            "a/..",
            "a/.");
    for (String path : refused) {
      assertThat(ArtifactPaths.isValid(path)).as(path.replace("\n", "\\n")).isFalse();
    }
    assertThat(ArtifactPaths.isValid(null)).isFalse();
  }

  @Test
  void theLengthBoundIsFiveHundredAndTwelveCharacters() {
    assertThat(ArtifactPaths.isValid("a".repeat(512))).isTrue();
    assertThat(ArtifactPaths.isValid("a".repeat(513))).isFalse();
    assertThat(ArtifactPaths.isValid(("a/".repeat(255)) + "ab")).as("512 characters with separators").isTrue();
    assertThat(ArtifactPaths.isValid("\ud83d\ude00".repeat(512))).as("512 code points, 1024 chars").isTrue();
    assertThat(ArtifactPaths.isValid("\ud83d\ude00".repeat(513))).isFalse();
  }

  @Test
  void aReplacementCharacterAndAnUnpairedSurrogateAreRefused() {
    assertThat(ArtifactPaths.isValid("a\ufffdb")).isFalse();
    assertThat(ArtifactPaths.isValid("\ud800")).isFalse();
    assertThat(ArtifactPaths.isValid("a\udc00b")).isFalse();
    assertThat(ArtifactPaths.isValid("ok\ud83d\ude00")).isTrue();
    assertThat(ArtifactPaths.hasReplacementCharacter("x\ufffd")).isTrue();
    assertThat(ArtifactPaths.hasReplacementCharacter("x")).isFalse();
  }

  @Test
  void aRequestValueTheHttpLayerDecodedOnceIsJudgedAsItIs() {
    assertThat(ArtifactPaths.isValid("%252e%252e")).as("a literal name, never traversal").isTrue();
    assertThat(ArtifactPaths.isValid("%2e%2e")).isTrue();
    assertThat(ArtifactPaths.isValid("a+b")).isTrue();
    assertThat(ArtifactPaths.isValid("a b")).isTrue();
    assertThat(ArtifactPaths.isValid("a/")).as("a trailing slash").isFalse();
    assertThat(ArtifactPaths.isValid("spec.md")).isTrue();
  }

  /** The rule decides what the schema's own pattern decides, string for string, except for the two extra refusals (U+FFFD, unpaired surrogate). */
  @Test
  void theRuleAgreesWithTheSchemaPatternOnACorpus() throws IOException {
    assertThat(SCHEMA).as("the contract schema is reachable from the service directory").exists();
    Matcher found = Pattern.compile("(?m)^pattern: '(.*)'$").matcher(Files.readString(SCHEMA, StandardCharsets.UTF_8));
    assertThat(found.find()).as("the schema carries a pattern line").isTrue();
    Pattern pattern = Pattern.compile(found.group(1).replace("''", "'"));
    List<String> corpus =
        List.of(
            "spec.md", "a/b", "a//b", "/a", "a/", "..", ".", "a/..", "a/../b", "~/x", "~x", "C:", "C:/x", "ab:c", "a\\b", "a\nb", "a\u0085b", "a\u2028b", "a\u00a0b",
            "...", ".a", "a.", "a/.b/c", "home/home", " ", "a b", "a\tb", "\u00e9", "x@y", "a\u0000", "a\u001fb", "a\u001cb", "1:x", "aa:x", "a/b:c", "a/./", "./", "/.", "a/..b", "a/b..");
    for (String candidate : corpus) {
      assertThat(ArtifactPaths.isValid(candidate)).as(candidate.replace("\n", "\\n")).isEqualTo(pattern.matcher(candidate).find() && candidate.length() >= 1 && candidate.length() <= 512);
    }
  }
}
