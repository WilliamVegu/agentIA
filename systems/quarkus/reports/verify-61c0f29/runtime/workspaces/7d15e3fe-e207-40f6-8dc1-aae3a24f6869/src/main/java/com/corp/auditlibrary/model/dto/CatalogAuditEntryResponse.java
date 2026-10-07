package com.corp.auditlibrary.model.dto;

import com.corp.auditlibrary.model.entity.CatalogAuditEntry;
import java.time.Instant;
import java.util.UUID;

public record CatalogAuditEntryResponse(
        UUID id,
        String isbn,
        String operation,
        String actor,
        String outcome,
        String detail,
        Instant occurredAt
) {
    public static CatalogAuditEntryResponse fromEntity(CatalogAuditEntry entry) {
        if (entry == null) {
            return null;
        }
        return new CatalogAuditEntryResponse(
                entry.getId(),
                entry.getIsbn(),
                entry.getOperation(),
                entry.getActor(),
                entry.getOutcome(),
                entry.getDetail(),
                entry.getOccurredAt()
        );
    }
}
