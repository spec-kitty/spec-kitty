package org.speckitty.missionstatus.application.query.port.in.dto;

import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursorException;

/**
 * Turns the text of a cursor ({@code offset:invariant}) into a cursor, or into the refusal of the contract. This is the one place
 * the operator's ruling is applied: a negative offset is {@code negative}; every other text that does not parse (no colon, a
 * non-hex digest, {@code -5:zz}, an offset that overflows a long) is {@code misaligned}, with a detail saying the cursor did not
 * parse.
 */
public final class StreamCursorText {

  /** The detail text for a cursor that did not parse (the fixed detail of the {@code misaligned} refusal). */
  public static final String UNPARSEABLE_DETAIL = "The stream cursor did not parse.";

  private StreamCursorText() {}

  public static StreamCursor parse(String text) {
    try {
      return StreamCursor.parse(text);
    } catch (StreamCursorException refused) {
      if (refused.reason() == StreamCursorException.Reason.NEGATIVE) {
        throw new StreamRefused(StreamRefused.Kind.NEGATIVE);
      }
      throw new StreamRefused(StreamRefused.Kind.MISALIGNED, UNPARSEABLE_DETAIL);
    }
  }
}
