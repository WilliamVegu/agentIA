package com.example.flowinventory.service;

import com.example.flowinventory.model.dto.CreateItemRequest;
import com.example.flowinventory.model.dto.ItemResponse;

import java.util.List;

/**
 * Business operations for inventory items.
 */
public interface ItemService {

    ItemResponse create(CreateItemRequest request);

    ItemResponse findById(Long id);

    List<ItemResponse> findAll();

    ItemResponse update(Long id, CreateItemRequest request);

    void delete(Long id);
}
