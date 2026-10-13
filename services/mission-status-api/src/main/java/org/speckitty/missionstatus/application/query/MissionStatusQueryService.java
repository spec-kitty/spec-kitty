package org.speckitty.missionstatus.application.query;

import java.time.Clock;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ScheduledExecutorService;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.stream.ChangeFeed;
import org.speckitty.missionstatus.application.query.stream.Resume;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.domain.readmodel.overview.InvalidInstantException;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.OverviewDeriver;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeaderDeriver;
import org.speckitty.missionstatus.domain.readmodel.paging.Pager;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.domain.readmodel.reducer.UnreducibleLedgerException;

/**
 * The application service behind {@link MissionStatusQuery}. It lists the Missions, reads each {@code meta.json}, stamps each ledger,
 * serves the reduction from the {@link ProjectionCache} when the stamp is unchanged, derives the overview and pages it. Every fault of
 * the failure table is decided here: a row that omits a Mission, a row that serves an empty item, or a row that refuses the whole read
 * with {@link MissionStatusUnavailable}. Each occurrence is reported once through the injected diagnostics consumer; a diagnostic never
 * carries a path, a line text or an operating-system message.
 */
public final class MissionStatusQueryService implements MissionStatusQuery {

  private final MissionEventSource source;
  private final Consumer<Diagnostic> diagnostics;
  private final LeakClasses leaks;
  private final ProjectionCache cache;
  private final ChangeFeed feed;

  /**
   * @param source the outbound port
   * @param clock the clock the feed uses to decide when a re-list is due
   * @param diagnostics called once per occurrence of a fault
   * @param executor runs the feed's poll tick; the application creates no thread
   * @param settings poll and re-list intervals and the subscriber queue capacity
   * @param leaks the host-path, e-mail and secret patterns the projection applies
   */
  public MissionStatusQueryService(
      MissionEventSource source, Clock clock, Consumer<Diagnostic> diagnostics, ScheduledExecutorService executor, StreamSettings settings, LeakClasses leaks) {
    this(source, clock, diagnostics, executor, settings, leaks, new ProjectionCache(new StatusReducer(new AtThenEventId())));
  }

  MissionStatusQueryService(
      MissionEventSource source,
      Clock clock,
      Consumer<Diagnostic> diagnostics,
      ScheduledExecutorService executor,
      StreamSettings settings,
      LeakClasses leaks,
      ProjectionCache cache) {
    this.source = Objects.requireNonNull(source, "source");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    this.cache = Objects.requireNonNull(cache, "cache");
    this.feed =
        new ChangeFeed(source, Objects.requireNonNull(clock, "clock"), diagnostics, Objects.requireNonNull(executor, "executor"), Objects.requireNonNull(settings, "settings"));
  }

  ProjectionCache cache() {
    return cache;
  }

  public ChangeFeed feed() {
    return feed;
  }

  // ---- project and missions --------------------------------------------------------------------------------------------------

