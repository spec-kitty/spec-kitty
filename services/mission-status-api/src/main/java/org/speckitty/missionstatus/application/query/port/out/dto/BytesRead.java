package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Objects;

/** The result of reading a regular file as bytes under a cap. */
public sealed interface BytesRead {

  /** The whole file; at most the cap. The array is owned by the receiver. */
  record Bytes(byte[] content) implements BytesRead {
    public Bytes {
      Objects.requireNonNull(content, "content");
    }
  }

  /** Nothing is at the path. */
  record Absent() implements BytesRead {}

  /** Something is there, and it is not a regular file. */
  record NotRegular() implements BytesRead {}

  /** The file is larger than the cap: by the size of the open handle, or by the bytes actually read. */
  record OverCap() implements BytesRead {}
}
