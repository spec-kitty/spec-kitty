package org.speckitty.missionstatus.application.query.stream;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.port.in.dto.Change;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;

/**
 * The one shared poller (NFR-004 c). It watches each Mission some subscriber cares about, reads only the appended bytes of a ledger
 * whose stamp changed, and fans the result out through the bounded queue of each subscriber, so a hundred connections cost the same
 * reads as one. It runs on the injected executor and creates no thread. It reports a fault it detects itself (a ledger that
 * stops being readable, a bad line, a vanished Mission, an unlistable {@code kitty-specs/}) once, however many subscribers see it;
 * the connect-time outcomes are returned to {@link MissionStatusQueryService}, which reports them, and are never repeated here.
 *
 * <p>Position of a watch: {@code offset} is the end of the last terminated line consumed and {@code invariant} the digest of that
 * line, so the position is a cursor. A Mission present at connect is watched from its current end and delivers none of its history; a
 * Mission discovered later is watched from offset 0, and so is one that a second unscoped subscriber finds before the first one's
 * re-list has (each unscoped subscriber then holds its own floor for that Mission, the offset it joined at, so the shared watch delivers
 * to each only the rows written after it joined). An unterminated tail is never consumed.
 */
public final class ChangeFeed {

  private static final String EMPTY_DIGEST = StreamCursor.start().invariant();

  /** A Mission that cannot be watched: the diagnostic of the row, for the caller to report. */
  public static final class Skipped extends RuntimeException {
    private static final long serialVersionUID = 1L;
    private final transient Diagnostic diagnostic;

    Skipped(Diagnostic diagnostic) {
      super("mission not watched: " + diagnostic.code().wire());
      this.diagnostic = diagnostic;
    }

    public Diagnostic diagnostic() {
      return diagnostic;
    }
  }

  public record ScopedConnect(StreamSubscriber subscriber, boolean unparseable) {}

  public record UnscopedConnect(StreamSubscriber subscriber, List<Diagnostic> skipped) {}

  private static final class Watch {
    final MissionRef ref;
    final MissionId id;
    final String mid8;
    long offset;
    String invariant = EMPTY_DIGEST;
    LedgerStamp stamp;

    Watch(MissionRef ref, MissionId id) {
      this.ref = ref;
      this.id = id;
      this.mid8 = id.mid8();
    }
  }

  private final MissionEventSource source;
  private final Clock clock;
  private final Consumer<Diagnostic> diagnostics;
  private final ScheduledExecutorService executor;
  private final StreamSettings settings;

  private final ReentrantLock lock = new ReentrantLock();
  private final Map<MissionRef, Watch> watches = new LinkedHashMap<>();
  private final Set<MissionRef> known = new HashSet<>();
  /** Missions whose failed discovery was already reported: a retry on the next listing stays quiet, so a permanent fault logs once. */
  private final Set<MissionRef> skippedReported = new HashSet<>();
  private final Set<StreamSubscriber> subscribers = new LinkedHashSet<>();
  private ScheduledFuture<?> tickTask;
  private Instant lastListing;
  private boolean listingFailed;

  public ChangeFeed(MissionEventSource source, Clock clock, Consumer<Diagnostic> diagnostics, ScheduledExecutorService executor, StreamSettings settings) {
    this.source = source;
    this.clock = clock;
    this.diagnostics = diagnostics;
    this.executor = executor;
    this.settings = settings;
  }

  // ---- connecting ------------------------------------------------------------------------------------------------------------

  /**
   * Opens a Mission-scoped subscription, with the catch-up rows after the cursor already queued. The watch is created before the
   * catch-up is read, so a row appended in between is read by one of them (and, if by both, delivered once: the subscriber's floor).
   *
   * @throws org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused a cursor that cannot be trusted
   * @throws Skipped the Mission cannot be read
   */
  public ScopedConnect connectScoped(MissionRef ref, MissionId id, Optional<StreamCursor> cursor) {
    lock.lock();
    try {
      return open(ref, id, cursor);
    } catch (RuntimeException refused) {
      gc();
      throw refused;
    } finally {
      lock.unlock();
    }
  }

