package com.corp.auditlibrary.repository;

import com.corp.auditlibrary.model.entity.CatalogAuditEntry;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CatalogAuditEntryRepository extends JpaRepository<CatalogAuditEntry, UUID> {
}
