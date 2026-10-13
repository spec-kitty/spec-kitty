package org.speckitty.missionstatus.perf;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** Request timing over a fixed number of concurrent keep-alive connections; the numbers are nanoseconds per request. */
final class Latency {

  private static final HttpClient CLIENT = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();

  private Latency() {}

  /** One timed GET; fails the test when the answer is not 200 with a body. */
  static long timedGet(int port, String path) {
    HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET().build();
    long start = System.nanoTime();
    try {
      HttpResponse<byte[]> response = CLIENT.send(request, HttpResponse.BodyHandlers.ofByteArray());
      long elapsed = System.nanoTime() - start;
      if (response.statusCode() != 200 || response.body().length == 0) {
        throw new AssertionError("GET " + path + " answered " + response.statusCode() + " with " + response.body().length + " byte(s)");
      }
      return elapsed;
    } catch (IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  /** {@code connections} workers each send {@code perConnection} requests one after the other; all timings, unsorted. */
  static long[] run(int port, String path, int connections, int perConnection) {
    try (ExecutorService workers = Executors.newVirtualThreadPerTaskExecutor()) {
      List<Future<long[]>> parts = new ArrayList<>();
      for (int c = 0; c < connections; c++) {
        parts.add(
            workers.submit(
                () -> {
                  long[] times = new long[perConnection];
                  for (int i = 0; i < perConnection; i++) {
                    times[i] = timedGet(port, path);
                  }
                  return times;
                }));
      }
      long[] all = new long[connections * perConnection];
      int at = 0;
      for (Future<long[]> part : parts) {
        long[] times = part.get();
        System.arraycopy(times, 0, all, at, times.length);
        at += times.length;
      }
      return all;
    } catch (java.util.concurrent.ExecutionException failure) {
      if (failure.getCause() instanceof AssertionError assertion) {
        throw assertion;
      }
      throw new IllegalStateException(failure.getCause());
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  /** The 95th percentile (nearest rank) in milliseconds. */
  static double p95Ms(long[] nanos) {
    long[] sorted = nanos.clone();
    Arrays.sort(sorted);
    int rank = (int) Math.ceil(0.95 * sorted.length) - 1;
    return sorted[Math.max(0, rank)] / 1_000_000.0;
  }

  static double medianMs(long[] nanos) {
    long[] sorted = nanos.clone();
    Arrays.sort(sorted);
    return sorted[sorted.length / 2] / 1_000_000.0;
  }

  static long[] concat(long[] a, long[] b) {
    long[] all = Arrays.copyOf(a, a.length + b.length);
    System.arraycopy(b, 0, all, a.length, b.length);
    return all;
  }
}