  @Override
  public ProjectHeader project() {
    ProjectInputs inputs;
    try {
      inputs = source.projectInputs();
    } catch (SourceFault fault) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null);
    }
    List<MissionOverview> overviews = listing().stream().map(Pager.Entry::overview).toList();
    return ProjectHeaderDeriver.derive(
        inputs.name(),
        inputs.specKittyVersion(),
        inputs.schemaVersion(),
        inputs.branchName(),
        leaks::strictHostPath,
        overviews.size(),
        overviews.stream().map(MissionOverview::lastActivityAt).toList());
  }

  @Override
  public MissionPage missions(PageRequest request) {
    return Pager.page(listing(), request.pageSize(), request.pageCursor());
  }

  // ---- changes and streams ---------------------------------------------------------------------------------------------------

  @Override
  public ChangeBatch changesSince(StreamScope scope, Optional<StreamCursor> cursor) {
    switch (scope) {
      case StreamScope.All all -> {
        if (cursor.isPresent()) {
          throw new StreamRefused(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
        }
        return new ChangeBatch(List.of(), StreamCursor.start());
      }
      case StreamScope.OneMission one -> {
        Resolved resolved = resolve(one.missionId());
        return changes(resolved, cursor);
      }
    }
  }

  private ChangeBatch changes(Resolved resolved, Optional<StreamCursor> cursor) {
    try {
      if (cursor.isEmpty()) {
        return new ChangeBatch(List.of(), ProjectionCache.cursorOf(source.readLedgerFrom(resolved.ref(), 0).lines()));
      }
      Resume.Result resumed = Resume.from(source, resolved.ref(), resolved.meta().missionId(), cursor.get());
      if (resumed.unparseable()) {
        throw refuse(DiagnosticCode.LEDGER_UNPARSEABLE, resolved.mid8(), null);
      }
      return new ChangeBatch(resumed.changes(), resumed.end());
    } catch (SourceFault fault) {
      throw ledgerFault(fault, resolved.mid8());
    }
  }

  @Override
  public Subscription subscribe(StreamScope scope, Optional<StreamCursor> cursor) {
    switch (scope) {
      case StreamScope.All all -> {
        if (cursor.isPresent()) {
          throw new StreamRefused(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
        }
        return subscribeAll();
      }
      case StreamScope.OneMission one -> {
        return subscribeOne(one.missionId(), cursor);
      }
    }
  }

  /** Rows S1 and S2 of the unscoped column: a Mission that cannot be read is left out with one diagnostic; an unlistable directory refuses. */
  private Subscription subscribeAll() {
    ChangeFeed.UnscopedConnect connected = feed.connectUnscoped(list());
    connected.skipped().forEach(diagnostics);
    return connected.subscriber();
  }

  private Subscription subscribeOne(MissionId id, Optional<StreamCursor> cursor) {
    Resolved resolved = resolve(id);
    try {
      ChangeFeed.ScopedConnect connected = feed.connectScoped(resolved.ref(), id, cursor);
      if (connected.unparseable()) {
        note(DiagnosticCode.LEDGER_UNPARSEABLE, resolved.mid8());
      }
      return connected.subscriber();
    } catch (ChangeFeed.Skipped notWatched) {
      throw refuse(notWatched.diagnostic().code(), notWatched.diagnostic().mid8(), null);
    }
  }

  private record Resolved(MissionRef ref, MissionMeta meta, String mid8) {}

  /**
   * Finds the Mission by its id and checks its ledger can be opened (rows S1 and S2). A Mission whose {@code meta.json} cannot be read
   * has no id to compare, so it could be the one asked for: when nothing else matches, its row decides instead of a plain 404.
   */
  private Resolved resolve(MissionId id) {
    SourceFault.Kind unreadable = null;
    Resolved first = null;
    boolean duplicate = false;
    for (MissionRef ref : list()) {
      try {
        MissionMeta meta = source.readMeta(ref);
        if (meta.missionId().equals(id)) {
          if (first != null) {
            duplicate = true;
            break;
          }
          first = new Resolved(ref, meta, meta.missionId().mid8());
        }
      } catch (SourceFault fault) {
        if (fault.kind() != SourceFault.Kind.VANISHED && unreadable == null) {
          unreadable = fault.kind();
        }
      }
    }
    if (first != null) {
      if (duplicate) {
        note(DiagnosticCode.MISSION_ID_DUPLICATE, first.mid8());
      }
      return probed(first);
    }
    if (unreadable == SourceFault.Kind.PATH_REFUSED) {
      note(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE);
    } else if (unreadable == SourceFault.Kind.META_UNPARSEABLE) {
      throw refuse(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE, null);
    } else if (unreadable != null) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null);
    }
    throw new StreamRefused(StreamRefused.Kind.UNKNOWN_MISSION);
  }

  private Resolved probed(Resolved resolved) {
    try {
      source.stampLedger(resolved.ref());
      return resolved;
    } catch (SourceFault fault) {
      throw ledgerFault(fault, resolved.mid8());
    }
  }

  /** A fault of the ledger at connect time: a vanished Mission is plainly unknown, the rest is a 500 with the row's code. */
  private RuntimeException ledgerFault(SourceFault fault, String mid8) {
    return switch (fault.kind()) {
      case VANISHED -> new StreamRefused(StreamRefused.Kind.UNKNOWN_MISSION);
      case DIR_UNREADABLE -> refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, mid8, null);
      case PATH_REFUSED, META_UNPARSEABLE, LEDGER_UNREADABLE -> refuse(DiagnosticCode.LEDGER_UNREADABLE, mid8, null);
    };
  }

  private List<MissionRef> list() {
    try {
      return source.listMissions();
    } catch (SourceFault fault) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null);
    }
  }

  /**
   * One overview per listed Mission that can be read, with the directory it came from; the count and the items come from this one
   * enumeration. Two directories that carry the same {@code mission_id} are both listed (a copied or backed-up directory), each once, and
   * one {@code mission_id_duplicate} diagnostic per such id is written: the id alone cannot tell them apart, the directory name does.
   */
  private List<Pager.Entry> listing() {
    List<MissionRef> refs = list();
    List<Pager.Entry> entries = new ArrayList<>();
    for (MissionRef ref : refs) {
      overview(ref).ifPresent(overview -> entries.add(new Pager.Entry(ref.name(), overview)));
    }
    cache.retainOnly(Set.copyOf(refs));
    noteDuplicateIds(entries);
    return entries;
  }

  private void noteDuplicateIds(List<Pager.Entry> entries) {
    Set<String> seen = new java.util.HashSet<>();
    Set<String> noted = new java.util.HashSet<>();
    for (Pager.Entry entry : entries) {
      String id = entry.overview().missionId().value();
      if (!seen.add(id) && noted.add(id)) {
        note(DiagnosticCode.MISSION_ID_DUPLICATE, entry.overview().mid8());
      }
    }
  }

  private Optional<MissionOverview> overview(MissionRef ref) {
    String mid8 = Diagnostic.NONE;
    try {
      MissionMeta meta = source.readMeta(ref);
      mid8 = meta.missionId().mid8();
      requireInstant(meta.createdAt(), DiagnosticCode.META_UNPARSEABLE, mid8);
      ProjectionCache.Entry entry = ledger(ref, mid8);
      return Optional.of(derive(meta, entry, mid8));
    } catch (SourceFault fault) {
      return omitted(fault, mid8);
    }
  }

  /** The rows that leave a Mission out (L6, L9) and the rows that refuse the whole read (L7, L11). */
  private Optional<MissionOverview> omitted(SourceFault fault, String mid8) {
    switch (fault.kind()) {
      case VANISHED -> note(DiagnosticCode.MISSION_VANISHED, mid8);
      case PATH_REFUSED -> note(DiagnosticCode.PATH_REFUSED, mid8);
      case META_UNPARSEABLE -> throw refuse(DiagnosticCode.META_UNPARSEABLE, mid8, null);
      case DIR_UNREADABLE, LEDGER_UNREADABLE -> throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, mid8, null);
    }
    return Optional.empty();
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
    return projected(derived, mid8);
  }

  /** The fields the oracle routes through its projector; the Mission id is a validated ULID and needs no pass. */
  private MissionOverview projected(MissionOverview o, String mid8) {
    Projector projector = new Projector(leaks);
    try {
      String slug = projector.strict(o.slug(), "slug", false);
      String friendlyName = projector.human(o.friendlyName(), "friendlyName");
      String missionType = projector.strict(o.missionType() == null || o.missionType().isEmpty() ? null : o.missionType(), "missionType", true);
      String targetBranch = projector.strict(o.targetBranch(), "targetBranch", false);
      String nextAction = projector.human(o.nextAction(), "nextAction");
      return new MissionOverview(
          o.missionId(),
          o.mid8(),
          slug,
          friendlyName,
          o.displayNumber(),
          missionType,
          targetBranch,
          o.topology(),
          o.createdAt(),
          o.statusLaneCounts(),
          o.wpTotal(),
          o.blockedCount(),
          o.progress(),
          o.lifecycleStatus(),
          o.acceptedAt(),
          o.mergedAt(),
          o.discardedAt(),
          o.lastEventId(),
          o.lastActivityAt(),
          o.eventCount(),
          o.streamCursor(),
          nextAction);
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, mid8, null);
    }
  }

  // ---- diagnostics -----------------------------------------------------------------------------------------------------------

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }

  private MissionStatusUnavailable refuse(DiagnosticCode code, String mid8, Integer line) {
    Diagnostic diagnostic = new Diagnostic(code, mid8, line);
    diagnostics.accept(diagnostic);
    return new MissionStatusUnavailable(diagnostic);
  }
}
