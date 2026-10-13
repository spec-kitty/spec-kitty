package org.speckitty.missionstatus.testsupport;

import java.util.List;
import java.util.function.Function;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The hook the AC-2a shells of {@code conformance.port} delegate to. A shell holds no assertion logic: it passes the name of its
 * fixture class and the way the selector obtains a {@link MissionStatusQuery} over a fixture description, and the hook does the rest.
 *
 * <p>For every Python-parity fixture of the class, the hook reads the committed tree as a source-neutral {@link FixtureSpec}, opens it
 * through the caller's function (so the in-memory and the filesystem source both run it), and compares the {@code Project} and the
 * first {@code MissionOverviewPage} it serves with the committed goldens by raw bytes ({@link GoldenComparison}). A class with no
 * fixture fails: an empty class must not pass.
 */
public final class Ac2aGoldenHook {

  private Ac2aGoldenHook() {}

  /**
   * @param fixtureClass the fixture class tag, for example {@code interleaved}
   * @param open how the selector realises a {@link FixtureSpec} as a {@link MissionStatusQuery}
   */
  public static void check(String fixtureClass, Function<FixtureSpec, MissionStatusQuery> open) {
    List<TreeFixture> fixtures =
        ConformanceTree.fixturesOf(fixtureClass).stream()
            .filter(fixture -> fixture.parity().equals(ConformanceTree.PARITY_GOLDEN) && !fixture.javaOnly() && !fixture.knownDivergence())
            .toList();
    if (fixtures.isEmpty()) {
      throw new AssertionError("AC-2a/" + fixtureClass + ": no fixture of this class has a golden");
    }
    for (TreeFixture fixture : fixtures) {
      GoldenComparison.verify(fixture, open.apply(FixtureTrees.specOf(fixture)));
    }
  }
}
