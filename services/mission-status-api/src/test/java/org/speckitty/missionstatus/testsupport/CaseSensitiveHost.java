package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;

/**
 * The file-system precondition of a fixture that holds two names differing only in case ({@code Sub/} and {@code sub/} in
 * {@code artifacts-sort}, which pins UTF-8 byte order on purpose). A case-insensitive checkout (macOS, Windows) merges them into one
 * directory, so the fixture on disk is not the fixture the golden describes. {@link #comparable} leaves such a fixture out of a
 * comparison and writes {@code not run: case-insensitive file system: <fixture key>} to the not-run report; a skip is never a pass.
 */
public final class CaseSensitiveHost {

  /** The keys of the fixtures that hold a case-only name pair (found by a case-folded scan of the committed tree). */
  static final Set<String> CASE_PAIR_FIXTURES = Set.of("artifacts-sort/artifacts-sort");

  private static Boolean sensitive;

  private CaseSensitiveHost() {}

  /** Whether the scratch file system tells {@code Probe} from {@code probe}; probed once per JVM. */
  public static synchronized boolean isCaseSensitive() {
    if (sensitive == null) {
      try {
        Path dir = ScratchDirs.create();
        Files.createFile(dir.resolve("Probe"));
        sensitive = !Files.exists(dir.resolve("probe"));
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }
    return sensitive;
  }

  /** False, with the not-run line written, when the fixture holds a case-only name pair and this host is case-insensitive. */
  public static boolean comparable(String fixtureKey) {
    return comparable(fixtureKey, isCaseSensitive(), NotRun.DEFAULT_FILE);
  }

  static boolean comparable(String fixtureKey, boolean caseSensitive, Path report) {
    if (caseSensitive || !CASE_PAIR_FIXTURES.contains(fixtureKey)) {
      return true;
    }
    NotRun.record(report, "not run: case-insensitive file system: " + fixtureKey);
    return false;
  }
}
