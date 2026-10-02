package com.audit.library.exception;

/**
 * Runtime exception raised when a requested resource cannot be located.
 */
public class ResourceNotFoundException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public ResourceNotFoundException(String message) {
        super(message);
    }
}
