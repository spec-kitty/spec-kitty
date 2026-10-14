package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;

/** The ordered classifier of {@code schemas/ArtifactKind.yaml}: the first match wins, the file is never read (AC-5.8). */
class ArtifactKindsTest {

  private record Row(String path, ArtifactKind kind) {}

  @Test
  void theTwelveWireWordsAreTheContractEnumInOrder() {
    assertThat(Arrays.stream(ArtifactKind.values()).map(ArtifactKind::wire).toList())
        .containsExactly("review_cycle", "work_package_prompt", "spec", "plan", "tasks", "data_model", "quickstart", "analysis_report", "research", "contract", "checklist", "other");
  }

  @Test
  void theClassifierDecidesEveryRowOfTheTable() {
    List<Row> rows =
        List.of(
            new Row("tasks/WP01-x/review-cycle-1.md", ArtifactKind.REVIEW_CYCLE),
            new Row("tasks/anything/review-cycle-12.md", ArtifactKind.REVIEW_CYCLE),
            new Row("tasks/WP01-x/review-cycle-01.md", ArtifactKind.OTHER),
            new Row("tasks/WP01-x/review-cycle-0.md", ArtifactKind.OTHER),
            new Row("tasks/review-cycle-1.md", ArtifactKind.OTHER),
            new Row("tasks/a/b/review-cycle-1.md", ArtifactKind.OTHER),
            new Row("tasks/WP01-x.md", ArtifactKind.WORK_PACKAGE_PROMPT),
            new Row("tasks/WP12-name.md", ArtifactKind.WORK_PACKAGE_PROMPT),
            new Row("tasks/WP1-x.md", ArtifactKind.OTHER),
            new Row("tasks/WP01.md", ArtifactKind.OTHER),
            new Row("tasks/WP01-x.txt", ArtifactKind.OTHER),
            new Row("tasks/sub/WP01-x.md", ArtifactKind.OTHER),
            new Row("spec.md", ArtifactKind.SPEC),
            new Row("plan.md", ArtifactKind.PLAN),
            new Row("tasks.md", ArtifactKind.TASKS),
            new Row("data-model.md", ArtifactKind.DATA_MODEL),
            new Row("quickstart.md", ArtifactKind.QUICKSTART),
            new Row("analysis-report.md", ArtifactKind.ANALYSIS_REPORT),
            new Row("sub/spec.md", ArtifactKind.OTHER),
            new Row("SPEC.md", ArtifactKind.OTHER),
            new Row("research.md", ArtifactKind.RESEARCH),
            new Row("research/a.md", ArtifactKind.RESEARCH),
            new Row("research/deep/b.bin", ArtifactKind.RESEARCH),
            new Row("sub/research.md", ArtifactKind.OTHER),
            new Row("contracts/api.yaml", ArtifactKind.CONTRACT),
            new Row("contracts/deep/x.json", ArtifactKind.CONTRACT),
            new Row("checklists/requirements.md", ArtifactKind.CHECKLIST),
            new Row("notes.md", ArtifactKind.OTHER),
            new Row("meta.json", ArtifactKind.OTHER),
            new Row("a/b/c.txt", ArtifactKind.OTHER));
    for (Row row : rows) {
      assertThat(ArtifactKinds.kindOf(row.path())).as(row.path()).isEqualTo(row.kind());
    }
  }

  @Test
  void theMediaTypeFollowsTheExtensionOnlyAndIsCaseSensitive() {
    assertThat(ArtifactKinds.mediaTypeOf("a.md")).isEqualTo("text/markdown");
    assertThat(ArtifactKinds.mediaTypeOf("A.MD")).isEqualTo("text/plain");
    assertThat(ArtifactKinds.mediaTypeOf("x/meta.json")).isEqualTo("application/json");
    assertThat(ArtifactKinds.mediaTypeOf("a.yaml")).isEqualTo("application/yaml");
    assertThat(ArtifactKinds.mediaTypeOf("a.yml")).isEqualTo("application/yaml");
    assertThat(ArtifactKinds.mediaTypeOf("status.events.jsonl")).isEqualTo("application/x-ndjson");
    assertThat(ArtifactKinds.mediaTypeOf("a.csv")).isEqualTo("text/csv");
    assertThat(ArtifactKinds.mediaTypeOf("a.txt")).isEqualTo("text/plain");
    assertThat(ArtifactKinds.mediaTypeOf("noextension")).isEqualTo("text/plain");
    assertThat(ArtifactKinds.mediaTypeOf("dir.md/file")).isEqualTo("text/plain");
    assertThat(ArtifactKinds.mediaTypeOf(".md")).isEqualTo("text/markdown");
  }
}
