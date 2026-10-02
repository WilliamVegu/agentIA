package com.corp.auditlibrary.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verifyNoMoreInteractions;

import com.corp.auditlibrary.exception.ResourceNotFoundException;
import com.corp.auditlibrary.model.dto.BookResponse;
import com.corp.auditlibrary.model.dto.CreateBookRequest;
import com.corp.auditlibrary.model.entity.Book;
import com.corp.auditlibrary.repository.BookRepository;
import com.corp.auditlibrary.service.impl.BookServiceImpl;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class BookServiceTest {

    private static final String ISBN = "9783161484100";
    private static final String AUTHOR = "Robert C. Martin";
    private static final Instant CREATED_AT = Instant.parse("2024-05-01T10:15:30Z");

    @Mock
    private BookRepository bookRepository;

    private BookService bookService;

    @BeforeEach
    void setUp() {
        bookService = new BookServiceImpl(bookRepository);
    }

    @Test
    void createBook_withUniqueIsbn_persistsBookAndReturnsRepresentationWithGeneratedIdAndCreatedAt() {
        CreateBookRequest request = new CreateBookRequest(ISBN, "Clean Code", AUTHOR);
        UUID generatedId = UUID.randomUUID();
        given(bookRepository.existsByIsbn(ISBN)).willReturn(false);
        given(bookRepository.save(any(Book.class))).willAnswer(invocation -> {
            Book pending = invocation.getArgument(0);
            assertThat(pending.getId()).isNull();
            assertThat(pending.getIsbn()).isEqualTo(ISBN);
            assertThat(pending.getTitle()).isEqualTo("Clean Code");
            assertThat(pending.getAuthor()).isEqualTo(AUTHOR);
            assertThat(pending.getCreatedAt()).isNotNull();
            pending.setId(generatedId);
            return pending;
        });

        BookResponse response = bookService.createBook(request);

        assertThat(response.id()).isEqualTo(generatedId);
        assertThat(response.isbn()).isEqualTo(ISBN);
        assertThat(response.title()).isEqualTo("Clean Code");
        assertThat(response.author()).isEqualTo(AUTHOR);
        assertThat(response.createdAt()).isNotNull();
        assertThat(response.updatedAt()).isNull();
        verify(bookRepository).existsByIsbn(ISBN);
        verify(bookRepository).save(any(Book.class));
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void createBook_withAlreadyRegisteredIsbn_throwsDuplicateIsbnAndStoresNothing() {
        CreateBookRequest request = new CreateBookRequest(ISBN, "Another Title", "Another Author");
        given(bookRepository.existsByIsbn(ISBN)).willReturn(true);

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("BOOK_ISBN_DUPLICATE");

        verify(bookRepository).existsByIsbn(ISBN);
        verify(bookRepository, never()).save(any(Book.class));
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void getBookByIsbn_withKnownIsbn_returnsStoredBookWithoutModifyingIt() {
        UUID id = UUID.randomUUID();
        Book stored = storedBook(id, ISBN, "Clean Code");
        given(bookRepository.findByIsbn(ISBN)).willReturn(Optional.of(stored));

        BookResponse response = bookService.getBookByIsbn(ISBN);

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo(ISBN);
        assertThat(response.title()).isEqualTo("Clean Code");
        assertThat(response.author()).isEqualTo(AUTHOR);
        assertThat(response.createdAt()).isEqualTo(CREATED_AT);
        assertThat(response.updatedAt()).isNull();
        verify(bookRepository).findByIsbn(ISBN);
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void getBookByIsbn_withUnknownIsbn_throwsResourceNotFound() {
        String unknownIsbn = "9780000000000";
        given(bookRepository.findByIsbn(unknownIsbn)).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.getBookByIsbn(unknownIsbn))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining(unknownIsbn);

        verify(bookRepository).findByIsbn(unknownIsbn);
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void getAllBooks_returnsEveryStoredBook() {
        Book first = storedBook(UUID.randomUUID(), ISBN, "Clean Code");
        Book second = storedBook(UUID.randomUUID(), "9780132350884", "Clean Architecture");
        given(bookRepository.findAll()).willReturn(List.of(first, second));

        List<BookResponse> books = bookService.getAllBooks();

        assertThat(books).hasSize(2);
        assertThat(books).extracting(BookResponse::isbn)
                .containsExactlyInAnyOrder(ISBN, "9780132350884");
        verify(bookRepository).findAll();
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void updateBookTitle_withKnownIsbn_updatesTitleAndTimestampAndLeavesIdentityUntouched() {
        UUID id = UUID.randomUUID();
        Book stored = storedBook(id, ISBN, "Clean Code");
        String newTitle = "Clean Code: A Handbook of Agile Software Craftsmanship";
        given(bookRepository.findByIsbn(ISBN)).willReturn(Optional.of(stored));
        given(bookRepository.save(any(Book.class))).willAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.updateBookTitle(ISBN, newTitle);

        assertThat(response.title()).isEqualTo(newTitle);
        assertThat(response.isbn()).isEqualTo(ISBN);
        assertThat(response.author()).isEqualTo(AUTHOR);
        assertThat(response.id()).isEqualTo(id);
        assertThat(response.createdAt()).isEqualTo(CREATED_AT);
        assertThat(response.updatedAt()).isNotNull();
        assertThat(stored.getTitle()).isEqualTo(newTitle);
        verify(bookRepository).findByIsbn(ISBN);
        verify(bookRepository).save(stored);
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void updateBookTitle_withUnknownIsbn_throwsResourceNotFoundAndCreatesNoRecord() {
        String newTitle = "Valid New Title";
        given(bookRepository.findByIsbn(ISBN)).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.updateBookTitle(ISBN, newTitle))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining(ISBN);

        verify(bookRepository).findByIsbn(ISBN);
        verify(bookRepository, never()).save(any(Book.class));
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void updateBookTitle_withBlankTitle_isRejectedWithoutTouchingTheCatalog() {
        assertThatThrownBy(() -> bookService.updateBookTitle(ISBN, "   "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("title");

        verifyNoInteractions(bookRepository);
    }

    @Test
    void deleteBookByIsbn_withKnownIsbn_removesTheStoredBook() {
        Book stored = storedBook(UUID.randomUUID(), ISBN, "Clean Code");
        given(bookRepository.findByIsbn(ISBN)).willReturn(Optional.of(stored));

        bookService.deleteBookByIsbn(ISBN);

        verify(bookRepository).findByIsbn(ISBN);
        verify(bookRepository).delete(stored);
        verifyNoMoreInteractions(bookRepository);
    }

    @Test
    void deleteBookByIsbn_withUnknownIsbn_throwsResourceNotFoundAndRemovesNothing() {
        given(bookRepository.findByIsbn(ISBN)).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.deleteBookByIsbn(ISBN))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining(ISBN);

        verify(bookRepository).findByIsbn(ISBN);
        verify(bookRepository, never()).delete(any(Book.class));
        verifyNoMoreInteractions(bookRepository);
    }

    private Book storedBook(UUID id, String isbn, String title) {
        Book book = new Book();
        book.setId(id);
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor(AUTHOR);
        book.setCreatedAt(CREATED_AT);
        return book;
    }
}
