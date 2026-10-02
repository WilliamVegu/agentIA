package com.corp.auditlibrary.service.impl;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.CatalogAuditEntryResponse;
import com.corp.auditlibrary.model.dto.CreateCatalogAuditEntryRequest;
import com.corp.auditlibrary.model.entity.CatalogAuditEntry;
import com.corp.auditlibrary.repository.CatalogAuditEntryRepository;
import com.corp.auditlibrary.service.CatalogAuditEntryService;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class CatalogAuditEntryServiceImpl implements CatalogAuditEntryService {

    private final CatalogAuditEntryRepository catalogAuditEntryRepository;

    public CatalogAuditEntryServiceImpl(CatalogAuditEntryRepository catalogAuditEntryRepository) {
        this.catalogAuditEntryRepository = catalogAuditEntryRepository;
    }

    @Override
    public CatalogAuditEntryResponse createCatalogAuditEntry(CreateCatalogAuditEntryRequest request) {
        CatalogAuditEntry entry = new CatalogAuditEntry();
        entry.setIsbn(request.isbn());
        entry.setOperation(request.operation());
        entry.setActor(request.actor());
        entry.setOutcome(request.outcome());
        entry.setDetail(request.detail());
        entry.setOccurredAt(Instant.now());
        CatalogAuditEntry saved = catalogAuditEntryRepository.save(entry);
        return CatalogAuditEntryResponse.fromEntity(saved);
    }

    @Override
    @Transactional(readOnly = true)
    public CatalogAuditEntryResponse getCatalogAuditEntry(UUID id) {
        CatalogAuditEntry entry = catalogAuditEntryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("CatalogAuditEntry not found with id: " + id));
        return CatalogAuditEntryResponse.fromEntity(entry);
    }

    @Override
    @Transactional(readOnly = true)
    public List<CatalogAuditEntryResponse> getAllCatalogAuditEntries() {
        return catalogAuditEntryRepository.findAll().stream()
                .map(CatalogAuditEntryResponse::fromEntity)
                .toList();
    }

    @Override
    public void deleteCatalogAuditEntry(UUID id) {
        CatalogAuditEntry entry = catalogAuditEntryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("CatalogAuditEntry not found with id: " + id));
        catalogAuditEntryRepository.delete(entry);
    }
}
