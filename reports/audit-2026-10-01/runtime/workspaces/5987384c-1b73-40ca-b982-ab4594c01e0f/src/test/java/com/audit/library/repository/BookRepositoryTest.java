package com.audit.library.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.audit.library.model.entity.Book;
import java.util.Optional;
import java.util.UUID;
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
    void saveAndReadBackBook_persistsRow() {
        UUID id = UUID.randomUUID();
        Book book = new Book();
        book.setId(id);
        book.setIsbn("isbn-1");
        book.setTitle("Title");
        book.setAuthor("Author");

        Book saved = bookRepository.save(book);
        entityManager.flush();
        entityManager.clear();

        Optional<Book> found = bookRepository.findById(saved.getId());

        assertThat(found).isPresent();
        assertThat(found.get().getId()).isEqualTo(id);
        assertThat(found.get().getIsbn()).isEqualTo("isbn-1");
        assertThat(found.get().getTitle()).isEqualTo("Title");
        assertThat(found.get().getAuthor()).isEqualTo("Author");
    }

    @Test
    void findByIsbn_whenSaved_returnsBook() {
        UUID id = UUID.randomUUID();
        Book book = new Book();
        book.setId(id);
        book.setIsbn("isbn-2");
        book.setTitle("Title 2");
        book.setAuthor("Author 2");

        bookRepository.save(book);
        entityManager.flush();
        entityManager.clear();

        Optional<Book> found = bookRepository.findByIsbn("isbn-2");

        assertThat(found).isPresent();
        assertThat(found.get().getId()).isEqualTo(id);
        assertThat(found.get().getTitle()).isEqualTo("Title 2");
    }
}
