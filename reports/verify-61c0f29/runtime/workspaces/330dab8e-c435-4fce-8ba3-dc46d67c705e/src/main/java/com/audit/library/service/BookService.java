package com.audit.library.service;

import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;

import java.util.List;

public interface BookService {

    BookResponse create(CreateBookRequest request);

    BookResponse findByIsbn(String isbn);

    List<BookResponse> findAll();

    BookResponse updateTitle(String isbn, String title);

    void deleteByIsbn(String isbn);
}
