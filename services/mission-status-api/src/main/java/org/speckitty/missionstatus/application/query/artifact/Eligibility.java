package org.speckitty.missionstatus.application.query.artifact;

import java.util.List;
import java.util.Locale;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat.EntryKind;
import org.speckitty.missionstatus.domain.readmodel.derive.ArtifactPaths;

/**
 * Which entries below a Mission's primary directory are artifacts. A regular file whose path the artifact-path rule accepts, that is not
 * a root status record, with every component a real directory (no link, no file, nothing missing). A name holding U+FFFD is ineligible:
 * the JDK produces it for bytes it could not decode. No I/O: it judges strings and the {@link EntryStat} values the caller passes.
 *
 * <p>Public on purpose: the index (WP11) and the detail routes (WP15) call it from other packages.
 */
public final class Eligibility {

  private static final String STATUS_JSON = "status.json";
  private static final String LEDGER = "status.events.jsonl";

  private static final boolean WINDOWS = System.getProperty("os.name", "").toLowerCase(Locale.ROOT).startsWith("windows");

  private Eligibility() {}

  /** Whether {@code path} is, at the Mission directory's root, the ledger or the materialised status (any case): never an artifact. */
  public static boolean isRootRecord(String path) {
    return isRootRecord(path, WINDOWS);
  }

  /**
   * Windows drops a trailing dot or space from a file name, so {@code status.json.} opens the root status record: on Windows those are
   * dropped before the comparison. Elsewhere they are distinct files, as in the Python oracle.
   */
  public static boolean isRootRecord(String path, boolean windowsNames) {
    String name = path;
    if (windowsNames) {
      int end = name.length();
      while (end > 0 && (name.charAt(end - 1) == '.' || name.charAt(end - 1) == ' ')) {
        end--;
      }
      name = name.substring(0, end);
    }
    String lower = name.toLowerCase(Locale.ROOT);
    return lower.equals(STATUS_JSON) || lower.equals(LEDGER);
  }

  /** Whether a single directory entry name can be an artifact path segment. */
  public static boolean isEligibleName(String name) {
    return name != null && name.indexOf('/') < 0 && ArtifactPaths.isValid(name);
  }

  /** Whether {@code path} could name an artifact by its text alone: a valid artifact path that is not a root status record. */
  public static boolean isEligiblePath(String path) {
    return ArtifactPaths.isValid(path) && !isRootRecord(path);
  }

  /**
   * Whether the entry at {@code path} is an artifact. {@code leaf} is its {@code lstat}; {@code ancestors} are the {@code lstat} of each
   * directory between the primary directory and the entry, outermost first (so {@code a/b/c.md} has two). Each must be a real
   * directory, and their number must match the path.
   */
  public static boolean isEligible(String path, EntryStat leaf, List<EntryStat> ancestors) {
    if (!isEligiblePath(path)) {
      return false;
    }
    long separators = path.chars().filter(c -> c == '/').count();
    if (ancestors.size() != separators) {
      return false;
    }
    if (!isKind(leaf, EntryKind.FILE)) {
      return false;
    }
    for (EntryStat ancestor : ancestors) {
      if (!isKind(ancestor, EntryKind.DIRECTORY)) {
        return false;
      }
    }
    return true;
  }

  private static boolean isKind(EntryStat stat, EntryKind kind) {
    return stat instanceof EntryStat.Present present && present.kind() == kind;
  }
}
