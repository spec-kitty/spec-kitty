package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;

/** The selector is the one place that picks a source; an override is honoured and restored. */
class PortSourceSelectorTest {

  private static final FixtureSpec SPEC = FixtureSpec.of(FixtureSpec.Mission.of("alpha", Rows.meta(Rows.ALPHA_ID, "alpha", "2026-09-02T10:00:00+00:00"), null));

  @Test
  void theDefaultIsTheInMemorySource() {
    assertThat(PortSourceSelector.isDefault()).isTrue();
    assertThat(PortSourceSelector.open(SPEC)).isInstanceOf(FixtureFactory.Built.class);
    assertThat(PortSourceSelector.open(SPEC).query().project().missionCount()).isEqualTo(1);
  }

  @Test
  void anOverrideIsHonouredAndRestoredAfterwards() throws Exception {
    Fixture marker = new Fixture() {
      @Override
      public MissionStatusQuery query() {
        return null;
      }

      @Override
      public List<org.speckitty.missionstatus.domain.model.Diagnostic> diagnostics() {
        return List.of();
      }
    };

    try (AutoCloseable installed = PortSourceSelector.override(spec -> marker)) {
      assertThat(PortSourceSelector.isDefault()).isFalse();
      assertThat(PortSourceSelector.open(SPEC)).isSameAs(marker);
    }

    assertThat(PortSourceSelector.isDefault()).isTrue();
    assertThat(PortSourceSelector.open(SPEC)).isNotSameAs(marker);
  }

  @Test
  void nestedOverridesUnwindInOrder() throws Exception {
    Fixture one = FixtureFactory.build(SPEC);
    Fixture two = FixtureFactory.build(SPEC);

    try (AutoCloseable outer = PortSourceSelector.override(spec -> one)) {
      try (AutoCloseable inner = PortSourceSelector.override(spec -> two)) {
        assertThat(PortSourceSelector.open(SPEC)).isSameAs(two);
      }
      assertThat(PortSourceSelector.open(SPEC)).isSameAs(one);
    }
    assertThat(PortSourceSelector.isDefault()).isTrue();
  }
}
