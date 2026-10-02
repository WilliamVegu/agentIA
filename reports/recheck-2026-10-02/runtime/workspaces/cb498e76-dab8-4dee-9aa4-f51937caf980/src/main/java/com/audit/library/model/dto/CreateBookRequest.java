package com.audit.library.model.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateBookRequest(
        @NotBlank String isbn,
        @NotBlank String title,
        @NotBlank String author) {
}
