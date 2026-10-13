package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/** The AC-2a hook: the real check of the five shells, over the committed trees and goldens, for whichever source the caller opens. */
class Ac2aGoldenHookTest {

  @ParameterizedTest
  @ValueSource(strings = {"interleaved", "lifecycle-only", "no-ledger", "log-truncated", "crlf-and-listing"})
  void theInMemorySourceEqualsTheGoldens(String fixtureClass) {
    assertThatCode(() -> Ac2aGoldenHook.check(fixtureClass, spec -> FixtureFactory.build(spec).query())).doesNotThrowAnyException();
  }

  @ParameterizedTest
  @ValueSource(strings = {"interleaved", "lifecycle-only", "no-ledger", "log-truncated", "crlf-and-listing"})
  void theFilesystemSourceEqualsTheGoldens(String fixtureClass) {
    assertThatCode(() -> Ac2aGoldenHook.check(fixtureClass, spec -> FilesystemFixtureFactory.fromSpec(spec).query())).doesNotThrowAnyException();
  }

  @Test
  void aSourceThatLosesAMissionFailsTheCheck() {
    assertThatThrownBy(() -> Ac2aGoldenHook.check("interleaved", spec -> FixtureFactory.build(new FixtureSpec(spec.project(), spec.missions().subList(0, 1))).query()))
        .isInstanceOf(AssertionError.class)
        .hasMessageContaining("difference at");
  }

  @Test
  void aSourceThatServesAnotherLedgerFailsTheCheck() {
    assertThatThrownBy(
            () ->
                Ac2aGoldenHook.check(
                    "crlf-and-listing",
                    spec -> {
                      List<FixtureSpec.Mission> changed =
                          spec.missions().stream()
                              .map(m -> new FixtureSpec.Mission(m.name(), m.metaJson(), m.ledger() == null ? null : new String(m.ledger(), java.nio.charset.StandardCharsets.UTF_8).replace("\r\n", "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8), m.lanesJson(), m.kittifyText()))
                              .toList();
                      return FixtureFactory.build(new FixtureSpec(spec.project(), changed)).query();
                    }))
        .isInstanceOf(AssertionError.class);
  }

  @Test
  void aClassWithNoFixtureFailsInsteadOfPassingVacuously() {
    assertThatThrownBy(() -> Ac2aGoldenHook.check("no-such-class", spec -> FixtureFactory.build(spec).query())).isInstanceOf(AssertionError.class).hasMessageContaining("no fixture");
  }
}
