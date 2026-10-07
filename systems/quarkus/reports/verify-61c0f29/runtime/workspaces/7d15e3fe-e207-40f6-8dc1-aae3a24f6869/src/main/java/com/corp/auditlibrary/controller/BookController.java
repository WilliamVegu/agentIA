package com.corp.auditlibrary.controller;

import com.corp.auditlibrary.model.dto.BookResponse;
import com.corp.auditlibrary.model.dto.CreateBookRequest;
import com.corp.auditlibrary.service.BookService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.net.URI;
import java.util.List;
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

@RestController
@RequestMapping("/api/v1/books")
@Validated
public class BookController {

    private static final String ISBN_PATTERN = "^(?:\\d{9}[\\dXx]|\\d{13})$";

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @PostMapping
    public ResponseEntity<BookResponse> createBook(@Valid @RequestBody CreateBookRequest request) {
        BookResponse created = bookService.createBook(request);
        return ResponseEntity.created(URI.create("/api/v1/books/" + created.isbn())).body(created);
    }

    @GetMapping
    public ResponseEntity<List<BookResponse>> getAllBooks() {
        return ResponseEntity.ok(bookService.getAllBooks());
    }

    @GetMapping("/{isbn}")
    public ResponseEntity<BookResponse> getBookByIsbn(
            @PathVariable @Pattern(regexp = ISBN_PATTERN) String isbn) {
        return ResponseEntity.ok(bookService.getBookByIsbn(isbn));
    }

    @PutMapping("/{isbn}")
    public ResponseEntity<BookResponse> updateBookTitle(
            @PathVariable @Pattern(regexp = ISBN_PATTERN) String isbn,
            @Valid @RequestBody UpdateBookTitleRequest request) {
        return ResponseEntity.ok(bookService.updateBookTitle(isbn, request.title()));
    }

    @DeleteMapping("/{isbn}")
    public ResponseEntity<Void> deleteBookByIsbn(
            @PathVariable @Pattern(regexp = ISBN_PATTERN) String isbn) {
        bookService.deleteBookByIsbn(isbn);
        return ResponseEntity.noContent().build();
    }

    public record UpdateBookTitleRequest(
            @NotBlank
            @Size(min = 1, max = 255)
            String title) {
    }
}
