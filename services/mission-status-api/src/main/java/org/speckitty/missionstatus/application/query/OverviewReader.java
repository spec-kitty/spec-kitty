package org.speckitty.missionstatus.application.query;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.InvalidInstantException;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.OverviewDeriver;
import org.speckitty.missionstatus.domain.readmodel.reducer.UnreducibleLedgerException;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;

/**
 * Derives the head of a Mission from its {@code meta.json} and its ledger, once. It owns the {@link ProjectionCache}: the reduction is
 * served from the cache when the stamp is unchanged, from the source otherwise. {@link #head} is the only way to obtain a projected
 * head; {@link #overview} delegates to it, so the list and the detail routes share one derivation, one projection and one cache.
 * Every fault of the failure table that belongs to the head is decided here: a row that omits the Mission, a row that serves an empty
 * item, or a row that refuses the whole read with {@link MissionStatusUnavailable}.
 */
final class OverviewReader {

  private final MissionEventSource source;
  private final Consumer<Diagnostic> diagnostics;
  private final ProjectionCache cache;
  private final MissionHeadProjection projection;

  OverviewReader(MissionEventSource source, Consumer<Diagnostic> diagnostics, ProjectionCache cache, MissionHeadProjection projection) {
    this.source = Objects.requireNonNull(source, "source");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.cache = Objects.requireNonNull(cache, "cache");
    this.projection = Objects.requireNonNull(projection, "projection");
  }

  ProjectionCache cache() {
    return cache;
  }

  /** The overview of the Mission, or empty when a row omits it. It is the head's overview: there is no second derivation. */
  Optional<MissionOverview> overview(MissionRef ref) {
    return head(ref).map(MissionHead::overview);
  }

  /**
   * The projected overview and the reduced ledger it was derived from, in one pass: one {@code meta.json} read, one ledger stamp and at
   * most one ledger read. Empty when a row leaves the Mission out (L6, L9).
   */
  Optional<MissionHead> head(MissionRef ref) {
    String mid8 = Diagnostic.NONE;
    try {
      MissionMeta meta = projection.withProjectedDates(source.readMeta(ref));
      mid8 = meta.missionId().mid8();
      requireInstant(meta.createdAt(), DiagnosticCode.META_UNPARSEABLE, mid8);
      ProjectionCache.Entry entry = ledger(ref, mid8);
      return Optional.of(new MissionHead(derive(meta, entry, mid8), entry));
    } catch (SourceFault fault) {
      omitted(fault, mid8);
      return Optional.empty();
    }
  }

  /** The rows that leave a Mission out (L6, L9) and the rows that refuse the whole read (L7, L11). */
  private void omitted(SourceFault fault, String mid8) {
    switch (fault.kind()) {
      case VANISHED -> note(DiagnosticCode.MISSION_VANISHED, mid8);
      case PATH_REFUSED -> note(DiagnosticCode.PATH_REFUSED, mid8);
      case META_UNPARSEABLE -> throw refuse(DiagnosticCode.META_UNPARSEABLE, mid8, null);
      case DIR_UNREADABLE, LEDGER_UNREADABLE -> throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, mid8, null);
    }
  }

  private void requireInstant(String text, DiagnosticCode code, String mid8) {
    try {
      Instants.parse(text);
    } catch (InvalidInstantException unusable) {
      throw refuse(code, mid8, null);
    }
  }

  /** The reduction of the Mission's ledger: from the cache when the stamp is unchanged, from the source otherwise (rows L1 to L4). */
  private ProjectionCache.Entry ledger(MissionRef ref, String mid8) {
    LedgerStamp stamp;
    LedgerRead read;
    try {
      stamp = source.stampLedger(ref);
      Optional<ProjectionCache.Entry> hit = cache.lookup(ref, stamp);
      if (hit.isPresent()) {
        return hit.get();
      }
      read = source.readLedger(ref, stamp);
    } catch (SourceFault fault) {
      if (fault.kind() == SourceFault.Kind.LEDGER_UNREADABLE || fault.kind() == SourceFault.Kind.PATH_REFUSED) {
        note(DiagnosticCode.LEDGER_UNREADABLE, mid8);
        return new ProjectionCache.Entry(new StatusSnapshot(Map.of(), 0, null, ""), StreamCursor.start());
      }
      throw fault;
    }
    if (read.tail() == TailClassification.NON_WHITESPACE) {
      refuseFirstMalformedLine(read.lines(), mid8);
      throw refuse(DiagnosticCode.LEDGER_TORN_TAIL, mid8, null);
    }
    try {
      return cache.load(ref, stamp, read.lines());
    } catch (UnreducibleLedgerException malformed) {
      throw refuse(DiagnosticCode.LEDGER_UNPARSEABLE, mid8, lineOf(malformed.reason(), malformed.lineNumber()));
    }
  }

  /** Python reports the first line that fails, and a torn tail comes after every terminated line: a bad earlier line is the answer. */
  private void refuseFirstMalformedLine(List<LedgerLine> terminated, String mid8) {
    for (LedgerLine line : terminated) {
      if (line.kind() instanceof LineKind.Malformed malformed) {
        throw refuse(DiagnosticCode.LEDGER_UNPARSEABLE, mid8, lineOf(malformed.reason(), line.lineNumber()));
      }
    }
  }

  /** The 1-based line number of a bad line; none for a line that is not valid UTF-8 (Python gives a byte position, not a line). */
  private static Integer lineOf(MalformedReason reason, long lineNumber) {
    return reason == MalformedReason.NOT_UTF8 ? null : (int) Math.min(lineNumber, Integer.MAX_VALUE);
  }

  private MissionOverview derive(MissionMeta meta, ProjectionCache.Entry entry, String mid8) {
    MissionOverview derived;
    try {
      derived = OverviewDeriver.derive(meta, entry.snapshot(), entry.cursor());
    } catch (InvalidInstantException unusable) {
      throw refuse(DiagnosticCode.LEDGER_UNPARSEABLE, mid8, null);
    }
    try {
      return projection.projected(derived, mid8);
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8, null);
    }
  }

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8, Integer line) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, line);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
