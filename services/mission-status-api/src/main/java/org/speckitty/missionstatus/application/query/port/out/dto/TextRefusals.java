package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.redaction.TextScreen;

/** The pure function from every outcome that can refuse to one {@link TextRefusal} (plan section 7.2). Total over those inputs. */
public final class TextRefusals {

  private TextRefusals() {}

  /** The refusal of a bytes read, or empty when the bytes were read. */
  public static Optional<TextRefusal> of(BytesRead read) {
    return switch (read) {
      case BytesRead.Bytes bytes -> Optional.empty();
      case BytesRead.Absent absent -> Optional.of(TextRefusal.NOT_FOUND);
      case BytesRead.NotRegular notRegular -> Optional.of(TextRefusal.NOT_REGULAR);
      case BytesRead.OverCap overCap -> Optional.of(TextRefusal.OVER_CAP);
    };
  }

  /** The refusal of a text read, or empty when the text was read. */
  public static Optional<TextRefusal> of(TextRead read) {
    return switch (read) {
      case TextRead.Text text -> Optional.empty();
      case TextRead.Absent absent -> Optional.of(TextRefusal.NOT_FOUND);
      case TextRead.NotRegular notRegular -> Optional.of(TextRefusal.NOT_REGULAR);
      case TextRead.OverCap overCap -> Optional.of(TextRefusal.OVER_CAP);
      case TextRead.NotText notText -> Optional.of(TextRefusal.NOT_TEXT);
    };
  }

  /** The refusal of a thrown fault: a vanished file is not found, a failed read or listing is an I/O failure. */
  public static TextRefusal of(TextFault.Kind kind) {
    return switch (kind) {
      case PATH_REFUSED -> TextRefusal.PATH_REFUSED;
      case VANISHED -> TextRefusal.NOT_FOUND;
      case DIR_UNREADABLE, FILE_UNREADABLE -> TextRefusal.IO_FAILURE;
    };
  }

  /** A credential found in the decoded text. */
  public static TextRefusal of(TextScreen.Screened.SecretFound found) {
    return TextRefusal.SECRET_REFUSED;
  }
}
