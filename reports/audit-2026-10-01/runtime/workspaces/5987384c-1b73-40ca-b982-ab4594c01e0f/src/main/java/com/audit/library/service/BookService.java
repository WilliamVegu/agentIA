package com.audit.library.service;

import com.audit.library.model.dto.BookResponse;
import com.audit.library.model.dto.CreateBookRequest;
import java.util.List;

public interface BookService {

    BookResponse createBook(CreateBookRequest request);

    BookResponse getBookByIsbn(String isbn);

    List<BookResponse> getAllBooks();

    BookResponse updateBookTitle(String isbn, String newTitle);

    void deleteBookByIsbn(String isbn);
}
