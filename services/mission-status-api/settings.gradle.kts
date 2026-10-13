// Standalone build: deliberately NOT included in contracts/settings.gradle (separate dependency set, separate verification
// metadata). No toolchain resolver plugin (no implicit JDK download; see gradle.properties). Dependencies come from Maven Central
// and the Gradle plugin portal only.
pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
    }
}

rootProject.name = "mission-status-api"
