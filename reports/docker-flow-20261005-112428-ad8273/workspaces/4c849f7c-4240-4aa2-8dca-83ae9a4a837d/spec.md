# Feature Specification: flow-inventory-service

Build a small Java 21 Spring Boot 3 REST microservice using Maven and PostgreSQL.
Service name flow-inventory-service, package com.example.flowinventory. Use one entity Item:
id Long generated identity, name String required and nonblank, quantity Integer required and minimum 0.
Provide CRUD at /api/v1/items: POST returns 201 with the persisted object and id, GET list and GET by id,
PUT updates name and quantity, DELETE returns 204. Return 404 when item does not exist; invalid input returns 400.
Use Controller, Service, Repository and JPA Entity layers, Java record request/response DTOs,
Jakarta validation and RestControllerAdvice. PostgreSQL-compatible SQL and no sample seed data.
Include meaningful Mockito unit tests and web validation tests. No external integrations, authentication,
messaging, Lombok, MapStruct, extra entities or modules. Maven single module, no Gradle.
Acceptance: create an item, read it, update quantity, preserve it after restart, delete it and reject blank name.
