package com.corp.auditlibrary.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.BookResponse;
import com.corp.auditlibrary.model.dto.CreateBookRequest;
import com.corp.auditlibrary.service.BookService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(controllers = BookController.class)
class BookControllerTest {

    private static final String ISBN = "9783161484100";
    private static final String AUTHOR = "Robert C. Martin";
    private static final Instant CREATED_AT = Instant.parse("2024-05-01T10:15:30Z");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private BookService bookService;

    @Test
    void createBook_withUniqueIsbn_respondsCreatedWithLocationHeaderAndBookRepresentation() throws Exception {
        UUID id = UUID.randomUUID();
        given(bookService.createBook(any(CreateBookRequest.class)))
                .willReturn(new BookResponse(id, ISBN, "Clean Code", AUTHOR, CREATED_AT, null));

        String body = mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"9783161484100","title":"Clean Code","author":"Robert C. Martin"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().string(HttpHeaders.LOCATION, "/api/v1/books/9783161484100"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        BookResponse created = objectMapper.readValue(body, BookResponse.class);
        assertThat(created.id()).isEqualTo(id);
        assertThat(created.isbn()).isEqualTo(ISBN);
        assertThat(created.title()).isEqualTo("Clean Code");
        assertThat(created.author()).isEqualTo(AUTHOR);
        assertThat(created.createdAt()).isEqualTo(CREATED_AT);
    }

    @Test
    void createBook_withAlreadyRegisteredIsbn_respondsConflictWithDuplicateErrorCode() throws Exception {
        given(bookService.createBook(any(CreateBookRequest.class)))
                .willThrow(new IllegalStateException("BOOK_ISBN_DUPLICATE"));

        String body = mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"9783161484100","title":"Another Title","author":"Another Author"}
                                """))
                .andExpect(status().isConflict())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(409);
        assertThat((String) JsonPath.read(body, "$.message")).isEqualTo("BOOK_ISBN_DUPLICATE");
    }

    @Test
    void createBook_withBlankTitle_respondsBadRequestWithFieldErrorOnTitleAndNeverReachesTheService() throws Exception {
        String body = mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"9783161484100","title":"   ","author":"Robert C. Martin"}
                                """))
                .andExpect(status().isBadRequest())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat((String) JsonPath.read(body, "$.fieldErrors.title")).isNotBlank();
        verifyNoInteractions(bookService);
    }

    @Test
    void createBook_withMalformedIsbn_respondsBadRequestWithFieldErrorOnIsbnAndNeverReachesTheService() throws Exception {
        String body = mockMvc.perform(post("/api/v1/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"isbn":"ABC-123","title":"Clean Code","author":"Robert C. Martin"}
                                """))
                .andExpect(status().isBadRequest())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat((String) JsonPath.read(body, "$.fieldErrors.isbn")).isNotBlank();
        verifyNoInteractions(bookService);
    }

    @Test
    void updateBookTitle_withValidTitle_respondsOkWithUpdatedRepresentation() throws Exception {
        UUID id = UUID.randomUUID();
        String newTitle = "Clean Code: A Handbook of Agile Software Craftsmanship";
        Instant updatedAt = Instant.parse("2024-06-01T09:00:00Z");
        given(bookService.updateBookTitle(ISBN, newTitle))
                .willReturn(new BookResponse(id, ISBN, newTitle, AUTHOR, CREATED_AT, updatedAt));

        String body = mockMvc.perform(put("/api/v1/books/{isbn}", ISBN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", newTitle))))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        BookResponse updated = objectMapper.readValue(body, BookResponse.class);
        assertThat(updated.id()).isEqualTo(id);
        assertThat(updated.isbn()).isEqualTo(ISBN);
        assertThat(updated.title()).isEqualTo(newTitle);
        assertThat(updated.author()).isEqualTo(AUTHOR);
        assertThat(updated.createdAt()).isEqualTo(CREATED_AT);
        assertThat(updated.updatedAt()).isEqualTo(updatedAt);
    }

    @Test
    void updateBookTitle_withUnknownIsbn_respondsNotFound() throws Exception {
        given(bookService.updateBookTitle(ISBN, "Valid New Title"))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: " + ISBN));

        String body = mockMvc.perform(put("/api/v1/books/{isbn}", ISBN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", "Valid New Title"))))
                .andExpect(status().isNotFound())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(404);
        assertThat((String) JsonPath.read(body, "$.message")).isEqualTo("Book not found with ISBN: " + ISBN);
        assertThat((String) JsonPath.read(body, "$.path")).isEqualTo("/api/v1/books/" + ISBN);
    }

    @Test
    void updateBookTitle_withBlankTitle_respondsBadRequestWithFieldErrorOnTitleAndNeverReachesTheService() throws Exception {
        String body = mockMvc.perform(put("/api/v1/books/{isbn}", ISBN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("title", ""))))
                .andExpect(status().isBadRequest())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat((String) JsonPath.read(body, "$.fieldErrors.title")).isNotBlank();
        verifyNoInteractions(bookService);
    }

    @Test
    void getBookByIsbn_withKnownIsbn_respondsOkWithFullRepresentation() throws Exception {
        UUID id = UUID.randomUUID();
        Instant updatedAt = Instant.parse("2024-06-01T09:00:00Z");
        given(bookService.getBookByIsbn(ISBN))
                .willReturn(new BookResponse(id, ISBN, "Clean Code", AUTHOR, CREATED_AT, updatedAt));

        String body = mockMvc.perform(get("/api/v1/books/{isbn}", ISBN))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        BookResponse book = objectMapper.readValue(body, BookResponse.class);
        assertThat(book.id()).isEqualTo(id);
        assertThat(book.isbn()).isEqualTo(ISBN);
        assertThat(book.title()).isEqualTo("Clean Code");
        assertThat(book.author()).isEqualTo(AUTHOR);
        assertThat(book.createdAt()).isEqualTo(CREATED_AT);
        assertThat(book.updatedAt()).isEqualTo(updatedAt);
    }

    @Test
    void getBookByIsbn_withUnknownIsbn_respondsNotFound() throws Exception {
        String unknownIsbn = "9780000000000";
        given(bookService.getBookByIsbn(unknownIsbn))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: " + unknownIsbn));

        String body = mockMvc.perform(get("/api/v1/books/{isbn}", unknownIsbn))
                .andExpect(status().isNotFound())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(404);
        assertThat((String) JsonPath.read(body, "$.message"))
                .isEqualTo("Book not found with ISBN: " + unknownIsbn);
    }

    @Test
    void getBookByIsbn_withMalformedIsbnPath_respondsBadRequestWithFieldLevelValidationError() throws Exception {
        String body = mockMvc.perform(get("/api/v1/books/not-an-isbn"))
                .andExpect(status().isBadRequest())
                .andReturn()
                .getResponse()
                .getContentAsString();

        Map<String, Object> fieldErrors = JsonPath.read(body, "$.fieldErrors");
        assertThat(fieldErrors).isNotEmpty();
        assertThat(fieldErrors.keySet()).anyMatch(key -> key.endsWith("isbn"));
        verifyNoInteractions(bookService);
    }

    @Test
    void deleteBookByIsbn_withKnownIsbn_respondsNoContentAndBookIsNoLongerRetrievable() throws Exception {
        mockMvc.perform(delete("/api/v1/books/{isbn}", ISBN))
                .andExpect(status().isNoContent());

        verify(bookService).deleteBookByIsbn(ISBN);

        given(bookService.getBookByIsbn(ISBN))
                .willThrow(new ResourceNotFoundException("Book not found with ISBN: " + ISBN));

        mockMvc.perform(get("/api/v1/books/{isbn}", ISBN))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteBookByIsbn_withUnknownIsbn_respondsNotFound() throws Exception {
        willThrow(new ResourceNotFoundException("Book not found with ISBN: " + ISBN))
                .given(bookService)
                .deleteBookByIsbn(ISBN);

        String body = mockMvc.perform(delete("/api/v1/books/{isbn}", ISBN))
                .andExpect(status().isNotFound())
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertThat(((Number) JsonPath.read(body, "$.status")).intValue()).isEqualTo(404);
        assertThat((String) JsonPath.read(body, "$.message")).isEqualTo("Book not found with ISBN: " + ISBN);
    }

    @Test
    void deleteBookByIsbn_withMalformedIsbnPath_respondsBadRequestAndRemovesNothing() throws Exception {
        mockMvc.perform(delete("/api/v1/books/12345"))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(bookService);
    }
}
