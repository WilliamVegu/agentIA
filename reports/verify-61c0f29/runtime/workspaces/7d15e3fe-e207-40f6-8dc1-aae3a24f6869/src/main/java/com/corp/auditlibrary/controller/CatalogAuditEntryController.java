package com.corp.auditlibrary.controller;

import com.corp.auditlibrary.model.dto.CatalogAuditEntryResponse;
import com.corp.auditlibrary.model.dto.CreateCatalogAuditEntryRequest;
import com.corp.auditlibrary.service.CatalogAuditEntryService;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/catalog-audit-entries")
public class CatalogAuditEntryController {

    private final CatalogAuditEntryService catalogAuditEntryService;

    public CatalogAuditEntryController(CatalogAuditEntryService catalogAuditEntryService) {
        this.catalogAuditEntryService = catalogAuditEntryService;
    }

    @PostMapping
    public ResponseEntity<CatalogAuditEntryResponse> createCatalogAuditEntry(
            @Valid @RequestBody CreateCatalogAuditEntryRequest request) {
        CatalogAuditEntryResponse created = catalogAuditEntryService.createCatalogAuditEntry(request);
        return ResponseEntity
                .created(URI.create("/api/v1/catalog-audit-entries/" + created.id()))
                .body(created);
    }

    @GetMapping
    public ResponseEntity<List<CatalogAuditEntryResponse>> getAllCatalogAuditEntries() {
        return ResponseEntity.ok(catalogAuditEntryService.getAllCatalogAuditEntries());
    }

    @GetMapping("/{id}")
    public ResponseEntity<CatalogAuditEntryResponse> getCatalogAuditEntry(@PathVariable UUID id) {
        return ResponseEntity.ok(catalogAuditEntryService.getCatalogAuditEntry(id));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteCatalogAuditEntry(@PathVariable UUID id) {
        catalogAuditEntryService.deleteCatalogAuditEntry(id);
        return ResponseEntity.noContent().build();
    }
}
