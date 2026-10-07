package com.example.flowinventory.exception;

/**
 * Runtime exception raised when a requested domain resource does not exist.
 */
public class ResourceNotFoundException extends RuntimeException {

    public ResourceNotFoundException(String message) {
        super(message);
    }
}
