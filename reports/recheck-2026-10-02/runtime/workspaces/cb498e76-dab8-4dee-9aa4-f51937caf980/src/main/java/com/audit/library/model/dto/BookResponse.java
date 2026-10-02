package com.audit.library.model.dto;

import com.audit.library.model.entity.Book;

import java.util.UUID;

public record BookResponse(
        UUID id,
        String isbn,
        String title,
        String author) {

    public static BookResponse from(Book entity) {
        if (entity == null) {
            return null;
        }
        return new BookResponse(
                entity.getId(),
                entity.getIsbn(),
                entity.getTitle(),
                entity.getAuthor());
    }
}
