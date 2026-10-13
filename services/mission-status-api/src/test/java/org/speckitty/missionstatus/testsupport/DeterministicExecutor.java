package org.speckitty.missionstatus.testsupport;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.AbstractExecutorService;
import java.util.concurrent.Callable;
import java.util.concurrent.Delayed;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * A scheduled executor that never starts a thread: scheduled tasks run only when a test calls {@link #tick()}. It makes the feed's
 * poll tick deterministic, with no sleeps.
 */
public final class DeterministicExecutor extends AbstractExecutorService implements ScheduledExecutorService {

  private final class Task implements ScheduledFuture<Object> {
    final Runnable body;
    boolean cancelled;

    Task(Runnable body) {
      this.body = body;
    }

    @Override
    public boolean cancel(boolean mayInterrupt) {
      cancelled = true;
      return true;
    }

    @Override
    public boolean isCancelled() {
      return cancelled;
    }

    @Override
    public boolean isDone() {
      return cancelled;
    }

    @Override
    public Object get() {
      return null;
    }

    @Override
    public Object get(long timeout, TimeUnit unit) {
      return null;
    }

    @Override
    public long getDelay(TimeUnit unit) {
      return 0;
    }

    @Override
    public int compareTo(Delayed other) {
      return 0;
    }
  }

  private final List<Task> tasks = new ArrayList<>();
  private boolean shutdown;

  /** Runs every live scheduled task once, in scheduling order. */
  public void tick() {
    for (Task task : new ArrayList<>(tasks)) {
      if (!task.cancelled) {
        task.body.run();
      }
    }
  }

  /** The number of scheduled tasks that have not been cancelled. */
  public int liveTasks() {
    return (int) tasks.stream().filter(task -> !task.cancelled).count();
  }

  private ScheduledFuture<?> add(Runnable command) {
    Task task = new Task(command);
    tasks.add(task);
    return task;
  }

  @Override
  public ScheduledFuture<?> scheduleWithFixedDelay(Runnable command, long initialDelay, long delay, TimeUnit unit) {
    return add(command);
  }

  @Override
  public ScheduledFuture<?> scheduleAtFixedRate(Runnable command, long initialDelay, long period, TimeUnit unit) {
    return add(command);
  }

  @Override
  public ScheduledFuture<?> schedule(Runnable command, long delay, TimeUnit unit) {
    return add(command);
  }

  @Override
  public <V> ScheduledFuture<V> schedule(Callable<V> callable, long delay, TimeUnit unit) {
    throw new UnsupportedOperationException();
  }

  @Override
  public void execute(Runnable command) {
    command.run();
  }

  @Override
  public void shutdown() {
    shutdown = true;
  }

  @Override
  public List<Runnable> shutdownNow() {
    shutdown = true;
    return List.of();
  }

  @Override
  public boolean isShutdown() {
    return shutdown;
  }

  @Override
  public boolean isTerminated() {
    return shutdown;
  }

  @Override
  public boolean awaitTermination(long timeout, TimeUnit unit) {
    return shutdown;
  }
}
