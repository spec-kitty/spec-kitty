package org.speckitty.missionstatus.application.query.stream;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicBoolean;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;

/**
 * A subscription as an inbound adapter sees it: the raw feed's signals projected into {@link StreamEvent}s on the caller's thread, so the
 * queue capacity, the overflow and the order of signals are those of the raw feed. Closing it closes the feed subscription and gives back
 * its admission place, once.
 */
public final class ProjectedSubscription implements Subscription {

  private static final StreamSignal IDLE = new StreamSignal.Idle();

  private final FeedSubscription feed;
  private final EventProjection projection;
  private final StreamAdmission admission;
  private final AtomicBoolean closed = new AtomicBoolean();

  public ProjectedSubscription(FeedSubscription feed, EventProjection projection, StreamAdmission admission) {
    this.feed = Objects.requireNonNull(feed, "feed");
    this.projection = Objects.requireNonNull(projection, "projection");
    this.admission = Objects.requireNonNull(admission, "admission");
  }

  @Override
  public StreamSignal next(Duration wait) throws InterruptedException {
    return switch (feed.next(wait)) {
      case FeedSignal.Forwarded forwarded -> {
        List<StreamEvent> events = new ArrayList<>();
        for (Change change : forwarded.batch().changes()) {
          projection.project(change).ifPresent(events::add);
        }
        yield new StreamSignal.Events(events);
      }
      case FeedSignal.Truncated truncated -> new StreamSignal.Events(projection.project(truncated).map(List::of).orElse(List.of()));
      case FeedSignal.Dropped dropped -> new StreamSignal.Dropped(dropped.mid8());
      case FeedSignal.Closed ended -> new StreamSignal.Closed(ended.closure());
      case FeedSignal.Idle idle -> IDLE;
    };
  }

  @Override
  public void close() {
    feed.close();
    if (closed.compareAndSet(false, true)) {
      admission.finished(this);
    }
  }
}
