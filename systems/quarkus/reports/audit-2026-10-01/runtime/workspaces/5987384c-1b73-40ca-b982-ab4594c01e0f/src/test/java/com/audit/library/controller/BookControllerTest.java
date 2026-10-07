package com.audit.library.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.service.BookService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(BookController.class)
class BookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private BookService bookService;

    @Test
    void createBook_whenValidRequest_returns201WithCreatedBook() throws Exception {
        UUID id = UUID.randomUUID();
        BookResponse response = new BookResponse(id, "isbn-1", "Title", "Author");
        when(bookService.createBook(any(CreateBookRequest.class))).thenReturn(response);

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateBookRequest("isbn-1", "Title", "Author"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.isbn").value("isbn-1"))
                .andExpect(jsonPath("$.title").value("Title"))
                .andExpect(jsonPath("$.author").value("Author"));
    }

    @Test
    void createBook_whenIsbnAlreadyExists_returns400() throws Exception {
        when(bookService.createBook(any(CreateBookRequest.class)))
                .thenThrow(new IllegalArgumentException("Book with ISBN isbn-1 already exists"));

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateBookRequest("isbn-1", "Title", "Author"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Book with ISBN isbn-1 already exists"));
    }

    @Test
    void createBook_whenTitleBlank_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new CreateBookRequest("isbn-1", "", "Author"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Validation failed"))
                .andExpect(jsonPath("$.fieldErrors.title").exists());
    }

    @Test
    void updateBookTitle_whenBookExists_returns200WithUpdatedBook() throws Exception {
        UUID id = UUID.randomUUID();
        BookResponse response = new BookResponse(id, "isbn-1", "New Title", "Author");
        when(bookService.updateBookTitle("isbn-1", "New Title")).thenReturn(response);

        mockMvc.perform(put("/api/v1/books/isbn-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", "New Title"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.isbn").value("isbn-1"))
                .andExpect(jsonPath("$.title").value("New Title"))
                .andExpect(jsonPath("$.author").value("Author"));
    }

    @Test
    void updateBookTitle_whenBookMissing_returns404() throws Exception {
        when(bookService.updateBookTitle("missing", "New Title"))
                .thenThrow(new ResourceNotFoundException("Book not found with ISBN missing"));

        mockMvc.perform(put("/api/v1/books/missing")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", "New Title"))))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN missing"));
    }

    @Test
    void updateBookTitle_whenTitleBlank_returns400() throws Exception {
        mockMvc.perform(put("/api/v1/books/isbn-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", ""))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Validation failed"))
                .andExpect(jsonPath("$.fieldErrors.title").exists());
    }

    @Test
    void getBookByIsbn_whenBookExists_returns200WithBook() throws Exception {
        UUID id = UUID.randomUUID();
        BookResponse response = new BookResponse(id, "isbn-1", "Title", "Author");
        when(bookService.getBookByIsbn("isbn-1")).thenReturn(response);

        mockMvc.perform(get("/api/v1/books/isbn-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.isbn").value("isbn-1"))
                .andExpect(jsonPath("$.title").value("Title"))
                .andExpect(jsonPath("$.author").value("Author"));
    }

    @Test
    void getBookByIsbn_whenBookMissing_returns404() throws Exception {
        when(bookService.getBookByIsbn("missing"))
                .thenThrow(new ResourceNotFoundException("Book not found with ISBN missing"));

        mockMvc.perform(get("/api/v1/books/missing"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN missing"));
    }

    @Test
    void deleteBookByIsbn_whenBookExists_returns204() throws Exception {
        mockMvc.perform(delete("/api/v1/books/isbn-1"))
                .andExpect(status().isNoContent());

        verify(bookService).deleteBookByIsbn("isbn-1");
    }

    @Test
    void deleteBookByIsbn_whenBookMissing_returns404() throws Exception {
        doThrow(new ResourceNotFoundException("Book not found with ISBN missing"))
                .when(bookService).deleteBookByIsbn("missing");

        mockMvc.perform(delete("/api/v1/books/missing"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Book not found with ISBN missing"));
    }

    @Test
    void getAllBooks_returns200WithAllBooks() throws Exception {
        UUID id1 = UUID.randomUUID();
        UUID id2 = UUID.randomUUID();
        when(bookService.getAllBooks()).thenReturn(List.of(
                new BookResponse(id1, "isbn-1", "Title 1", "Author 1"),
                new BookResponse(id2, "isbn-2", "Title 2", "Author 2")
        ));

        mockMvc.perform(get("/api/v1/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].isbn").value("isbn-1"))
                .andExpect(jsonPath("$[1].isbn").value("isbn-2"));
    }
}
