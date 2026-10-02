package com.audit.library.service;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.impl.BookServiceImpl;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookServiceTest {

    @Mock
    private BookRepository bookRepository;

    @InjectMocks
    private BookServiceImpl bookService;

    @Test
    void createBook_createsAndReturnsBook_whenRequestIsValid() {
        CreateBookRequest request = new CreateBookRequest("978-0-123456-47-2", "Effective Java", "Joshua Bloch");
        when(bookRepository.existsByIsbn(request.isbn())).thenReturn(false);
        when(bookRepository.save(any(Book.class))).thenAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.createBook(request);

        assertThat(response.id()).isNotNull();
        assertThat(response.isbn()).isEqualTo(request.isbn());
        assertThat(response.title()).isEqualTo(request.title());
        assertThat(response.author()).isEqualTo(request.author());

        ArgumentCaptor<Book> bookCaptor = ArgumentCaptor.forClass(Book.class);
        verify(bookRepository).save(bookCaptor.capture());
        assertThat(bookCaptor.getValue().getIsbn()).isEqualTo(request.isbn());
        assertThat(bookCaptor.getValue().getTitle()).isEqualTo(request.title());
        assertThat(bookCaptor.getValue().getAuthor()).isEqualTo(request.author());
    }

    @Test
    void createBook_rejectsDuplicateIsbn_whenIsbnAlreadyExists() {
        CreateBookRequest request = new CreateBookRequest("duplicate-isbn", "Title", "Author");
        when(bookRepository.existsByIsbn(request.isbn())).thenReturn(true);

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("already exists");

        verify(bookRepository, never()).save(any(Book.class));
    }

    @Test
    void createBook_rejectsEmptyTitle_whenTitleIsBlank() {
        CreateBookRequest request = new CreateBookRequest("isbn-1", "   ", "Author");

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Title cannot be empty");

        verifyNoInteractions(bookRepository);
    }

    @Test
    void updateBookTitle_updatesAndReturnsBook_whenBookExistsAndTitleIsValid() {
        String isbn = "isbn-1";
        Book existing = new Book(UUID.randomUUID(), isbn, "Old Title", "Author");
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.of(existing));
        when(bookRepository.save(any(Book.class))).thenAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.updateBookTitle(isbn, "New Title");

        assertThat(response.title()).isEqualTo("New Title");
        assertThat(existing.getTitle()).isEqualTo("New Title");
        verify(bookRepository).save(existing);
    }

    @Test
    void updateBookTitle_throwsNotFound_whenBookDoesNotExist() {
        String isbn = "missing-isbn";
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.updateBookTitle(isbn, "New Title"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN");

        verify(bookRepository, never()).save(any(Book.class));
    }

    @Test
    void updateBookTitle_rejectsEmptyTitle_whenNewTitleIsBlank() {
        assertThatThrownBy(() -> bookService.updateBookTitle("isbn-1", "  "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Title cannot be empty");

        verifyNoInteractions(bookRepository);
    }

    @Test
    void getBookByIsbn_returnsBook_whenBookExists() {
        String isbn = "isbn-1";
        Book book = new Book(UUID.randomUUID(), isbn, "Title", "Author");
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.of(book));

        BookResponse response = bookService.getBookByIsbn(isbn);

        assertThat(response.id()).isEqualTo(book.getId());
        assertThat(response.isbn()).isEqualTo(isbn);
        assertThat(response.title()).isEqualTo("Title");
        assertThat(response.author()).isEqualTo("Author");
        verify(bookRepository).findByIsbn(isbn);
    }

    @Test
    void getBookByIsbn_throwsNotFound_whenBookDoesNotExist() {
        String isbn = "missing-isbn";
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.getBookByIsbn(isbn))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN");
    }

    @Test
    void getAllBooks_returnsAllBooks_whenRepositoryHasBooks() {
        Book first = new Book(UUID.randomUUID(), "isbn-1", "Title 1", "Author 1");
        Book second = new Book(UUID.randomUUID(), "isbn-2", "Title 2", "Author 2");
        when(bookRepository.findAll()).thenReturn(List.of(first, second));

        List<BookResponse> responses = bookService.getAllBooks();

        assertThat(responses).hasSize(2);
        assertThat(responses).extracting(BookResponse::isbn).containsExactly("isbn-1", "isbn-2");
        verify(bookRepository).findAll();
    }

    @Test
    void deleteBookByIsbn_deletesBook_whenBookExists() {
        String isbn = "isbn-1";
        Book book = new Book(UUID.randomUUID(), isbn, "Title", "Author");
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.of(book));

        bookService.deleteBookByIsbn(isbn);

        verify(bookRepository).delete(book);
    }

    @Test
    void deleteBookByIsbn_throwsNotFound_whenBookDoesNotExist() {
        String isbn = "missing-isbn";
        when(bookRepository.findByIsbn(isbn)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.deleteBookByIsbn(isbn))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN");

        verify(bookRepository, never()).delete(any(Book.class));
    }
}
