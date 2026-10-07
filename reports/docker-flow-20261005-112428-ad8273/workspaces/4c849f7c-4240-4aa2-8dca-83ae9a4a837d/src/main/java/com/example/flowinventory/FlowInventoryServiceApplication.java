package com.example.flowinventory;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point for the flow-inventory-service application.
 * Component scanning is rooted at the base package so that every layer
 * (controller, service, repository, model) generated later is discovered.
 */
@SpringBootApplication
public class FlowInventoryServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(FlowInventoryServiceApplication.class, args);
    }
}
