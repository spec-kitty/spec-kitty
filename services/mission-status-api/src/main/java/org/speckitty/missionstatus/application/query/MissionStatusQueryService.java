package org.speckitty.missionstatus.application.query;

import java.time.Clock;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ScheduledExecutorService;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.stream.Change;
import org.speckitty.missionstatus.application.query.stream.ChangeFeed;
import org.speckitty.missionstatus.application.query.stream.EventProjection;
import org.speckitty.missionstatus.application.query.stream.ProjectedSubscription;
import org.speckitty.missionstatus.application.query.stream.Resume;
import org.speckitty.missionstatus.application.query.stream.StreamAdmission;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.application.query.stream.StreamSubscriber;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeaderDeriver;
import org.speckitty.missionstatus.domain.readmodel.paging.Pager;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

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
  private final MissionReadModel readModel;
  private final ChangeFeed feed;
  private final EventProjection projection;
  private final StreamAdmission admission;

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
    this(source, clock, diagnostics, executor, settings, leaks, new MissionReadModel(source, diagnostics, leaks));
  }

  MissionStatusQueryService(
      MissionEventSource source,
      Clock clock,
      Consumer<Diagnostic> diagnostics,
      ScheduledExecutorService executor,
      StreamSettings settings,
      LeakClasses leaks,
      ProjectionCache cache) {
    this(source, clock, diagnostics, executor, settings, leaks, new MissionReadModel(source, diagnostics, leaks, cache));
  }

  /**
   * @param readModel the read path shared with the other services of the query side: one lookup, one head derivation, one cache
   */
  public MissionStatusQueryService(
      MissionEventSource source,
      Clock clock,
      Consumer<Diagnostic> diagnostics,
      ScheduledExecutorService executor,
      StreamSettings settings,
      LeakClasses leaks,
      MissionReadModel readModel) {
    this.source = Objects.requireNonNull(source, "source");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    this.readModel = Objects.requireNonNull(readModel, "readModel");
    this.feed =
        new ChangeFeed(source, Objects.requireNonNull(clock, "clock"), diagnostics, Objects.requireNonNull(executor, "executor"), Objects.requireNonNull(settings, "settings"));
    this.projection = new EventProjection(leaks, diagnostics);
    this.admission = new StreamAdmission(settings.maxConnections());
  }

  ProjectionCache cache() {
    return readModel.cache();
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
        strictName(inputs.name()),
        inputs.specKittyVersion(),
        inputs.schemaVersion(),
        inputs.branchName(),
        leaks::strictHostPath,
        overviews.size(),
        overviews.stream().map(MissionOverview::lastActivityAt).toList());
  }

  /**
   * The Project name is a strict field (landing fold A1): a slug shaped like a path, an address or a secret refuses the read with
   * {@code projection_refused}, as the same shape does in a Mission slug. The oracle refuses the same slug (build_project), so this
   * is not a divergence.
   */
  private String strictName(String name) {
    try {
      return new Projector(leaks).strict(name, "name", false);
    } catch (ProjectionError refused) {
      throw refuse(DiagnosticCode.PROJECTION_REFUSED, Diagnostic.NONE, null);
    }
  }

  @Override
  public MissionPage missions(PageRequest request) {
    return Pager.page(listing(), request.pageSize(), request.pageCursor());
  }

  // ---- changes and streams ---------------------------------------------------------------------------------------------------

  @Override
  public StreamBatch changesSince(StreamScope scope, Optional<StreamCursor> cursor) {
    switch (scope) {
      case StreamScope.All all -> {
        if (cursor.isPresent()) {
          throw new StreamRefused(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
        }
        return new StreamBatch(List.of(), StreamCursor.start());
      }
      case StreamScope.OneMission one -> {
        Resolved resolved = resolve(one.missionId());
        return changes(resolved, cursor);
      }
    }
  }

  private StreamBatch changes(Resolved resolved, Optional<StreamCursor> cursor) {
    try {
      if (cursor.isEmpty()) {
        return new StreamBatch(List.of(), ProjectionCache.cursorOf(source.readLedgerFrom(resolved.ref(), 0).lines()));
      }
      Resume.Result resumed = Resume.from(source, resolved.ref(), resolved.meta().missionId(), cursor.get());
      if (resumed.unparseable()) {
        throw refuse(DiagnosticCode.LEDGER_UNPARSEABLE, resolved.mid8(), null);
      }
      return new StreamBatch(projected(resumed.changes()), resumed.end());
    } catch (SourceFault fault) {
      throw ledgerFault(fault, resolved.mid8());
    }
  }

  private List<StreamEvent> projected(List<Change> changes) {
    List<StreamEvent> events = new ArrayList<>();
    for (Change change : changes) {
      projection.project(change).ifPresent(events::add);
    }
    return events;
  }

  /**
   * The place is taken first (the check must not cost a listing), and given back if the connect fails for any reason; a refused call
   * takes none. The subscription hands its place back when it is closed.
   */
  @Override
  public Subscription subscribe(StreamScope scope, Optional<StreamCursor> cursor) {
    admission.admit();
    boolean connected = false;
    try {
      Subscription subscription = connect(scope, cursor);
      connected = true;
      return subscription;
    } finally {
      if (!connected) {
        admission.release();
      }
    }
  }

  @Override
  public void endStreams() {
    admission.endAll();
  }

  private Subscription connect(StreamScope scope, Optional<StreamCursor> cursor) {
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

  private Subscription open(StreamSubscriber subscriber) {
    ProjectedSubscription subscription = new ProjectedSubscription(subscriber, projection, admission);
    admission.register(subscription);
    return subscription;
  }

  /** Rows S1 and S2 of the unscoped column: a Mission that cannot be read is left out with one diagnostic; an unlistable directory refuses. */
  private Subscription subscribeAll() {
    ChangeFeed.UnscopedConnect connected = feed.connectUnscoped(list());
    connected.skipped().forEach(diagnostics);
    return open(connected.subscriber());
  }

  private Subscription subscribeOne(MissionId id, Optional<StreamCursor> cursor) {
    Resolved resolved = resolve(id);
    try {
      ChangeFeed.ScopedConnect connected = feed.connectScoped(resolved.ref(), id, cursor);
      if (connected.unparseable()) {
        note(DiagnosticCode.LEDGER_UNPARSEABLE, resolved.mid8());
      }
      return open(connected.subscriber());
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
    MissionLookup.Scan scan;
    try {
      scan = readModel.find(id);
    } catch (SourceFault fault) {
      throw refuse(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null);
    }
    MissionLookup.Found first = scan.found();
    if (first != null) {
      if (readModel.hasDuplicate(scan)) {
        note(DiagnosticCode.MISSION_ID_DUPLICATE, first.mid8());
      }
      return probed(new Resolved(first.ref(), first.meta(), first.mid8()));
    }
    SourceFault.Kind unreadable = scan.firstFault();
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
      readModel.overview(ref).ifPresent(overview -> entries.add(new Pager.Entry(ref.name(), overview)));
    }
    readModel.cache().retainOnly(Set.copyOf(refs));
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
