package com.audit.library.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class HomeController {

    private static final String SERVICE_NAME = "audit-library";

    @GetMapping("/")
    public ServiceCatalog home() {
        return new ServiceCatalog(
                SERVICE_NAME,
                "UP",
                List.of(
                        new Endpoint("POST", "/api/v1/books", "Create a book"),
                        new Endpoint("GET", "/api/v1/books", "List all books"),
                        new Endpoint("GET", "/api/v1/books/{isbn}", "Get a book by ISBN"),
                        new Endpoint("PATCH", "/api/v1/books/{isbn}/title", "Update book title by ISBN"),
                        new Endpoint("DELETE", "/api/v1/books/{isbn}", "Delete a book by ISBN")
                ));
    }

    public record ServiceCatalog(String service, String status, List<Endpoint> endpoints) {
    }

    public record Endpoint(String method, String path, String description) {
    }
}
