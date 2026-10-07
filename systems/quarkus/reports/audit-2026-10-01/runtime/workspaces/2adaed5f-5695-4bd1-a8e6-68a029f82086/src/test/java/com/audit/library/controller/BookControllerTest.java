package com.audit.library.controller;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.service.BookService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * HTTP contract slice for {@link BookController}. The service layer is replaced by a mock,
 * so this layer observes neither persistence nor the business logic implementation: it only
 * asserts transport status codes and error mapping produced by the global handler.
 */
@WebMvcTest(BookController.class)
class BookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private BookService bookService;

    // AC-1.1: valid registration returns 201 with the created book.
    @Test
    void createBook_returns201WithCreatedBook_whenRequestIsValid() throws Exception {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        UUID id = UUID.randomUUID();
        given(bookService.createBook(any(CreateBookRequest.class)))
                .willReturn(new BookResponse(id, "978-0-13-468599-1", "Effective Java", "Joshua Bloch"));

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.isbn").value("978-0-13-468599-1"))
                .andExpect(jsonPath("$.title").value("Effective Java"))
                .andExpect(jsonPath("$.author").value("Joshua Bloch"));
    }

    // AC-1.2: duplicate ISBN is surfaced as HTTP 400 by the global handler.
    @Test
    void createBook_returns400_whenIsbnAlreadyExists() throws Exception {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        given(bookService.createBook(any(CreateBookRequest.class)))
                .willThrow(new IllegalArgumentException("Book with ISBN 978-0-13-468599-1 already exists"));

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value("Book with ISBN 978-0-13-468599-1 already exists"));
    }

    // AC-1.3: a blank title fails body validation with HTTP 400 before the service is called.
    @Test
    void createBook_returns400_whenTitleIsBlank() throws Exception {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "   ", "Joshua Bloch");

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Request body validation failed"))
                .andExpect(jsonPath("$.fieldErrors[0].field").value("title"));

        verifyNoInteractions(bookService);
    }

    // AC-2.1: updating an existing book's title returns 200 with the updated book.
    @Test
    void updateTitle_returns200WithUpdatedBook_whenBookExists() throws Exception {
        UUID id = UUID.randomUUID();
        given(bookService.updateTitle(eq("978-0-13-468599-1"), eq("Effective Java, 3rd Edition")))
                .willReturn(new BookResponse(id, "978-0-13-468599-1", "Effective Java, 3rd Edition", "Joshua Bloch"));

        mockMvc.perform(patch("/api/v1/books/{isbn}", "978-0-13-468599-1")
                        .param("title", "Effective Java, 3rd Edition"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.isbn").value("978-0-13-468599-1"))
                .andExpect(jsonPath("$.title").value("Effective Java, 3rd Edition"));
    }

    // AC-2.2: updating an unknown ISBN returns 404 with the not-found message.
    @Test
    void updateTitle_returns404_whenBookDoesNotExist() throws Exception {
        given(bookService.updateTitle(eq("978-0-00-000000-0"), anyString()))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: 978-0-00-000000-0"));

        mockMvc.perform(patch("/api/v1/books/{isbn}", "978-0-00-000000-0")
                        .param("title", "New Title"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: 978-0-00-000000-0"));
    }

    // AC-2.3: an empty replacement title fails parameter validation with HTTP 400.
    @Test
    void updateTitle_returns400_whenNewTitleIsBlank() throws Exception {
        mockMvc.perform(patch("/api/v1/books/{isbn}", "978-0-13-468599-1")
                        .param("title", "   "))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Request parameter validation failed"));

        verifyNoInteractions(bookService);
    }

    // AC-3.1: retrieving an existing book by ISBN returns 200 with its details.
    @Test
    void getBookByIsbn_returns200WithBook_whenBookExists() throws Exception {
        UUID id = UUID.randomUUID();
        given(bookService.getBookByIsbn("978-0-13-468599-1"))
                .willReturn(new BookResponse(id, "978-0-13-468599-1", "Effective Java", "Joshua Bloch"));

        mockMvc.perform(get("/api/v1/books/{isbn}", "978-0-13-468599-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.isbn").value("978-0-13-468599-1"))
                .andExpect(jsonPath("$.title").value("Effective Java"));
    }

    // AC-3.2: retrieving an unknown ISBN returns 404 with the not-found message.
    @Test
    void getBookByIsbn_returns404_whenBookDoesNotExist() throws Exception {
        given(bookService.getBookByIsbn("978-0-00-000000-0"))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: 978-0-00-000000-0"));

        mockMvc.perform(get("/api/v1/books/{isbn}", "978-0-00-000000-0"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: 978-0-00-000000-0"));
    }

    // AC-4.1: deleting an existing book returns 204 No Content.
    @Test
    void deleteBookByIsbn_returns204_whenBookExists() throws Exception {
        mockMvc.perform(delete("/api/v1/books/{isbn}", "978-0-13-468599-1"))
                .andExpect(status().isNoContent());

        verify(bookService).deleteBookByIsbn("978-0-13-468599-1");
    }

    // AC-4.2: deleting an unknown ISBN returns 404 with the not-found message.
    @Test
    void deleteBookByIsbn_returns404_whenBookDoesNotExist() throws Exception {
        willThrow(new ResourceNotFoundException("Book not found with ISBN: 978-0-00-000000-0"))
                .given(bookService).deleteBookByIsbn("978-0-00-000000-0");

        mockMvc.perform(delete("/api/v1/books/{isbn}", "978-0-00-000000-0"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: 978-0-00-000000-0"));
    }

    // Collection read: the catalog is exposed as a JSON array with HTTP 200.
    @Test
    void getAllBooks_returns200WithCollection_whenCatalogHasEntries() throws Exception {
        given(bookService.getAllBooks()).willReturn(List.of(
                new BookResponse(UUID.randomUUID(), "978-0-13-468599-1", "Effective Java", "Joshua Bloch"),
                new BookResponse(UUID.randomUUID(), "978-0-201-63361-0", "Design Patterns", "Erich Gamma")));

        mockMvc.perform(get("/api/v1/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.").isArray())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].isbn").value("978-0-13-468599-1"))
                .andExpect(jsonPath("$[1].isbn").value("978-0-201-63361-0"));
    }
}
