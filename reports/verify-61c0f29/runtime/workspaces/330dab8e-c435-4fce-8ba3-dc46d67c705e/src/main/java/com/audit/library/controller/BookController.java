package com.audit.library.controller;

import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.service.BookService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;

/**
 * REST surface for the Book catalogue. The controller only receives HTTP, delegates to
 * {@link BookService} and serialises the record contracts; errors bubble up to the single
 * global advice.
 */
@RestController
@RequestMapping("/api/v1/books")
@Validated
public class BookController {

    private static final String ISBN_PATTERN = "^(?:\\d{9}[\\dXx]|\\d{13})$";
    private static final String BOOKS_PATH = "/api/v1/books/";

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @PostMapping
    public ResponseEntity<BookResponse> create(@Valid @RequestBody CreateBookRequest request) {
        BookResponse created = bookService.create(request);
        return ResponseEntity.created(URI.create(BOOKS_PATH + created.isbn())).body(created);
    }

    @GetMapping("/{isbn}")
    public ResponseEntity<BookResponse> findByIsbn(
            @PathVariable("isbn") @NotBlank @Pattern(regexp = ISBN_PATTERN) String isbn) {
        return ResponseEntity.ok(bookService.findByIsbn(isbn));
    }

    @GetMapping
    public ResponseEntity<List<BookResponse>> findAll() {
        return ResponseEntity.ok(bookService.findAll());
    }

    @PutMapping("/{isbn}")
    public ResponseEntity<BookResponse> updateTitle(
            @PathVariable("isbn") @NotBlank @Pattern(regexp = ISBN_PATTERN) String isbn,
            @Valid @RequestBody UpdateBookTitleRequest request) {
        return ResponseEntity.ok(bookService.updateTitle(isbn, request.title()));
    }

    @DeleteMapping("/{isbn}")
    public ResponseEntity<Void> delete(
            @PathVariable("isbn") @NotBlank @Pattern(regexp = ISBN_PATTERN) String isbn) {
        bookService.deleteByIsbn(isbn);
        return ResponseEntity.noContent().build();
    }

    public record UpdateBookTitleRequest(
            @NotBlank
            @Size(min = 1, max = 255)
            String title) {
    }
}
