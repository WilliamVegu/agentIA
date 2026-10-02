package com.audit.library.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.audit.library.exception.ResourceNotFoundException;
import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import com.audit.library.model.entity.Book;
import com.audit.library.repository.BookRepository;
import com.audit.library.service.impl.BookServiceImpl;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class BookServiceTest {

    @Mock
    private BookRepository bookRepository;

    @InjectMocks
    private BookServiceImpl bookService;

    @Test
    void createBook_whenValidRequest_returnsCreatedBookAndPersists() {
        CreateBookRequest request = new CreateBookRequest("isbn-1", "Title", "Author");
        when(bookRepository.findByIsbn("isbn-1")).thenReturn(Optional.empty());
        when(bookRepository.save(any(Book.class))).thenAnswer(invocation -> invocation.getArgument(0));

        BookResponse response = bookService.createBook(request);

        assertThat(response.id()).isNotNull();
        assertThat(response.isbn()).isEqualTo("isbn-1");
        assertThat(response.title()).isEqualTo("Title");
        assertThat(response.author()).isEqualTo("Author");

        ArgumentCaptor<Book> captor = ArgumentCaptor.forClass(Book.class);
        verify(bookRepository).findByIsbn("isbn-1");
        verify(bookRepository).save(captor.capture());
        Book saved = captor.getValue();
        assertThat(saved.getId()).isEqualTo(response.id());
        assertThat(saved.getIsbn()).isEqualTo("isbn-1");
        assertThat(saved.getTitle()).isEqualTo("Title");
        assertThat(saved.getAuthor()).isEqualTo("Author");
    }

    @Test
    void createBook_whenIsbnAlreadyExists_throwsIllegalArgumentException() {
        CreateBookRequest request = new CreateBookRequest("isbn-1", "Title", "Author");
        Book existing = book(UUID.randomUUID(), "isbn-1", "Existing", "Author");
        when(bookRepository.findByIsbn("isbn-1")).thenReturn(Optional.of(existing));

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("already exists");

        verify(bookRepository).findByIsbn("isbn-1");
        verify(bookRepository, never()).save(any(Book.class));
    }

    @Test
    void createBook_whenTitleBlank_throwsIllegalArgumentException() {
        CreateBookRequest request = new CreateBookRequest("isbn-1", " ", "Author");

        assertThatThrownBy(() -> bookService.createBook(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Title cannot be empty");

        verifyNoInteractions(bookRepository);
    }

    @Test
    void getBookByIsbn_whenBookExists_returnsBook() {
        UUID id = UUID.randomUUID();
        Book book = book(id, "isbn-1", "Title", "Author");
        when(bookRepository.findByIsbn("isbn-1")).thenReturn(Optional.of(book));

        BookResponse response = bookService.getBookByIsbn("isbn-1");

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo("isbn-1");
        assertThat(response.title()).isEqualTo("Title");
        assertThat(response.author()).isEqualTo("Author");
        verify(bookRepository).findByIsbn("isbn-1");
    }

    @Test
    void getBookByIsbn_whenBookMissing_throwsResourceNotFoundException() {
        when(bookRepository.findByIsbn("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.getBookByIsbn("missing"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN missing");

        verify(bookRepository).findByIsbn("missing");
    }

    @Test
    void getAllBooks_returnsAllBooks() {
        Book book1 = book(UUID.randomUUID(), "isbn-1", "Title 1", "Author 1");
        Book book2 = book(UUID.randomUUID(), "isbn-2", "Title 2", "Author 2");
        when(bookRepository.findAll()).thenReturn(List.of(book1, book2));

        List<BookResponse> responses = bookService.getAllBooks();

        assertThat(responses).hasSize(2);
        assertThat(responses).extracting(BookResponse::isbn).containsExactly("isbn-1", "isbn-2");
        verify(bookRepository).findAll();
    }

    @Test
    void updateBookTitle_whenBookExists_updatesTitle() {
        UUID id = UUID.randomUUID();
        Book book = book(id, "isbn-1", "Old Title", "Author");
        when(bookRepository.findByIsbn("isbn-1")).thenReturn(Optional.of(book));
        when(bookRepository.save(book)).thenReturn(book);

        BookResponse response = bookService.updateBookTitle("isbn-1", "New Title");

        assertThat(response.id()).isEqualTo(id);
        assertThat(response.isbn()).isEqualTo("isbn-1");
        assertThat(response.title()).isEqualTo("New Title");
        assertThat(response.author()).isEqualTo("Author");
        assertThat(book.getTitle()).isEqualTo("New Title");
        verify(bookRepository).findByIsbn("isbn-1");
        verify(bookRepository).save(book);
    }

    @Test
    void updateBookTitle_whenNewTitleBlank_throwsIllegalArgumentException() {
        assertThatThrownBy(() -> bookService.updateBookTitle("isbn-1", " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Title cannot be empty");

        verifyNoInteractions(bookRepository);
    }

    @Test
    void updateBookTitle_whenBookMissing_throwsResourceNotFoundException() {
        when(bookRepository.findByIsbn("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.updateBookTitle("missing", "New Title"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN missing");

        verify(bookRepository).findByIsbn("missing");
    }

    @Test
    void deleteBookByIsbn_whenBookExists_deletesBook() {
        Book book = book(UUID.randomUUID(), "isbn-1", "Title", "Author");
        when(bookRepository.findByIsbn("isbn-1")).thenReturn(Optional.of(book));

        bookService.deleteBookByIsbn("isbn-1");

        verify(bookRepository).findByIsbn("isbn-1");
        verify(bookRepository).delete(book);
    }

    @Test
    void deleteBookByIsbn_whenBookMissing_throwsResourceNotFoundException() {
        when(bookRepository.findByIsbn("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> bookService.deleteBookByIsbn("missing"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Book not found with ISBN missing");

        verify(bookRepository).findByIsbn("missing");
        verify(bookRepository, never()).delete(any(Book.class));
    }

    private Book book(UUID id, String isbn, String title, String author) {
        Book book = new Book();
        book.setId(id);
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor(author);
        return book;
    }
}
