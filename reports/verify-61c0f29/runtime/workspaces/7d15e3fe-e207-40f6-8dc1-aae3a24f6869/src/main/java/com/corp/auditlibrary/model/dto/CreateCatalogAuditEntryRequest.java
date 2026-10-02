package com.corp.auditlibrary.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CreateCatalogAuditEntryRequest(
        @NotBlank
        @Size(min = 10, max = 17)
        @Pattern(regexp = "^(?:\\d{9}[\\dXx]|\\d{13})$")
        String isbn,

        @NotBlank
        @Size(min = 1, max = 32)
        @Pattern(regexp = "^(CREATE|UPDATE|DELETE|READ)$")
        String operation,

        @NotBlank
        @Size(min = 1, max = 128)
        String actor,

        @NotBlank
        @Pattern(regexp = "^(SUCCESS|FAILURE)$")
        String outcome,

        @Size(max = 1024)
        String detail
) {
}
