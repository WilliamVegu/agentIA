package com.corp.auditlibrary.controller;

import java.time.Instant;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HomeController {

    private static final String SERVICE_NAME = "audit-library";

    @GetMapping("/")
    public ServiceCatalog catalog() {
        return new ServiceCatalog(
                SERVICE_NAME,
                "UP",
                Instant.now(),
                List.of(
                        new Endpoint("POST", "/api/v1/books", "Register a new book"),
                        new Endpoint("GET", "/api/v1/books", "List all books"),
                        new Endpoint("GET", "/api/v1/books/{isbn}", "Retrieve a book by its ISBN"),
                        new Endpoint("PUT", "/api/v1/books/{isbn}", "Update the title of a book"),
                        new Endpoint("DELETE", "/api/v1/books/{isbn}", "Delete a book by its ISBN"),
                        new Endpoint("POST", "/api/v1/catalog-audit-entries", "Record a catalog audit entry"),
                        new Endpoint("GET", "/api/v1/catalog-audit-entries", "List all catalog audit entries"),
                        new Endpoint("GET", "/api/v1/catalog-audit-entries/{id}", "Retrieve a catalog audit entry by id"),
                        new Endpoint("DELETE", "/api/v1/catalog-audit-entries/{id}", "Delete a catalog audit entry by id")));
    }

    public record ServiceCatalog(
            String service,
            String status,
            Instant timestamp,
            List<Endpoint> endpoints) {
    }

    public record Endpoint(
            String method,
            String path,
            String description) {
    }
}
