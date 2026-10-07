package com.corp.auditlibrary.service;

import com.corp.auditlibrary.model.dto.CatalogAuditEntryResponse;
import com.corp.auditlibrary.model.dto.CreateCatalogAuditEntryRequest;
import java.util.List;
import java.util.UUID;

public interface CatalogAuditEntryService {

    CatalogAuditEntryResponse createCatalogAuditEntry(CreateCatalogAuditEntryRequest request);

    CatalogAuditEntryResponse getCatalogAuditEntry(UUID id);

    List<CatalogAuditEntryResponse> getAllCatalogAuditEntries();

    void deleteCatalogAuditEntry(UUID id);
}
