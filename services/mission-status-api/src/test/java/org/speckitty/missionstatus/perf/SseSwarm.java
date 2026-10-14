package org.speckitty.missionstatus.perf;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.SocketChannel;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicIntegerArray;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Many event-stream connections read by ONE thread (an NIO selector). The clients of a thread-count budget must not add threads of their
 * own: this class starts exactly one platform thread, when it is created, so a baseline taken after {@link #start()} already counts it.
 * Connections are plain loopback sockets that send the accepted Host ({@code 127.0.0.1:<port>}); a connection counts the
 * {@code event: status-transition} lines it receives and ignores heartbeat comments.
 */
public final class SseSwarm implements AutoCloseable {

  private static final String EVENT_LINE = "event: status-transition\n";
  private static final int KEEP = EVENT_LINE.length() + 8;

  private final Selector selector;
  private final Thread reader;
  // The reader thread takes each new channel with its index from this queue; it never reads `channels`, which only the caller's
  // thread appends to (an unsynchronised list read across threads once lost the reader thread on Windows: 61 of 100 opened).
  private final Queue<Pending> pending = new ConcurrentLinkedQueue<>();
  private final List<SocketChannel> channels = new ArrayList<>();
  private final AtomicInteger open = new AtomicInteger();
  private final AtomicInteger refused = new AtomicInteger();
  private volatile AtomicIntegerArray counts = new AtomicIntegerArray(0);
  private volatile boolean closed;
  private volatile Throwable readerFailure;

  private SseSwarm() {
    try {
      this.selector = Selector.open();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
    this.reader = new Thread(this::loop, "perf-sse-clients");
    this.reader.setDaemon(true);
  }

  /** Creates the swarm and starts its one thread. */
  public static SseSwarm start() {
    SseSwarm swarm = new SseSwarm();
    swarm.reader.start();
    return swarm;
  }


  /** Opens {@code count} more connections to {@code /api/v1/events} (unscoped) of the server on {@code port}. */
  public void connect(int port, int count) {
    int first = channels.size();
    counts = grow(counts, first + count);
    for (int i = 0; i < count; i++) {
      try {
        SocketChannel channel = SocketChannel.open(new InetSocketAddress("127.0.0.1", port));
        String request = "GET /api/v1/events HTTP/1.1\r\nHost: 127.0.0.1:" + port + "\r\nAccept: text/event-stream\r\n\r\n";
        channel.write(ByteBuffer.wrap(request.getBytes(StandardCharsets.ISO_8859_1)));
        channels.add(channel);
        pending.add(new Pending(channel, first + i));
        selector.wakeup();
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }
  }

  private static AtomicIntegerArray grow(AtomicIntegerArray old, int size) {
    AtomicIntegerArray bigger = new AtomicIntegerArray(size);
    for (int i = 0; i < old.length(); i++) {
      bigger.set(i, old.get(i));
    }
    return bigger;
  }

  /** Waits until {@code expected} connections have received a 200 head; fails once when they have not within {@code bound}. */
  public void awaitOpen(int expected, Duration bound) {
    long deadline = System.nanoTime() + bound.toNanos();
    while (open.get() < expected && System.nanoTime() < deadline) {
      pause(20);
    }
    if (open.get() < expected) {
      throw new AssertionError(
          "only " + open.get() + " of " + expected + " stream connections were accepted within " + bound.toSeconds() + " s (" + refused.get()
              + " refused)" + (readerFailure == null ? "" : "; the client reader thread failed: " + readerFailure),
          readerFailure);
    }
  }

  /** Events received so far, per connection. */
  public int[] received() {
    AtomicIntegerArray now = counts;
    int[] out = new int[now.length()];
    for (int i = 0; i < out.length; i++) {
      out[i] = now.get(i);
    }
    return out;
  }

  public int minReceived() {
    int min = Integer.MAX_VALUE;
    for (int count : received()) {
      min = Math.min(min, count);
    }
    return min == Integer.MAX_VALUE ? 0 : min;
  }

  /** Waits for every connection to have {@code events} events; true when they have, false at the bound (the caller fails the test, once). */
  public boolean awaitEveryConnectionHas(int events, Duration bound) {
    long deadline = System.nanoTime() + bound.toNanos();
    while (minReceived() < events && System.nanoTime() < deadline) {
      pause(25);
    }
    return minReceived() >= events;
  }

  private void loop() {
    ByteBuffer buffer = ByteBuffer.allocate(8192);
    try {
      while (!closed) {
        selector.select(250);
        Pending fresh;
        while ((fresh = pending.poll()) != null) {
          fresh.channel().configureBlocking(false);
          fresh.channel().register(selector, SelectionKey.OP_READ, new Conn(fresh.index()));
        }
        for (SelectionKey key : selector.selectedKeys()) {
          read(key, buffer);
        }
        selector.selectedKeys().clear();
      }
    } catch (IOException | java.nio.channels.ClosedSelectorException ended) {
      // closing the swarm ends the loop
    } catch (RuntimeException | Error failure) {
      // Any other failure ends the only reader: record it so awaitOpen reports it instead of a bare shortfall.
      readerFailure = failure;
    }
  }

  private void read(SelectionKey key, ByteBuffer buffer) {
    Conn conn = (Conn) key.attachment();
    SocketChannel channel = (SocketChannel) key.channel();
    try {
      buffer.clear();
      int read = channel.read(buffer);
      if (read < 0) {
        key.cancel();
        return;
      }
      conn.text.append(new String(buffer.array(), 0, read, StandardCharsets.ISO_8859_1));
      if (!conn.headSeen) {
        int end = conn.text.indexOf("\r\n\r\n");
        if (end < 0) {
          return;
        }
        conn.headSeen = true;
        boolean ok = conn.text.indexOf("HTTP/1.1 200") == 0;
        conn.text.delete(0, end + 4);
        if (ok) {
          open.incrementAndGet();
        } else {
          refused.incrementAndGet();
        }
      }
      int at;
      while ((at = conn.text.indexOf(EVENT_LINE)) >= 0) {
        counts.incrementAndGet(conn.index);
        conn.text.delete(0, at + EVENT_LINE.length());
      }
      if (conn.text.length() > KEEP) {
        conn.text.delete(0, conn.text.length() - KEEP);
      }
    } catch (IOException gone) {
      key.cancel();
    }
  }

  private record Pending(SocketChannel channel, int index) {}

  private static final class Conn {
    final int index;
    final StringBuilder text = new StringBuilder();
    boolean headSeen;

    Conn(int index) {
      this.index = index;
    }
  }

  private static void pause(long millis) {
    try {
      Thread.sleep(millis);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  @Override
  public void close() {
    closed = true;
    selector.wakeup();
    for (SocketChannel channel : channels) {
      try {
        channel.close();
      } catch (IOException ignored) {
        // a client socket cannot fail the test by closing
      }
    }
    try {
      selector.close();
    } catch (IOException ignored) {
      // the swarm is over
    }
  }
}
