package com.corp.auditlibrary;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.TestPropertySource;
import com.corp.auditlibrary.repository.BookRepository;
import com.corp.auditlibrary.repository.CatalogAuditEntryRepository;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Platform-authored persistence contract test.
 *
 * <p>Not written by the generation model, and not visible to it. Hibernate is
 * asked to <em>validate</em> every entity mapping against a database created from
 * this project's own {@code schema.sql}. If the schema and the entities disagree,
 * the context fails to start and this test fails with it.
 *
 * <p>This is the executable form of a check that was previously only a text
 * comparison between two generated files. It does not assert that the service
 * behaves correctly -- only that its persistence layer is internally consistent.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestPropertySource(properties = {
        // H2 in PostgreSQL mode: the generated DDL is written to be compatible
        // with both, and the datasource must be in-memory so the build stays
        // hermetic.
        "spring.datasource.url=jdbc:h2:mem:platformcontract;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        // Validate, never generate: a generated schema would make this test pass
        // by construction and prove nothing.
        "spring.jpa.hibernate.ddl-auto=validate",
        // The schema is the project's own artifact, at the workspace root.
        "spring.sql.init.mode=always",
        "spring.sql.init.schema-locations=file:./schema.sql",
        "spring.jpa.defer-datasource-initialization=false",
})
class PlatformPersistenceContractTest {

    @Autowired
    private ApplicationContext context;

    @Test
    void the_schema_the_entities_and_the_repositories_agree() {
        assertThat(context).isNotNull();
        assertThat(context.getBean(BookRepository.class)).isNotNull();
        assertThat(context.getBean(CatalogAuditEntryRepository.class)).isNotNull();
    }
}
