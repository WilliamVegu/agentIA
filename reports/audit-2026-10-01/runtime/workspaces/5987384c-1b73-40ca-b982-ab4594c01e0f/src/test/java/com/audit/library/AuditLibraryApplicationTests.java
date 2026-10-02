package com.audit.library;

import static org.assertj.core.api.Assertions.assertThat;

import com.audit.library.controller.BookController;
import com.audit.library.service.BookService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

@SpringBootTest
class AuditLibraryApplicationTests {

    @Autowired
    private ApplicationContext applicationContext;

    @Test
    void contextLoadsWithBookBeans() {
        assertThat(applicationContext).isNotNull();
        assertThat(applicationContext.getBean(BookController.class)).isNotNull();
        assertThat(applicationContext.getBean(BookService.class)).isNotNull();
    }
}
