package com.audit.library.service.impl;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.BookService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
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
    public BookResponse create(CreateBookRequest request) {
        if (bookRepository.existsByIsbn(request.isbn())) {
            throw new IllegalStateException(
                    "Book with ISBN " + request.isbn() + " already exists");
        }

        Book book = new Book();
        book.setId(UUID.randomUUID());
        book.setIsbn(request.isbn());
        book.setTitle(request.title());
        book.setAuthor(request.author());
        book.setCreatedAt(LocalDateTime.now());

        Book persisted = bookRepository.save(book);
        return BookResponse.from(persisted);
    }

    @Override
    @Transactional(readOnly = true)
    public BookResponse findByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Book not found with ISBN: " + isbn));
        return BookResponse.from(book);
    }

    @Override
    @Transactional(readOnly = true)
    public List<BookResponse> findAll() {
        return bookRepository.findAll().stream()
                .map(BookResponse::from)
                .toList();
    }

    @Override
    public BookResponse updateTitle(String isbn, String title) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Book not found with ISBN: " + isbn));

        book.setTitle(title);
        book.setUpdatedAt(LocalDateTime.now());

        Book persisted = bookRepository.save(book);
        return BookResponse.from(persisted);
    }

    @Override
    public void deleteByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Book not found with ISBN: " + isbn));

        bookRepository.delete(book);
    }
}