  private ScopedConnect open(MissionRef ref, MissionId id, Optional<StreamCursor> cursor) {
    StreamSubscriber subscriber = new StreamSubscriber(this, new StreamScope.OneMission(id), settings.queueCapacity());
    Watch watch = watches.get(ref);
    if (watch != null && !poll(watch)) {
      // The shared watch faulted at this poll: it is gone, and its co-subscribers were told. This connect decides as it would with nobody
      // else there: a fresh watch, which starts at the end of the ledger, past a bad line (R-4).
      watch = null;
    }
    long end;
    if (watch == null) {
      // A Mission that no unscoped subscriber has discovered yet, while one listens, is watched from offset 0 so that subscriber still
      // receives every row of it; this subscriber's floor is the end of the ledger now (R-3).
      boolean replay = unscopedListening() && !known.contains(ref);
      end = joinOffset(ref, replay);
      if (replay) {
        known.add(ref);
      }
      watch = watches.get(ref);
    } else {
      end = watch.offset;
    }
    if (cursor.isEmpty()) {
      subscriber.floor(ref, end);
      attach(subscriber);
      return new ScopedConnect(subscriber, false);
    }
    Resume.Result resumed = resume(ref, id, cursor.get(), watch.mid8);
    if (!resumed.changes().isEmpty()) {
      subscriber.offer(new StreamSignal.Forwarded(new ChangeBatch(resumed.changes(), resumed.end())));
    }
    subscriber.floor(ref, resumed.end().offset());
    if (resumed.unparseable()) {
      subscriber.finish(Closure.LEDGER_UNPARSEABLE);
      gc();
      return new ScopedConnect(subscriber, true);
    }
    attach(subscriber);
    return new ScopedConnect(subscriber, false);
  }

  private boolean unscopedListening() {
    return subscribers.stream().anyMatch(other -> other.scope() instanceof StreamScope.All);
  }

  /**
   * Opens an unscoped subscription. Rows already in the ledgers are history: the watches are first brought up to date for the
   * subscribers that are already there, and the new subscriber's floor for each Mission is that Mission's end at this moment, so
   * nothing written before this call reaches it. A Mission that nobody has discovered yet while another unscoped subscriber listens
   * (it was created after the last listing) is watched from offset 0 like a later discovery, so that subscriber still receives every
   * row of it, the ones the new subscriber skips included.
   */
  public UnscopedConnect connectUnscoped(List<MissionRef> listed) {
    lock.lock();
    try {
      pollAll();
      boolean othersListening = unscopedListening();
      StreamSubscriber subscriber = new StreamSubscriber(this, new StreamScope.All(), settings.queueCapacity());
      List<Diagnostic> skipped = new ArrayList<>();
      for (MissionRef ref : listed) {
        boolean undiscovered = !known.contains(ref);
        try {
          subscriber.floor(ref, joinOffset(ref, undiscovered && othersListening));
          // Known only once the watch exists: a Mission that could not be watched is found again by the next listing.
          known.add(ref);
        } catch (Skipped notWatched) {
          skipped.add(notWatched.diagnostic());
        }
      }
      if (lastListing == null) {
        lastListing = clock.instant();
      }
      attach(subscriber);
      return new UnscopedConnect(subscriber, skipped);
    } catch (RuntimeException refused) {
      gc();
      throw refused;
    } finally {
      lock.unlock();
    }
  }

  /**
   * The end of the Mission's ledger now, creating the watch if there is none: from the end, or, when {@code replay} is set, from
   * offset 0 so that the next poll delivers the rows to the subscribers that were there before.
   */
  private long joinOffset(MissionRef ref, boolean replay) {
    Watch watch = watches.get(ref);
    if (watch != null) {
      return watch.offset;
    }
    watch = createWatch(ref, replay);
    if (!replay) {
      return watch.offset;
    }
    try {
      return terminatedEnd(source.readLedgerFrom(ref, 0));
    } catch (SourceFault fault) {
      watches.remove(ref);
      throw new Skipped(new Diagnostic(ledgerStageCode(fault.kind()), watch.mid8, null));
    }
  }

