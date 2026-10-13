package org.speckitty.missionstatus.perf;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadInfo;
import java.util.regex.Pattern;

/**
 * Live platform threads, with the carrier pool of the virtual-thread scheduler counted apart. Carriers are platform threads named
 * {@code ForkJoinPool-<n>-worker-<m>}; their number is capped by the core count of the runner (parallelism) and does not grow with the
 * number of connections, so a budget on "threads per connection" has to read them separately or it measures the runner (24 carriers on
 * a 24-core workstation, 4 on a CI runner). The raw total is always printed beside the net figure.
 */
public final class PlatformThreads {

  private static final Pattern CARRIER = Pattern.compile("ForkJoinPool-\\d+-worker-\\d+");

  /** The live platform threads now: all of them, and how many of those are virtual-thread carriers. */
  public record Count(int total, int carriers) {
    /** Threads that are not carriers: the ones a per-connection leak would add to. */
    public int net() {
      return total - carriers;
    }
  }

  private PlatformThreads() {}

  public static Count count() {
    var bean = ManagementFactory.getThreadMXBean();
    int total = 0;
    int carriers = 0;
    for (ThreadInfo info : bean.getThreadInfo(bean.getAllThreadIds())) {
      if (info == null) {
        continue;
      }
      total++;
      if (CARRIER.matcher(info.getThreadName()).matches()) {
        carriers++;
      }
    }
    return new Count(total, carriers);
  }
}
