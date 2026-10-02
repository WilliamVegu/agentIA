package com.corp.auditlibrary.model.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "books")
public class Book {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @NotNull
    private UUID id;

    @NotBlank
    @Size(min = 10, max = 17)
    @Pattern(regexp = "^(?:\\d{9}[\\dXx]|\\d{13})$")
    @Column(name = "isbn", nullable = false, unique = true, length = 17)
    private String isbn;

    @NotBlank
    @Size(min = 1, max = 255)
    @Column(name = "title", nullable = false, length = 255)
    private String title;

    @NotBlank
    @Size(min = 1, max = 255)
    @Column(name = "author", nullable = false, length = 255)
    private String author;

    @NotNull
    @PastOrPresent
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PastOrPresent
    @Column(name = "updated_at", nullable = true)
    private Instant updatedAt;

    public Book() {
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getIsbn() {
        return isbn;
    }

    public void setIsbn(String isbn) {
        this.isbn = isbn;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getAuthor() {
        return author;
    }

    public void setAuthor(String author) {
        this.author = author;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Book book)) return false;
        return id != null && id.equals(book.id);
    }

    @Override
    public int hashCode() {
        return id != null ? id.hashCode() : 0;
    }
}
