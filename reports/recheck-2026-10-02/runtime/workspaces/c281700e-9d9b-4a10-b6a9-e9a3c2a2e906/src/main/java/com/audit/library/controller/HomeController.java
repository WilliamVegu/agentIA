package com.audit.library.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class HomeController {

    @GetMapping("/")
    public ResponseEntity<ServiceCatalog> home() {
        ServiceCatalog catalog = new ServiceCatalog(
                "audit-library",
                "UP",
                List.of(
                        new Endpoint("GET", "/", "Service catalogue"),
                        new Endpoint("POST", "/api/v1/books", "Create a book"),
                        new Endpoint("GET", "/api/v1/books", "List all books"),
                        new Endpoint("GET", "/api/v1/books/{isbn}", "Get a book by ISBN"),
                        new Endpoint("PATCH", "/api/v1/books/{isbn}", "Update a book title by ISBN"),
                        new Endpoint("DELETE", "/api/v1/books/{isbn}", "Delete a book by ISBN")
                )
        );
        return ResponseEntity.ok(catalog);
    }

    public record ServiceCatalog(String service, String status, List<Endpoint> endpoints) {
    }

    public record Endpoint(String method, String path, String description) {
    }
}
