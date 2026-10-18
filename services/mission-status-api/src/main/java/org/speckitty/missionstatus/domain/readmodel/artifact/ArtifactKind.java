package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Map;
import java.util.regex.Pattern;

/**
 * The class of an artifact ({@code ArtifactKind}), decided from its path by the contract's ordered rule where the first match wins.
 * The file is never read. The order and the patterns are those of {@code classify} in the reference reader.
 */
public enum ArtifactKind {
  REVIEW_CYCLE("review_cycle"),
  WORK_PACKAGE_PROMPT("work_package_prompt"),
  SPEC("spec"),
  PLAN("plan"),
  TASKS("tasks"),
  DATA_MODEL("data_model"),
  QUICKSTART("quickstart"),
  ANALYSIS_REPORT("analysis_report"),
  RESEARCH("research"),
  CONTRACT("contract"),
  CHECKLIST("checklist"),
  OTHER("other");

  private static final String TASKS_DIR = "tasks";
  private static final Pattern REVIEW_CYCLE_NAME = Pattern.compile("review-cycle-[1-9][0-9]*\\.md");
  private static final Pattern PROMPT_NAME = Pattern.compile("WP[0-9]{2,}-[^/]*\\.md");
  private static final Map<String, ArtifactKind> ROOT_FILES =
      Map.of(
          "spec.md", SPEC,
          "plan.md", PLAN,
          "tasks.md", TASKS,
          "data-model.md", DATA_MODEL,
          "quickstart.md", QUICKSTART,
          "analysis-report.md", ANALYSIS_REPORT);

  private final String wire;

  ArtifactKind(String wire) {
    this.wire = wire;
  }

  /** The value as the contract writes it. */
  public String wire() {
    return wire;
  }

  /** The class of {@code path}, a path the artifact-path rule accepts. */
  public static ArtifactKind classify(String path) {
    String[] segments = path.split("/", -1);
    String name = segments[segments.length - 1];
    if (segments.length == 3 && segments[0].equals(TASKS_DIR) && REVIEW_CYCLE_NAME.matcher(name).matches()) {
      return REVIEW_CYCLE;
    }
    if (segments.length == 2 && segments[0].equals(TASKS_DIR) && PROMPT_NAME.matcher(name).matches()) {
      return WORK_PACKAGE_PROMPT;
    }
    if (segments.length == 1 && ROOT_FILES.containsKey(name)) {
      return ROOT_FILES.get(name);
    }
    if (path.equals("research.md") || (segments.length > 1 && segments[0].equals("research"))) {
      return RESEARCH;
    }
    if (segments.length > 1 && segments[0].equals("contracts")) {
      return CONTRACT;
    }
    if (segments.length > 1 && segments[0].equals("checklists")) {
      return CHECKLIST;
    }
    return OTHER;
  }
}
