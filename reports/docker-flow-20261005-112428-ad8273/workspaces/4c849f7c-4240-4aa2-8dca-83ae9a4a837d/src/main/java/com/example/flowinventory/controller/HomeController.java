package com.example.flowinventory.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Root-path service catalogue. Lets an operator confirm at a glance that the
 * service is running and which endpoints it exposes.
 */
@RestController
public class HomeController {

    @GetMapping("/")
    public ServiceCatalogue index() {
        return new ServiceCatalogue(
                "flow-inventory-service",
                "UP",
                List.of(
                        "POST /api/v1/items",
                        "GET /api/v1/items",
                        "GET /api/v1/items/{id}",
                        "PUT /api/v1/items/{id}",
                        "DELETE /api/v1/items/{id}"
                ));
    }

    public record ServiceCatalogue(String service, String status, List<String> endpoints) {
    }
}
