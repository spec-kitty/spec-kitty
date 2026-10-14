package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;

/**
 * Counts the reads of a Mission's {@code meta.json} that a recorder saw (AC-1.8: three reads of the matched Mission when warm, four when
 * cold). Only a {@code (MISSION_META, READ)} access counts; a stat of the same file does not, and neither does the coordination copy.
 * {@link #reset(RecordingAllowlistAccess)} makes the next {@link #count} start from here, so a test can measure one request without clearing the recorder.
 */
public final class MetaReadCounter {

  private int mark;

  public int count(RecordingAllowlistAccess recorder) {
    return Math.max(0, total(recorder) - mark);
  }

  /** Counts again from the first read of any recorder. */
  public void reset() {
    mark = 0;
  }

  /** Forgets the reads {@code recorder} has seen so far; the recorder itself is left alone. */
  public void reset(RecordingAllowlistAccess recorder) {
    mark = total(recorder);
  }

  private static int total(RecordingAllowlistAccess recorder) {
    return (int) recorder.accesses().stream().filter(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ).count();
  }
}
