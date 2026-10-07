package com.corp.auditlibrary.service.impl;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.BookResponse;
import com.corp.auditlibrary.model.dto.CreateBookRequest;
import com.corp.auditlibrary.model.entity.Book;
import com.corp.auditlibrary.repository.BookRepository;
import com.corp.auditlibrary.service.BookService;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class BookServiceImpl implements BookService {

    private final BookRepository bookRepository;

    public BookServiceImpl(BookRepository bookRepository) {
        this.bookRepository = bookRepository;
    }

    @Override
    public BookResponse createBook(CreateBookRequest request) {
        if (bookRepository.existsByIsbn(request.isbn())) {
            throw new IllegalStateException("BOOK_ISBN_DUPLICATE");
        }
        Book book = new Book();
        book.setIsbn(request.isbn());
        book.setTitle(request.title());
        book.setAuthor(request.author());
        book.setCreatedAt(Instant.now());
        Book saved = bookRepository.save(book);
        return BookResponse.fromEntity(saved);
    }

    @Override
    @Transactional(readOnly = true)
    public BookResponse getBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        return BookResponse.fromEntity(book);
    }

    @Override
    @Transactional(readOnly = true)
    public List<BookResponse> getAllBooks() {
        return bookRepository.findAll().stream()
                .map(BookResponse::fromEntity)
                .toList();
    }

    @Override
    public BookResponse updateBookTitle(String isbn, String title) {
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("title must not be blank");
        }
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        book.setTitle(title);
        book.setUpdatedAt(Instant.now());
        Book saved = bookRepository.save(book);
        return BookResponse.fromEntity(saved);
    }

    @Override
    public void deleteBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + isbn));
        bookRepository.delete(book);
    }
}
