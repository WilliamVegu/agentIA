# Feature Specification: Audit Library

**Feature Branch**: `audit-library`

**Created**: 2026-10-02

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - register a new book with a unique ISBN, title and author (Priority: P1)

As a Librarian, I want register a new book with a unique ISBN, title and author, so that the library catalog is kept accurate and no duplicate titles can be registered under the same ISBN.

**Acceptance Scenarios**:

1. **Given** the library catalog does not contain any book with ISBN '9783161484100', **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "Clean Code", "author": "Robert C. Martin" }, **Then** the service persists the book with a generated UUID and createdAt timestamp and responds with HTTP 201 Created, a Location header '/api/v1/books/9783161484100' and the created representation including isbn, title and author.
2. **Given** a book with ISBN '9783161484100' already exists in the catalog, **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "Another Title", "author": "Another Author" }, **Then** the service does not create a second record and responds with HTTP 409 Conflict and errorCode 'BOOK_ISBN_DUPLICATE'.
3. **Given** the library catalog is available and the client is authenticated as Librarian, **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "   ", "author": "Robert C. Martin" }, **Then** the service rejects the request with HTTP 400 Bad Request and a field-level validation error indicating that 'title' must not be blank.
4. **Given** the library catalog is available, **When** the Librarian sends POST /api/v1/books with body { "isbn": "ABC-123", "title": "Clean Code", "author": "Robert C. Martin" }, **Then** the service responds with HTTP 400 Bad Request and a field-level validation error indicating that 'isbn' does not match the expected format.

---

### User Story 2 - update the title of an existing book identified by its ISBN (Priority: P2)

As a Librarian, I want update the title of an existing book identified by its ISBN, so that corrected or refined metadata is reflected in the catalog without changing the book identity.

**Acceptance Scenarios**:

1. **Given** a book with ISBN '9783161484100' and title 'Clean Code' exists in the catalog, **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "Clean Code: A Handbook of Agile Software Craftsmanship" }, **Then** the service updates the stored title, sets updatedAt, leaves isbn and author unchanged and responds with HTTP 200 OK containing the updated representation.
2. **Given** no book with ISBN '9783161484100' exists in the catalog, **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "Valid New Title" }, **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND', and no record is created.
3. **Given** a book with ISBN '9783161484100' exists in the catalog, **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "" }, **Then** the service rejects the request with HTTP 400 Bad Request, the stored title remains 'Clean Code' and no updatedAt change is persisted.

---

### User Story 3 - retrieve a book by its ISBN to verify catalog integrity (Priority: P3)

As a Auditor, I want retrieve a book by its ISBN to verify catalog integrity, so that catalog data can be inspected and audited without modifying any record.

**Acceptance Scenarios**:

1. **Given** a book with ISBN '9783161484100', title 'Clean Code' and author 'Robert C. Martin' exists in the catalog, **When** the Auditor sends GET /api/v1/books/9783161484100, **Then** the service responds with HTTP 200 OK and the full book representation including id, isbn, title, author and createdAt.
2. **Given** no book with ISBN '9780000000000' exists in the catalog, **When** the Auditor sends GET /api/v1/books/9780000000000, **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND'.
3. **Given** the catalog is available and read access is granted, **When** the Auditor sends GET /api/v1/books/not-an-isbn, **Then** the service responds with HTTP 400 Bad Request and a validation error indicating that the ISBN format is invalid.

---

### User Story 4 - delete a book from the catalog by its ISBN (Priority: P2)

As a Librarian, I want delete a book from the catalog by its ISBN, so that obsolete or incorrectly registered titles can be removed so the catalog stays reliable.

**Acceptance Scenarios**:

1. **Given** a book with ISBN '9783161484100' exists in the catalog, **When** the Librarian sends DELETE /api/v1/books/9783161484100, **Then** the service removes the record and responds with HTTP 204 No Content, and a subsequent GET for that ISBN returns HTTP 404.
2. **Given** no book with ISBN '9783161484100' exists in the catalog, **When** the Librarian sends DELETE /api/v1/books/9783161484100, **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND' and the catalog remains unchanged.
3. **Given** the catalog is available, **When** the Librarian sends DELETE /api/v1/books/12345, **Then** the service responds with HTTP 400 Bad Request and a validation error indicating that the ISBN format is invalid.

---

### Assumptions & Edge Cases

- The service is a stateless REST microservice implemented with Java 21 and Spring Boot 3 (spring-boot-starter-web, spring-boot-starter-validation, spring-boot-starter-data-jpa).
- H2 is used as the runtime/test datastore (in-memory for automated tests, file/embedded mode otherwise); no external database migration tool is strictly required, but Flyway/Liquibase may be added later.
- The ISBN is the natural business key used for retrieval, update and deletion; the surrogate primary key is a server-generated UUID (UUID.randomUUID()) and is never supplied by clients.
- Duplicate ISBN submissions violate a unique business constraint and are returned as HTTP 409 Conflict with error code BOOK_ISBN_DUPLICATE. If the platform contract allows only 400/404, the duplicate case may be downgraded to HTTP 400 with the same error code without changing the business rule.
- Malformed or missing request payload fields (blank title, blank author, malformed ISBN) are returned as HTTP 400 Bad Request with a field-level validation error list.
- Lookup, update and delete of a non-existent ISBN return HTTP 404 Not Found with error code BOOK_NOT_FOUND.
- Successful creation returns HTTP 201 Created with a Location header pointing to /api/v1/books/{isbn} and the persisted representation in the body.
- Deletion is a hard delete (physical removal) for the MVP; soft delete can be introduced later by adding a deleted flag without breaking the HTTP contract.
- Authentication/authorization (e.g. OAuth2/JWT for the Librarian role) is out of scope for this draft and is assumed to be enforced by an API gateway; all endpoints are treated as internal/trusted.
- ISBN uniqueness is enforced both at the application layer (pre-check) and by a database unique constraint to avoid race conditions.
- Timestamps are stored in UTC using java.time.Instant/OffsetDateTime, serialized in ISO-8601 format.
- Pagination is not required because retrieval is always by exact ISBN; a future search-by-author/title endpoint would add paging parameters.
- Error responses follow a consistent RFC 7807-style payload (type, title, status, detail, errorCode, timestamp).

## Requirements *(mandatory)*

### Key Entities

- **Book**: Attributes: id (UUID, PK, @NotNull), isbn (String, @NotBlank, @Size(min = 10, max = 17), @Pattern(regexp = "^(?:\\d{9}[\\dXx]|\\d{13})$")), title (String, @NotBlank, @Size(min = 1, max = 255)), author (String, @NotBlank, @Size(min = 1, max = 255)), createdAt (DateTime, @NotNull, @PastOrPresent), updatedAt (DateTime)
