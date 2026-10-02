package com.audit.library.repository;

import com.audit.library.model.entity.Book;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class BookRepositoryTest {

    @Autowired
    private BookRepository bookRepository;

    @Test
    void save_persistsBookAndFindByIsbnReadsItBack() {
        UUID id = UUID.randomUUID();
        Book book = new Book(id, "978-0-123456-47-2", "Effective Java", "Joshua Bloch");

        Book saved = bookRepository.save(book);
        bookRepository.flush();

        Optional<Book> byIsbn = bookRepository.findByIsbn("978-0-123456-47-2");
        Optional<Book> byId = bookRepository.findById(id);

        assertThat(saved.getId()).isEqualTo(id);
        assertThat(byIsbn).isPresent();
        assertThat(byIsbn.get().getId()).isEqualTo(id);
        assertThat(byIsbn.get().getIsbn()).isEqualTo("978-0-123456-47-2");
        assertThat(byIsbn.get().getTitle()).isEqualTo("Effective Java");
        assertThat(byIsbn.get().getAuthor()).isEqualTo("Joshua Bloch");
        assertThat(byId).isPresent();
        assertThat(byId.get().getTitle()).isEqualTo("Effective Java");
    }
}
