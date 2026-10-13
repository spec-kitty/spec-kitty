package org.speckitty.missionstatus.nativesmoke;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * A raw-socket HTTP/1.1 client for the smoke replay. It sends literal request bytes with the accepted Host ({@code 127.0.0.1:<port>}),
 * and hands back the BODY BYTES exactly as the server framed them: chunked framing and the Content-Length bound are removed, nothing
 * else is touched (no charset decoding, no parsing). Those bytes are what is compared with the goldens and what the digest covers.
 * Only loopback; no Spring.
 */
final class RawHttp {

  /** A whole response: the status code, the lower-cased header names (first value wins) and the raw body bytes. */
  record Response(int status, Map<String, String> headers, byte[] body) {
    String header(String name) {
      return headers.get(name.toLowerCase(java.util.Locale.ROOT));
    }
  }

  private RawHttp() {}

  static Response exchange(int port, String method, String path, Map<String, String> headers) {
    try (Socket socket = connect(port)) {
      socket.setSoTimeout(10_000);
      socket.getOutputStream().write(requestBytes(port, method, path, headers));
      socket.getOutputStream().flush();
      InputStream in = new BufferedInputStream(socket.getInputStream());
      Head head = readHead(in);
      return new Response(head.status(), head.headers(), bodyStream(head, in).readAllBytes());
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** The status of a probe request, or 0 when no HTTP answer arrived (nothing listening yet, connection reset). */
  static int probe(int port, String path) {
    try {
      return exchange(port, "GET", path, Map.of()).status();
    } catch (UncheckedIOException notYet) {
      return 0;
    }
  }

  private static Socket connect(int port) throws IOException {
    Socket socket = new Socket();
    try {
      socket.connect(new InetSocketAddress("127.0.0.1", port), 5_000);
      return socket;
    } catch (IOException failure) {
      socket.close();
      throw failure;
    }
  }

  private static byte[] requestBytes(int port, String method, String path, Map<String, String> headers) {
    Map<String, String> all = new LinkedHashMap<>();
    all.put("Host", "127.0.0.1:" + port);
    all.put("Connection", "close");
    headers.forEach((name, value) -> all.keySet().removeIf(existing -> existing.equalsIgnoreCase(name)));
    all.putAll(headers);
    StringBuilder text = new StringBuilder(method).append(' ').append(path).append(" HTTP/1.1\r\n");
    all.forEach((name, value) -> text.append(name).append(": ").append(value).append("\r\n"));
    return text.append("\r\n").toString().getBytes(StandardCharsets.ISO_8859_1);
  }

  private record Head(int status, Map<String, String> headers) {}

  private static Head readHead(InputStream in) throws IOException {
    ByteArrayOutputStream collected = new ByteArrayOutputStream();
    int matched = 0;
    while (matched < 4) {
      int next = in.read();
      if (next < 0) {
        throw new EOFException("the connection closed before the end of the response head");
      }
      collected.write(next);
      boolean expected = (matched % 2 == 0) ? next == '\r' : next == '\n';
      matched = expected ? matched + 1 : (next == '\r' ? 1 : 0);
    }
    String[] lines = collected.toString(StandardCharsets.ISO_8859_1).split("\r\n");
    if (lines.length == 0 || !lines[0].startsWith("HTTP/") || lines[0].length() < 12) {
      throw new IOException("not an HTTP status line");
    }
    Map<String, String> headers = new LinkedHashMap<>();
    for (int i = 1; i < lines.length; i++) {
      int colon = lines[i].indexOf(':');
      if (colon > 0) {
        headers.putIfAbsent(lines[i].substring(0, colon).trim().toLowerCase(java.util.Locale.ROOT), lines[i].substring(colon + 1).trim());
      }
    }
    return new Head(Integer.parseInt(lines[0].substring(9, 12)), headers);
  }

  private static InputStream bodyStream(Head head, InputStream in) {
    String encoding = head.headers().getOrDefault("transfer-encoding", "");
    if (encoding.toLowerCase(java.util.Locale.ROOT).contains("chunked")) {
      return new ChunkedInputStream(in);
    }
    String length = head.headers().get("content-length");
    if (length != null) {
      return new BoundedInputStream(in, Long.parseLong(length));
    }
    return in;
  }

  /** Opens an event stream: the head is read now (it is flushed at connect), the frames are collected on a thread of their own. */
  static EventStream openStream(int port, String path, Map<String, String> headers) {
    Socket socket = null;
    try {
      socket = connect(port);
      socket.setSoTimeout(10_000);
      socket.getOutputStream().write(requestBytes(port, "GET", path, headers));
      socket.getOutputStream().flush();
      InputStream in = new BufferedInputStream(socket.getInputStream());
      Head head = readHead(in);
      socket.setSoTimeout(0);
      return new EventStream(socket, head.status(), head.headers(), bodyStream(head, in));
    } catch (IOException failure) {
      try {
        if (socket != null) {
          socket.close();
        }
      } catch (IOException ignored) {
        // the first failure is the one to report
      }
      throw new UncheckedIOException(failure);
    }
  }

  /** An open event stream. Frames end at a blank line; a comment frame (a heartbeat) is counted and never delivered as an event. */
  static final class EventStream implements AutoCloseable {
    private final Socket socket;
    private final int status;
    private final Map<String, String> headers;
    private final BlockingQueue<byte[]> events = new LinkedBlockingQueue<>();
    private volatile boolean ended;

    private EventStream(Socket socket, int status, Map<String, String> headers, InputStream body) {
      this.socket = socket;
      this.status = status;
      this.headers = headers;
      Thread reader = new Thread(() -> read(body), "smoke-event-stream");
      reader.setDaemon(true);
      reader.start();
    }

    private void read(InputStream body) {
      ByteArrayOutputStream frame = new ByteArrayOutputStream();
      try {
        int previous = -1;
        int next;
        while ((next = body.read()) >= 0) {
          frame.write(next);
          if (next == '\n' && previous == '\n') {
            byte[] bytes = frame.toByteArray();
            frame.reset();
            if (bytes[0] != ':') {
              events.add(bytes);
            }
          }
          previous = next;
        }
      } catch (IOException closed) {
        // the stream ended or this client closed it
      } finally {
        ended = true;
      }
    }

    int status() {
      return status;
    }

    String header(String name) {
      return headers.get(name.toLowerCase(java.util.Locale.ROOT));
    }

    boolean ended() {
      return ended;
    }

    /** The next event frame (its bytes, blank line included), or null when none arrives within {@code bound}. */
    byte[] nextEvent(Duration bound) {
      try {
        return events.poll(bound.toMillis(), TimeUnit.MILLISECONDS);
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        return null;
      }
    }

    @Override
    public void close() {
      try {
        socket.close();
      } catch (IOException ignored) {
        // closing a client socket cannot fail the test
      }
    }
  }

  private static final class BoundedInputStream extends InputStream {
    private final InputStream in;
    private long remaining;

    BoundedInputStream(InputStream in, long length) {
      this.in = in;
      this.remaining = length;
    }

    @Override
    public int read() throws IOException {
      if (remaining <= 0) {
        return -1;
      }
      int next = in.read();
      if (next >= 0) {
        remaining--;
      }
      return next;
    }

    @Override
    public int read(byte[] buffer, int offset, int length) throws IOException {
      if (remaining <= 0) {
        return -1;
      }
      int read = in.read(buffer, offset, (int) Math.min(length, remaining));
      if (read > 0) {
        remaining -= read;
      }
      return read;
    }
  }

  private static final class ChunkedInputStream extends InputStream {
    private final InputStream in;
    private long left;
    private boolean done;

    ChunkedInputStream(InputStream in) {
      this.in = in;
    }

    @Override
    public int read() throws IOException {
      byte[] one = new byte[1];
      int read = read(one, 0, 1);
      return read < 0 ? -1 : one[0] & 0xFF;
    }

    @Override
    public int read(byte[] buffer, int offset, int length) throws IOException {
      if (done) {
        return -1;
      }
      if (left == 0) {
        String size = line();
        int extension = size.indexOf(';');
        left = Long.parseLong((extension < 0 ? size : size.substring(0, extension)).trim(), 16);
        if (left == 0) {
          while (!line().isEmpty()) {
            // trailers are skipped
          }
          done = true;
          return -1;
        }
      }
      int read = in.read(buffer, offset, (int) Math.min(length, left));
      if (read < 0) {
        throw new EOFException("the connection closed inside a chunk");
      }
      left -= read;
      if (left == 0 && !line().isEmpty()) {
        throw new IOException("a chunk is not followed by CRLF");
      }
      return read;
    }

    private String line() throws IOException {
      ByteArrayOutputStream text = new ByteArrayOutputStream();
      int next;
      while ((next = in.read()) >= 0) {
        if (next == '\n') {
          break;
        }
        text.write(next);
      }
      if (next < 0) {
        throw new EOFException("the connection closed inside the chunk framing");
      }
      String value = text.toString(StandardCharsets.ISO_8859_1);
      return value.endsWith("\r") ? value.substring(0, value.length() - 1) : value;
    }
  }
}
