package org.speckitty.missionstatus.spike.lockinterop;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/**
 * The spike's rows and the Java append. A row is one lane transition in today's {@code status.events.jsonl} shape (no envelope),
 * serialised exactly as {@code lock_interop_peer.render_row} serialises it ({@code json.dumps(row, sort_keys=True)}); the harness
 * compares the two renderings before it trusts either.
 */
final class SpikeRows {

  private static final String CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
  private static final int ULID_LENGTH = 26;
  private static final long WRITER_STRIDE = 1_000_000L;
  private static final String MISSION_ID = "01M5Z69W0NVCDP2P7BXS5TV391";
  private static final String MISSION_SLUG = "lock-interop-spike-01M5Z69W";

  private SpikeRows() {}

  /** The log's last byte is not LF; nothing was appended (the Java twin of {@code EVENT_LOG_TORN_TAIL}). */
  static final class TornTailException extends IOException {
    TornTailException(Path log) {
      super(log + ": torn tail, append refused");
    }
  }

  static String eventId(int writer, int index) {
    long value = writer * WRITER_STRIDE + index;
    StringBuilder digits = new StringBuilder();
    while (value > 0) {
      digits.append(CROCKFORD.charAt((int) (value % 32)));
      value /= 32;
    }
    return "0".repeat(ULID_LENGTH - digits.length()) + digits.reverse();
  }

  /** Writer {@code writer}'s {@code index}-th row, without the line terminator. */
  static String render(int writer, int index) {
    return "{\"actor\": \"lock-interop-%d\", \"at\": \"2026-10-27T12:00:00.%06d+00:00\", \"event_id\": \"%s\", \"evidence\": null, "
            .formatted(writer, index, eventId(writer, index))
        + "\"execution_mode\": \"worktree\", \"force\": false, \"from_lane\": \"planned\", \"mission_id\": \"%s\", \"mission_slug\": \"%s\", "
            .formatted(MISSION_ID, MISSION_SLUG)
        + "\"reason\": null, \"review_ref\": null, \"to_lane\": \"claimed\", \"wp_id\": \"WP%02d\"}".formatted(writer);
  }

  /**
   * The Java counterpart of {@code append_event_log_lines} for one row, to be called with the lock held: refuse a torn tail, then one
   * write of the whole line and its LF on an append-mode channel, then force it to disk.
   */
  static void appendUnderLock(Path log, String row) throws IOException {
    long size = Files.exists(log) ? Files.size(log) : 0;
    if (size > 0) {
      try (FileChannel reader = FileChannel.open(log, StandardOpenOption.READ)) {
        ByteBuffer last = ByteBuffer.allocate(1);
        reader.read(last, size - 1);
        if (last.get(0) != '\n') {
          throw new TornTailException(log);
        }
      }
    }
    byte[] unit = (row + "\n").getBytes(StandardCharsets.UTF_8);
    try (FileChannel writer = FileChannel.open(log, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND)) {
      int written = writer.write(ByteBuffer.wrap(unit));
      if (written != unit.length) {
        throw new IOException(log + ": short write " + written + " of " + unit.length);
      }
      writer.force(true);
    }
  }
}
