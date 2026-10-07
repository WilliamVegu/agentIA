package com.example.flowinventory.model.dto;

import com.example.flowinventory.model.entity.Item;

/**
 * Readable API representation of an inventory item.
 */
public record ItemResponse(
        Long id,
        String name,
        Integer quantity
) {

    public static ItemResponse from(Item entity) {
        if (entity == null) {
            return null;
        }
        return new ItemResponse(entity.getId(), entity.getName(), entity.getQuantity());
    }
}
