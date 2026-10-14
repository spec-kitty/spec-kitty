package org.speckitty.missionstatus.application.query.stream;

import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.MissionId;

/**
 * Reading a Mission's log from a cursor: the refusals that make a cursor untrustworthy (checked in the order of the tail reader:
 * {@code out_of_range}, {@code misaligned}, {@code content_mismatch}; a negative offset cannot reach here) and the forwarded rows after
 * it. The same code serves the batch call and the connect of a resuming stream.
 */
public final class Resume {

  /** The forwarded rows after the cursor, the cursor after the last row consumed, and whether a bad line stopped the read. */
  public record Result(List<Change> changes, StreamCursor end, boolean unparseable) {}

  private Resume() {}

  public static Result from(MissionEventSource source, MissionRef ref, MissionId id, StreamCursor from) {
    LedgerWindow window = source.readLedgerFrom(ref, from.offset());
    if (window.size() < from.offset()) {
      throw new StreamRefused(StreamRefused.Kind.OUT_OF_RANGE);
    }
    if (!window.aligned()) {
      throw new StreamRefused(StreamRefused.Kind.MISALIGNED);
    }
    if (!window.precedingLineSha256().equals(from.invariant())) {
      throw new StreamRefused(StreamRefused.Kind.CONTENT_MISMATCH);
    }
    List<Change> changes = new ArrayList<>();
    long offset = from.offset();
    String invariant = from.invariant();
    for (LedgerLine line : window.lines()) {
      if (isUnparseable(line.kind())) {
        return new Result(changes, new StreamCursor(offset, invariant), true);
      }
      offset += line.byteLength();
      invariant = line.rawLineSha256();
      if (isForwarded(line.kind())) {
        changes.add(new Change(id, line.kind(), new StreamCursor(offset, invariant)));
      }
    }
    return new Result(changes, new StreamCursor(offset, invariant), false);
  }

  /** A status transition or one of the seven lifecycle types; every other well-formed row is dropped. */
  static boolean isForwarded(LineKind kind) {
    return kind instanceof LineKind.Status || kind instanceof LineKind.Lifecycle;
  }

  /**
   * A terminated line that is not valid JSON or not a JSON object, a blank line included (row S4): it ends a stream. A well-formed object
   * that is no usable row ({@link MalformedReason#UNUSABLE_ROW}: an unknown lane or kind, a missing key) is not one: Python's
   * {@code poll_once} raises only on invalid JSON or a non-object, so a stream skips such a row, advances past it and stays open.
   */
  static boolean isUnparseable(LineKind kind) {
    return kind instanceof LineKind.Blank || (kind instanceof LineKind.Malformed malformed && malformed.reason() != MalformedReason.UNUSABLE_ROW);
  }
}
