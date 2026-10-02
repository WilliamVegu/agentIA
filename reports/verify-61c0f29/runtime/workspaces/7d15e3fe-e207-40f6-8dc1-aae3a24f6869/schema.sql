-- ============================================================================
-- Microservice Code Studio: Relational Schema DDL
-- Dialect: ANSI SQL / PostgreSQL & H2 (MODE=PostgreSQL) Compatible
-- ============================================================================

CREATE TABLE IF NOT EXISTS books (
    id UUID PRIMARY KEY,
    isbn VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
