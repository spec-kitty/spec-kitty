package org.speckitty.missionstatus.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
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
  private final Duration heartbeat;

  EventsController(MissionStatusQuery query, JsonMapper mapper, @Value("${mission-status.stream.heartbeat-interval:PT30S}") Duration heartbeat) {
    if (heartbeat == null || heartbeat.isZero() || heartbeat.isNegative()) {
      throw new IllegalArgumentException("mission-status.stream.heartbeat-interval must be positive");
    }
    this.query = query;
    this.data = new EventData(mapper);
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
    // the order of the connect-time decisions, the admission bound and the lookup are the port's (StreamRequest, MissionStatusQuery#subscribe)
    StreamRequest streamRequest = StreamRequest.parse(missionId, cursorText);
    return open(streamRequest, response);
  }

  private SseEmitter open(StreamRequest request, HttpServletResponse response) {
    Subscription subscription = query.subscribe(request.scope(), request.cursor());
    // From here the subscription holds an admission place: any failure before the pump owns it closes it.
    try {
      // The response starts now, not at the first event: a client learns that the stream is open (and the subscription exists) before
      // anything has happened, and a quiet Mission does not hold the headers back until the first heartbeat.
      response.setContentType(MediaType.TEXT_EVENT_STREAM_VALUE + ";charset=UTF-8");
      response.setHeader("Cache-Control", "no-cache");
      try {
        response.flushBuffer();
      } catch (IOException gone) {
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
      boolean scoped = request.scope() instanceof StreamScope.OneMission;
      Thread.ofVirtual().name("events-" + CONNECTIONS.incrementAndGet()).start(() -> pump(subscription, emitter, scoped));
      return emitter;
    } catch (RuntimeException failure) {
      subscription.close();
      throw failure;
    }
  }

  /** Runs on the connection's own thread until the stream is over or the client is gone. */
  private void pump(Subscription subscription, SseEmitter emitter, boolean scoped) {
    try {
      while (true) {
        StreamSignal signal = subscription.next(heartbeat);
        switch (signal) {
          case StreamSignal.Idle idle -> emitter.send(SseEmitter.event().comment(" heartbeat"));
          case StreamSignal.Events events -> {
            for (StreamEvent event : events.events()) {
              emit(emitter, data.of(event), scoped && !(event instanceof StreamEvent.LogTruncated));
            }
          }
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
      try {
        emitter.complete();
      } catch (RuntimeException alreadyOver) {
        // the response had already ended
      }
    }
  }

  /** The id line is the cursor after the row, on a Mission-scoped stream only; a log-truncated event never has one. */
  private static void emit(SseEmitter emitter, EventData.Frame frame, boolean scoped) throws IOException {
    SseEmitter.SseEventBuilder builder = SseEmitter.event().name(" " + frame.name());
    if (scoped && frame.resumeCursor() != null) {
      builder.id(" " + frame.resumeCursor().toText());
    }
    emitter.send(builder.data(" " + frame.data(), UTF8_TEXT));
  }
}
