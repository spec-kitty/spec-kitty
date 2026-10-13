package org.speckitty.missionstatus.testsupport.http;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpHeaders;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * A client of the event stream over a real socket: it reads the response on its own thread, splits it into frames at the blank line
 * and hands them out with a bound on every wait (a wait that times out returns null; nothing here waits unbounded). A refused
 * connection is the status and the whole body; an accepted one keeps its frames and records the end of the stream.
 */
public final class SseClient implements AutoCloseable {

  /** One thing the stream sent: a named event or a comment line. */
  public sealed interface Item permits Event, Comment {}

  /** An event as received: name, id (null when there is no {@code id:} line), the data text and the raw frame text. */
  public record Event(String name, String id, String data, String raw) implements Item {}

  /** A comment frame ({@code : heartbeat}): the text after the colon, one leading space removed, and the raw frame text. */
  public record Comment(String text, String raw) implements Item {}

  private static final HttpClient CLIENT = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();

  private final int status;
  private final HttpHeaders headers;
  private final InputStream stream;
  private final BlockingQueue<Item> items = new LinkedBlockingQueue<>();
  private final List<Item> received = java.util.Collections.synchronizedList(new ArrayList<>());
  private final StringBuilder everything = new StringBuilder();
  private final StringBuilder body = new StringBuilder();
  private final Thread reader;
  private volatile boolean ended;

  private SseClient(HttpResponse<InputStream> response) {
    this.status = response.statusCode();
    this.headers = response.headers();
    this.stream = response.body();
    this.reader = Thread.ofVirtual().name("sse-client").unstarted(this::read);
    this.reader.start();
  }

  /** Opens {@code pathAndQuery} on the harness's port with the given header pairs ({@code name, value, name, value ...}). */
  public static SseClient open(HttpHarness harness, String pathAndQuery, String... headerPairs) {
    return open(harness.port(), pathAndQuery, headerPairs);
  }

  public static SseClient open(int port, String pathAndQuery, String... headerPairs) {
    try {
      HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + pathAndQuery)).GET().header("Accept", "text/event-stream");
      for (int i = 0; i + 1 < headerPairs.length; i += 2) {
        request.header(headerPairs[i], headerPairs[i + 1]);
      }
      return new SseClient(CLIENT.send(request.build(), HttpResponse.BodyHandlers.ofInputStream()));
    } catch (IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  private void read() {
    try (BufferedReader in = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
      if (status != 200) {
        String line;
        while ((line = in.readLine()) != null) {
          body.append(line).append('\n');
        }
        return;
      }
      StringBuilder frame = new StringBuilder();
      String line;
      while ((line = in.readLine()) != null) {
        synchronized (everything) {
          everything.append(line).append('\n');
        }
        if (line.isEmpty()) {
          if (frame.length() > 0) {
            publish(frame.toString());
            frame.setLength(0);
          }
        } else {
          frame.append(line).append('\n');
        }
      }
    } catch (IOException closed) {
      // the connection ended or this client closed it
    } finally {
      ended = true;
    }
  }

  private void publish(String raw) {
    String name = null;
    String id = null;
    StringBuilder data = new StringBuilder();
    boolean comment = false;
    String commentText = null;
    for (String line : raw.split("\n")) {
      if (line.startsWith(":")) {
        comment = true;
        commentText = line.substring(1).startsWith(" ") ? line.substring(2) : line.substring(1);
      } else if (line.startsWith("event:")) {
        name = value(line, "event:");
      } else if (line.startsWith("id:")) {
        id = value(line, "id:");
      } else if (line.startsWith("data:")) {
        if (data.length() > 0) {
          data.append('\n');
        }
        data.append(value(line, "data:"));
      }
    }
    Item item = comment && name == null ? new Comment(commentText, raw) : new Event(name, id, data.toString(), raw);
    received.add(item);
    items.add(item);
  }

  private static String value(String line, String prefix) {
    String rest = line.substring(prefix.length());
    return rest.startsWith(" ") ? rest.substring(1) : rest;
  }

  public int status() {
    return status;
  }

  public String header(String name) {
    return headers.firstValue(name).orElse(null);
  }

  /** The text of a refused connection's body (waits for the end of the stream). */
  public String body() {
    awaitEnd(Duration.ofSeconds(5));
    return body.toString();
  }

  /** The next item, or null when none arrives within {@code wait}. */
  public Item next(Duration wait) {
    try {
      return items.poll(wait.toNanos(), TimeUnit.NANOSECONDS);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  /** The next EVENT within {@code wait} (comments in between are skipped but kept in {@link #items()}), or null. */
  public Event nextEvent(Duration wait) {
    long deadline = System.nanoTime() + wait.toNanos();
    while (true) {
      long left = deadline - System.nanoTime();
      if (left <= 0) {
        return null;
      }
      Item item = next(Duration.ofNanos(left));
      if (item == null) {
        return null;
      }
      if (item instanceof Event event) {
        return event;
      }
    }
  }

  /** Events within {@code wait} until {@code count} have arrived (fewer when the wait ends first). */
  public List<Event> events(int count, Duration wait) {
    List<Event> events = new ArrayList<>();
    long deadline = System.nanoTime() + wait.toNanos();
    while (events.size() < count) {
      Event event = nextEvent(Duration.ofNanos(Math.max(0, deadline - System.nanoTime())));
      if (event == null) {
        break;
      }
      events.add(event);
    }
    return events;
  }

  /** Every item received so far, in order. */
  public List<Item> items() {
    synchronized (received) {
      return List.copyOf(received);
    }
  }

  /** True when no item arrives within {@code wait}. */
  public boolean quietFor(Duration wait) {
    return next(wait) == null;
  }

  /** Waits for the server to end the stream (EOF); true when it ended within {@code wait}. */
  public boolean awaitEnd(Duration wait) {
    long deadline = System.nanoTime() + wait.toNanos();
    while (!ended && System.nanoTime() < deadline) {
      try {
        reader.join(Duration.ofMillis(10));
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException(interrupted);
      }
    }
    return ended;
  }

  /** Every line received, joined (for scans of the whole stream). */
  public String transcript() {
    synchronized (everything) {
      return everything.toString();
    }
  }

  @Override
  public void close() {
    try {
      stream.close();
    } catch (IOException ignored) {
      // closing a stream that already ended
    }
  }
}
