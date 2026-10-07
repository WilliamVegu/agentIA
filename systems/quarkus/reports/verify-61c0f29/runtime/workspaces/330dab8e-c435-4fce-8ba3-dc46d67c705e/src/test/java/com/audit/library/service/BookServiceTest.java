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

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookServiceTest {

    @Mock
    private BookRepository bookRepository;

    @InjectMocks
    private BookServiceImpl bookService;

    @Test
    void create_persistsNewBookWithGeneratedIdAndTimestamp_whenIsbnIsUnique() {
        CreateBookRequest request = new CreateBookRequest(
                "9783161484100", "Clean Code", "Robert C. Martin");
        when(bookRepository.existsByIsbn("9783161484100")).thenReturn(false);
        when(bookRepository.save(any(Book.class))).thenAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.create(request);

        assertThat(response).isNotNull();
        assertThat(response.id()).isNotNull();
        assertThat(response.isbn()).isEqualTo("9783161484100");
        assertThat(response.title()).isEqualTo("Clean Code");
        assertThat(response.author()).isEqualTo("Robert C. Martin");
        assertThat(response.createdAt()).isNotNull();
        assertThat(response.updatedAt()).isNull();

        ArgumentCaptor<Book> bookCaptor = ArgumentCaptor.forClass(Book.class);
        verify(bookRepository).existsByIsbn("9783161484100");
        verify(bookRepository).save(bookCaptor.capture());
        Book persisted = bookCaptor.getValue();
        assertThat(persisted.getId()).isEqualTo(response.id());
        assertThat(persisted.getIsbn()).isEqualTo("9783161484100");
        assertThat(persisted.getTitle()).isEqualTo("Clean Code");
        assertThat(persisted.getAuthor()).isEqualTo("Robert C. Martin");
        assertThat(persisted.getCreatedAt()).isNotNull();
    }

    @Test
    void create_throwsIllegalStateException_whenIsbnAlreadyExists() {
        CreateBookRequest request = new CreateBookRequest(
                "9783161484100", "Another Title", "Another Author");
        when(bookRepository.existsByIsbn("9783161484100")).thenReturn(true);

        assertThatThrownBy(() -> bookService.create(request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("9783161484100")
                .hasMessageContaining("already exists");

        verify(bookRepository).existsByIsbn("9783161484100");
        verify(bookRepository, never()).save(any(Book.class));
    }

    @Test
    void findByIsbn_returnsBookRepresentation_whenBookExists() {
        UUID id = UUID.randomUUID();
        LocalDateTime createdAt = LocalDateTime.now().minusDays(1);
        Book book = book(id, "9783161484100", "Clean Code", "Robert C. Martin", createdAt);
        when(bookRepository.findByIsbn("9783161484100")).thenReturn(Optional.of(book));

        BookResponse response = bookService.findByIsbn("9783161484100");

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo("9783161484100");
        assertThat(response.title()).isEqualTo("Clean Code");
        assertThat(response.author()).isEqualTo("Robert C. Martin");
        assertThat(response.createdAt()).isEqualTo(createdAt);
        assertThat(response.updatedAt()).isNull();
        verify(bookRepository).findByIsbn("9783161484100");
    }

    @Test
    void findByIsbn_throwsResourceNotFoundException_whenBookMissing() {
        when(bookRepository.findByIsbn("9780000000000")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.findByIsbn("9780000000000"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("9780000000000");

        verify(bookRepository).findByIsbn("9780000000000");
    }

    @Test
    void findAll_returnsAllBooksAsRepresentations() {
        Book first = book(UUID.randomUUID(), "9783161484100", "Clean Code", "Robert C. Martin",
                LocalDateTime.now().minusDays(1));
        Book second = book(UUID.randomUUID(), "9780132350884", "Effective Java", "Joshua Bloch",
                LocalDateTime.now().minusDays(2));
        when(bookRepository.findAll()).thenReturn(List.of(first, second));

        List<BookResponse> responses = bookService.findAll();

        assertThat(responses).hasSize(2);
        assertThat(responses).extracting(BookResponse::isbn)
                .containsExactly("9783161484100", "9780132350884");
        assertThat(responses).extracting(BookResponse::title)
                .containsExactly("Clean Code", "Effective Java");
        verify(bookRepository).findAll();
    }

    @Test
    void updateTitle_updatesTitleAndUpdatedAtAndPreservesIsbnAndAuthor_whenBookExists() {
        UUID id = UUID.randomUUID();
        Book book = book(id, "9783161484100", "Clean Code", "Robert C. Martin",
                LocalDateTime.now().minusDays(1));
        when(bookRepository.findByIsbn("9783161484100")).thenReturn(Optional.of(book));
        when(bookRepository.save(any(Book.class))).thenAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.updateTitle(
                "9783161484100", "Clean Code: A Handbook of Agile Software Craftsmanship");

        assertThat(response.title()).isEqualTo("Clean Code: A Handbook of Agile Software Craftsmanship");
        assertThat(response.isbn()).isEqualTo("9783161484100");
        assertThat(response.author()).isEqualTo("Robert C. Martin");
        assertThat(response.updatedAt()).isNotNull();
        verify(bookRepository).findByIsbn("9783161484100");
        verify(bookRepository).save(book);
    }

    @Test
    void updateTitle_throwsResourceNotFoundException_whenBookMissing() {
        when(bookRepository.findByIsbn("9783161484100")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.updateTitle("9783161484100", "Valid New Title"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("9783161484100");

        verify(bookRepository).findByIsbn("9783161484100");
        verify(bookRepository, never()).save(any(Book.class));
    }

    @Test
    void deleteByIsbn_deletesBook_whenBookExists() {
        Book book = book(UUID.randomUUID(), "9783161484100", "Clean Code", "Robert C. Martin",
                LocalDateTime.now().minusDays(1));
        when(bookRepository.findByIsbn("9783161484100")).thenReturn(Optional.of(book));

        bookService.deleteByIsbn("9783161484100");

        verify(bookRepository).findByIsbn("9783161484100");
        verify(bookRepository).delete(book);
    }

    @Test
    void deleteByIsbn_throwsResourceNotFoundException_whenBookMissing() {
        when(bookRepository.findByIsbn("9783161484100")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.deleteByIsbn("9783161484100"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("9783161484100");

        verify(bookRepository).findByIsbn("9783161484100");
        verify(bookRepository, never()).delete(any(Book.class));
    }

    private static Book book(UUID id, String isbn, String title, String author, LocalDateTime createdAt) {
        Book book = new Book();
        book.setId(id);
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor(author);
        book.setCreatedAt(createdAt);
        return book;
    }
}