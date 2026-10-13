package org.speckitty.missionstatus.testsupport;

import java.util.function.Function;
import org.opentest4j.TestAbortedException;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;

/**
 * The hook the AC-2a shells of {@code conformance.port} delegate to. A shell holds no assertion logic: it passes the name of its
 * fixture class and the way the selector obtains a {@link MissionStatusQuery} over a fixture description, and the hook does the rest.
 *
 * <p>This is the stub of phase 2a. It reports "not yet backed by goldens" by aborting the test (an assumption failure, so the test is
 * skipped), because the goldens are the Python oracle's output of another work package. The golden work package replaces the body with
 * the real check over the committed fixture trees and goldens, inside this package, so the shells never change.
 */
public final class Ac2aGoldenHook {

  private Ac2aGoldenHook() {}

  /**
   * @param fixtureClass the fixture class tag, for example {@code interleaved}
   * @param open how the selector realises a {@link FixtureSpec} as a {@link MissionStatusQuery}
   */
  public static void check(String fixtureClass, Function<FixtureSpec, MissionStatusQuery> open) {
    throw new TestAbortedException("AC-2a/" + fixtureClass + ": not yet backed by goldens");
  }
}
