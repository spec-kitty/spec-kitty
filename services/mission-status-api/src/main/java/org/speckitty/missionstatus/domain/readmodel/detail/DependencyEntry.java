package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;

/**
 * One dependency of a Work Package detail (the contract's {@code DependencyRef}).
 *
 * @param statusLane the lane of the dependency, or null
 */
public record DependencyEntry(WpId wpId, String title, Lane statusLane) {

  public DependencyEntry {
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(title, "title");
  }
}
