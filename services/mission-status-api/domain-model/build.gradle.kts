import org.gradle.api.tasks.testing.logging.TestExceptionFormat
import org.springframework.boot.gradle.plugin.SpringBootPlugin

// domain-model: the shared Mission status types (Mission, work package, lane, status event and snapshot). A library of #6117
// decision 12, extracted from the query service by #6192. It is framework-free and uses no java.io or java.nio.file: it declares no
// dependency outside the tests, and DomainModelBoundaryTest holds its classes to the JDK packages of the root architecture rule 1b.
// The Spring Boot BOM is imported for the test libraries' versions only (no version literal in this script, as in the root).

plugins {
    `java-library`
    jacoco
    id("io.spring.dependency-management")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}

dependencies {
    testImplementation(libs.junit.jupiter)
    testImplementation(libs.assertj.core)
    testImplementation(libs.archunit.junit5)
    testRuntimeOnly(libs.junit.platform.launcher)
}

jacoco {
    toolVersion = libs.versions.jacoco.get()
}

// The compiler settings the Spring Boot plugin gives the root project, kept for the moved sources (non-ASCII literals in the tests).
tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.compilerArgs.add("-parameters")
}

tasks.named<Test>("test") {
    useJUnitPlatform()
    testLogging {
        exceptionFormat = TestExceptionFormat.FULL
    }
    // A root-level `./gradlew test --tests <pattern>` selects this task too; a pattern that names a root test must not fail it.
    filter.isFailOnNoMatchingTests = false
    // The boundary test imports exactly this module's production classes.
    systemProperty("module.mainClasses", sourceSets.main.get().output.classesDirs.asPath)
}
