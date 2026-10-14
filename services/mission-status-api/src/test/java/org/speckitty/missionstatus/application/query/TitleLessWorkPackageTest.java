package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.detail.MissionDetailRowsTest;
import org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * V27: a Work Package file with no {@code title} is a valid indexed file whose display title is its id (spec line 289, the rule {@code dependencyTitle}
 * already follows). The oracle serves a null title there, which the contract's {@code minLength: 1} forbids, so the divergence is recorded.
 */
class TitleLessWorkPackageTest {

  private static DetailFixture titleLess() {
    return DetailRoute.fixture(root -> DetailRoute.write(root, "tasks/WP02-two.md", "---\nwork_package_id: WP02\n---\n\nBody of WP02\n"));
  }

  @Test
  void theMissionSummaryOfATitleLessWorkPackageShowsItsId() {
    DetailFixture fixture = titleLess();

    var summaries = MissionDetailRowsTest.serviceOver(fixture).mission(new MissionId(DetailRoute.ID)).workPackages();

    assertThat(summaries).filteredOn(summary -> summary.wpId().value().equals("WP02")).singleElement().satisfies(summary -> assertThat(summary.title()).isEqualTo("WP02"));
    assertThat(summaries).filteredOn(summary -> summary.wpId().value().equals("WP01")).singleElement().satisfies(summary -> assertThat(summary.title()).isNotEqualTo("WP01"));
  }

  @Test
  void theWorkPackageViewOfATitleLessWorkPackageShowsItsId() {
    DetailFixture fixture = titleLess();

    var view = WorkPackageControllerRowsTest.serviceOver(fixture).workPackage(new MissionId(DetailRoute.ID), new WpId("WP02"), false);

    assertThat(view.title()).isEqualTo("WP02");
  }
}
