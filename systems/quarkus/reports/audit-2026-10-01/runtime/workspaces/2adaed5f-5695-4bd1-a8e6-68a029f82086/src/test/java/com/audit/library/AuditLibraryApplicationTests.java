package com.audit.library;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Context-load test for the Spring Boot entry point. Asserts that the generated
 * configuration (application + JPA + web + validation) actually boots and that the
 * declared service, repository, controller and advice beans are present.
 */
@SpringBootTest
class AuditLibraryApplicationTests {

    @Autowired
    private ApplicationContext applicationContext;

    @Test
    void contextLoadsWithGeneratedAuditLibraryConfiguration() {
        assertThat(applicationContext).isNotNull();
        assertThat(applicationContext.getBean(AuditLibraryApplication.class)).isNotNull();
        assertThat(applicationContext.containsBean("homeController")).isTrue();
        assertThat(applicationContext.containsBean("bookController")).isTrue();
        assertThat(applicationContext.containsBean("bookServiceImpl")).isTrue();
        assertThat(applicationContext.containsBean("bookRepository")).isTrue();
        assertThat(applicationContext.containsBean("globalExceptionHandler")).isTrue();
    }
}
