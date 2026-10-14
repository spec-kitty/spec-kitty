package org.speckitty.missionstatus.domain.redaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.redaction.TextScreen.Screened;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * J-S2a: the e-mail label run and the PEM word run are group loops, which {@code java.util.regex} recurses once per iteration. A few KB of
 * hostile text overflows the stack where Python's {@code re} does not; every question must fail closed, as a detected leak.
 */
class LeakStackOverflowTest {

  private final LeakClasses leaks = LeakPatternsFile.load();

  /** The reviewer found the overflow at about 3000 labels; the JIT shifts that threshold, so the inputs are well past it (still under the 256 KiB cap). */
  private static String hostileEmail() {
    return "see a@b" + ".b".repeat(40000);
  }

  private static String hostilePem() {
    return "-----BEGIN " + "A ".repeat(20000);
  }

  @Test
  void aStrictFieldWithAHostileEmailRunIsALeak() {
    assertThat(leaks.strictLeak(hostileEmail())).isTrue();
  }

  @Test
  void aHumanFieldWithAHostileEmailRunIsALeak() {
    assertThat(leaks.humanLeak(hostileEmail())).isTrue();
  }

  @Test
  void aHostilePemRunIsACredential() {
    assertThat(leaks.credential(hostilePem())).isTrue();
  }

  @Test
  void theTextScreenRefusesBothInputs() {
    TextScreen screen = new TextScreen(leaks);
    assertThat(screen.screen(hostileEmail())).isInstanceOf(Screened.SecretFound.class);
    assertThat(screen.screen(hostilePem())).isInstanceOf(Screened.SecretFound.class);
  }

  @Test
  void theProjectorRefusesAHumanFieldAndNullsAStrictOne() {
    assertThatThrownBy(() -> new Projector(leaks).human(hostileEmail(), "title")).isInstanceOf(ProjectionError.class);
    assertThatThrownBy(() -> new Projector(leaks).human(hostilePem(), "title")).isInstanceOf(ProjectionError.class);
    assertThat(new Projector(leaks).strict(hostileEmail(), "handle", true)).isNull();
  }

  @Test
  void ordinaryTextStillPasses() {
    assertThat(leaks.humanLeak("a plain sentence " + "word ".repeat(500))).isFalse();
    assertThat(new TextScreen(leaks).screen("fine")).isInstanceOf(Screened.Clean.class);
  }
}
