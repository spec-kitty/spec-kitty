package org.speckitty.missionstatus.application.query.port.out.dto;

/** What a bounded read of one file gave: the file could not be opened or read, it is larger than the cap, or its bytes. */
public sealed interface ArtifactBytes {

  /** The file could not be opened or read. */
  record Unreadable() implements ArtifactBytes {}

  /** The open handle reports more bytes than the cap; the content was not read. */
  record TooLarge(long sizeBytes) implements ArtifactBytes {}

  /** The size of the open handle and at most cap + 1 bytes of the file. */
  record Content(long sizeBytes, byte[] data) implements ArtifactBytes {}
}
