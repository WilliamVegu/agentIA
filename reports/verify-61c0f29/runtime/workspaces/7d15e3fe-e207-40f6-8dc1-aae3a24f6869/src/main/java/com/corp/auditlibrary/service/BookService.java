package com.corp.auditlibrary.service;

import com.corp.auditlibrary.model.dto.BookResponse;
import com.corp.auditlibrary.model.dto.CreateBookRequest;
import java.util.List;

public interface BookService {

    BookResponse createBook(CreateBookRequest request);

    BookResponse getBookByIsbn(String isbn);

    List<BookResponse> getAllBooks();

    BookResponse updateBookTitle(String isbn, String title);

    void deleteBookByIsbn(String isbn);
}
