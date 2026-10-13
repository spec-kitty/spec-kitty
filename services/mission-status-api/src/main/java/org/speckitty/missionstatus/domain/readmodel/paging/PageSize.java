package org.speckitty.missionstatus.domain.readmodel.paging;

/** The bounds of the contract's {@code PageSize} parameter: minimum 1, maximum 200, default 50. */
public final class PageSize {

  public static final int MIN = 1;
  public static final int MAX = 200;
  public static final int DEFAULT = 50;

  private PageSize() {}

  /** The size applied for a request; an absent size is the default and an out-of-range one is clamped to the bounds. */
  public static int resolve(Integer requested) {
    return requested == null ? DEFAULT : Math.max(MIN, Math.min(MAX, requested));
  }
}
