package com.example.flowinventory.model.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Writable API payload for creating an inventory item.
 */
public record CreateItemRequest(

        @NotBlank
        String name,

        @NotNull
        @Min(0)
        Integer quantity
) {
}
