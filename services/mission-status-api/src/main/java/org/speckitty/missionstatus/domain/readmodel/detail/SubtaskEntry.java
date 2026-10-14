package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.Lane;

/**
 * One subtask of a Work Package detail.
 *
 * @param id the subtask reference
 * @param title the subtask title, or null
 * @param statusLane the resolved lane, or null when the status model holds none
 */
public record SubtaskEntry(String id, String title, Lane statusLane) {

  public SubtaskEntry {
    Objects.requireNonNull(id, "id");
  }
}
