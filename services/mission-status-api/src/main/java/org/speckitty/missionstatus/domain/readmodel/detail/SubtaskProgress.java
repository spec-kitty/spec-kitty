package org.speckitty.missionstatus.domain.readmodel.detail;

/** How many of a Work Package's subtasks are done, both numbers from the resolved subtask map. */
public record SubtaskProgress(int done, int total) {

  public SubtaskProgress {
    if (done < 0 || total < done) {
      throw new IllegalArgumentException("progress out of range");
    }
  }
}
