package org.speckitty.missionstatus.application.query.artifact;

/**
 * The constants of the two artifact routes and nothing else. It is not a seam: mission #5533 does not import it. Each name states the
 * rule it holds.
 */
public final class ArtifactLimits {

  /** The most entries the listing carries. */
  public static final int LISTING_ENTRIES = 1000;

  /** The size of the collector of the walk: one more than the listing, so that the extra one says {@code truncated}. */
  public static final int COLLECTOR_ENTRIES = 1001;

  /** The longest artifact path, in characters; a directory whose own path has this many is not entered. */
  public static final int PATH_CHARACTERS = 512;

  /** The most names the walk counts below the Mission directory, root records and directories included. */
  public static final int WALK_NAMES = 100_000;

  /** The largest file a content read serves, and the largest a {@code readable} check opens. */
  public static final int CONTENT_CAP_BYTES = 262_144;

  /** What a read asks for at most: one byte more than the cap, so that a byte beyond it is seen. */
  public static final int READ_REQUEST_BYTES = CONTENT_CAP_BYTES + 1;

  private ArtifactLimits() {}
}
