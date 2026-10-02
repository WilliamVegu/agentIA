package com.audit.library;

import com.audit.library.repository.BookRepository;
import com.audit.library.service.BookService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class AuditLibraryApplicationTests {

    @Autowired
    private ApplicationContext context;

    @Test
    void contextLoadsWithBookServiceAndRepositoryBeans() {
        assertThat(context).isNotNull();
        assertThat(context.containsBean("bookServiceImpl")).isTrue();
        assertThat(context.getBean(BookService.class)).isNotNull();
        assertThat(context.getBean(BookRepository.class)).isNotNull();
    }
}
