package com.example.flowinventory.service.impl;

import com.example.flowinventory.exception.ResourceNotFoundException;
import com.example.flowinventory.model.dto.CreateItemRequest;
import com.example.flowinventory.model.dto.ItemResponse;
import com.example.flowinventory.model.entity.Item;
import com.example.flowinventory.repository.ItemRepository;
import com.example.flowinventory.service.ItemService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Transactional implementation of inventory item business logic.
 */
@Service
@Transactional
public class ItemServiceImpl implements ItemService {

    private final ItemRepository itemRepository;

    public ItemServiceImpl(ItemRepository itemRepository) {
        this.itemRepository = itemRepository;
    }

    @Override
    public ItemResponse create(CreateItemRequest request) {
        validateRequest(request);
        Item entity = new Item(null, request.name(), request.quantity());
        Item saved = itemRepository.save(entity);
        return ItemResponse.from(saved);
    }

    @Override
    @Transactional(readOnly = true)
    public ItemResponse findById(Long id) {
        Item entity = itemRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Item not found with id: " + id));
        return ItemResponse.from(entity);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ItemResponse> findAll() {
        return itemRepository.findAll().stream()
                .map(ItemResponse::from)
                .toList();
    }

    @Override
    public ItemResponse update(Long id, CreateItemRequest request) {
        validateRequest(request);
        Item entity = itemRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Item not found with id: " + id));
        entity.setName(request.name());
        entity.setQuantity(request.quantity());
        Item updated = itemRepository.save(entity);
        return ItemResponse.from(updated);
    }

    @Override
    public void delete(Long id) {
        if (!itemRepository.existsById(id)) {
            throw new ResourceNotFoundException("Item not found with id: " + id);
        }
        itemRepository.deleteById(id);
    }

    private void validateRequest(CreateItemRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Item request must not be null");
        }
        if (request.name() == null || request.name().isBlank()) {
            throw new IllegalArgumentException("Item name must not be blank");
        }
        if (request.quantity() == null) {
            throw new IllegalArgumentException("Item quantity must not be null");
        }
        if (request.quantity() < 0) {
            throw new IllegalArgumentException("Item quantity must not be negative");
        }
    }
}
