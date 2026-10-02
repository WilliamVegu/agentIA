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

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
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
    void createBook_returnsCreatedWithLocationAndBody_whenRequestIsValid() throws Exception {
        CreateBookRequest request = new CreateBookRequest(
                "9783161484100", "Clean Code", "Robert C. Martin");
        BookResponse response = new BookResponse(
                UUID.randomUUID(),
                "9783161484100",
                "Clean Code",
                "Robert C. Martin",
                LocalDateTime.now().minusDays(1),
                null);
        given(bookService.create(any(CreateBookRequest.class))).willReturn(response);

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "/api/v1/books/9783161484100"))
                .andExpect(jsonPath("$.id").value(response.id().toString()))
                .andExpect(jsonPath("$.isbn").value("9783161484100"))
                .andExpect(jsonPath("$.title").value("Clean Code"))
                .andExpect(jsonPath("$.author").value("Robert C. Martin"));

        verify(bookService).create(any(CreateBookRequest.class));
    }

    @Test
    void createBook_returnsConflict_whenIsbnAlreadyExists() throws Exception {
        CreateBookRequest request = new CreateBookRequest(
                "9783161484100", "Another Title", "Another Author");
        given(bookService.create(any(CreateBookRequest.class)))
                .willThrow(new IllegalStateException("Book with ISBN 9783161484100 already exists"));

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value(409))
                .andExpect(jsonPath("$.errorCode").value("BOOK_ISBN_DUPLICATE"));

        verify(bookService).create(any(CreateBookRequest.class));
    }

    @Test
    void createBook_returnsBadRequest_whenTitleIsBlank() throws Exception {
        CreateBookRequest request = new CreateBookRequest(
                "9783161484100", "   ", "Robert C. Martin");

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.fieldErrors[0].field").value("title"));

        verifyNoInteractions(bookService);
    }

    @Test
    void createBook_returnsBadRequest_whenIsbnIsMalformed() throws Exception {
        CreateBookRequest request = new CreateBookRequest(
                "ABC-123", "Clean Code", "Robert C. Martin");

        mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.fieldErrors[0].field").value("isbn"));

        verifyNoInteractions(bookService);
    }

    @Test
    void findBookByIsbn_returnsOkWithFullRepresentation_whenBookExists() throws Exception {
        BookResponse response = new BookResponse(
                UUID.randomUUID(),
                "9783161484100",
                "Clean Code",
                "Robert C. Martin",
                LocalDateTime.now().minusDays(1),
                null);
        given(bookService.findByIsbn("9783161484100")).willReturn(response);

        mockMvc.perform(get("/api/v1/books/9783161484100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(response.id().toString()))
                .andExpect(jsonPath("$.isbn").value("9783161484100"))
                .andExpect(jsonPath("$.title").value("Clean Code"))
                .andExpect(jsonPath("$.author").value("Robert C. Martin"))
                .andExpect(jsonPath("$.createdAt").exists());

        verify(bookService).findByIsbn("9783161484100");
    }

    @Test
    void findBookByIsbn_returnsNotFound_whenBookMissing() throws Exception {
        given(bookService.findByIsbn("9780000000000"))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: 9780000000000"));

        mockMvc.perform(get("/api/v1/books/9780000000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.errorCode").value("BOOK_NOT_FOUND"))
                .andExpect(jsonPath("$.message").value("Book not found with ISBN: 9780000000000"));

        verify(bookService).findByIsbn("9780000000000");
    }

    @Test
    void findBookByIsbn_returnsBadRequest_whenIsbnIsMalformed() throws Exception {
        mockMvc.perform(get("/api/v1/books/not-an-isbn"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));

        verifyNoInteractions(bookService);
    }

    @Test
    void findAllBooks_returnsOkWithCompleteCollection() throws Exception {
        BookResponse first = new BookResponse(
                UUID.randomUUID(),
                "9783161484100",
                "Clean Code",
                "Robert C. Martin",
                LocalDateTime.now().minusDays(1),
                null);
        BookResponse second = new BookResponse(
                UUID.randomUUID(),
                "9780132350884",
                "Effective Java",
                "Joshua Bloch",
                LocalDateTime.now().minusDays(2),
                null);
        given(bookService.findAll()).willReturn(List.of(first, second));

        mockMvc.perform(get("/api/v1/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].isbn").value("9783161484100"))
                .andExpect(jsonPath("$[1].isbn").value("9780132350884"));

        verify(bookService).findAll();
    }

    @Test
    void updateBookTitle_returnsOkWithUpdatedRepresentation_whenBookExists() throws Exception {
        BookResponse response = new BookResponse(
                UUID.randomUUID(),
                "9783161484100",
                "Clean Code: A Handbook of Agile Software Craftsmanship",
                "Robert C. Martin",
                LocalDateTime.now().minusDays(1),
                LocalDateTime.now());
        given(bookService.updateTitle("9783161484100",
                "Clean Code: A Handbook of Agile Software Craftsmanship"))
                .willReturn(response);

        mockMvc.perform(put("/api/v1/books/9783161484100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new BookController.UpdateBookTitleRequest(
                                        "Clean Code: A Handbook of Agile Software Craftsmanship"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.isbn").value("9783161484100"))
                .andExpect(jsonPath("$.title").value("Clean Code: A Handbook of Agile Software Craftsmanship"))
                .andExpect(jsonPath("$.author").value("Robert C. Martin"))
                .andExpect(jsonPath("$.updatedAt").exists());

        verify(bookService).updateTitle("9783161484100",
                "Clean Code: A Handbook of Agile Software Craftsmanship");
    }

    @Test
    void updateBookTitle_returnsNotFound_whenBookMissing() throws Exception {
        given(bookService.updateTitle("9783161484100", "Valid New Title"))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: 9783161484100"));

        mockMvc.perform(put("/api/v1/books/9783161484100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new BookController.UpdateBookTitleRequest("Valid New Title"))))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.errorCode").value("BOOK_NOT_FOUND"));

        verify(bookService).updateTitle("9783161484100", "Valid New Title");
    }

    @Test
    void updateBookTitle_returnsBadRequest_whenTitleIsBlank() throws Exception {
        mockMvc.perform(put("/api/v1/books/9783161484100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new BookController.UpdateBookTitleRequest(""))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.fieldErrors[0].field").value("title"));

        verifyNoInteractions(bookService);
    }

    @Test
    void deleteBook_returnsNoContent_whenBookExists() throws Exception {
        mockMvc.perform(delete("/api/v1/books/9783161484100"))
                .andExpect(status().isNoContent());

        verify(bookService).deleteByIsbn("9783161484100");
    }

    @Test
    void deleteBook_returnsNotFound_whenBookMissing() throws Exception {
        doThrow(new ResourceNotFoundException("Book not found with ISBN: 9783161484100"))
                .when(bookService).deleteByIsbn("9783161484100");

        mockMvc.perform(delete("/api/v1/books/9783161484100"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.errorCode").value("BOOK_NOT_FOUND"));

        verify(bookService).deleteByIsbn("9783161484100");
    }

    @Test
    void deleteBook_returnsBadRequest_whenIsbnIsMalformed() throws Exception {
        mockMvc.perform(delete("/api/v1/books/12345"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));

        verifyNoInteractions(bookService);
    }
}