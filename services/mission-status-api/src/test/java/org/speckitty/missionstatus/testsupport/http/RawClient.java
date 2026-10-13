package org.speckitty.missionstatus.testsupport.http;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/** A raw-socket client that sends literal request bytes and reads until the server closes (the requests say {@code Connection: close}). */
public final class RawClient {

  /** The reply: the status line's code (0 when none) and the full text. */
  public record Reply(int status, String text) {}

  private RawClient() {}

  public static Reply send(int port, String requestBytes) {
    try (Socket socket = new Socket()) {
      socket.connect(new InetSocketAddress("127.0.0.1", port), 5000);
      socket.setSoTimeout(10000);
      OutputStream out = socket.getOutputStream();
      out.write(requestBytes.getBytes(StandardCharsets.ISO_8859_1));
      out.flush();
      ByteArrayOutputStream collected = new ByteArrayOutputStream();
      InputStream in = socket.getInputStream();
      byte[] buffer = new byte[4096];
      int read;
      try {
        while ((read = in.read(buffer)) >= 0) {
          collected.write(buffer, 0, read);
        }
      } catch (java.net.SocketTimeoutException timeout) {
        // return what arrived
      }
      String text = collected.toString(StandardCharsets.UTF_8);
      int status = 0;
      if (text.startsWith("HTTP/") && text.length() > 12) {
        status = Integer.parseInt(text.substring(9, 12));
      }
      return new Reply(status, text);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
