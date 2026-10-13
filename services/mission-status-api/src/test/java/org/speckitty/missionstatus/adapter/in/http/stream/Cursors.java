package org.speckitty.missionstatus.adapter.in.http.stream;

import java.nio.charset.StandardCharsets;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;

/** The cursor a ledger text has after a number of its terminated lines (the position the contract says an event's id is). */
final class Cursors {

  private Cursors() {}

  static StreamCursor after(String ledger, int lines) {
    String[] parts = ledger.split("(?<=\n)");
    long offset = 0;
    String last = null;
    for (int i = 0; i < lines; i++) {
      offset += parts[i].getBytes(StandardCharsets.UTF_8).length;
      last = parts[i];
    }
    return new StreamCursor(offset, last == null ? StreamCursor.start().invariant() : StreamCursor.digestOf(last.getBytes(StandardCharsets.UTF_8)));
  }

  static String text(String ledger, int lines) {
    return after(ledger, lines).toText();
  }
}
