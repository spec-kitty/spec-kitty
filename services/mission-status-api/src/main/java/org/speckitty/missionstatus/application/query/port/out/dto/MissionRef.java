package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Objects;

/** The handle of one Mission directory, as the source names it (the directory name). The application only passes it back. */
public record MissionRef(String name) {

  public MissionRef {
    Objects.requireNonNull(name, "name");
  }
}
