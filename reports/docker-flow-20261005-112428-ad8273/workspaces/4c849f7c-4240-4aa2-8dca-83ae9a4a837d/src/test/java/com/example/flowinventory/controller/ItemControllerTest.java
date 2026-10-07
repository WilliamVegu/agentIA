package com.example.flowinventory.controller;

import com.example.flowinventory.exception.ResourceNotFoundException;
import com.example.flowinventory.model.dto.CreateItemRequest;
import com.example.flowinventory.model.dto.ItemResponse;
import com.example.flowinventory.service.ItemService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Web-layer slice for {@link ItemController}. The service layer is replaced by a
 * mock, so these tests observe only the HTTP contract: status codes, JSON
 * payloads, bean-validation rejection through the global exception handler and
 * the not-found mapping. They see neither persistence nor business logic.
 */
@WebMvcTest(controllers = ItemController.class)
class ItemControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ItemService itemService;

    @Test
    void createReturns201WithPersistedItem() throws Exception {
        // AC-1.1
        given(itemService.create(any(CreateItemRequest.class)))
                .willReturn(new ItemResponse(1L, "Widget", 10));

        mockMvc.perform(post(ItemController.BASE_PATH)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("Widget", 10))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(1))
                .andExpect(jsonPath("$.name").value("Widget"))
                .andExpect(jsonPath("$.quantity").value(10));
    }

    @Test
    void createWithBlankNameReturns400AndPersistsNothing() throws Exception {
        // AC-1.2
        mockMvc.perform(post(ItemController.BASE_PATH)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("   ", 10))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.details").isNotEmpty())
                .andExpect(jsonPath("$.details[0].field").value("name"));

        verify(itemService, never()).create(any(CreateItemRequest.class));
    }

    @Test
    void createWithNegativeQuantityReturns400AndPersistsNothing() throws Exception {
        // AC-1.3
        mockMvc.perform(post(ItemController.BASE_PATH)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("Widget", -1))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.details").isNotEmpty())
                .andExpect(jsonPath("$.details[0].field").value("quantity"));

        verify(itemService, never()).create(any(CreateItemRequest.class));
    }

    @Test
    void updateReturns200WithUpdatedItem() throws Exception {
        // AC-2.1
        given(itemService.update(eq(42L), any(CreateItemRequest.class)))
                .willReturn(new ItemResponse(42L, "Gadget", 20));

        mockMvc.perform(put(ItemController.BASE_PATH + "/42")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("Gadget", 20))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(42))
                .andExpect(jsonPath("$.name").value("Gadget"))
                .andExpect(jsonPath("$.quantity").value(20));
    }

    @Test
    void deleteReturns204AndItemIsNoLongerRetrievable() throws Exception {
        // AC-2.2
        mockMvc.perform(delete(ItemController.BASE_PATH + "/42"))
                .andExpect(status().isNoContent());

        verify(itemService).delete(42L);

        given(itemService.findById(42L))
                .willThrow(new ResourceNotFoundException("Item not found with id: 42"));

        mockMvc.perform(get(ItemController.BASE_PATH + "/42"))
                .andExpect(status().isNotFound());
    }

    @Test
    void updateMissingItemReturns404() throws Exception {
        // AC-2.3
        given(itemService.update(eq(999L), any(CreateItemRequest.class)))
                .willThrow(new ResourceNotFoundException("Item not found with id: 999"));

        mockMvc.perform(put(ItemController.BASE_PATH + "/999")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("Gadget", 20))))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Item not found with id: 999"));
    }

    @Test
    void deleteMissingItemReturns404() throws Exception {
        // AC-2.4
        doThrow(new ResourceNotFoundException("Item not found with id: 999"))
                .when(itemService).delete(999L);

        mockMvc.perform(delete(ItemController.BASE_PATH + "/999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Item not found with id: 999"));
    }

    @Test
    void updateWithBlankNameReturns400AndLeavesItemUnchanged() throws Exception {
        // AC-2.5
        mockMvc.perform(put(ItemController.BASE_PATH + "/42")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("  ", 20))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));

        verify(itemService, never()).update(eq(42L), any(CreateItemRequest.class));
    }

    @Test
    void updateWithNegativeQuantityReturns400AndLeavesItemUnchanged() throws Exception {
        // AC-2.6
        mockMvc.perform(put(ItemController.BASE_PATH + "/42")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateItemRequest("Gadget", -5))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));

        verify(itemService, never()).update(eq(42L), any(CreateItemRequest.class));
    }

    @Test
    void findByIdReturns200WithStoredItem() throws Exception {
        // AC-3.1
        given(itemService.findById(42L)).willReturn(new ItemResponse(42L, "Widget", 10));

        mockMvc.perform(get(ItemController.BASE_PATH + "/42"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(42))
                .andExpect(jsonPath("$.name").value("Widget"))
                .andExpect(jsonPath("$.quantity").value(10));
    }

    @Test
    void findAllReturns200WithEveryStoredItem() throws Exception {
        // AC-3.2
        given(itemService.findAll()).willReturn(List.of(
                new ItemResponse(1L, "Widget", 10),
                new ItemResponse(2L, "Gadget", 20)));

        mockMvc.perform(get(ItemController.BASE_PATH))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].name").value("Widget"))
                .andExpect(jsonPath("$[1].name").value("Gadget"));
    }

    @Test
    void findByIdMissingItemReturns404() throws Exception {
        // AC-3.3
        given(itemService.findById(999L))
                .willThrow(new ResourceNotFoundException("Item not found with id: 999"));

        mockMvc.perform(get(ItemController.BASE_PATH + "/999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Item not found with id: 999"));
    }
}
