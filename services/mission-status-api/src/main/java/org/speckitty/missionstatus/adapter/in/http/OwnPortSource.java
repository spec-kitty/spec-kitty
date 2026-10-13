package org.speckitty.missionstatus.adapter.in.http;

/** The port the server is bound to, as the Host and Origin filter needs it. Implemented in {@code config}, which listens for the bound server. */
public interface OwnPortSource {

  /** The bound port, or a negative number while no server is bound (nothing is then accepted). */
  int port();
}
