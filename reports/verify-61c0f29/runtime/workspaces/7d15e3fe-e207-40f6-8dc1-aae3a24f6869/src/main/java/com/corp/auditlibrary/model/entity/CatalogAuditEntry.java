package com.corp.auditlibrary.model.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "catalog_audit_entries")
public class CatalogAuditEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @NotNull
    private UUID id;

    @NotBlank
    @Size(min = 10, max = 17)
    @Pattern(regexp = "^(?:\\d{9}[\\dXx]|\\d{13})$")
    @Column(name = "isbn", nullable = false, length = 17)
    private String isbn;

    @NotBlank
    @Size(min = 1, max = 32)
    @Pattern(regexp = "^(CREATE|UPDATE|DELETE|READ)$")
    @Column(name = "operation", nullable = false, length = 32)
    private String operation;

    @NotBlank
    @Size(min = 1, max = 128)
    @Column(name = "actor", nullable = false, length = 128)
    private String actor;

    @NotBlank
    @Pattern(regexp = "^(SUCCESS|FAILURE)$")
    @Column(name = "outcome", nullable = false, length = 16)
    private String outcome;

    @Size(max = 1024)
    @Column(name = "detail", nullable = true, length = 1024)
    private String detail;

    @NotNull
    @PastOrPresent
    @Column(name = "occurred_at", nullable = false, updatable = false)
    private Instant occurredAt;

    public CatalogAuditEntry() {
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getIsbn() {
        return isbn;
    }

    public void setIsbn(String isbn) {
        this.isbn = isbn;
    }

    public String getOperation() {
        return operation;
    }

    public void setOperation(String operation) {
        this.operation = operation;
    }

    public String getActor() {
        return actor;
    }

    public void setActor(String actor) {
        this.actor = actor;
    }

    public String getOutcome() {
        return outcome;
    }

    public void setOutcome(String outcome) {
        this.outcome = outcome;
    }

    public String getDetail() {
        return detail;
    }

    public void setDetail(String detail) {
        this.detail = detail;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public void setOccurredAt(Instant occurredAt) {
        this.occurredAt = occurredAt;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof CatalogAuditEntry entry)) return false;
        return id != null && id.equals(entry.id);
    }

    @Override
    public int hashCode() {
        return id != null ? id.hashCode() : 0;
    }
}
