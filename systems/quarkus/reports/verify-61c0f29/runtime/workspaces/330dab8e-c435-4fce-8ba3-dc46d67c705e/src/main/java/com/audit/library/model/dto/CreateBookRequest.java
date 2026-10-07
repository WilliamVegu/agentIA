package com.audit.library.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CreateBookRequest(
        @NotBlank
        @Size(min = 10, max = 17)
        @Pattern(regexp = "^(?:\\d{9}[\\dXx]|\\d{13})$")
        String isbn,

        @NotBlank
        @Size(min = 1, max = 255)
        String title,

        @NotBlank
        @Size(min = 1, max = 255)
        String author
) {
}
