package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.OptionalInt;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * {@link CycleNames}: the file-name rule {@code ^review-cycle-([1-9][0-9]*)\.md$} of the oracle and the pointer its {@code cycle_pointer}
 * builds; each pointer row was run through the product's builder and validator.
 */
class CycleNamesTest {

  @Test
  void aCycleNumberIsReadNumerically() {
    assertThat(CycleNames.cycleNumber("review-cycle-1.md")).isEqualTo(OptionalInt.of(1));
    assertThat(CycleNames.cycleNumber("review-cycle-9.md")).isEqualTo(OptionalInt.of(9));
    assertThat(CycleNames.cycleNumber("review-cycle-10.md")).isEqualTo(OptionalInt.of(10));
    assertThat(CycleNames.cycleNumber("review-cycle-123456789.md")).isEqualTo(OptionalInt.of(123456789));
  }

  @Test
  void aNameThatIsNoCycleFileHasNoNumber() {
    for (String name :
        new String[] {
          "review-cycle-0.md", "review-cycle-01.md", "review-cycle-.md", "review-cycle-1.md ", "review-cycle-1.MD", "Review-cycle-1.md", "review-cycle-1a.md",
          "review-cycle-\u0661.md", "review-cycle-1.txt", "review-cycle-1", "x-review-cycle-1.md", "review-cycle-1.md\n", "", "review-cycle-2147483648.md"
        }) {
      assertThat(CycleNames.cycleNumber(name)).as(name).isEmpty();
    }
  }

  @Test
  void aNumberTooLargeForTheServedIntegerIsACycleNameWithNoNumber() {
    assertThat(CycleNames.cycleNumber("review-cycle-2147483647.md")).isEqualTo(OptionalInt.of(Integer.MAX_VALUE));
    assertThat(CycleNames.cycleNumber("review-cycle-1234567890.md")).isEqualTo(OptionalInt.of(1_234_567_890));
    for (String name : new String[] {"review-cycle-2147483648.md", "review-cycle-99999999999999999999.md"}) {
      assertThat(CycleNames.cycleNumber(name)).as(name).isEmpty();
      assertThat(CycleNames.isCycleName(name)).as(name).isTrue();
    }
    for (String name : new String[] {"review-cycle-0.md", "review-cycle-01.md", "review-cycle-1a.md", "review-cycle-.md", "review-cycle-1.txt"}) {
      assertThat(CycleNames.isCycleName(name)).as(name).isFalse();
    }
  }

  @ParameterizedTest
  @CsvSource({
    "alpha,WP01-x,review-cycle-1.md,review-cycle://alpha/WP01-x/review-cycle-1.md",
    "a_b-c.d,WP01,review-cycle-10.md,review-cycle://a_b-c.d/WP01/review-cycle-10.md"
  })
  void aSafePointerIsBuilt(String mission, String workPackage, String file, String pointer) {
    assertThat(CycleNames.pointer(mission, workPackage, file)).isEqualTo(pointer);
  }

  @Test
  void aSegmentTheProductRefusesGivesNoPointer() {
    assertThat(CycleNames.pointer("al pha", "WP01", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("alpha", "WP01..x", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer(".alpha", "WP01", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("alpha", "WP01 ", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("alpha\n", "WP01", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("\u00e9", "WP01", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("a", "-b", "review-cycle-1.md")).isNull();
    assertThat(CycleNames.pointer("a/b", "WP01", "review-cycle-1.md")).isNull();
  }

  @Test
  void aFileNameThatIsNoCycleFileGivesNoPointer() {
    assertThat(CycleNames.pointer("alpha", "WP01", "review-cycle-01.md")).isNull();
    assertThat(CycleNames.pointer("alpha", "WP01", "review-cycle-0.md")).isNull();
    assertThat(CycleNames.pointer("alpha", "WP01", "review-cycle-1.md ")).isNull();
  }
}
