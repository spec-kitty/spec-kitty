package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Set;

/**
 * The two root status records of a Mission, {@code status.events.jsonl} and {@code status.json}, which are not artifacts. A path names
 * one when its Python {@code str.casefold()} equals the record's name ({@link AsciiCaseFold}).
 */
public final class StatusRecordNames {

  private static final Set<String> NAMES = Set.of("status.events.jsonl", "status.json");

  private StatusRecordNames() {}

  /** Whether {@code path} (relative to the Mission directory) is one of the two root status records. */
  public static boolean isStatusRecord(String path) {
    return NAMES.contains(AsciiCaseFold.fold(path));
  }
}
