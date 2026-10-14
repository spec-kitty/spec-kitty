package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.RecordComponent;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.WpMetadata;

/** D-76 and FRESH3-007: the index record never holds the body of a file, directly or through the metadata it holds. */
class IndexedWorkPackageShapeTest {

  private static final List<String> BODY_NAMES = List.of("body", "prompt", "markdown", "content", "text", "bytes");

  private static void assertNoBody(Class<? extends Record> type) {
    for (RecordComponent component : type.getRecordComponents()) {
      String name = component.getName().toLowerCase(Locale.ROOT);
      assertThat(BODY_NAMES.stream().noneMatch(name::contains)).as("%s.%s is not named like a body", type.getSimpleName(), component.getName()).isTrue();
      assertThat(component.getType()).as("%s.%s is not a byte array", type.getSimpleName(), component.getName()).isNotEqualTo(byte[].class);
      assertThat(component.getType().isArray()).as("%s.%s is no array", type.getSimpleName(), component.getName()).isFalse();
    }
  }

  @Test
  void noComponentOfTheIndexedWorkPackageIsABody() {
    assertNoBody(IndexedWorkPackage.class);
    assertThat(Arrays.stream(IndexedWorkPackage.class.getRecordComponents()).map(RecordComponent::getName)).containsExactly("id", "fileName", "metadata");
  }

  @Test
  void noComponentOfTheMetadataTheEntryHoldsIsABodyEither() {
    assertNoBody(WpMetadata.class);
  }

  @Test
  void theCheckIsNotVacuousItWouldCatchABodyComponent() {
    record Bad(String body) {}
    record BadBytes(byte[] raw) {}
    record Prompt(String promptMarkdown) {}
    for (Class<? extends Record> type : List.of(Bad.class, BadBytes.class, Prompt.class)) {
      boolean flagged = false;
      try {
        assertNoBody(type);
      } catch (AssertionError caught) {
        flagged = true;
      }
      assertThat(flagged).as(type.getSimpleName()).isTrue();
    }
  }

  @Test
  void theBodyTravelsBesideTheEntriesInTheResultAndInNoEntry() {
    assertThat(Arrays.stream(WorkPackageIndex.Result.class.getRecordComponents()).map(RecordComponent::getName)).containsExactly("workPackages", "capturedBody");
  }
}
