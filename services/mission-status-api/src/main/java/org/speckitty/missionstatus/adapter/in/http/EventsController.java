package org.speckitty.missionstatus.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.http.MediaType;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.speckitty.missionstatus.application.query.port.in.dto.Change;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import tools.jackson.databind.json.JsonMapper;

/**
 * {@code GET /api/v1/events}: the change stream. Hand-written because the contract describes a stream of named events, which a
 * generated interface cannot (decision D-Q2). Every connect-time outcome is decided before the response starts: a refused cursor, an
 * unknown Mission and an unreadable ledger leave through the advice as a Problem, with no event sent.
 *
 * <p>Each connection owns one virtual thread that blocks on {@link Subscription#next} for one heartbeat interval; an idle wait
 * becomes the comment line {@code : heartbeat}. The emitter has no timeout ({@code new SseEmitter(0L)} and
 * {@code spring.mvc.async.request-timeout=-1}); a completed, failed or timed-out response closes the subscription, and so does a write
 * that finds the client gone, which is how a disconnect is noticed (at the next heartbeat or event write).
 */
@RestController
class EventsController {

  private static final Logger LOG = LoggerFactory.getLogger(EventsController.class);
  private static final MediaType UTF8_TEXT = new MediaType("text", "plain", StandardCharsets.UTF_8);
  private static final AtomicLong CONNECTIONS = new AtomicLong();

  private final MissionStatusQuery query;
  private final EventData data;
  private final Consumer<Diagnostic> diagnostics;
  private final Duration heartbeat;
  private final Set<Subscription> live = ConcurrentHashMap.newKeySet();
  private final int maxConnections;
  /** Streams admitted and not yet finished: from the admission to the end of {@link #pump}. */
  private final AtomicInteger admitted = new AtomicInteger();

  EventsController(
      MissionStatusQuery query,
      JsonMapper mapper,
      LeakClasses leaks,
      Consumer<Diagnostic> diagnostics,
      @Value("${mission-status.stream.heartbeat-interval:PT30S}") Duration heartbeat,
      @Value("${mission-status.stream.max-connections:128}") int maxConnections) {
    if (maxConnections < 1) {
      throw new IllegalArgumentException("mission-status.stream.max-connections must be at least 1");
    }
    if (heartbeat == null || heartbeat.isZero() || heartbeat.isNegative()) {
      throw new IllegalArgumentException("mission-status.stream.heartbeat-interval must be positive");
    }
    this.maxConnections = maxConnections;
    this.query = query;
    this.data = new EventData(mapper, leaks);
    this.diagnostics = diagnostics;
    this.heartbeat = heartbeat;
  }

