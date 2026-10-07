package com.audit.library.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.List;

/**
 * Root-path service catalogue. Lets an operator confirm at a glance that the service is
 * running and which endpoints it exposes.
 */
@RestController
public class HomeController {

    private static final String SERVICE_NAME = "audit-library";
    private static final String SERVICE_STATUS = "UP";

    @GetMapping("/")
    public ResponseEntity<ServiceCatalogue> catalogue() {
        List<EndpointDescriptor> endpoints = List.of(
                new EndpointDescriptor("GET", "/api/v1/books", "List all books"),
                new EndpointDescriptor("POST", "/api/v1/books", "Register a new book"),
                new EndpointDescriptor("GET", "/api/v1/books/{isbn}", "Retrieve a book by ISBN"),
                new EndpointDescriptor("PUT", "/api/v1/books/{isbn}", "Update the title of a book"),
                new EndpointDescriptor("DELETE", "/api/v1/books/{isbn}", "Delete a book by ISBN")
        );
        ServiceCatalogue catalogue = new ServiceCatalogue(
                SERVICE_NAME, SERVICE_STATUS, Instant.now(), endpoints);
        return ResponseEntity.ok(catalogue);
    }

    public record ServiceCatalogue(
            String service,
            String status,
            Instant timestamp,
            List<EndpointDescriptor> endpoints
    ) {
    }

    public record EndpointDescriptor(String method, String path, String description) {
    }
}
