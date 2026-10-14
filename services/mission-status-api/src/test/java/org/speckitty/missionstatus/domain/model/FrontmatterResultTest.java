package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.FrontmatterResult.RejectionClass;

class FrontmatterResultTest {

  private static final WpMetadata METADATA = new WpMetadata("WP01", null, null, null, null, null, null, null, null, null, null, List.of(), List.of(), List.of(), List.of(), List.of(), false);

  @Test
  void theTwoVariantsAreDistinctAndEqualByValue() {
    FrontmatterResult parsed = new FrontmatterResult.Parsed(METADATA, "body");
    FrontmatterResult rejected = new FrontmatterResult.Rejected(RejectionClass.VALIDATION);
    assertThat(parsed).isEqualTo(new FrontmatterResult.Parsed(METADATA, "body")).isNotEqualTo(rejected);
    assertThat(rejected).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.VALIDATION)).isNotEqualTo(new FrontmatterResult.Rejected(RejectionClass.NOT_UTF8));
  }

  @Test
  void aVariantRefusesNullMembers() {
    assertThatNullPointerException().isThrownBy(() -> new FrontmatterResult.Parsed(null, ""));
    assertThatNullPointerException().isThrownBy(() -> new FrontmatterResult.Parsed(METADATA, null));
    assertThatNullPointerException().isThrownBy(() -> new FrontmatterResult.Rejected(null));
  }

  @Test
  void aSwitchOverTheSealedInterfaceIsExhaustive() {
    FrontmatterResult result = new FrontmatterResult.Rejected(RejectionClass.NO_FRONTMATTER);
    String name =
        switch (result) {
          case FrontmatterResult.Parsed parsed -> "parsed";
          case FrontmatterResult.Rejected rejected -> rejected.kind().name();
        };
    assertThat(name).isEqualTo("NO_FRONTMATTER");
    assertThat(RejectionClass.values()).hasSize(8);
  }
}
