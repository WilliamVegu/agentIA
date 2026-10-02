package com.corp.auditlibrary.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.CatalogAuditEntryResponse;
import com.corp.auditlibrary.model.dto.CreateCatalogAuditEntryRequest;
import com.corp.auditlibrary.model.entity.CatalogAuditEntry;
import com.corp.auditlibrary.repository.CatalogAuditEntryRepository;
import com.corp.auditlibrary.service.impl.CatalogAuditEntryServiceImpl;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CatalogAuditEntryServiceTest {

    private static final String ISBN = "9783161484100";
    private static final Instant OCCURRED_AT = Instant.parse("2024-05-01T10:15:30Z");

    @Mock
    private CatalogAuditEntryRepository catalogAuditEntryRepository;

    private CatalogAuditEntryService catalogAuditEntryService;

    @BeforeEach
    void setUp() {
        catalogAuditEntryService = new CatalogAuditEntryServiceImpl(catalogAuditEntryRepository);
    }

    @Test
    void createCatalogAuditEntry_recordsEntryAndReturnsRepresentationWithGeneratedId() {
        CreateCatalogAuditEntryRequest request = new CreateCatalogAuditEntryRequest(
                ISBN, "CREATE", "librarian", "SUCCESS", "Book registered");
        UUID generatedId = UUID.randomUUID();
        given(catalogAuditEntryRepository.save(any(CatalogAuditEntry.class))).willAnswer(invocation -> {
            CatalogAuditEntry pending = invocation.getArgument(0);
            assertThat(pending.getId()).isNull();
            assertThat(pending.getIsbn()).isEqualTo(ISBN);
            assertThat(pending.getOperation()).isEqualTo("CREATE");
            assertThat(pending.getActor()).isEqualTo("librarian");
            assertThat(pending.getOutcome()).isEqualTo("SUCCESS");
            assertThat(pending.getDetail()).isEqualTo("Book registered");
            assertThat(pending.getOccurredAt()).isNotNull();
            pending.setId(generatedId);
            return pending;
        });

        CatalogAuditEntryResponse response = catalogAuditEntryService.createCatalogAuditEntry(request);

        assertThat(response.id()).isEqualTo(generatedId);
        assertThat(response.isbn()).isEqualTo(ISBN);
        assertThat(response.operation()).isEqualTo("CREATE");
        assertThat(response.actor()).isEqualTo("librarian");
        assertThat(response.outcome()).isEqualTo("SUCCESS");
        assertThat(response.detail()).isEqualTo("Book registered");
        assertThat(response.occurredAt()).isNotNull();
        verify(catalogAuditEntryRepository).save(any(CatalogAuditEntry.class));
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    @Test
    void getCatalogAuditEntry_withKnownId_returnsStoredRepresentation() {
        UUID id = UUID.randomUUID();
        CatalogAuditEntry stored = storedEntry(id);
        given(catalogAuditEntryRepository.findById(id)).willReturn(Optional.of(stored));

        CatalogAuditEntryResponse response = catalogAuditEntryService.getCatalogAuditEntry(id);

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo(ISBN);
        assertThat(response.operation()).isEqualTo("CREATE");
        assertThat(response.actor()).isEqualTo("librarian");
        assertThat(response.outcome()).isEqualTo("SUCCESS");
        assertThat(response.detail()).isEqualTo("Book registered");
        assertThat(response.occurredAt()).isEqualTo(OCCURRED_AT);
        verify(catalogAuditEntryRepository).findById(id);
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    @Test
    void getCatalogAuditEntry_withUnknownId_throwsResourceNotFound() {
        UUID id = UUID.randomUUID();
        given(catalogAuditEntryRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> catalogAuditEntryService.getCatalogAuditEntry(id))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining(id.toString());

        verify(catalogAuditEntryRepository).findById(id);
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    @Test
    void getAllCatalogAuditEntries_returnsEveryStoredEntry() {
        CatalogAuditEntry first = storedEntry(UUID.randomUUID());
        CatalogAuditEntry second = storedEntry(UUID.randomUUID());
        given(catalogAuditEntryRepository.findAll()).willReturn(List.of(first, second));

        List<CatalogAuditEntryResponse> responses = catalogAuditEntryService.getAllCatalogAuditEntries();

        assertThat(responses).hasSize(2);
        assertThat(responses).extracting(CatalogAuditEntryResponse::id)
                .containsExactlyInAnyOrder(first.getId(), second.getId());
        verify(catalogAuditEntryRepository).findAll();
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    @Test
    void deleteCatalogAuditEntry_withKnownId_removesStoredEntry() {
        UUID id = UUID.randomUUID();
        CatalogAuditEntry stored = storedEntry(id);
        given(catalogAuditEntryRepository.findById(id)).willReturn(Optional.of(stored));

        catalogAuditEntryService.deleteCatalogAuditEntry(id);

        verify(catalogAuditEntryRepository).findById(id);
        verify(catalogAuditEntryRepository).delete(stored);
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    @Test
    void deleteCatalogAuditEntry_withUnknownId_throwsResourceNotFoundAndRemovesNothing() {
        UUID id = UUID.randomUUID();
        given(catalogAuditEntryRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> catalogAuditEntryService.deleteCatalogAuditEntry(id))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining(id.toString());

        verify(catalogAuditEntryRepository).findById(id);
        verify(catalogAuditEntryRepository, never()).delete(any(CatalogAuditEntry.class));
        verifyNoMoreInteractions(catalogAuditEntryRepository);
    }

    private CatalogAuditEntry storedEntry(UUID id) {
        CatalogAuditEntry entry = new CatalogAuditEntry();
        entry.setId(id);
        entry.setIsbn(ISBN);
        entry.setOperation("CREATE");
        entry.setActor("librarian");
        entry.setOutcome("SUCCESS");
        entry.setDetail("Book registered");
        entry.setOccurredAt(OCCURRED_AT);
        return entry;
    }
}
