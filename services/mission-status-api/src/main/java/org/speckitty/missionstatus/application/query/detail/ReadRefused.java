package org.speckitty.missionstatus.application.query.detail;

/**
 * A source of the Work Package detail exists and cannot be used: {@code tasks.md} over its cap or not text, a review-cycle directory that is
 * too large to list, a {@code lanes.json} that is corrupt, of the legacy shape, over its cap or not a file. The route answers 500
 * {@code source_unreadable}. Unchecked, with no message, no cause and no path, so nothing of the file system can reach a response.
 */
public final class ReadRefused extends RuntimeException {

  private static final long serialVersionUID = 1L;

  public ReadRefused() {
    super(null, null, false, false);
  }
}
