package org.speckitty.missionstatus.domain.readmodel.overview;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.List;
import java.util.function.Predicate;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

class ProjectHeaderDeriverTest {

  /** The three strict host-path patterns of leak-patterns.json (the production predicate is built by the caller from that file). */
  private static final List<Pattern> HOST_PATHS =
      List.of(
          Pattern.compile("^(?:/|~/|[A-Za-z]:[\\\\/])", Pattern.UNICODE_CHARACTER_CLASS),
          Pattern.compile("(?:^|/)(?:home|Users)/[^/\\s]+/", Pattern.UNICODE_CHARACTER_CLASS),
          Pattern.compile("[A-Za-z]:\\\\Users\\\\", Pattern.UNICODE_CHARACTER_CLASS));
  private static final Predicate<String> HOST_PATH = text -> HOST_PATHS.stream().anyMatch(p -> p.matcher(text).find());

  private static ProjectHeader header(String version, Integer schema, String branch) {
    return ProjectHeaderDeriver.derive("fixture-project", version, schema, branch, HOST_PATH, 1, List.of("2026-09-01T10:01:00Z"));
  }

  @Test
  void aHealthyProject() {
    ProjectHeader header = header("4.0.0", 3, "main");
    assertThat(header.name()).isEqualTo("fixture-project");
    assertThat(header.missionCount()).isEqualTo(1);
    assertThat(header.specKittyVersion()).isEqualTo("4.0.0");
    assertThat(header.schemaVersion()).isEqualTo(3);
    assertThat(header.health()).isEqualTo(Health.HEALTHY);
    assertThat(header.currentBranch()).isEqualTo("main");
    assertThat(header.lastActivityAt()).isEqualTo("2026-09-01T10:01:00Z");
  }

  @Test
  void missingMetadataIsNullAndNotHealthy() {
    ProjectHeader header = header(null, null, "main");
    assertThat(header.specKittyVersion()).isNull();
    assertThat(header.schemaVersion()).isNull();
    assertThat(header.health()).isEqualTo(Health.SCHEMA_DRIFT);
  }

  @Test
  void aSchemaOutsideTheSupportedRangeIsDriftAndStillServed() {
    ProjectHeader above = header("4.0.0", 99, "main");
    assertThat(above.health()).isEqualTo(Health.SCHEMA_DRIFT);
    assertThat(above.schemaVersion()).isEqualTo(99);
    assertThat(header("4.0.0", 2, "main").health()).isEqualTo(Health.SCHEMA_DRIFT);
    assertThat(Health.HEALTHY.wire()).isEqualTo("healthy");
    assertThat(Health.SCHEMA_DRIFT.wire()).isEqualTo("schema_drift");
  }

  @Test
  void theVersionMustMatchTheContractPattern() {
    assertThat(header("4.0.0rc5+local_1", 3, "main").specKittyVersion()).isEqualTo("4.0.0rc5+local_1");
    assertThat(header("", 3, "main").specKittyVersion()).isNull();
    assertThat(header("not a version", 3, "main").specKittyVersion()).isNull();
    assertThat(header(".4.0", 3, "main").specKittyVersion()).isNull();
    assertThat(header("1".repeat(64), 3, "main").specKittyVersion()).isNotNull();
    assertThat(header("1".repeat(65), 3, "main").specKittyVersion()).isNull();
  }

  @Test
  void aBranchNameIsServedOnlyWhenItMeetsEveryRule() {
    assertThat(header("4.0.0", 3, "unborn/topic").currentBranch()).isEqualTo("unborn/topic");
    assertThat(header("4.0.0", 3, "a".repeat(255)).currentBranch()).hasSize(255);
    assertThat(header("4.0.0", 3, null).currentBranch()).isNull();
    assertThat(header("4.0.0", 3, "").currentBranch()).isNull();
    assertThat(header("4.0.0", 3, ".hidden-topic").currentBranch()).isNull();
    assertThat(header("4.0.0", 3, "a".repeat(256)).currentBranch()).isNull();
    assertThat(header("4.0.0", 3, "home/someone/topic").currentBranch()).isNull();
    assertThat(header("4.0.0", 3, "feature/with space").currentBranch()).isNull();
  }

  @Test
  void lastActivityIsTheLatestInstantOfTheListedMissions() {
    List<String> activity = Arrays.asList("2026-09-01T10:30:00+02:00", null, "2026-09-01T09:00:00Z");
    assertThat(ProjectHeaderDeriver.derive("p", "4.0.0", 3, "main", HOST_PATH, 3, activity).lastActivityAt()).isEqualTo("2026-09-01T09:00:00Z");
    assertThat(ProjectHeaderDeriver.derive("p", "4.0.0", 3, "main", HOST_PATH, 0, List.of()).lastActivityAt()).isNull();
    assertThat(ProjectHeaderDeriver.derive("p", "4.0.0", 3, "main", HOST_PATH, 2, Arrays.asList(null, null)).lastActivityAt()).isNull();
  }
}
