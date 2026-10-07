package com.corp.auditlibrary;

import static org.assertj.core.api.Assertions.assertThat;

import com.corp.auditlibrary.controller.BookController;
import com.corp.auditlibrary.controller.CatalogAuditEntryController;
import com.corp.auditlibrary.repository.BookRepository;
import com.corp.auditlibrary.repository.CatalogAuditEntryRepository;
import com.corp.auditlibrary.service.BookService;
import com.corp.auditlibrary.service.CatalogAuditEntryService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;

@SpringBootTest
class AuditLibraryApplicationTests {

    @Autowired
    private ApplicationContext applicationContext;

    @Test
    void contextLoadsWithEveryApplicationBeanWired() {
        assertThat(applicationContext.getBean(AuditLibraryApplication.class)).isNotNull();
        assertThat(applicationContext.getBeansOfType(BookController.class)).hasSize(1);
        assertThat(applicationContext.getBeansOfType(CatalogAuditEntryController.class)).hasSize(1);
        assertThat(applicationContext.getBeansOfType(BookService.class)).hasSize(1);
        assertThat(applicationContext.getBeansOfType(CatalogAuditEntryService.class)).hasSize(1);
        assertThat(applicationContext.getBeansOfType(BookRepository.class)).hasSize(1);
        assertThat(applicationContext.getBeansOfType(CatalogAuditEntryRepository.class)).hasSize(1);
    }
}
