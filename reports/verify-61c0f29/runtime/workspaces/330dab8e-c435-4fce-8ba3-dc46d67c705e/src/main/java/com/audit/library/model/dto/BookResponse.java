package com.audit.library.model.dto;

import com.audit.library.model.entity.Book;

import java.time.LocalDateTime;
import java.util.UUID;

public record BookResponse(
        UUID id,
        String isbn,
        String title,
        String author,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {

    public static BookResponse from(Book book) {
        if (book == null) {
            return null;
        }
        return new BookResponse(
                book.getId(),
                book.getIsbn(),
                book.getTitle(),
                book.getAuthor(),
                book.getCreatedAt(),
                book.getUpdatedAt()
        );
    }
}
