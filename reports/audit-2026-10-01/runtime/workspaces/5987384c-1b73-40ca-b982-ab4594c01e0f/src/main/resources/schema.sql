CREATE TABLE IF NOT EXISTS books (
    id UUID NOT NULL,
    isbn VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uk_books_isbn UNIQUE (isbn)
);
