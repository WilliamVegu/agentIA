package com.audit.library.service;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.impl.BookServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

/**
 * Mockito-backed unit tests for {@link BookServiceImpl}. The repository is substituted
 * with a mock injected through the constructor, so no persistence provider runs here:
 * this layer verifies business rules and the interactions the implementation must perform.
 */
@ExtendWith(MockitoExtension.class)
class BookServiceTest {

    @Mock
    private BookRepository bookRepository;

    private BookServiceImpl bookService;

    @BeforeEach
    void setUp() {
        bookService = new BookServiceImpl(bookRepository);
    }

    // AC-1.1: valid book details are registered and returned.
    @Test
    void createBook_savesBookAndReturnsCreatedDetails_whenRequestIsValid() {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        given(bookRepository.existsByIsbn("978-0-13-468599-1")).willReturn(false);
        given(bookRepository.save(any(Book.class))).willAnswer(invocation -> {
            Book toSave = invocation.getArgument(0);
            toSave.setId(UUID.randomUUID());
            return toSave;
        });

        BookResponse response = bookService.createBook(request);

        assertThat(response.id()).isNotNull();
        assertThat(response.isbn()).isEqualTo("978-0-13-468599-1");
        assertThat(response.title()).isEqualTo("Effective Java");
        assertThat(response.author()).isEqualTo("Joshua Bloch");

        ArgumentCaptor<Book> savedBook = ArgumentCaptor.forClass(Book.class);
        verify(bookRepository).save(savedBook.capture());
        assertThat(savedBook.getValue().getIsbn()).isEqualTo("978-0-13-468599-1");
        assertThat(savedBook.getValue().getTitle()).isEqualTo("Effective Java");
        assertThat(savedBook.getValue().getAuthor()).isEqualTo("Joshua Bloch");
        verify(bookRepository).existsByIsbn("978-0-13-468599-1");
    }

    // AC-1.2: a duplicate ISBN is rejected as a business-rule violation.
    @Test
    void createBook_throwsIllegalArgumentException_whenIsbnAlreadyExists() {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        given(bookRepository.existsByIsbn("978-0-13-468599-1")).willReturn(true);

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("978-0-13-468599-1");

        verify(bookRepository, never()).save(any(Book.class));
    }

    // AC-1.3: a blank title is rejected before any persistence interaction.
    @Test
    void createBook_throwsIllegalArgumentException_whenTitleIsBlank() {
        CreateBookRequest request = new CreateBookRequest("978-0-13-468599-1", "   ", "Joshua Bloch");

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Title cannot be empty");

        verifyNoInteractions(bookRepository);
    }

    // AC-2.1: updating the title of an existing book returns the updated representation.
    @Test
    void updateTitle_savesNewTitleAndReturnsUpdatedBook_whenBookExists() {
        UUID id = UUID.randomUUID();
        Book existing = new Book(id, "978-0-13-468599-1", "Old Title", "Joshua Bloch");
        given(bookRepository.findByIsbn("978-0-13-468599-1")).willReturn(Optional.of(existing));
        given(bookRepository.save(existing)).willReturn(existing);

        BookResponse response = bookService.updateTitle("978-0-13-468599-1", "Effective Java, 3rd Edition");

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo("978-0-13-468599-1");
        assertThat(response.title()).isEqualTo("Effective Java, 3rd Edition");
        verify(bookRepository).save(existing);
    }

    // AC-2.2: updating an unknown ISBN raises the dedicated not-found exception.
    @Test
    void updateTitle_throwsResourceNotFoundException_whenBookDoesNotExist() {
        given(bookRepository.findByIsbn("978-0-00-000000-0")).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.updateTitle("978-0-00-000000-0", "New Title"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("978-0-00-000000-0");

        verify(bookRepository, never()).save(any(Book.class));
    }

    // AC-2.3: an empty replacement title is rejected as a business-rule violation.
    @Test
    void updateTitle_throwsIllegalArgumentException_whenNewTitleIsBlank() {
        UUID id = UUID.randomUUID();
        Book existing = new Book(id, "978-0-13-468599-1", "Old Title", "Joshua Bloch");
        given(bookRepository.findByIsbn("978-0-13-468599-1")).willReturn(Optional.of(existing));

        assertThatThrownBy(() -> bookService.updateTitle("978-0-13-468599-1", "  "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Title cannot be empty");

        verify(bookRepository, never()).save(any(Book.class));
    }

    // AC-3.1: retrieving an existing book by ISBN returns its details.
    @Test
    void getBookByIsbn_returnsBookDetails_whenBookExists() {
        UUID id = UUID.randomUUID();
        Book stored = new Book(id, "978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        given(bookRepository.findByIsbn("978-0-13-468599-1")).willReturn(Optional.of(stored));

        BookResponse response = bookService.getBookByIsbn("978-0-13-468599-1");

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo("978-0-13-468599-1");
        assertThat(response.title()).isEqualTo("Effective Java");
        assertThat(response.author()).isEqualTo("Joshua Bloch");
        verify(bookRepository).findByIsbn("978-0-13-468599-1");
    }

    // AC-3.2: retrieving an unknown ISBN raises the dedicated not-found exception.
    @Test
    void getBookByIsbn_throwsResourceNotFoundException_whenBookDoesNotExist() {
        given(bookRepository.findByIsbn("978-0-00-000000-0")).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.getBookByIsbn("978-0-00-000000-0"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("978-0-00-000000-0");
    }

    // Collection read: the full catalog is mapped from persisted rows.
    @Test
    void getAllBooks_returnsAllBooks_whenCatalogHasEntries() {
        Book first = new Book(UUID.randomUUID(), "978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        Book second = new Book(UUID.randomUUID(), "978-0-201-63361-0", "Design Patterns", "Erich Gamma");
        given(bookRepository.findAll()).willReturn(List.of(first, second));

        List<BookResponse> result = bookService.getAllBooks();

        assertThat(result).hasSize(2);
        assertThat(result).extracting(BookResponse::isbn)
                .containsExactly("978-0-13-468599-1", "978-0-201-63361-0");
    }

    // Collection read: an empty catalog yields an empty (not null) result.
    @Test
    void getAllBooks_returnsEmptyList_whenCatalogIsEmpty() {
        given(bookRepository.findAll()).willReturn(List.of());

        List<BookResponse> result = bookService.getAllBooks();

        assertThat(result).isEmpty();
    }

    // AC-4.1: deleting an existing book removes the persisted row.
    @Test
    void deleteBookByIsbn_removesBook_whenBookExists() {
        Book stored = new Book(UUID.randomUUID(), "978-0-13-468599-1", "Effective Java", "Joshua Bloch");
        given(bookRepository.findByIsbn("978-0-13-468599-1")).willReturn(Optional.of(stored));

        bookService.deleteBookByIsbn("978-0-13-468599-1");

        verify(bookRepository).findByIsbn("978-0-13-468599-1");
        verify(bookRepository).delete(stored);
    }

    // AC-4.2: deleting an unknown ISBN raises the dedicated not-found exception.
    @Test
    void deleteBookByIsbn_throwsResourceNotFoundException_whenBookDoesNotExist() {
        given(bookRepository.findByIsbn("978-0-00-000000-0")).willReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.deleteBookByIsbn("978-0-00-000000-0"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("978-0-00-000000-0");

        verify(bookRepository, never()).delete(any(Book.class));
    }
}
