# Implementation Plan: 016 - Quarkus AI-Native Studio

**Branch**: `016-quarkus-ai-native-studio` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary
Migrar de forma integral el generador de microservicios de Spring Boot 3.x a Quarkus 3.x (Java 21 LTS), incorporar el principio de generación exclusiva por IA con inicio limpio (cero precargas/mocks estáticos) y formalizar historias de usuario y criterios de aceptación BDD en idioma español.

## Componentes Afectados

1. **Gobernanza y Reglas de Agentes (`backend/app/resources/`)**:
   - `instructions/scaffolder.md`: Reglas de generación para Maven `quarkus-bom`, `quarkus-maven-plugin` y `application.properties`.
   - `instructions/domain.md`: Entidades con Panache y Records con Jakarta Validation.
   - `instructions/controller.md`: Jakarta REST (`@Path`, `@GET`, `@POST`, etc.).
   - `instructions/service.md`: CDI Beans con `@ApplicationScoped` y `@Transactional`.
   - `instructions/test.md`: Pruebas con `@QuarkusTest`, REST-assured y `@InjectMock`.
   - `dependency_allowlist.json`: Lista blanca de artefactos Quarkus 3.

2. **Servicios de Backend (`backend/app/services/`)**:
   - `requirements_service.py`: Prompts de descomposición en español (`Como... quiero... para...` / `Dado... cuando... entonces...`), remoción de fallback mock hardcodeado `order-service` cuando se requiere IA.
   - `architecture_service.py`: Capas y dependencias Quarkus.
   - `model_sql_service.py`: Generación de entidades y repositorios Panache.
   - `test_analysis_service.py`: Análisis de pruebas `@QuarkusTest`.
   - `devops_service.py` & `docker_service.py`: Dockerfile multi-stage Fast-jar de Quarkus.

3. **Frontend (`frontend/src/`)**:
   - `context/StudioContext.tsx`: No precargar la primera sesión si no fue solicitada explícitamente; proveer estado inicial vacío.
   - `context/LlmContext.tsx`: Eliminar o despriorizar mock como estado por defecto en favor de proveedores reales.
   - `views/RequirementsView.tsx`: Soporte nativo para BDD en español, placeholders en español.
   - `views/ArchitectureView.tsx`, `CodeExplorerView.tsx`, `DevOpsDeploymentView.tsx`, `StudioOverviewView.tsx`: Actualización de textos, menciones y contratos de Spring Boot a Quarkus.

4. **Verificación**:
   - Ejecución de suite de tests en backend y frontend para validar consistencia.