  /** The catch-up read, with a fault of the ledger turned into the row's diagnostic for the caller to report. */
  Resume.Result resume(MissionRef ref, MissionId id, StreamCursor from, String mid8) {
    try {
      return Resume.from(source, ref, id, from);
    } catch (SourceFault fault) {
      throw new Skipped(new Diagnostic(ledgerStageCode(fault.kind()), mid8, null));
    }
  }

  // ---- watches ---------------------------------------------------------------------------------------------------------------

  /** Starts watching a Mission: from offset 0 for a Mission discovered after connect, from its current end otherwise. */
  private Watch createWatch(MissionRef ref, boolean fromStart) {
    MissionMeta meta;
    try {
      meta = source.readMeta(ref);
    } catch (SourceFault fault) {
      throw new Skipped(new Diagnostic(metaStageCode(fault.kind()), Diagnostic.NONE, null));
    }
    Watch watch = new Watch(ref, meta.missionId());
    try {
      if (!fromStart) {
        watch.stamp = source.stampLedger(ref);
        baseline(watch, source.readLedgerFrom(ref, 0));
      }
    } catch (SourceFault fault) {
      throw new Skipped(new Diagnostic(ledgerStageCode(fault.kind()), watch.mid8, null));
    }
    watches.put(ref, watch);
    return watch;
  }

  /** Moves the position to the end of the terminated lines of a window read from offset 0. */
  private static void baseline(Watch watch, LedgerWindow whole) {
    String invariant = EMPTY_DIGEST;
    for (LedgerLine line : whole.lines()) {
      invariant = line.rawLineSha256();
    }
    watch.offset = terminatedEnd(whole);
    watch.invariant = invariant;
  }

  /** The byte offset just after the last terminated line of a window read from offset 0. */
  private static long terminatedEnd(LedgerWindow whole) {
    long offset = 0;
    for (LedgerLine line : whole.lines()) {
      offset += line.byteLength();
    }
    return offset;
  }

  private static DiagnosticCode metaStageCode(SourceFault.Kind kind) {
    return switch (kind) {
      case VANISHED -> DiagnosticCode.MISSION_VANISHED;
      case PATH_REFUSED -> DiagnosticCode.PATH_REFUSED;
      case META_UNPARSEABLE -> DiagnosticCode.META_UNPARSEABLE;
      case DIR_UNREADABLE, LEDGER_UNREADABLE -> DiagnosticCode.MISSION_DIR_UNREADABLE;
    };
  }

  private static DiagnosticCode ledgerStageCode(SourceFault.Kind kind) {
    return switch (kind) {
      case VANISHED -> DiagnosticCode.MISSION_VANISHED;
      case DIR_UNREADABLE -> DiagnosticCode.MISSION_DIR_UNREADABLE;
      case PATH_REFUSED, META_UNPARSEABLE, LEDGER_UNREADABLE -> DiagnosticCode.LEDGER_UNREADABLE;
    };
  }

  // ---- subscribers -----------------------------------------------------------------------------------------------------------

  private void attach(StreamSubscriber subscriber) {
    subscribers.add(subscriber);
    if (tickTask == null) {
      long millis = settings.pollInterval().toMillis();
      tickTask = executor.scheduleWithFixedDelay(this::tick, millis, millis, TimeUnit.MILLISECONDS);
    }
  }

  void detach(StreamSubscriber subscriber) {
    lock.lock();
    try {
      subscribers.remove(subscriber);
      gc();
    } finally {
      lock.unlock();
    }
  }

  /** Stops watching what nobody listens to, and stops the tick when nobody is left. */
  private void gc() {
    watches.values().removeIf(watch -> subscribers.stream().noneMatch(subscriber -> wants(subscriber, watch)));
    if (subscribers.stream().noneMatch(subscriber -> subscriber.scope() instanceof StreamScope.All)) {
      known.clear();
      skippedReported.clear();
      listingFailed = false;
      lastListing = null;
    }
    if (subscribers.isEmpty() && tickTask != null) {
      tickTask.cancel(false);
      tickTask = null;
    }
  }

