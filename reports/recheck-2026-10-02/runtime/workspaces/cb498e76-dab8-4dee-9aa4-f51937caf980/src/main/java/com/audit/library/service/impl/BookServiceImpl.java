package com.audit.library.service.impl;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.BookService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@Transactional
public class BookServiceImpl implements BookService {

    private final BookRepository bookRepository;

    public BookServiceImpl(BookRepository bookRepository) {
        this.bookRepository = bookRepository;
    }

    @Override
    public BookResponse createBook(CreateBookRequest request) {
        validateCreateRequest(request);
        if (bookRepository.existsByIsbn(request.isbn())) {
            throw new IllegalArgumentException("Book with ISBN " + request.isbn() + " already exists");
        }
        Book book = new Book(UUID.randomUUID(), request.isbn(), request.title(), request.author());
        Book saved = bookRepository.save(book);
        return BookResponse.from(saved);
    }

    @Override
    @Transactional(readOnly = true)
    public BookResponse getBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        return BookResponse.from(book);
    }

    @Override
    @Transactional(readOnly = true)
    public List<BookResponse> getAllBooks() {
        return bookRepository.findAll().stream()
                .map(BookResponse::from)
                .toList();
    }

    @Override
    public BookResponse updateBookTitle(String isbn, String newTitle) {
        if (newTitle == null || newTitle.isBlank()) {
            throw new IllegalArgumentException("Title cannot be empty");
        }
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        book.setTitle(newTitle);
        Book saved = bookRepository.save(book);
        return BookResponse.from(saved);
    }

    @Override
    public void deleteBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        bookRepository.delete(book);
    }

    private void validateCreateRequest(CreateBookRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Book request must not be null");
        }
        if (request.isbn() == null || request.isbn().isBlank()) {
            throw new IllegalArgumentException("ISBN cannot be empty");
        }
        if (request.title() == null || request.title().isBlank()) {
            throw new IllegalArgumentException("Title cannot be empty");
        }
        if (request.author() == null || request.author().isBlank()) {
            throw new IllegalArgumentException("Author cannot be empty");
        }
    }
}
