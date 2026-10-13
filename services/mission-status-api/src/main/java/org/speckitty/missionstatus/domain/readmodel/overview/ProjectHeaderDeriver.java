package org.speckitty.missionstatus.domain.readmodel.overview;

import java.util.Collection;
import java.util.function.Predicate;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.model.SupportedSchemaRange;

/** The null rules and the health rule of FR-001, from inputs the outbound port supplies. */
public final class ProjectHeaderDeriver {

  private static final Pattern VERSION = Pattern.compile("^[0-9A-Za-z][0-9A-Za-z.+!_-]{0,63}$");
  private static final Pattern BRANCH = Pattern.compile("^[A-Za-z0-9][A-Za-z0-9._/-]*$");
  private static final int BRANCH_MAX = 255;

  private ProjectHeaderDeriver() {}

  /**
   * @param version the recorded version text, or null
   * @param schemaVersion the recorded schema version after the CLI's coercion, or null
   * @param branchName the branch HEAD names, or null when there is none this contract can carry
   * @param hostPath true for a text that is shaped like a host path (built by the caller from the strict leak patterns)
   * @param missionCount the number of listed overviews, supplied by the caller
   * @param missionLastActivity the {@code lastActivityAt} of each listed Mission, null entries allowed
   */
  public static ProjectHeader derive(
      String name,
      String version,
      Integer schemaVersion,
      String branchName,
      Predicate<String> hostPath,
      int missionCount,
      Collection<String> missionLastActivity) {
    String servedVersion = version != null && VERSION.matcher(version).matches() ? version : null;
    Health health = schemaVersion != null && SupportedSchemaRange.contains(schemaVersion) ? Health.HEALTHY : Health.SCHEMA_DRIFT;
    return new ProjectHeader(name, missionCount, servedVersion, schemaVersion, health, servedBranch(branchName, hostPath), OverviewDeriver.lastActivityAt(missionLastActivity));
  }

  private static String servedBranch(String branch, Predicate<String> hostPath) {
    boolean servable = branch != null && branch.length() <= BRANCH_MAX && BRANCH.matcher(branch).matches() && !hostPath.test(branch);
    return servable ? branch : null;
  }
}
