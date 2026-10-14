package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Objects;

/** The result of reading a regular file as strictly decoded UTF-8 text under a cap. */
public sealed interface TextRead {

  /** The decoded text and the size of the file in bytes. */
  record Text(String text, long sizeBytes) implements TextRead {
    public Text {
      Objects.requireNonNull(text, "text");
    }
  }

  /** Nothing is at the path. */
  record Absent() implements TextRead {}

  /** Something is there, and it is not a regular file. */
  record NotRegular() implements TextRead {}

  /** The file is larger than the cap. */
  record OverCap() implements TextRead {}

  /** The bytes are not strict UTF-8. */
  record NotText() implements TextRead {}
}
