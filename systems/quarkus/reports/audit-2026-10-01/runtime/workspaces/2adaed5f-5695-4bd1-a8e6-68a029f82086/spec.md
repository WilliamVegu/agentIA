# Feature Specification: Audit Library

**Feature Branch**: `audit-library`

**Created**: 2026-10-02

**Status**: Draft

**Note**: derived from the validated blueprint at the start of code generation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - register a new book with a unique ISBN, title, and author (Priority: P1)

As a Librarian, I want register a new book with a unique ISBN, title, and author, so that maintain an accurate and up-to-date library catalog.

**AC-1.1**
- **Given** a librarian with valid book details (ISBN, title, author)
- **When** they submit a request to register the book
- **Then** the system creates the book and returns HTTP 201 with the created book details

**AC-1.2**
- **Given** a book with an ISBN that already exists in the system
- **When** the librarian attempts to register it
- **Then** the system rejects the request and returns HTTP 400 with an error message indicating duplicate ISBN

**AC-1.3**
- **Given** a book with an empty title
- **When** the librarian attempts to register it
- **Then** the system rejects the request and returns HTTP 400 with an error message indicating title cannot be empty

### User Story 2 - update the title of an existing book identified by its ISBN (Priority: P2)

As a Librarian, I want update the title of an existing book identified by its ISBN, so that correct or modify book information as needed.

**AC-2.1**
- **Given** a book exists with a known ISBN
- **When** the librarian updates the title with a valid new title
- **Then** the system updates the title and returns HTTP 200 with the updated book details

**AC-2.2**
- **Given** a book does not exist for a given ISBN
- **When** the librarian attempts to update its title
- **Then** the system returns HTTP 404 with an error message indicating the book was not found

**AC-2.3**
- **Given** a book exists with a known ISBN
- **When** the librarian attempts to update the title to an empty string
- **Then** the system returns HTTP 400 with an error message indicating title cannot be empty

### User Story 3 - retrieve book details by its ISBN (Priority: P3)

As a Library Patron, I want retrieve book details by its ISBN, so that find information about a specific book in the library.

**AC-3.1**
- **Given** a book exists with a specific ISBN
- **When** the patron requests the book by ISBN
- **Then** the system returns HTTP 200 with the book details

**AC-3.2**
- **Given** no book exists with a specific ISBN
- **When** the patron requests the book by ISBN
- **Then** the system returns HTTP 404 with an error message indicating the book was not found

### User Story 4 - delete a book from the library catalog by its ISBN (Priority: P2)

As a Librarian, I want delete a book from the library catalog by its ISBN, so that remove outdated or lost books from the system.

**AC-4.1**
- **Given** a book exists with a specific ISBN
- **When** the librarian deletes the book by ISBN
- **Then** the system removes the book and returns HTTP 204 No Content

**AC-4.2**
- **Given** no book exists with a specific ISBN
- **When** the librarian attempts to delete it
- **Then** the system returns HTTP 404 with an error message indicating the book was not found

## Domain Entities

### Book (`books`)

- `id`: UUID — PK, required
- `isbn`: String — required
- `title`: String — required
- `author`: String — required
