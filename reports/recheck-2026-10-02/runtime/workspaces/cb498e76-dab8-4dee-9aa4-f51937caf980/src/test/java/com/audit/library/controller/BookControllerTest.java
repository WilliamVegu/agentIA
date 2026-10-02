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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(BookController.class)
class BookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private BookService bookService;

    @Test
    void createBook_returns201WithCreatedBook_whenRequestIsValid() throws Exception {
        CreateBookRequest request = new CreateBookRequest("978-0-123456-47-2", "Effective Java", "Joshua Bloch");
        BookResponse response = new BookResponse(UUID.randomUUID(), request.isbn(), request.title(), request.author());
        when(bookService.createBook(any(CreateBookRequest.class))).thenReturn(response);

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(response.id().toString()))
                .andExpect(jsonPath("$.isbn").value(request.isbn()))
                .andExpect(jsonPath("$.title").value(request.title()))
                .andExpect(jsonPath("$.author").value(request.author()));
    }

    @Test
    void createBook_returns400WithDuplicateIsbnMessage_whenIsbnAlreadyExists() throws Exception {
        CreateBookRequest request = new CreateBookRequest("duplicate-isbn", "Title", "Author");
        when(bookService.createBook(any(CreateBookRequest.class)))
                .thenThrow(new IllegalArgumentException("Book with ISBN duplicate-isbn already exists"));

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Book with ISBN duplicate-isbn already exists"));
    }

    @Test
    void createBook_returns400WithTitleValidationMessage_whenTitleIsBlank() throws Exception {
        CreateBookRequest request = new CreateBookRequest("isbn-1", "", "Author");

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Validation failed"))
                .andExpect(jsonPath("$.details.title").value("must not be blank"));
    }

    @Test
    void updateBookTitle_returns200WithUpdatedBook_whenBookExistsAndTitleIsValid() throws Exception {
        BookResponse response = new BookResponse(UUID.randomUUID(), "isbn-1", "New Title", "Author");
        when(bookService.updateBookTitle(eq("isbn-1"), eq("New Title"))).thenReturn(response);

        mockMvc.perform(patch("/api/v1/books/{isbn}/title", "isbn-1")
                        .param("title", "New Title"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("New Title"));
    }

    @Test
    void updateBookTitle_returns404_whenBookDoesNotExist() throws Exception {
        when(bookService.updateBookTitle(eq("missing-isbn"), eq("New Title")))
                .thenThrow(new ResourceNotFoundException("Book not found with ISBN: missing-isbn"));

        mockMvc.perform(patch("/api/v1/books/{isbn}/title", "missing-isbn")
                        .param("title", "New Title"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: missing-isbn"));
    }

    @Test
    void updateBookTitle_returns400WithTitleValidationMessage_whenTitleIsBlank() throws Exception {
        mockMvc.perform(patch("/api/v1/books/{isbn}/title", "isbn-1")
                        .param("title", ""))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Validation failed"));
    }

    @Test
    void getBookByIsbn_returns200WithBook_whenBookExists() throws Exception {
        BookResponse response = new BookResponse(UUID.randomUUID(), "isbn-1", "Title", "Author");
        when(bookService.getBookByIsbn("isbn-1")).thenReturn(response);

        mockMvc.perform(get("/api/v1/books/{isbn}", "isbn-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.isbn").value("isbn-1"))
                .andExpect(jsonPath("$.title").value("Title"));
    }

    @Test
    void getBookByIsbn_returns404_whenBookDoesNotExist() throws Exception {
        when(bookService.getBookByIsbn("missing-isbn"))
                .thenThrow(new ResourceNotFoundException("Book not found with ISBN: missing-isbn"));

        mockMvc.perform(get("/api/v1/books/{isbn}", "missing-isbn"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: missing-isbn"));
    }

    @Test
    void getAllBooks_returns200WithAllBooks() throws Exception {
        List<BookResponse> responses = List.of(
                new BookResponse(UUID.randomUUID(), "isbn-1", "Title 1", "Author 1"),
                new BookResponse(UUID.randomUUID(), "isbn-2", "Title 2", "Author 2"));
        when(bookService.getAllBooks()).thenReturn(responses);

        mockMvc.perform(get("/api/v1/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].isbn").value("isbn-1"))
                .andExpect(jsonPath("$[1].isbn").value("isbn-2"));
    }

    @Test
    void deleteBookByIsbn_returns204_whenBookExists() throws Exception {
        mockMvc.perform(delete("/api/v1/books/{isbn}", "isbn-1"))
                .andExpect(status().isNoContent());
    }

    @Test
    void deleteBookByIsbn_returns404_whenBookDoesNotExist() throws Exception {
        doThrow(new ResourceNotFoundException("Book not found with ISBN: missing-isbn"))
                .when(bookService).deleteBookByIsbn("missing-isbn");

        mockMvc.perform(delete("/api/v1/books/{isbn}", "missing-isbn"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: missing-isbn"));
    }
}
