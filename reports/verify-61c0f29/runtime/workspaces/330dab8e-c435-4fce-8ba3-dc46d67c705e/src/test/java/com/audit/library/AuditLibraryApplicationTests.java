package com.audit.library;

import com.audit.library.controller.BookController;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.BookService;
import com.audit.library.service.impl.BookServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(classes = AuditLibraryApplication.class)
class AuditLibraryApplicationTests {

    @Autowired
    private ApplicationContext applicationContext;

    @Test
    void springContextLoadsWithGeneratedConfigurationAndBeans() {
        assertThat(applicationContext).isNotNull();
        assertThat(applicationContext.getEnvironment().getProperty("spring.application.name"))
                .isEqualTo("audit-library");
        assertThat(applicationContext.getBean(BookController.class)).isNotNull();
        assertThat(applicationContext.getBean(BookService.class)).isInstanceOf(BookServiceImpl.class);
        assertThat(applicationContext.getBean(BookRepository.class)).isNotNull();
        assertThat(applicationContext.containsBean("bookServiceImpl")).isTrue();
    }
}