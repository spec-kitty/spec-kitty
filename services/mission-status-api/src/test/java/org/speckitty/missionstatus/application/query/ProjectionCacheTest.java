package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/** FR-007: the cache key is the stamp; a warm request reads and reduces nothing. */
class ProjectionCacheTest {

  private static FixtureSpec threeMissions() {
    return FixtureSpec.of(
        Fx.mission("alpha", Rows.ALPHA_ID, "2026-09-02T10:00:00+00:00", Fx.twoMoves("WP01", 1)),
        Fx.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Fx.twoMoves("WP01", 10)),
        Fx.mission("gamma", Rows.GAMMA_ID, "2026-09-04T10:00:00+00:00", Fx.twoMoves("WP01", 20)));
  }

  @Test
  void ac7aTwoRequestsWithNoAppendsReadEveryLedgerOnceAndStampEachMissionOnTheSecond() {
    Fx fx = new Fx(threeMissions());

    fx.service.missions(new PageRequest(null, null));
    assertThat(fx.source.calls("readLedger")).isEqualTo(3);
    assertThat(fx.cache.reductions()).isEqualTo(3);
    fx.source.resetCalls();
    fx.service.missions(new PageRequest(null, null));

    assertThat(fx.source.calls("readLedger")).as("warm: zero whole-ledger reads").isZero();
    assertThat(fx.source.calls("stampLedger")).as("warm: one stat per Mission").isEqualTo(3);
    assertThat(fx.cache.reductions()).as("an equal stamp never re-reduces").isEqualTo(3);
  }

  @Test
  void theProjectHeaderIsServedFromTheSameCache() {
    Fx fx = new Fx(threeMissions());
    fx.service.missions(new PageRequest(null, null));
    fx.source.resetCalls();

    fx.service.project();

    assertThat(fx.source.calls("readLedger")).isZero();
    assertThat(fx.cache.reductions()).isEqualTo(3);
  }

  @Test
  void ac7bAnAppendInvalidatesOnlyThatMission() {
    Fx fx = new Fx(threeMissions());
    fx.service.missions(new PageRequest(null, null));
    fx.source.resetCalls();

    fx.source.appendLedger("beta", Rows.status(Rows.id(12), Fx.T2, "WP02", "planned", "claimed"));
    var page = fx.service.missions(new PageRequest(null, null));

    assertThat(fx.source.calls("readLedger")).isEqualTo(1);
    assertThat(fx.cache.reductions()).isEqualTo(4);
    assertThat(page.items()).filteredOn(item -> item.slug().equals("beta")).singleElement().satisfies(item -> assertThat(item.wpTotal()).isEqualTo(2));
    assertThat(page.items()).filteredOn(item -> item.slug().equals("alpha")).singleElement().satisfies(item -> assertThat(item.wpTotal()).isEqualTo(1));
  }

  @Test
  void aSameLengthRewriteOfTheLastLineChangesTheStampAndIsRead() {
    Fx fx = new Fx(threeMissions());
    fx.service.missions(new PageRequest(null, null));
    fx.source.resetCalls();

    String original = Fx.twoMoves("WP01", 1);
    String rewritten = original.replace(Rows.id(2), Rows.id(9));
    assertThat(rewritten).hasSameSizeAs(original);
    fx.source.replaceLedger("alpha", rewritten.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    fx.service.missions(new PageRequest(null, null));

    assertThat(fx.source.calls("readLedger")).isEqualTo(1);
  }

  @Test
  void aMissionThatDisappearedIsEvicted() {
    Fx fx = new Fx(threeMissions());
    fx.service.missions(new PageRequest(null, null));
    assertThat(fx.cache.size()).isEqualTo(3);

    fx.source.removeMission("gamma");
    fx.service.missions(new PageRequest(null, null));

    assertThat(fx.cache.size()).isEqualTo(2);
  }

  @Test
  void theCacheUnitLooksUpByStampAndCountsReductions() {
    ProjectionCache cache = new ProjectionCache(new StatusReducer(new AtThenEventId()));
    MissionRef ref = new MissionRef("m");
    LedgerStamp first = LedgerStamp.of(1, 1);
    List<LedgerLine> lines = List.of(new LedgerLine(1, "a".repeat(64), 10, new LineKind.Blank()));

    assertThat(cache.lookup(ref, first)).isEmpty();
    ProjectionCache.Entry stored = cache.load(ref, first, lines);

    assertThat(cache.lookup(ref, first)).contains(stored);
    assertThat(cache.lookup(ref, LedgerStamp.of(1, 2))).as("a changed stamp is a miss").isEmpty();
    assertThat(cache.reductions()).isEqualTo(1);
    cache.retainOnly(Set.of());
    assertThat(cache.size()).isZero();
  }

  @Test
  void aStampIsComparedByValueOnly() {
    assertThat(LedgerStamp.of(1, "x", 3L)).isEqualTo(LedgerStamp.of(1, "x", 3L)).hasSameHashCodeAs(LedgerStamp.of(1, "x", 3L));
    assertThat(LedgerStamp.of(1, "x", 3L)).isNotEqualTo(LedgerStamp.of(1, "x", 4L));
    assertThat(LedgerStamp.of(1, "secret").toString()).doesNotContain("secret");
  }

  @Test
  void theCacheIsAnApplicationInternalAndNothingOfItIsPublic() {
    assertThat(java.lang.reflect.Modifier.isPublic(ProjectionCache.class.getModifiers())).as("class").isFalse();
    assertThat(java.lang.reflect.Modifier.isPublic(ProjectionCache.Entry.class.getModifiers())).as("Entry").isFalse();
    assertThat(java.util.Arrays.stream(ProjectionCache.class.getDeclaredConstructors()).filter(c -> java.lang.reflect.Modifier.isPublic(c.getModifiers()))).as("constructors").isEmpty();
    assertThat(java.util.Arrays.stream(ProjectionCache.class.getDeclaredMethods()).filter(m -> java.lang.reflect.Modifier.isPublic(m.getModifiers()))).as("methods").isEmpty();
  }
}
