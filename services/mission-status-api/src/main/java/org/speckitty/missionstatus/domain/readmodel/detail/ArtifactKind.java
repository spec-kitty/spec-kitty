package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Locale;

/** The twelve classes of an artifact (the contract's {@code ArtifactKind}), decided from its path by the ordered classifier. */
public enum ArtifactKind {
  REVIEW_CYCLE,
  WORK_PACKAGE_PROMPT,
  SPEC,
  PLAN,
  TASKS,
  DATA_MODEL,
  QUICKSTART,
  ANALYSIS_REPORT,
  RESEARCH,
  CONTRACT,
  CHECKLIST,
  OTHER;

  /** The word the contract serves: the lower-case name. */
  public String wire() {
    return name().toLowerCase(Locale.ROOT);
  }
}
