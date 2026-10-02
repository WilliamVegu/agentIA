package com.corp.auditlibrary.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.corp.auditlibrary.model.entity.Book;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

@DataJpaTest
class BookRepositoryTest {

    @Autowired
    private BookRepository bookRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void save_persistsBookAndFindByIsbnReadsTheStoredRowBack() {
        Book saved = bookRepository.save(newBook("9783161484100", "Clean Code"));
        entityManager.flush();
        entityManager.clear();

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getCreatedAt()).isNotNull();

        Book reloaded = bookRepository.findByIsbn("9783161484100").orElseThrow();

        assertThat(reloaded.getId()).isEqualTo(saved.getId());
        assertThat(reloaded.getIsbn()).isEqualTo("9783161484100");
        assertThat(reloaded.getTitle()).isEqualTo("Clean Code");
        assertThat(reloaded.getAuthor()).isEqualTo("Robert C. Martin");
        assertThat(reloaded.getUpdatedAt()).isNull();
        assertThat(bookRepository.existsByIsbn("9783161484100")).isTrue();
    }

    @Test
    void save_thenFindAllReadsEveryPersistedRowBack() {
        Book first = bookRepository.save(newBook("9783161484100", "Clean Code"));
        Book second = bookRepository.save(newBook("9780132350884", "Clean Architecture"));
        entityManager.flush();
        entityManager.clear();

        List<Book> all = bookRepository.findAll();

        assertThat(all).hasSize(2);
        assertThat(all).extracting(Book::getIsbn)
                .containsExactlyInAnyOrder("9783161484100", "9780132350884");
        assertThat(all).extracting(Book::getId)
                .containsExactlyInAnyOrder(first.getId(), second.getId());
    }

    private Book newBook(String isbn, String title) {
        Book book = new Book();
        book.setIsbn(isbn);
        book.setTitle(title);
        book.setAuthor("Robert C. Martin");
        book.setCreatedAt(Instant.now());
        return book;
    }
}
