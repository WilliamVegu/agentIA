package com.audit.library.service.impl;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.BookService;
import java.util.List;
import java.util.UUID;
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
        if (request == null) {
            throw new IllegalArgumentException("Create book request must not be null");
        }

        String isbn = request.isbn();
        String title = request.title();
        String author = request.author();

        if (isbn == null || isbn.isBlank()) {
            throw new IllegalArgumentException("ISBN cannot be empty");
        }
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("Title cannot be empty");
        }
        if (author == null || author.isBlank()) {
            throw new IllegalArgumentException("Author cannot be empty");
        }

        if (bookRepository.findByIsbn(isbn).isPresent()) {
            throw new IllegalArgumentException("Book with ISBN " + isbn + " already exists");
        }

        Book book = new Book();
        book.setId(UUID.randomUUID());
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor(author);

        return BookResponse.fromEntity(bookRepository.save(book));
    }

    @Override
    @Transactional(readOnly = true)
    public BookResponse getBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN " + isbn));
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
    public BookResponse updateBookTitle(String isbn, String newTitle) {
        if (newTitle == null || newTitle.isBlank()) {
            throw new IllegalArgumentException("Title cannot be empty");
        }

        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN " + isbn));

        book.setTitle(newTitle);
        return BookResponse.fromEntity(bookRepository.save(book));
    }

    @Override
    public void deleteBookByIsbn(String isbn) {
        Book book = bookRepository.findByIsbn(isbn)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN " + isbn));
        bookRepository.delete(book);
    }
}
