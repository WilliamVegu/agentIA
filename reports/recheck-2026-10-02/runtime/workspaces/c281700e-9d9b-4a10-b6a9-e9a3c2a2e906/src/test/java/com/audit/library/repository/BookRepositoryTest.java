package com.audit.library.repository;

import com.audit.library.model.entity.Book;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Persistence slice for {@link BookRepository}. This is the only generated test layer that
 * runs a real {@code save()} against a database and reads the row back, which the unit tests
 * (repository substituted) and the web slice (service substituted) can never prove.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class BookRepositoryTest {

    @Autowired
    private BookRepository bookRepository;

    @Autowired
    private TestEntityManager testEntityManager;

    @Test
    void save_persistsBookAndFindByIdReadsRowBack() {
        Book book = newBook("978-0-13-468599-1", "Effective Java", "Joshua Bloch");

        Book saved = bookRepository.save(book);
        testEntityManager.flush();
        testEntityManager.clear();

        Optional<Book> reloaded = bookRepository.findById(saved.getId());

        assertThat(saved.getId()).isNotNull();
        assertThat(reloaded).isPresent();
        assertThat(reloaded.get().getId()).isEqualTo(saved.getId());
        assertThat(reloaded.get().getIsbn()).isEqualTo("978-0-13-468599-1");
        assertThat(reloaded.get().getTitle()).isEqualTo("Effective Java");
        assertThat(reloaded.get().getAuthor()).isEqualTo("Joshua Bloch");
    }

    @Test
    void findByIsbn_readsBackPersistedRow() {
        bookRepository.save(newBook("978-0-201-63361-0", "Design Patterns", "Erich Gamma"));
        testEntityManager.flush();
        testEntityManager.clear();

        Optional<Book> found = bookRepository.findByIsbn("978-0-201-63361-0");

        assertThat(found).isPresent();
        assertThat(found.get().getTitle()).isEqualTo("Design Patterns");
        assertThat(found.get().getAuthor()).isEqualTo("Erich Gamma");
    }

    @Test
    void existsByIsbn_reflectsPersistedRows() {
        bookRepository.save(newBook("978-0-13-468599-1", "Effective Java", "Joshua Bloch"));
        testEntityManager.flush();
        testEntityManager.clear();

        assertThat(bookRepository.existsByIsbn("978-0-13-468599-1")).isTrue();
        assertThat(bookRepository.existsByIsbn("978-0-00-000000-0")).isFalse();
    }

    @Test
    void findAll_returnsEveryPersistedBook() {
        bookRepository.save(newBook("978-0-13-468599-1", "Effective Java", "Joshua Bloch"));
        bookRepository.save(newBook("978-0-201-63361-0", "Design Patterns", "Erich Gamma"));
        testEntityManager.flush();
        testEntityManager.clear();

        List<Book> all = bookRepository.findAll();

        assertThat(all).hasSize(2);
        assertThat(all).extracting(Book::getIsbn)
                .containsExactlyInAnyOrder("978-0-13-468599-1", "978-0-201-63361-0");
    }

    private static Book newBook(String isbn, String title, String author) {
        Book book = new Book();
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor(author);
        return book;
    }
}
