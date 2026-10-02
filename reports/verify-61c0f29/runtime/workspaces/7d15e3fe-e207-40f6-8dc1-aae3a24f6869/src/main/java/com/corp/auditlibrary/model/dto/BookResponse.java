package com.corp.auditlibrary.model.dto;

import com.corp.auditlibrary.model.entity.Book;
import java.time.Instant;
import java.util.UUID;

public record BookResponse(
        UUID id,
        String isbn,
        String title,
        String author,
        Instant createdAt,
        Instant updatedAt
) {
    public static BookResponse fromEntity(Book book) {
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
