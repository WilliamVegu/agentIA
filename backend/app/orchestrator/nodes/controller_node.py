from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState

def controller_node(state: GenerationAgentState) -> Dict[str, Any]:
    blueprint = state.get("blueprint", {})
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "sample-service")
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
import org.springframework.web.servlet.resource.NoResourceFoundException;

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

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNoResourceFound(NoResourceFoundException ex) {{
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", LocalDateTime.now().toString());
        body.put("status", HttpStatus.NOT_FOUND.value());
        body.put("error", "Not Found");
        body.put("message", "Endpoint o recurso estático no encontrado: /" + ex.getResourcePath());
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

    # 2. HomeController (@GetMapping("/") - Welcome & API Catalog)
    endpoints_java = []
    endpoints_html = []
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        plural = ent_name.lower() + "s"
        endpoints_java.append(f'            "/api/v1/{plural}",')
        endpoints_html.append(f"""                  <a class="link-item" href="/api/v1/{plural}" target="_blank">
                    <span><span class="method">GET</span>/api/v1/{plural}</span>
                    <span class="tag">{ent_name} API ↗</span>
                  </a>""")

    java_endpoints_str = "\n".join(endpoints_java)
    html_links_str = "\n".join(endpoints_html)

    home_src = f"""package {package_name}.controller;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@CrossOrigin(origins = "*")
public class HomeController {{

    @GetMapping(value = "/", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> homeHtml() {{
        return ResponseEntity.ok(\"\"\"
            <!DOCTYPE html>
            <html lang="es">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>{service_name} - TCS Microservice Code Studio</title>
              <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b1120; color: #f8fafc; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }}
                .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 32px; max-width: 640px; width: 100%; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
                .badge {{ background: #064e3b; color: #34d399; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; margin-bottom: 16px; border: 1px solid #059669; }}
                .badge-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #34d399; }}
                h1 {{ margin: 0 0 8px 0; font-size: 24px; color: #ffffff; letter-spacing: -0.02em; }}
                p {{ color: #94a3b8; font-size: 13px; margin: 0 0 24px 0; }}
                .endpoints {{ margin-top: 24px; }}
                .endpoints h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-bottom: 12px; }}
                .link-item {{ display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: #0f172a; border-radius: 10px; margin-bottom: 10px; border: 1px solid #334155; text-decoration: none; color: #38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; transition: all 0.15s; }}
                .link-item:hover {{ border-color: #38bdf8; background: #172554; }}
                .method {{ color: #34d399; font-weight: bold; margin-right: 8px; }}
                .tag {{ font-size: 11px; color: #94a3b8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .footer {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid #334155; font-size: 12px; color: #64748b; text-align: center; }}
              </style>
            </head>
            <body>
              <div class="card">
                <span class="badge"><span class="badge-dot"></span>SISTEMA OPERATIVO (UP 200 OK)</span>
                <h1>Microservicio: {service_name}</h1>
                <p>Spring Boot 3.2.3 &bull; Java 21 LTS &bull; PostgreSQL &bull; TCS Architecture Studio</p>
                <div class="endpoints">
                  <h3>Endpoints REST Disponibles</h3>
{html_links_str}
                  <a class="link-item" href="/actuator/health" target="_blank">
                    <span><span class="method">GET</span>/actuator/health</span>
                    <span class="tag">Health Status ↗</span>
                  </a>
                </div>
                <div class="footer">
                  TCS Microservice Code Studio &bull; Generación Autónoma con Arquitectura Limpia
                </div>
              </div>
            </body>
            </html>
        \"\"\");
    }}

    @GetMapping(value = "/", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> homeJson() {{
        Map<String, Object> info = new HashMap<>();
        info.put("service", "{service_name}");
        info.put("status", "UP");
        info.put("framework", "Spring Boot 3.2.3 / Java 21 LTS");
        info.put("timestamp", LocalDateTime.now().toString());
        info.put("description", "TCS Microservice Code Studio - Microservicio Activo");
        info.put("endpoints", List.of(
{java_endpoints_str}
            "/actuator/health"
        ));
        return ResponseEntity.ok(info);
    }}
}}
"""
    home_path = f"src/main/java/{pkg_path}/controller/HomeController.java"
    generated_files[home_path] = home_src
    home_fp = base_dir / home_path
    home_fp.write_text(home_src, encoding="utf-8")
    logs.append(f"[CONTROLLER] Generated HomeController for root path / with API catalog")

    # 3. Controllers for each entity
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
@CrossOrigin(origins = "*")
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
