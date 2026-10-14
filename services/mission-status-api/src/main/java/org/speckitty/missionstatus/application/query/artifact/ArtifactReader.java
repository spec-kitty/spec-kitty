package org.speckitty.missionstatus.application.query.artifact;

import java.util.Objects;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRefusal;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRefusals;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.derive.ArtifactKinds;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.redaction.TextScreen;

/**
 * The order of decision of {@code getArtifactContent} (FR-005), and the same decision for the {@code readable} flag of a listing entry,
 * so that the flag cannot drift from the status of the content read. The caller has already judged the path with {@code ArtifactPaths}
 * (400 comes first).
 *
 * <p>After the path: nothing eligible at it (a directory, a link, a path through a link, a root status record, a missing file) is 404;
 * a file larger than the cap by the open handle is 413 and is not read; a failure to open or read is 500; a byte beyond the cap while
 * reading is 413; a NUL byte or bytes that are not strict UTF-8 are 415; a credential in the text is 422 with no content; otherwise 200
 * with the screened text. The cap is applied by the port, twice (the open handle, then the bytes read). A refusal maps through
 * {@link TextRefusals}, the one table of plan section 7.2.
 */
public final class ArtifactReader {

  /** The outcome of reading one artifact, without a refusal being thrown or a diagnostic written. */
  public sealed interface Probe {
    /** The file would be served. */
    record Readable(ArtifactContent content) implements Probe {
      public Readable {
        Objects.requireNonNull(content, "content");
      }
    }

    /** The file is there and would be refused with this kind. */
    record Refused(DetailRefusal.Kind kind) implements Probe {
      public Refused {
        Objects.requireNonNull(kind, "kind");
      }
    }

    /** Nothing eligible is there: absent, not a regular file, a link, a path through a link, a root status record, or vanished. */
    record Gone() implements Probe {}
  }

  private final TextSource source;
  private final TextScreen screen;
  private final Consumer<Diagnostic> diagnostics;

  public ArtifactReader(TextSource source, TextScreen screen, Consumer<Diagnostic> diagnostics) {
    this.source = Objects.requireNonNull(source, "source");
    this.screen = Objects.requireNonNull(screen, "screen");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
  }

  /** Reads one artifact and says what the content read would answer. It writes no diagnostic. {@code path} must be a valid artifact path. */
  public Probe probe(MissionRef mission, String path) {
    if (!Eligibility.isEligiblePath(path)) {
      return new Probe.Gone();
    }
    TextRead read;
    try {
      read = source.readText(new FileRef.MissionFile(mission, RelativePath.of(path)), ArtifactLimits.CONTENT_CAP_BYTES, ReadScope.ARTIFACT);
    } catch (TextFault fault) {
      return refused(TextRefusals.of(fault.kind()));
    }
    if (read instanceof TextRead.Text text) {
      return decided(path, text);
    }
    return refused(TextRefusals.of(read).orElseThrow());
  }

  private Probe decided(String path, TextRead.Text text) {
    if (text.text().indexOf('\0') >= 0) {
      return refused(TextRefusal.NOT_TEXT);
    }
    return switch (screen.screen(text.text())) {
      case TextScreen.Screened.SecretFound found -> refused(TextRefusals.of(found));
      case TextScreen.Screened.Clean clean ->
          new Probe.Readable(new ArtifactContent(path, ArtifactKinds.kindOf(path), ArtifactKinds.mediaTypeOf(path), text.sizeBytes(), clean.redacted(), clean.text()));
    };
  }

  private static Probe refused(TextRefusal refusal) {
    return switch (refusal) {
      case NOT_FOUND, NOT_REGULAR, PATH_REFUSED -> new Probe.Gone();
      case OVER_CAP -> new Probe.Refused(DetailRefusal.Kind.ARTIFACT_TOO_LARGE);
      case NOT_TEXT -> new Probe.Refused(DetailRefusal.Kind.ARTIFACT_NOT_TEXT);
      case SECRET_REFUSED -> new Probe.Refused(DetailRefusal.Kind.ARTIFACT_SECRET);
      case IO_FAILURE -> new Probe.Refused(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    };
  }

  /**
   * Serves the artifact at {@code path}, or throws the refusal of the order of decision and writes its one diagnostic (none for a 404).
   * A path that is not pure ASCII on a host that cannot decode file names is 500 {@code artifact_unreadable}: the name cannot be told
   * from a mangled one (row A8).
   */
  public ArtifactContent read(MissionRef mission, String mid8, String path) {
    if (hasNonAscii(path) && !namesTrustworthy(mission)) {
      throw unreadable(mid8, DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    }
    return switch (probe(mission, path)) {
      case Probe.Readable readable -> readable.content();
      case Probe.Gone gone -> throw DetailRefusal.notFound();
      case Probe.Refused refused -> throw unreadable(mid8, refused.kind());
    };
  }

  /** Writes the diagnostic of the kind and returns the refusal to throw. */
  private DetailRefusal unreadable(String mid8, DetailRefusal.Kind kind) {
    DiagnosticCode code =
        switch (kind) {
          case ARTIFACT_TOO_LARGE -> DiagnosticCode.ARTIFACT_TOO_LARGE;
          case ARTIFACT_NOT_TEXT -> DiagnosticCode.ARTIFACT_NOT_TEXT;
          case ARTIFACT_SECRET -> DiagnosticCode.ARTIFACT_SECRET;
          default -> DiagnosticCode.ARTIFACT_UNREADABLE;
        };
    diagnostics.accept(new Diagnostic(code, mid8, null));
    return new DetailRefusal(kind);
  }

  /** Whether the host's file-name decoding can be believed, asked of the port by a one-name listing of the Mission directory. */
  private boolean namesTrustworthy(MissionRef mission) {
    try {
      return !(source.list(new FileRef.MissionFile(mission, RelativePath.ROOT), 1, ReadScope.ARTIFACT) instanceof DirListing.Names names) || names.trustworthy();
    } catch (TextFault fault) {
      return true;
    }
  }

  private static boolean hasNonAscii(String text) {
    for (int i = 0; i < text.length(); i++) {
      if (text.charAt(i) > 0x7f) {
        return true;
      }
    }
    return false;
  }
}
