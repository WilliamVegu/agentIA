"""Native Quarkus offline generator, restored and wired into the Studio stage boundary."""

from app.orchestrator.stages.deterministic.schema import identifier
from app.services.workspace_guard import io_path
from pathlib import Path
from typing import Dict, Any
from app.orchestrator.state import GenerationAgentState

def emit(state: GenerationAgentState) -> Dict[str, Any]:
    from app.services.domain_descriptor import normalize_blueprint
    blueprint = normalize_blueprint(state.get("blueprint", {}))
    state["blueprint"] = blueprint
    service_name = blueprint.get("serviceName") or blueprint.get("service_name", "sample-service")
    package_name = blueprint.get("packageName") or blueprint.get("package_name", "com.corp.service")
    workspace_path = state.get("workspace_path", "./workspaces/sample")
    generated_files = state.get("generated_files", {})
    logs = state.get("logs", [])

    pkg_path = package_name.replace(".", "/")
    entities = blueprint.get("entities", [])
    base_dir = Path(workspace_path)

    # 1. GlobalExceptionHandler (JAX-RS @Provider ExceptionMapper - Principle III:
    # exactly one central, application-wide exception handler)
    handler_src = f"""package {package_name}.controller;

import {package_name}.exception.ResourceNotFoundException;
import jakarta.validation.ConstraintViolationException;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Provider
public class GlobalExceptionHandler implements ExceptionMapper<Exception> {{

    @Override
    public Response toResponse(Exception ex) {{
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", LocalDateTime.now().toString());

        if (ex instanceof WebApplicationException webException) {{
            return Response.status(webException.getResponse().getStatus())
                    .type(MediaType.APPLICATION_JSON).entity(body).build();
        }}

        if (ex instanceof ResourceNotFoundException) {{
            body.put("status", Response.Status.NOT_FOUND.getStatusCode());
            body.put("error", "Not Found");
            body.put("message", ex.getMessage());
            return Response.status(Response.Status.NOT_FOUND)
                    .type(MediaType.APPLICATION_JSON)
                    .entity(body)
                    .build();
        }}

        if (ex instanceof ConstraintViolationException) {{
            body.put("status", Response.Status.BAD_REQUEST.getStatusCode());
            body.put("error", "Bad Request");
            body.put("message", ex.getMessage());
            return Response.status(Response.Status.BAD_REQUEST)
                    .type(MediaType.APPLICATION_JSON)
                    .entity(body)
                    .build();
        }}

        Throwable cause = ex;
        java.util.Set<Throwable> visited = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
        while (cause != null && visited.add(cause)) {{
            if (cause instanceof org.hibernate.exception.ConstraintViolationException) {{
                body.put("status", 409);
                body.put("error", "Conflict");
                body.put("message", "The request conflicts with a database constraint");
                return Response.status(Response.Status.CONFLICT).type(MediaType.APPLICATION_JSON).entity(body).build();
            }}
            cause = cause.getCause();
        }}
        body.put("status", Response.Status.INTERNAL_SERVER_ERROR.getStatusCode());
        body.put("error", "Internal Server Error");
        body.put("message", "An unexpected error occurred");
        return Response.status(Response.Status.INTERNAL_SERVER_ERROR)
                .type(MediaType.APPLICATION_JSON)
                .entity(body)
                .build();
    }}
}}
"""
    handler_path = f"src/main/java/{pkg_path}/controller/GlobalExceptionHandler.java"
    generated_files[handler_path] = handler_src
    h_fp = base_dir / handler_path
    io_path(h_fp.parent).mkdir(parents=True, exist_ok=True)
    io_path(h_fp).write_text(handler_src, encoding="utf-8")

    # 2. HomeController (@GetMapping("/") - Welcome & API Catalog)
    endpoints_java = []
    endpoints_html = []
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        id_name, id_type = identifier(ent)
        id_cap = id_name[0].upper() + id_name[1:]
        plural = ent_name.lower() + "s"
        endpoints_java.append(f'            "/api/v1/{plural}"')
        endpoints_html.append(f"""                  <a class="link-item" href="/api/v1/{plural}" target="_blank">
                    <span><span class="method">GET</span>/api/v1/{plural}</span>
                    <span class="tag">{ent_name} API ↗</span>
                  </a>""")

    java_endpoints_str = ",\n".join(endpoints_java)
    html_links_str = "\n".join(endpoints_html)

    home_src = f"""package {package_name}.controller;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Path("/")
public class HomeController {{

    @GET
    @Produces(MediaType.TEXT_HTML)
    public Response homeHtml() {{
        return Response.ok(\"\"\"
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
                <p>Quarkus 3.x &bull; Java 21 LTS &bull; H2 &bull; TCS Architecture Studio</p>
                <div class="endpoints">
                  <h3>Endpoints REST Disponibles</h3>
{html_links_str}
                </div>
                <div class="footer">
                  TCS Microservice Code Studio &bull; Generación Autónoma con Arquitectura Limpia
                </div>
              </div>
            </body>
            </html>
        \"\"\").build();
    }}

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public Response homeJson() {{
        Map<String, Object> info = new HashMap<>();
        info.put("service", "{service_name}");
        info.put("status", "UP");
        info.put("framework", "Quarkus 3.x / Java 21 LTS");
        info.put("timestamp", LocalDateTime.now().toString());
        info.put("description", "TCS Microservice Code Studio - Microservicio Activo");
        info.put("endpoints", List.of(
{java_endpoints_str}
        ));
        return Response.ok(info).build();
    }}
}}
"""
    home_path = f"src/main/java/{pkg_path}/controller/HomeController.java"
    generated_files[home_path] = home_src
    home_fp = base_dir / home_path
    io_path(home_fp).write_text(home_src, encoding="utf-8")
    logs.append(f"[CONTROLLER] Generated HomeController for root path / with API catalog")

    # 3. Controllers for each entity
    for ent in entities:
        ent_name = ent.get("name", "Entity")
        id_name, id_type = identifier(ent)
        id_cap = id_name[0].upper() + id_name[1:]
        plural = ent_name.lower() + "s"

        ctrl_src = f"""package {package_name}.controller;

import {package_name}.model.dto.Create{ent_name}Request;
import {package_name}.model.dto.{ent_name}Response;
import {package_name}.service.{ent_name}Service;
import jakarta.inject.Inject;
import jakarta.validation.Valid;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;

@Path("/api/v1/{plural}")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class {ent_name}Controller {{

    private final {ent_name}Service service;

    @Inject
    public {ent_name}Controller({ent_name}Service service) {{
        this.service = service;
    }}

    @POST
    public Response create(@Valid Create{ent_name}Request request) {{
        {ent_name}Response response = service.create(request);
        return Response.status(Response.Status.CREATED).entity(response).build();
    }}

    @GET
    @Path("/{{id}}")
    public Response getById(@PathParam("id") {id_type} id) {{
        return Response.ok(service.findById(id)).build();
    }}

    @GET
    public List<{ent_name}Response> getAll() {{
        return service.findAll();
    }}

    @DELETE
    @Path("/{{id}}")
    public Response delete(@PathParam("id") {id_type} id) {{
        service.delete(id);
        return Response.noContent().build();
    }}
}}
"""
        ctrl_path = f"src/main/java/{pkg_path}/controller/{ent_name}Controller.java"
        generated_files[ctrl_path] = ctrl_src
        c_fp = base_dir / ctrl_path
        io_path(c_fp.parent).mkdir(parents=True, exist_ok=True)
        io_path(c_fp).write_text(ctrl_src, encoding="utf-8")

        logs.append(f"[CONTROLLER] Generated {ent_name}Controller with REST endpoints")

    return {
        "generated_files": generated_files,
        "logs": logs
    }
