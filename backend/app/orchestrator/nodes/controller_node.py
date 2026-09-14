from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState

def controller_node(state: GenerationAgentState) -> Dict[str, Any]:
    blueprint = state.get("blueprint", {})
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    base_dir = Path(workspace_path)

    # 1. GlobalExceptionHandler (@RestControllerAdvice - Principle III)
    handler_src = f"""package {package_name}.controller;

import {package_name}.exception.ResourceNotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {{

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(ResourceNotFoundException ex) {{
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", LocalDateTime.now().toString());
        body.put("status", HttpStatus.NOT_FOUND.value());
        body.put("error", "Not Found");
        body.put("message", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
    }}

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {{
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", LocalDateTime.now().toString());
        body.put("status", HttpStatus.BAD_REQUEST.value());
        body.put("error", "Bad Request");
        List<String> errors = ex.getBindingResult().getFieldErrors().stream()
                .map(err -> err.getField() + ": " + err.getDefaultMessage())
                .collect(Collectors.toList());
        body.put("errors", errors);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }}

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGeneral(Exception ex) {{
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", LocalDateTime.now().toString());
        body.put("status", HttpStatus.INTERNAL_SERVER_ERROR.value());
        body.put("error", "Internal Server Error");
        body.put("message", ex.getMessage());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
    }}
}}
"""
    handler_path = f"src/main/java/{pkg_path}/controller/GlobalExceptionHandler.java"
    generated_files[handler_path] = handler_src
    h_fp = base_dir / handler_path
    h_fp.parent.mkdir(parents=True, exist_ok=True)
    h_fp.write_text(handler_src, encoding="utf-8")

    # 2. Controllers for each entity
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        plural = ent_name.lower() + "s"

        ctrl_src = f"""package {package_name}.controller;

import {package_name}.model.dto.Create{ent_name}Request;
import {package_name}.model.dto.{ent_name}Response;
import {package_name}.service.{ent_name}Service;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/{plural}")
@Validated
public class {ent_name}Controller {{

    private final {ent_name}Service service;

    public {ent_name}Controller({ent_name}Service service) {{
        this.service = service;
    }}

    @PostMapping
    public ResponseEntity<{ent_name}Response> create(@Valid @RequestBody Create{ent_name}Request request) {{
        {ent_name}Response response = service.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }}

    @GetMapping("/{{id}}")
    public ResponseEntity<{ent_name}Response> getById(@PathVariable Long id) {{
        return ResponseEntity.ok(service.findById(id));
    }}

    @GetMapping
    public ResponseEntity<List<{ent_name}Response>> getAll() {{
        return ResponseEntity.ok(service.findAll());
    }}

    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {{
        service.delete(id);
        return ResponseEntity.noContent().build();
    }}
}}
"""
        ctrl_path = f"src/main/java/{pkg_path}/controller/{ent_name}Controller.java"
        generated_files[ctrl_path] = ctrl_src
        c_fp = base_dir / ctrl_path
        c_fp.parent.mkdir(parents=True, exist_ok=True)
        c_fp.write_text(ctrl_src, encoding="utf-8")

        logs.append(f"[CONTROLLER] Generated {ent_name}Controller with REST endpoints")

    return {
        "generated_files": generated_files,
        "logs": logs
    }
