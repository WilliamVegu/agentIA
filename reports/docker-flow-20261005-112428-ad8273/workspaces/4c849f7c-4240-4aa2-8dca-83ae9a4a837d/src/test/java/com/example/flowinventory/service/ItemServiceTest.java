package com.example.flowinventory.service;

import com.example.flowinventory.exception.ResourceNotFoundException;
import com.example.flowinventory.model.dto.CreateItemRequest;
import com.example.flowinventory.model.dto.ItemResponse;
import com.example.flowinventory.model.entity.Item;
import com.example.flowinventory.repository.ItemRepository;
import com.example.flowinventory.service.impl.ItemServiceImpl;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link ItemServiceImpl}, one per declared acceptance scenario.
 *
 * The repository is substituted by a Mockito mock injected through the
 * constructor, so these tests observe business behaviour and repository
 * interactions only: they cannot see persistence, SQL, or the generated
 * identifier strategy.
 */
@ExtendWith(MockitoExtension.class)
class ItemServiceTest {

    @Mock
    private ItemRepository itemRepository;

    @InjectMocks
    private ItemServiceImpl itemService;

    @Test
    void createPersistsValidItemAndReturnsItWithGeneratedId() {
        // AC-1.1: non-blank name "Widget", quantity 10 -> persisted item with generated id
        given(itemRepository.save(any(Item.class))).willReturn(new Item(7L, "Widget", 10));

        ItemResponse response = itemService.create(new CreateItemRequest("Widget", 10));

        assertThat(response).isEqualTo(new ItemResponse(7L, "Widget", 10));

        ArgumentCaptor<Item> captor = ArgumentCaptor.forClass(Item.class);
        verify(itemRepository).save(captor.capture());
        assertThat(captor.getValue().getId()).isNull();
        assertThat(captor.getValue().getName()).isEqualTo("Widget");
        assertThat(captor.getValue().getQuantity()).isEqualTo(10);
    }

    @Test
    void createRejectsBlankNameAndPersistsNothing() {
        // AC-1.2: blank name, quantity 10 -> rejected, no item persisted
        assertThatThrownBy(() -> itemService.create(new CreateItemRequest("   ", 10)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("name");

        verify(itemRepository, never()).save(any(Item.class));
    }

    @Test
    void createRejectsNegativeQuantityAndPersistsNothing() {
        // AC-1.3: name "Widget", quantity -1 -> rejected, no item persisted
        assertThatThrownBy(() -> itemService.create(new CreateItemRequest("Widget", -1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("quantity");

        verify(itemRepository, never()).save(any(Item.class));
    }

    @Test
    void updateReplacesFieldsOfExistingItem() {
        // AC-2.1: item 42 exists -> PUT applies "Gadget"/20 and returns the updated item
        Item existing = new Item(42L, "Widget", 5);
        given(itemRepository.findById(42L)).willReturn(Optional.of(existing));
        given(itemRepository.save(any(Item.class))).willAnswer(invocation -> invocation.getArgument(0));

        ItemResponse response = itemService.update(42L, new CreateItemRequest("Gadget", 20));

        assertThat(response).isEqualTo(new ItemResponse(42L, "Gadget", 20));
        assertThat(existing.getName()).isEqualTo("Gadget");
        assertThat(existing.getQuantity()).isEqualTo(20);
        verify(itemRepository).save(existing);
    }

    @Test
    void deleteRemovesExistingItem() {
        // AC-2.2: item 42 exists -> DELETE removes it
        given(itemRepository.existsById(42L)).willReturn(true);

        itemService.delete(42L);

        verify(itemRepository).deleteById(42L);
    }

    @Test
    void updateThrowsWhenItemDoesNotExist() {
        // AC-2.3: no item 999 -> not-found failure and no write
        given(itemRepository.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> itemService.update(999L, new CreateItemRequest("Gadget", 20)))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("999");

        verify(itemRepository, never()).save(any(Item.class));
    }

    @Test
    void deleteThrowsWhenItemDoesNotExist() {
        // AC-2.4: no item 999 -> not-found failure and no delete
        given(itemRepository.existsById(999L)).willReturn(false);

        assertThatThrownBy(() -> itemService.delete(999L))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("999");

        verify(itemRepository, never()).deleteById(anyLong());
    }

    @Test
    void updateRejectsBlankNameAndLeavesStoredItemUnchanged() {
        // AC-2.5: existing item 42, blank name -> rejected, stored item untouched
        assertThatThrownBy(() -> itemService.update(42L, new CreateItemRequest("  ", 20)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("name");

        verify(itemRepository, never()).save(any(Item.class));
    }

    @Test
    void updateRejectsNegativeQuantityAndLeavesStoredItemUnchanged() {
        // AC-2.6: existing item 42, quantity -5 -> rejected, stored item untouched
        assertThatThrownBy(() -> itemService.update(42L, new CreateItemRequest("Gadget", -5)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("quantity");

        verify(itemRepository, never()).save(any(Item.class));
    }

    @Test
    void findByIdReturnsStoredItem() {
        // AC-3.1: item 42 exists -> returned with its stored values
        given(itemRepository.findById(42L)).willReturn(Optional.of(new Item(42L, "Widget", 10)));

        ItemResponse response = itemService.findById(42L);

        assertThat(response).isEqualTo(new ItemResponse(42L, "Widget", 10));
    }

    @Test
    void findAllReturnsEveryStoredItem() {
        // AC-3.2: multiple items exist -> full collection returned
        given(itemRepository.findAll()).willReturn(List.of(
                new Item(1L, "Widget", 10),
                new Item(2L, "Gadget", 20)));

        List<ItemResponse> responses = itemService.findAll();

        assertThat(responses)
                .hasSize(2)
                .containsExactly(
                        new ItemResponse(1L, "Widget", 10),
                        new ItemResponse(2L, "Gadget", 20));
    }

    @Test
    void findByIdThrowsWhenItemDoesNotExist() {
        // AC-3.3: no item 999 -> dedicated not-found failure, not an empty result
        given(itemRepository.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> itemService.findById(999L))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("999");
    }
}
