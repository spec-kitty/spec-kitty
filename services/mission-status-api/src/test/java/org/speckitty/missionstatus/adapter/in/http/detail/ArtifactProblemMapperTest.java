package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.speckitty.missionstatus.adapter.in.http.ProblemBody;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.springframework.http.ResponseEntity;

/**
 * The named edit of {@code ProblemMapper} that the artifact goldens force: the Problem of every artifact refusal equals the contract's
 * {@code ArtifactRefusal} example for its code, member by member, and names no path, value or enum name.
 */
class ArtifactProblemMapperTest {

  private static final Path EXAMPLES = Path.of("..", "..", "contracts", "mission-status", "examples");

  /** The flat {@code key: value} lines of one example file. */
  private static Map<String, String> example(Path file) throws IOException {
    Map<String, String> members = new LinkedHashMap<>();
    for (String line : Files.readAllLines(file, StandardCharsets.UTF_8)) {
      int colon = line.indexOf(": ");
      if (colon > 0) {
        members.put(line.substring(0, colon), line.substring(colon + 2));
      }
    }
    return members;
  }

  @Test
  void everyArtifactRefusalEqualsTheContractExampleOfItsCode() throws IOException {
    List<Path> files;
    try (Stream<Path> found = Files.list(EXAMPLES)) {
      files = found.filter(path -> path.getFileName().toString().startsWith("ArtifactRefusal.")).sorted().toList();
    }
    assertThat(files).as("the seven examples of ArtifactRefusal").hasSize(7);
    for (Path file : files) {
      Map<String, String> expected = example(file);
      DetailRefusal.Kind kind = java.util.Arrays.stream(DetailRefusal.Kind.values()).filter(candidate -> candidate.wire().equals(expected.get("code"))).findFirst().orElseThrow();

      ResponseEntity<ProblemBody> response = ProblemMapper.artifact(new DetailRefusal(kind));
      ProblemBody body = response.getBody();

      assertThat(body.code()).as(file.getFileName().toString()).isEqualTo(expected.get("code"));
      assertThat(body.type()).isEqualTo(expected.get("type")).isEqualTo("about:blank");
      assertThat(body.title()).isEqualTo(expected.get("title"));
      assertThat(body.detail()).isEqualTo(expected.get("detail"));
      assertThat(body.status()).isEqualTo(Integer.parseInt(expected.get("status")));
      assertThat(response.getStatusCode().value()).isEqualTo(body.status());
      assertThat(response.getHeaders().getContentType()).hasToString("application/problem+json");
    }
  }

  @ParameterizedTest
  @EnumSource(DetailRefusal.Kind.class)
  void noKindNamesAPathAFileOrAnEnum(DetailRefusal.Kind kind) {
    ProblemBody body = ProblemMapper.artifact(new DetailRefusal(kind)).getBody();
    String all = body.code() + "|" + body.title() + "|" + body.detail();

    assertThat(all).doesNotContain("kitty-specs", "NOT_FOUND", "ARTIFACT_", "Exception", "\\", System.getProperty("user.home"));
  }

  @Test
  void aKindThatIsNotAnArtifactRefusalGetsTheGenericTextAndTheGenericDetailIsUnchanged() {
    ProblemBody generic = ProblemMapper.detail(new DetailRefusal(DetailRefusal.Kind.SOURCE_UNREADABLE)).getBody();

    assertThat(ProblemMapper.artifact(new DetailRefusal(DetailRefusal.Kind.SOURCE_UNREADABLE)).getBody()).isEqualTo(generic);
    assertThat(generic.type()).isNull();
    assertThat(ProblemMapper.detail(new DetailRefusal(DetailRefusal.Kind.NOT_FOUND)).getBody().title()).isEqualTo("The resource was not found.");
  }
}