  private static boolean wants(StreamSubscriber subscriber, Watch watch) {
    return switch (subscriber.scope()) {
      case StreamScope.All all -> !subscriber.dropped().contains(watch.ref);
      case StreamScope.OneMission one -> one.missionId().equals(watch.id);
    };
  }

  public int subscriberCount() {
    lock.lock();
    try {
      return subscribers.size();
    } finally {
      lock.unlock();
    }
  }

  public int watchCount() {
    lock.lock();
    try {
      return watches.size();
    } finally {
      lock.unlock();
    }
  }

  // ---- the tick --------------------------------------------------------------------------------------------------------------

  void tick() {
    lock.lock();
    try {
      guarded(this::pollAll);
      guarded(this::listIfDue);
    } finally {
      lock.unlock();
    }
  }

  /**
   * A failure nobody anticipated must not end the tick for good: an exception that escapes a task of {@code scheduleWithFixedDelay}
   * cancels every later run, and every open stream would go silent. It is reported once (without a value) and the schedule goes on.
   */
  private void guarded(Runnable step) {
    try {
      step.run();
    } catch (RuntimeException stray) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
    }
  }

  private void pollAll() {
    for (Watch watch : new ArrayList<>(watches.values())) {
      poll(watch);
    }
  }

  /** Polls one watch; false when it faulted and is no longer watched. */
  private boolean poll(Watch watch) {
    try {
      LedgerStamp stamp = source.stampLedger(watch.ref);
      if (!stamp.equals(watch.stamp)) {
        consume(watch, source.readLedgerFrom(watch.ref, watch.offset), stamp);
      }
      return watches.containsKey(watch.ref);
    } catch (SourceFault fault) {
      fault(watch, fault.kind() == SourceFault.Kind.VANISHED ? Closure.MISSION_VANISHED : Closure.LEDGER_UNREADABLE);
      return false;
    } catch (RuntimeException unexpected) {
      fault(watch, Closure.LEDGER_UNREADABLE);
      return false;
    }
  }

  private void consume(Watch watch, LedgerWindow window, LedgerStamp stamp) {
    StreamSignal.Truncated truncation = truncation(watch, window);
    if (truncation != null) {
      fanOut(watch, truncation);
      resetFloors(watch);
      baseline(watch, source.readLedgerFrom(watch.ref, 0));
      watch.stamp = stamp;
      return;
    }
    List<Change> changes = new ArrayList<>();
    boolean unparseable = false;
    for (LedgerLine line : window.lines()) {
      if (Resume.isUnparseable(line.kind())) {
        unparseable = true;
        break;
      }
      watch.offset += line.byteLength();
      watch.invariant = line.rawLineSha256();
      if (Resume.isForwarded(line.kind())) {
        changes.add(new Change(watch.id, line.kind(), new StreamCursor(watch.offset, watch.invariant)));
      }
    }
    watch.stamp = stamp;
    deliver(watch, changes);
    if (unparseable) {
      fault(watch, Closure.LEDGER_UNPARSEABLE);
    }
  }

  /** The log shrank (smaller than the position) or its last consumed line no longer hashes to the position's digest. */
  private static StreamSignal.Truncated truncation(Watch watch, LedgerWindow window) {
    if (window.size() < watch.offset) {
      return new StreamSignal.Truncated(watch.id, StreamSignal.Truncated.Reason.SIZE_SHRINK, watch.offset);
    }
    if (!window.aligned() || !window.precedingLineSha256().equals(watch.invariant)) {
      return new StreamSignal.Truncated(watch.id, StreamSignal.Truncated.Reason.CONTENT_MISMATCH, watch.offset);
    }
    return null;
  }

  private void resetFloors(Watch watch) {
    for (StreamSubscriber subscriber : subscribers) {
      if (wants(subscriber, watch)) {
        subscriber.resetFloor(watch.ref);
      }
    }
  }

  // ---- fan-out ---------------------------------------------------------------------------------------------------------------

  /** Each interested subscriber gets the changes it has not seen, in one batch. */
  private void deliver(Watch watch, List<Change> changes) {
    if (changes.isEmpty()) {
      return;
    }
    for (StreamSubscriber subscriber : new ArrayList<>(subscribers)) {
      if (!wants(subscriber, watch)) {
        continue;
      }
      List<Change> unseen = changes.stream().filter(change -> change.cursor().offset() > subscriber.floor(watch.ref)).toList();
      if (!unseen.isEmpty()) {
        offerOrClose(subscriber, new StreamSignal.Forwarded(new ChangeBatch(unseen, unseen.getLast().cursor())));
      }
    }
  }

  private void fanOut(Watch watch, StreamSignal signal) {
    for (StreamSubscriber subscriber : new ArrayList<>(subscribers)) {
      if (wants(subscriber, watch)) {
        offerOrClose(subscriber, signal);
      }
    }
  }

  /** A signal that does not fit closes the subscriber as a slow consumer: nothing is dropped or reordered before the close. */
  private void offerOrClose(StreamSubscriber subscriber, StreamSignal signal) {
    if (!subscriber.offer(signal)) {
      subscriber.finish(Closure.SLOW_CONSUMER);
      detach(subscriber);
    }
  }

  /** A Mission faulted while watched (rows S3 to S5): one diagnostic, then a scoped stream closes and an unscoped one drops the Mission. */
  private void fault(Watch watch, Closure closure) {
    watches.remove(watch.ref);
    diagnostics.accept(new Diagnostic(codeOf(closure), watch.mid8, null));
    for (StreamSubscriber subscriber : new ArrayList<>(subscribers)) {
      if (!wants(subscriber, watch)) {
        continue;
      }
      if (subscriber.scope() instanceof StreamScope.All) {
        subscriber.dropped().add(watch.ref);
        offerOrClose(subscriber, new StreamSignal.Dropped(watch.mid8));
      } else {
        subscriber.finish(closure);
        detach(subscriber);
      }
    }
  }

  private static DiagnosticCode codeOf(Closure closure) {
    return switch (closure) {
      case MISSION_VANISHED -> DiagnosticCode.MISSION_VANISHED;
      case LEDGER_UNPARSEABLE -> DiagnosticCode.LEDGER_UNPARSEABLE;
      case LEDGER_UNREADABLE, SLOW_CONSUMER -> DiagnosticCode.LEDGER_UNREADABLE;
    };
  }

  // ---- discovery (the unscoped rule) -----------------------------------------------------------------------------------------

  /** Re-lists {@code kitty-specs/} when the interval has passed and an unscoped subscriber is listening. */
  private void listIfDue() {
    if (subscribers.stream().noneMatch(subscriber -> subscriber.scope() instanceof StreamScope.All)) {
      return;
    }
    Instant now = clock.instant();
    if (lastListing != null && now.isBefore(lastListing.plus(settings.relistInterval()))) {
      return;
    }
    lastListing = now;
    List<MissionRef> listed;
    try {
      listed = source.listMissions();
    } catch (RuntimeException fault) {
      if (!listingFailed) {
        listingFailed = true;
        diagnostics.accept(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
      }
      return;
    }
    listingFailed = false;
    for (MissionRef ref : listed) {
      if (!known.contains(ref)) {
        discover(ref);
      }
    }
  }

  /** A listed Mission nobody has seen: watched from offset 0, and known only once that worked, so a failure is retried by the next listing. */
  private void discover(MissionRef ref) {
    if (watches.containsKey(ref)) {
      known.add(ref);
      return;
    }
    try {
      Watch watch = createWatch(ref, true);
      known.add(ref);
      skippedReported.remove(ref);
      poll(watch);
    } catch (Skipped notWatched) {
      if (skippedReported.add(ref)) {
        diagnostics.accept(notWatched.diagnostic());
      }
    } catch (RuntimeException stray) {
      if (skippedReported.add(ref)) {
        diagnostics.accept(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
      }
    }
  }
}
