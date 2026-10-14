package org.speckitty.missionstatus.domain.readmodel.detail;

/**
 * One review cycle read from its file (the contract's {@code ReviewCycle}).
 *
 * @param cycleNumber the number from the file name, at least 1
 * @param reviewedAt when the review was recorded, or null
 * @param reviewer the reviewer handle, or null
 * @param verdict the verdict of the last status event that names this cycle, or null
 * @param feedbackReference the canonical review-cycle pointer, or null
 * @param artifactPath the path of the cycle file relative to the Mission directory, or null when it is not an eligible artifact
 */
public record ReviewCycleEntry(
    int cycleNumber, String reviewedAt, String reviewer, ReviewView.Verdict verdict, String feedbackReference, String artifactPath) {

  public ReviewCycleEntry {
    if (cycleNumber < 1) {
      throw new IllegalArgumentException("cycle numbers start at 1");
    }
  }
}
