package com.audit.library.controller;

import com.audit.library.exception.ResourceNotFoundException;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Single global exception handler for the whole service. Every error response is produced
 * here and shares the same {@link ErrorResponse} envelope: timestamp, HTTP status, error
 * code, descriptive message and, for validation failures, per-field details.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    private static final String CODE_BOOK_NOT_FOUND = "BOOK_NOT_FOUND";
    private static final String CODE_BOOK_ISBN_DUPLICATE = "BOOK_ISBN_DUPLICATE";
    private static final String CODE_VALIDATION_ERROR = "VALIDATION_ERROR";
    private static final String CODE_BAD_REQUEST = "BAD_REQUEST";
    private static final String CODE_INTERNAL_ERROR = "INTERNAL_ERROR";

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleResourceNotFound(ResourceNotFoundException exception) {
        logger.error("Resource not found", exception);
        return build(HttpStatus.NOT_FOUND, CODE_BOOK_NOT_FOUND, exception.getMessage(), List.of());
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ErrorResponse> handleIllegalState(IllegalStateException exception) {
        logger.error("Request conflicts with current state", exception);
        return build(HttpStatus.CONFLICT, CODE_BOOK_ISBN_DUPLICATE, exception.getMessage(), List.of());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleMethodArgumentNotValid(MethodArgumentNotValidException exception) {
        logger.error("Request body validation failed", exception);
        List<FieldValidationError> fieldErrors = new ArrayList<>();
        for (FieldError fieldError : exception.getBindingResult().getFieldErrors()) {
            fieldErrors.add(new FieldValidationError(fieldError.getField(), fieldError.getDefaultMessage()));
        }
        return build(HttpStatus.BAD_REQUEST, CODE_VALIDATION_ERROR, "Request validation failed", fieldErrors);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ErrorResponse> handleConstraintViolation(ConstraintViolationException exception) {
        logger.error("Request parameter validation failed", exception);
        List<FieldValidationError> fieldErrors = new ArrayList<>();
        for (ConstraintViolation<?> violation : exception.getConstraintViolations()) {
            fieldErrors.add(new FieldValidationError(
                    violation.getPropertyPath().toString(), violation.getMessage()));
        }
        return build(HttpStatus.BAD_REQUEST, CODE_VALIDATION_ERROR, "Request validation failed", fieldErrors);
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    public ResponseEntity<ErrorResponse> handleHandlerMethodValidation(HandlerMethodValidationException exception) {
        logger.error("Request parameter validation failed", exception);
        List<FieldValidationError> fieldErrors = new ArrayList<>();
        exception.getAllValidationResults().forEach(result ->
                result.getResolvableErrors().forEach(error ->
                        fieldErrors.add(new FieldValidationError(
                                String.valueOf(result.getMethodParameter().getParameterName()),
                                error.getDefaultMessage()))));
        return build(HttpStatus.BAD_REQUEST, CODE_VALIDATION_ERROR, "Request validation failed", fieldErrors);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ErrorResponse> handleUnreadableBody(HttpMessageNotReadableException exception) {
        logger.error("Request body could not be read", exception);
        return build(HttpStatus.BAD_REQUEST, CODE_BAD_REQUEST, "Request body is malformed or missing", List.of());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception exception) {
        logger.error("Unexpected failure", exception);
        return build(HttpStatus.INTERNAL_SERVER_ERROR, CODE_INTERNAL_ERROR,
                "Unexpected error: " + exception.getMessage(), List.of());
    }

    private ResponseEntity<ErrorResponse> build(HttpStatus status, String errorCode,
                                                String message, List<FieldValidationError> fieldErrors) {
        ErrorResponse body = new ErrorResponse(
                Instant.now(), status.value(), errorCode, message, fieldErrors);
        return ResponseEntity.status(status).body(body);
    }

    public record ErrorResponse(
            Instant timestamp,
            int status,
            String errorCode,
            String message,
            List<FieldValidationError> fieldErrors
    ) {
    }

    public record FieldValidationError(String field, String message) {
    }

    /**
     * An unmapped path is a client error, not a server fault.
     *
     * Spring raises NoResourceFoundException for a request that matches no handler. Without
     * this method it reaches the generic Exception handler and is reported as 500, which
     * makes a missing endpoint -- or a request aimed at a different service -- look like an
     * internal failure.
     */
    @org.springframework.web.bind.annotation.ExceptionHandler(
            org.springframework.web.servlet.resource.NoResourceFoundException.class)
    public org.springframework.http.ResponseEntity<?> handleNoResourceFound(
            org.springframework.web.servlet.resource.NoResourceFoundException ex) {
        return org.springframework.http.ResponseEntity
                .status(org.springframework.http.HttpStatus.NOT_FOUND)
                .body(java.util.Map.of(
                        "timestamp", java.time.Instant.now().toString(),
                        "status", org.springframework.http.HttpStatus.NOT_FOUND.value(),
                        "error", "Not Found",
                        "message", "Endpoint no encontrado: /" + ex.getResourcePath()));
    }
}
