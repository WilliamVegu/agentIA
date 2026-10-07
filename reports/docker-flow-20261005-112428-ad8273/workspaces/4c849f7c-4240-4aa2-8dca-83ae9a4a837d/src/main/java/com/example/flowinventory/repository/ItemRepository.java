package com.example.flowinventory.repository;

import com.example.flowinventory.model.entity.Item;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * Persistence access for inventory items.
 */
public interface ItemRepository extends JpaRepository<Item, Long> {
}
