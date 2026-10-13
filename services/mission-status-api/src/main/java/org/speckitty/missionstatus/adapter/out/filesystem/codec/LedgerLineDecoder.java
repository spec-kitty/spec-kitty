package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.TailClassification;

/**
 * The one place ledger lines are decoded. It turns raw ledger bytes into {@link LedgerLine} records (Python-parity classification of
 * every line) and classifies the unterminated tail. It has no file API: the filesystem adapter hands it bytes, and the in-memory test
 * source hands it raw lines, so both read a line the same way (plan section 13, E-13).
 *
 * <p>A physical line ends at a newline byte. The raw bytes of a line, the newline and any carriage return before it included, are what
 * the digest and the length describe (the tail reader's {@code sha256(chunk + b"\n")}). A terminated line is decoded as Python's
 * {@code read_event_stream} reads it: the text is the line stripped of Python whitespace; an empty result is {@code Blank}; the rest
 * must be JSON that {@code json.loads} accepts, an object, and a known row shape (see {@link RowClassifier}). Bytes that are not UTF-8
 * make the line {@code Malformed(NOT_UTF8)} (Python raises {@code UnicodeDecodeError} for the whole file and gives a byte position; the
 * line number is the codec's addition). The unterminated tail is never a line.
 *
 * <p>Known differences from Python, all in line framing: a lone carriage return and the separators U+000B, U+000C, U+001C to U+001E,
 * U+0085, U+2028 and U+2029 do not end a line here, because the cursor and the stream are defined over newline bytes.
 */
public final class LedgerLineDecoder {

  /** The decoded terminated lines of a ledger (or of a window of it) and the classification of what follows the last newline. */
  public record Decoded(List<LedgerLine> lines, TailClassification tail) {
    public Decoded {
      lines = List.copyOf(Objects.requireNonNull(lines, "lines"));
      Objects.requireNonNull(tail, "tail");
    }
  }

  private static final byte NEWLINE = '\n';

  private LedgerLineDecoder() {}

  /** Decodes a whole ledger; the first line is line 1. */
  public static Decoded decode(byte[] ledger) {
    return decode(ledger, 1);
  }

  /** Decodes bytes that start at a line boundary; {@code firstLineNumber} is the 1-based number of their first line. */
  public static Decoded decode(byte[] bytes, long firstLineNumber) {
    requireLineNumber(firstLineNumber);
    List<LedgerLine> lines = new ArrayList<>();
    int start = 0;
    long number = firstLineNumber;
    for (int index = 0; index < bytes.length; index++) {
      if (bytes[index] == NEWLINE) {
        lines.add(line(number, bytes, start, index + 1));
        number++;
        start = index + 1;
      }
    }
    return new Decoded(lines, classifyTail(bytes, start));
  }

  /** Decodes one terminated line given with its newline. */
  public static LedgerLine decodeLine(long lineNumber, byte[] rawLineWithNewline) {
    requireLineNumber(lineNumber);
    int length = rawLineWithNewline.length;
    boolean oneTerminatedLine = length > 0 && rawLineWithNewline[length - 1] == NEWLINE;
    for (int index = 0; oneTerminatedLine && index < length - 1; index++) {
      oneTerminatedLine = rawLineWithNewline[index] != NEWLINE;
    }
    if (!oneTerminatedLine) {
      throw new IllegalArgumentException("a line is the bytes up to and including its single trailing newline");
    }
    return line(lineNumber, rawLineWithNewline, 0, length);
  }

  private static void requireLineNumber(long lineNumber) {
    if (lineNumber < 1) {
      throw new IllegalArgumentException("line numbers are 1-based");
    }
  }

  private static LedgerLine line(long number, byte[] bytes, int start, int endExclusive) {
    int length = endExclusive - start;
    return new LedgerLine(number, sha256Hex(bytes, start, length), length, kind(bytes, start, endExclusive - 1));
  }

  /** The kind of the line whose content is {@code bytes[start, contentEnd)} (the newline excluded). */
  private static LineKind kind(byte[] bytes, int start, int contentEnd) {
    String text;
    try {
      text = strictUtf8(bytes, start, contentEnd - start);
    } catch (CharacterCodingException notUtf8) {
      return new LineKind.Malformed(MalformedReason.NOT_UTF8);
    }
    if (PyText.isBlank(text)) {
      return new LineKind.Blank();
    }
    Object document;
    try {
      document = PythonJson.parse(PyText.strip(text));
    } catch (PythonJson.Invalid notJson) {
      return new LineKind.Malformed(MalformedReason.NOT_JSON);
    }
    return RowClassifier.classify(document);
  }

  private static TailClassification classifyTail(byte[] bytes, int tailStart) {
    if (tailStart >= bytes.length) {
      return TailClassification.NONE;
    }
    try {
      String tail = strictUtf8(bytes, tailStart, bytes.length - tailStart);
      return PyText.isBlank(tail) ? TailClassification.WHITESPACE : TailClassification.NON_WHITESPACE;
    } catch (CharacterCodingException notUtf8) {
      return TailClassification.NON_WHITESPACE;
    }
  }

  private static String strictUtf8(byte[] bytes, int offset, int length) throws CharacterCodingException {
    return StandardCharsets.UTF_8
        .newDecoder()
        .onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT)
        .decode(ByteBuffer.wrap(bytes, offset, length))
        .toString();
  }

  private static String sha256Hex(byte[] bytes, int offset, int length) {
    try {
      MessageDigest digest = MessageDigest.getInstance("SHA-256");
      digest.update(bytes, offset, length);
      return HexFormat.of().formatHex(digest.digest());
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException("SHA-256 is a required JDK algorithm", impossible);
    }
  }
}
