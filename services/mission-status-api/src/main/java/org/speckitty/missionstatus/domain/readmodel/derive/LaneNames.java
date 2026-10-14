package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.regex.Pattern;

/**
 * The names a code lane gets, ported from {@code src/specify_cli/lanes/branch_naming.py} ({@code lane_branch_name} and
 * {@code worktree_dir_name}) with the two shapes the contract's {@code Workspace} schema holds them to. The recorded Mission slug is used
 * verbatim. Pure functions over text.
 */
public final class LaneNames {

  /** The one lane that has no branch and no worktree: its Work Packages run in the repository checkout. */
  public static final String PLANNING_LANE_ID = "lane-planning";

  private static final String MISSION_PREFIX = "kitty/mission-";
  private static final int LANE_ID_MAX = 64;
  private static final int BRANCH_MAX = 255;
  private static final Pattern LANE_ID = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]*");
  private static final Pattern BRANCH = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._/-]*");
  /** Crockford base32, exactly eight characters (the oracle's {@code _MID8_RE}). */
  private static final Pattern MID8 = Pattern.compile("[0-9A-HJKMNP-TV-Z]{8}");
  private static final Pattern NUMERIC_PREFIX = Pattern.compile("\\p{Nd}{3}-(.+)", Pattern.DOTALL);

  private LaneNames() {}

  /**
   * The branch of a code lane: {@code kitty/mission-<body>-<lane id>}, where the body is the slug, except that a slug that carries a mid8
   * tail loses a stale {@code NNN-} prefix. The planning lane has no branch of this form: the caller does not ask for it.
   */
  public static String codeLaneBranch(String missionSlug, String laneId) {
    return MISSION_PREFIX + body(missionSlug) + "-" + laneId;
  }

  /** The name of the lane worktree directory, with no {@code .worktrees/} prefix: {@code <slug>-<lane id>}. */
  public static String worktreeDirName(String missionSlug, String laneId) {
    return missionSlug + "-" + laneId;
  }

  /** The lane id when it fits the contract (pattern and 64 characters), else null. */
  public static String fittingLaneId(String laneId) {
    return fits(laneId, LANE_ID, LANE_ID_MAX);
  }

  /** The branch name when it fits the contract (pattern and 255 characters), else null. */
  public static String fittingBranch(String branch) {
    return fits(branch, BRANCH, BRANCH_MAX);
  }

  /** The planning branch when it is not longer than 255 characters, else null. */
  public static String fittingPlanningBranch(String branch) {
    return branch != null && branch.codePointCount(0, branch.length()) > BRANCH_MAX ? null : branch;
  }

  private static String fits(String value, Pattern pattern, int maximum) {
    return value.codePointCount(0, value.length()) <= maximum && pattern.matcher(value).matches() ? value : null;
  }

  private static String body(String slug) {
    return hasMid8Tail(slug) ? stripNumericPrefix(slug) : slug;
  }

  /** The best-effort detector of a mid8 tail: a hyphen, and a last segment of eight Crockford characters. */
  private static boolean hasMid8Tail(String slug) {
    int dash = slug.lastIndexOf('-');
    return dash >= 0 && MID8.matcher(slug.substring(dash + 1)).matches();
  }

  /** Exactly three digits (of any script, as Python's {@code \d}) and a hyphen are stripped when something remains; otherwise the slug is unchanged. */
  private static String stripNumericPrefix(String slug) {
    java.util.regex.Matcher prefix = NUMERIC_PREFIX.matcher(slug);
    return prefix.matches() ? prefix.group(1) : slug;
  }
}