  @GetMapping("/events")
  SseEmitter events(
      @RequestParam(name = "missionId", required = false) String missionId,
      @RequestParam(name = "streamCursor", required = false) String streamCursor,
      @RequestHeader(name = "Last-Event-ID", required = false) String lastEventId,
      HttpServletRequest request,
      HttpServletResponse response)
      throws HttpRequestMethodNotSupportedException {
    // Spring routes HEAD to a GET mapping. A HEAD request never writes a body, so a disconnect would never be noticed and its place never
    // freed: refuse it before anything is admitted or subscribed (the contract declares GET only).
    if ("HEAD".equals(request.getMethod())) {
      throw new HttpRequestMethodNotSupportedException("HEAD", List.of("GET"));
    }
    // streamCursor wins over Last-Event-ID (AC-3h); an empty header is no header
    String cursorText = streamCursor != null ? streamCursor : (lastEventId == null || lastEventId.isEmpty() ? null : lastEventId);
    if (cursorText != null && missionId == null) {
      throw new StreamRefused(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
    }
    Optional<StreamCursor> cursor = cursorText == null ? Optional.empty() : Optional.of(parse(cursorText));
    StreamScope scope = scope(missionId);
    // Admission bound (pre-merge fold J3): checked before subscribe(), which costs a full listing for an unscoped stream
    if (admitted.incrementAndGet() > maxConnections) {
      admitted.decrementAndGet();
      throw new StreamCapacityReached();
    }
    boolean started = false;
    try {
      SseEmitter emitter = open(scope, cursor, response);
      started = true;
      return emitter;
    } finally {
      if (!started) {
        admitted.decrementAndGet();
      }
    }
  }

  private SseEmitter open(StreamScope scope, Optional<StreamCursor> cursor, HttpServletResponse response) {
    Subscription subscription = query.subscribe(scope, cursor);
    // The response starts now, not at the first event: a client learns that the stream is open (and the subscription exists) before
    // anything has happened, and a quiet Mission does not hold the headers back until the first heartbeat.
    response.setContentType(MediaType.TEXT_EVENT_STREAM_VALUE + ";charset=UTF-8");
    response.setHeader("Cache-Control", "no-cache");
    try {
      response.flushBuffer();
    } catch (IOException gone) {
      subscription.close();
      throw new java.io.UncheckedIOException(gone);
    }
    SseEmitter emitter = new SseEmitter(0L);
    emitter.onCompletion(subscription::close);
    emitter.onTimeout(
        () -> {
          // the container ended the asynchronous cycle (only a misconfigured emitter has a timeout): finish the response so the client sees the end
          subscription.close();
          emitter.complete();
        });
    emitter.onError(failure -> subscription.close());
    boolean scoped = scope instanceof StreamScope.OneMission;
    live.add(subscription);
    Thread.ofVirtual().name("events-" + CONNECTIONS.incrementAndGet()).start(() -> pump(subscription, emitter, scoped));
    return emitter;
  }

  /** Shutting down ends every open stream first, so the container's graceful shutdown does not wait on connections that never finish. */
  @EventListener(ContextClosedEvent.class)
  void endStreams() {
    live.forEach(Subscription::close);
  }

  private static StreamCursor parse(String text) {
    try {
      return StreamCursorText.parse(text);
    } catch (StreamRefused refused) {
      if (refused.kind() == StreamRefused.Kind.MISALIGNED) {
        // a text that does not parse is misaligned, with the fixed unparseable detail
        throw new UnparseableCursor();
      }
      throw refused;
    }
  }

  private static StreamScope scope(String missionId) {
    if (missionId == null) {
      return StreamScope.all();
    }
    try {
      return StreamScope.mission(new MissionId(missionId));
    } catch (IllegalArgumentException notAUlid) {
      throw new StreamRefused(StreamRefused.Kind.UNKNOWN_MISSION);
    }
  }

  /** Runs on the connection's own thread until the stream is over or the client is gone. */
  private void pump(Subscription subscription, SseEmitter emitter, boolean scoped) {
    try {
      while (true) {
        StreamSignal signal = subscription.next(heartbeat);
        switch (signal) {
          case StreamSignal.Idle idle -> emitter.send(SseEmitter.event().comment(" heartbeat"));
          case StreamSignal.Forwarded forwarded -> {
            for (Change change : forwarded.batch().changes()) {
              send(emitter, change, scoped);
            }
          }
          case StreamSignal.Truncated truncated -> sendTruncation(emitter, truncated);
          case StreamSignal.Dropped dropped -> {
            // an unscoped stream stopped watching one Mission; the connection, the heartbeat and the other Missions stay
          }
          case StreamSignal.Closed closed -> {
            return;
          }
        }
      }
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
    } catch (IOException | IllegalStateException gone) {
      // the client went away (a failed write) or the subscription was closed under a blocked read: a disconnect
    } catch (RuntimeException unexpected) {
      LOG.error("stream failed class={}", unexpected.getClass().getSimpleName());
    } finally {
      subscription.close();
      live.remove(subscription);
      admitted.decrementAndGet();
      try {
        emitter.complete();
      } catch (RuntimeException alreadyOver) {
        // the response had already ended
      }
    }
  }

  private void send(SseEmitter emitter, Change change, boolean scoped) throws IOException {
    Optional<EventData.Frame> frame;
    try {
      frame = data.of(change);
    } catch (ProjectionError refused) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, change.missionId().mid8(), null));
      return;
    }
    if (frame.isPresent()) {
      emit(emitter, frame.get(), scoped);
    }
  }

  private void sendTruncation(SseEmitter emitter, StreamSignal.Truncated truncated) throws IOException {
    EventData.Frame frame;
    try {
      frame = data.of(truncated);
    } catch (ProjectionError refused) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, truncated.missionId().mid8(), null));
      return;
    }
    emit(emitter, frame, false);
  }

  /** The id line is the cursor after the row, on a Mission-scoped stream only; a log-truncated event never has one. */
  private static void emit(SseEmitter emitter, EventData.Frame frame, boolean scoped) throws IOException {
    SseEmitter.SseEventBuilder builder = SseEmitter.event().name(" " + frame.name());
    if (scoped && frame.resumeCursor() != null) {
      builder.id(" " + frame.resumeCursor().toText());
    }
    emitter.send(builder.data(" " + frame.data(), UTF8_TEXT));
  }

  /** The service already holds {@code mission-status.stream.max-connections} open streams: 503, the advice maps it. */
  static final class StreamCapacityReached extends RuntimeException {
    private static final long serialVersionUID = 1L;

    StreamCapacityReached() {
      super("stream capacity reached", null, false, false);
    }
  }

  /** A cursor text that is not {@code offset:digest}: misaligned, with the fixed detail (the advice maps it). */
  static final class UnparseableCursor extends RuntimeException {
    private static final long serialVersionUID = 1L;

    UnparseableCursor() {
      super("stream cursor did not parse", null, false, false);
    }
  }
}
