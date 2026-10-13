package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** The actor value: the handle shape of the contract's {@code ActorHandle}, applied to each of the three handles. */
class ActorTest {

  @Test
  void aHandleKeepsLettersDigitsAndTheFourPunctuationCharacters() {
    Actor actor = new Actor("Claude-4.1", "role_x", "java:Jenny0");

    assertThat(actor.tool()).isEqualTo("Claude-4.1");
    assertThat(actor.role()).isEqualTo("role_x");
    assertThat(actor.profile()).isEqualTo("java:Jenny0");
  }

  @Test
  void aHandleThatDoesNotFitIsNullAndTheOthersAreKept() {
    Actor actor = new Actor("user@example.com", "a b", "ok");

    assertThat(actor).isEqualTo(new Actor(null, null, "ok"));
  }

  @Test
  void theLengthBoundIs128CharactersAndAnEmptyHandleIsNull() {
    assertThat(new Actor("x".repeat(128), null, null).tool()).hasSize(128);
    assertThat(new Actor("x".repeat(129), "", null)).isEqualTo(Actor.NONE);
  }

  @Test
  void everyCharacterAtTheEdgeOfEachAllowedClassIsKeptAndTheNeighboursAreNot() {
    for (String kept : new String[] {"a", "z", "A", "Z", "0", "9", ".", "_", ":", "-"}) {
      assertThat(new Actor(kept, null, null).tool()).as(kept).isEqualTo(kept);
    }
    for (String refused : new String[] {"`", "{", "@", "[", "/", ":" + "\n", "\n", "\t", " ", String.valueOf((char) 233), "~", ";", "<", "+", ","}) {
      assertThat(new Actor(refused, null, null).tool()).as(refused).isNull();
    }
  }

  @Test
  void aPlainTextActorIsTheToolAndAColonJoinedTextIsNotSplit() {
    assertThat(Actor.ofText("claude:opus:implementer")).isEqualTo(new Actor("claude:opus:implementer", null, null));
    assertThat(Actor.ofText("a b")).isEqualTo(Actor.NONE);
    assertThat(Actor.NONE).isEqualTo(new Actor(null, null, null));
  }

  @Test
  void theFourResolverSentinelsAreNotHandlesButTheirLookalikesAre() {
    for (String sentinel : new String[] {"__resolved_model_absent__", "__resolved_profile_absent__", "__resolved_profile_version_absent__", "__resolved_provider_absent__"}) {
      assertThat(new Actor(sentinel, sentinel, sentinel)).as(sentinel).isEqualTo(Actor.NONE);
    }
    assertThat(new Actor("__resolved_model_absent", "x__resolved_model_absent__", "ok").tool()).isEqualTo("__resolved_model_absent");
    assertThat(new Actor("__resolved_model_absent", "x__resolved_model_absent__", "ok").role()).isEqualTo("x__resolved_model_absent__");
  }
}
