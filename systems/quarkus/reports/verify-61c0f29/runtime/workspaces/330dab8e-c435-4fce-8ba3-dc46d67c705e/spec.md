# Feature Specification: Audit Library

**Feature Branch**: `audit-library`

**Created**: 2026-10-02

**Status**: Draft

**Note**: derived from the validated blueprint at the start of code generation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - register a new book with a unique ISBN, title and author (Priority: P1)

As a Librarian, I want register a new book with a unique ISBN, title and author, so that the library catalog is kept accurate and no duplicate titles can be registered under the same ISBN.

**AC-1.1**
- **Given** the library catalog does not contain any book with ISBN '9783161484100'
- **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "Clean Code", "author": "Robert C. Martin" }
- **Then** the service persists the book with a generated UUID and createdAt timestamp and responds with HTTP 201 Created, a Location header '/api/v1/books/9783161484100' and the created representation including isbn, title and author

**AC-1.2**
- **Given** a book with ISBN '9783161484100' already exists in the catalog
- **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "Another Title", "author": "Another Author" }
- **Then** the service does not create a second record and responds with HTTP 409 Conflict and errorCode 'BOOK_ISBN_DUPLICATE'

**AC-1.3**
- **Given** the library catalog is available and the client is authenticated as Librarian
- **When** the Librarian sends POST /api/v1/books with body { "isbn": "9783161484100", "title": "   ", "author": "Robert C. Martin" }
- **Then** the service rejects the request with HTTP 400 Bad Request and a field-level validation error indicating that 'title' must not be blank

**AC-1.4**
- **Given** the library catalog is available
- **When** the Librarian sends POST /api/v1/books with body { "isbn": "ABC-123", "title": "Clean Code", "author": "Robert C. Martin" }
- **Then** the service responds with HTTP 400 Bad Request and a field-level validation error indicating that 'isbn' does not match the expected format

### User Story 2 - update the title of an existing book identified by its ISBN (Priority: P2)

As a Librarian, I want update the title of an existing book identified by its ISBN, so that corrected or refined metadata is reflected in the catalog without changing the book identity.

**AC-2.1**
- **Given** a book with ISBN '9783161484100' and title 'Clean Code' exists in the catalog
- **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "Clean Code: A Handbook of Agile Software Craftsmanship" }
- **Then** the service updates the stored title, sets updatedAt, leaves isbn and author unchanged and responds with HTTP 200 OK containing the updated representation

**AC-2.2**
- **Given** no book with ISBN '9783161484100' exists in the catalog
- **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "Valid New Title" }
- **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND', and no record is created

**AC-2.3**
- **Given** a book with ISBN '9783161484100' exists in the catalog
- **When** the Librarian sends PUT /api/v1/books/9783161484100 with body { "title": "" }
- **Then** the service rejects the request with HTTP 400 Bad Request, the stored title remains 'Clean Code' and no updatedAt change is persisted

### User Story 3 - retrieve a book by its ISBN to verify catalog integrity (Priority: P3)

As a Auditor, I want retrieve a book by its ISBN to verify catalog integrity, so that catalog data can be inspected and audited without modifying any record.

**AC-3.1**
- **Given** a book with ISBN '9783161484100', title 'Clean Code' and author 'Robert C. Martin' exists in the catalog
- **When** the Auditor sends GET /api/v1/books/9783161484100
- **Then** the service responds with HTTP 200 OK and the full book representation including id, isbn, title, author and createdAt

**AC-3.2**
- **Given** no book with ISBN '9780000000000' exists in the catalog
- **When** the Auditor sends GET /api/v1/books/9780000000000
- **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND'

**AC-3.3**
- **Given** the catalog is available and read access is granted
- **When** the Auditor sends GET /api/v1/books/not-an-isbn
- **Then** the service responds with HTTP 400 Bad Request and a validation error indicating that the ISBN format is invalid

### User Story 4 - delete a book from the catalog by its ISBN (Priority: P2)

As a Librarian, I want delete a book from the catalog by its ISBN, so that obsolete or incorrectly registered titles can be removed so the catalog stays reliable.

**AC-4.1**
- **Given** a book with ISBN '9783161484100' exists in the catalog
- **When** the Librarian sends DELETE /api/v1/books/9783161484100
- **Then** the service removes the record and responds with HTTP 204 No Content, and a subsequent GET for that ISBN returns HTTP 404

**AC-4.2**
- **Given** no book with ISBN '9783161484100' exists in the catalog
- **When** the Librarian sends DELETE /api/v1/books/9783161484100
- **Then** the service responds with HTTP 404 Not Found and errorCode 'BOOK_NOT_FOUND' and the catalog remains unchanged

**AC-4.3**
- **Given** the catalog is available
- **When** the Librarian sends DELETE /api/v1/books/12345
- **Then** the service responds with HTTP 400 Bad Request and a validation error indicating that the ISBN format is invalid

## Domain Entities

### Book (`books`)

- `id`: UUID — PK, required
- `isbn`: String — required
- `title`: String — required
- `author`: String — required
- `createdAt`: DateTime — required
- `updatedAt`: DateTime
