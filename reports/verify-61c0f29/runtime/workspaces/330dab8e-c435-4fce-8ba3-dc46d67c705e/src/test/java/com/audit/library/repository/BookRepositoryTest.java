package com.audit.library.repository;

import com.audit.library.model.entity.Book;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class BookRepositoryTest {

    @Autowired
    private BookRepository bookRepository;

    @Test
    void saveAndFindByIsbn_persistsAndReadsBackRealRow() {
        UUID id = UUID.randomUUID();
        Book book = new Book();
        book.setId(id);
        book.setIsbn("9783161484100");
        book.setTitle("Clean Code");
        book.setAuthor("Robert C. Martin");
        book.setCreatedAt(LocalDateTime.now().minusDays(1));

        bookRepository.saveAndFlush(book);

        Optional<Book> found = bookRepository.findByIsbn("9783161484100");

        assertThat(found).isPresent();
        assertThat(found.get().getId()).isEqualTo(id);
        assertThat(found.get().getIsbn()).isEqualTo("9783161484100");
        assertThat(found.get().getTitle()).isEqualTo("Clean Code");
        assertThat(found.get().getAuthor()).isEqualTo("Robert C. Martin");
        assertThat(found.get().getCreatedAt()).isNotNull();
        assertThat(bookRepository.existsByIsbn("9783161484100")).isTrue();
    }
}