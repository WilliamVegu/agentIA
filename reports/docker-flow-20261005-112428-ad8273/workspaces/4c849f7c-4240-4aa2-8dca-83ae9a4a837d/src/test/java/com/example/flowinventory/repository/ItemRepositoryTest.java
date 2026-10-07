package com.example.flowinventory.repository;

import com.example.flowinventory.model.entity.Item;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Persistence slice for {@link ItemRepository} against a real in-memory
 * database. This is the only generated test that exercises an actual save and
 * reads the committed row back through the persistence provider; the service
 * unit test substitutes the repository and therefore proves nothing about
 * persistence.
 */
@DataJpaTest
class ItemRepositoryTest {

    @Autowired
    private ItemRepository itemRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void savesItemAndReadsPersistedRowBackById() {
        Item persisted = itemRepository.save(new Item(null, "Widget", 10));
        itemRepository.flush();

        assertThat(persisted.getId()).isNotNull();

        entityManager.clear();

        Item reloaded = itemRepository.findById(persisted.getId()).orElseThrow();

        assertThat(reloaded.getId()).isEqualTo(persisted.getId());
        assertThat(reloaded.getName()).isEqualTo("Widget");
        assertThat(reloaded.getQuantity()).isEqualTo(10);
    }

    @Test
    void savesMultipleItemsAndReadsTheFullCollectionBack() {
        itemRepository.save(new Item(null, "Widget", 10));
        itemRepository.save(new Item(null, "Gadget", 20));
        itemRepository.flush();

        entityManager.clear();

        List<Item> stored = itemRepository.findAll();

        assertThat(stored)
                .hasSize(2)
                .extracting(Item::getName)
                .containsExactlyInAnyOrder("Widget", "Gadget");
    }
}
