package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetAddress;
import java.net.UnknownHostException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

/** The decision of the bind guard (AC-9a): only the literal 127.0.0.1 passes; unset is refused by name; the connector check demands loopback. */
class BindGuardTest {

  @Test
  void theLiteralLoopbackPasses() {
    assertThat(BindGuard.refusal("127.0.0.1")).isEmpty();
  }

  @ParameterizedTest
  @ValueSource(strings = {"0.0.0.0", "::", "::1", "localhost", "192.168.1.20", "10.0.0.5", "example.org", "127.0.0.2", " 127.0.0.1", "127.0.0.1 "})
  void anyOtherValueIsRefusedAndNamed(String address) {
    assertThat(BindGuard.refusal(address)).hasValueSatisfying(message -> assertThat(message).contains(address.trim()).contains("server.address"));
  }

  @ParameterizedTest
  @NullAndEmptySource
  @ValueSource(strings = {"   "})
  void anUnsetOrBlankValueIsRefusedAsUnset(String address) {
    assertThat(BindGuard.refusal(address)).hasValueSatisfying(message -> assertThat(message).contains("unset"));
  }

  @Test
  void theConnectorAddressMustBeLoopbackAndNeverNull() throws UnknownHostException {
    assertThat(BindGuard.connectorRefusal(InetAddress.getByName("127.0.0.1"))).isEmpty();
    assertThat(BindGuard.connectorRefusal(null)).hasValueSatisfying(message -> assertThat(message).contains("all interfaces"));
    assertThat(BindGuard.connectorRefusal(InetAddress.getByName("0.0.0.0"))).isPresent();
    assertThat(BindGuard.connectorRefusal(InetAddress.getByName("::"))).isPresent();
    assertThat(BindGuard.connectorRefusal(InetAddress.getByName("192.0.2.7"))).isPresent();
  }
}
