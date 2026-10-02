package com.corp.auditlibrary.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.corp.auditlibrary.model.entity.CatalogAuditEntry;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

@DataJpaTest
class CatalogAuditEntryRepositoryTest {

    @Autowired
    private CatalogAuditEntryRepository catalogAuditEntryRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void save_persistsCatalogAuditEntryAndFindByIdReadsTheStoredRowBack() {
        CatalogAuditEntry saved = catalogAuditEntryRepository.save(newEntry("CREATE"));
        entityManager.flush();
        entityManager.clear();

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getOccurredAt()).isNotNull();

        CatalogAuditEntry reloaded = catalogAuditEntryRepository.findById(saved.getId()).orElseThrow();

        assertThat(reloaded.getId()).isEqualTo(saved.getId());
        assertThat(reloaded.getIsbn()).isEqualTo("9783161484100");
        assertThat(reloaded.getOperation()).isEqualTo("CREATE");
        assertThat(reloaded.getActor()).isEqualTo("librarian");
        assertThat(reloaded.getOutcome()).isEqualTo("SUCCESS");
        assertThat(reloaded.getDetail()).isEqualTo("Book registered");
        assertThat(reloaded.getOccurredAt()).isNotNull();
    }

    @Test
    void save_thenFindAllReadsEveryPersistedRowBack() {
        UUID firstId = catalogAuditEntryRepository.save(newEntry("CREATE")).getId();
        UUID secondId = catalogAuditEntryRepository.save(newEntry("DELETE")).getId();
        entityManager.flush();
        entityManager.clear();

        List<CatalogAuditEntry> all = catalogAuditEntryRepository.findAll();

        assertThat(all).hasSize(2);
        assertThat(all).extracting(CatalogAuditEntry::getId)
                .containsExactlyInAnyOrder(firstId, secondId);
        assertThat(all).extracting(CatalogAuditEntry::getOperation)
                .containsExactlyInAnyOrder("CREATE", "DELETE");
    }

    private CatalogAuditEntry newEntry(String operation) {
        CatalogAuditEntry entry = new CatalogAuditEntry();
        entry.setIsbn("9783161484100");
        entry.setOperation(operation);
        entry.setActor("librarian");
        entry.setOutcome("SUCCESS");
        entry.setDetail("Book registered");
        entry.setOccurredAt(Instant.now());
        return entry;
    }
}
