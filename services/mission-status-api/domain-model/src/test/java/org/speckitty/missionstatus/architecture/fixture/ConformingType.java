package org.speckitty.missionstatus.architecture.fixture;

import java.util.List;
import java.util.Objects;

/** Positive control: a type that uses only allowed JDK packages. */
public record ConformingType(List<String> names) {

  public ConformingType {
    Objects.requireNonNull(names);
  }
}
