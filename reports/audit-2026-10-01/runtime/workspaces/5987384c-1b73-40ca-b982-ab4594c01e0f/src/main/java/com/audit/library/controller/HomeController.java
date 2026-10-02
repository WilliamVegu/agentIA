package com.audit.library.controller;

import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HomeController {

    @GetMapping(value = "/", produces = MediaType.APPLICATION_JSON_VALUE)
    public ServiceCatalog home() {
        return new ServiceCatalog(
                "audit-library",
                "UP",
                List.of(
                        new Endpoint("POST", "/api/v1/books", "Create a book"),
                        new Endpoint("GET", "/api/v1/books", "List all books"),
                        new Endpoint("GET", "/api/v1/books/{isbn}", "Get a book by ISBN"),
                        new Endpoint("PUT", "/api/v1/books/{isbn}", "Update a book title by ISBN"),
                        new Endpoint("DELETE", "/api/v1/books/{isbn}", "Delete a book by ISBN")
                )
        );
    }

    public record ServiceCatalog(
            String service,
            String status,
            List<Endpoint> endpoints
    ) {
    }

    public record Endpoint(
            String method,
            String path,
            String description
    ) {
    }
}
