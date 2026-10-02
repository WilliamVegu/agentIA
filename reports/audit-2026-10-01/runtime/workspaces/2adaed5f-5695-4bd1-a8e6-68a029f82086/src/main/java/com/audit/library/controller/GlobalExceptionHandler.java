package com.audit.library.controller;

import com.audit.library.exception.ResourceNotFoundException;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;

import java.time.Instant;
import java.util.List;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ApiError> handleResourceNotFoundException(ResourceNotFoundException ex) {
        logger.error("Resource not found: {}", ex.getMessage(), ex);
        return build(HttpStatus.NOT_FOUND, ex.getMessage(), List.of());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleMethodArgumentNotValidException(MethodArgumentNotValidException ex) {
        logger.error("Request body validation failed: {}", ex.getMessage(), ex);
        List<FieldErrorDetail> fieldErrors = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> new FieldErrorDetail(error.getField(), error.getDefaultMessage()))
                .toList();
        return build(HttpStatus.BAD_REQUEST, "Request body validation failed", fieldErrors);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiError> handleConstraintViolationException(ConstraintViolationException ex) {
        logger.error("Request parameter validation failed: {}", ex.getMessage(), ex);
        List<FieldErrorDetail> fieldErrors = ex.getConstraintViolations().stream()
                .map(violation -> new FieldErrorDetail(
                        lastPathSegment(violation.getPropertyPath().toString()),
                        violation.getMessage()))
                .toList();
        return build(HttpStatus.BAD_REQUEST, "Request parameter validation failed", fieldErrors);
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    public ResponseEntity<ApiError> handleHandlerMethodValidationException(HandlerMethodValidationException ex) {
        logger.error("Request parameter validation failed: {}", ex.getMessage(), ex);
        List<FieldErrorDetail> fieldErrors = ex.getAllValidationResults().stream()
                .flatMap(result -> {
                    String fieldName = result.getMethodParameter().getParameterName();
                    return result.getResolvableErrors().stream()
                            .map(error -> new FieldErrorDetail(fieldName, error.getDefaultMessage()));
                })
                .toList();
        return build(HttpStatus.BAD_REQUEST, "Request parameter validation failed", fieldErrors);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiError> handleIllegalArgumentException(IllegalArgumentException ex) {
        logger.error("Invalid request: {}", ex.getMessage(), ex);
        return build(HttpStatus.BAD_REQUEST, ex.getMessage(), List.of());
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiError> handleHttpMessageNotReadableException(HttpMessageNotReadableException ex) {
        logger.error("Malformed request body: {}", ex.getMessage(), ex);
        return build(HttpStatus.BAD_REQUEST, "Malformed request body", List.of());
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ApiError> handleDataIntegrityViolationException(DataIntegrityViolationException ex) {
        logger.error("Data integrity violation", ex);
        return build(HttpStatus.BAD_REQUEST, "Request conflicts with existing data", List.of());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleUnexpectedException(Exception ex) {
        logger.error("Unexpected error: {}", ex.getMessage(), ex);
        String message = ex.getMessage() == null
                ? "Unexpected error: no message available"
                : "Unexpected error: " + ex.getMessage();
        return build(HttpStatus.INTERNAL_SERVER_ERROR, message, List.of());
    }

    private ResponseEntity<ApiError> build(HttpStatus status, String message, List<FieldErrorDetail> fieldErrors) {
        ApiError body = new ApiError(
                Instant.now(),
                status.value(),
                status.getReasonPhrase(),
                message,
                fieldErrors
        );
        return ResponseEntity.status(status).body(body);
    }

    private static String lastPathSegment(String path) {
        int index = path.lastIndexOf('.');
        return index >= 0 ? path.substring(index + 1) : path;
    }

    public record ApiError(
            Instant timestamp,
            int status,
            String error,
            String message,
            List<FieldErrorDetail> fieldErrors
    ) {
    }

    public record FieldErrorDetail(
            String field,
            String message
    ) {
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
