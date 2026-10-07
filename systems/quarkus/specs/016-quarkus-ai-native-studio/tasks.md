# Tasks: 016 - Quarkus AI-Native Studio

**Feature**: 016-quarkus-ai-native-studio | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Gobernanza y Reglas de Agentes (Quarkus 3.x)
- [X] T001 [Backend] Actualizar `backend/app/resources/instructions/scaffolder.md` para generar `pom.xml` con `io.quarkus.platform:quarkus-bom` (3.x), `quarkus-maven-plugin` y `application.properties`.
- [X] T002 [Backend] Actualizar `backend/app/resources/instructions/domain.md` para generar entidades Panache (`PanacheRepository<T>` / `PanacheEntityBase`) y records inmutables con Jakarta Validation.
- [X] T003 [Backend] Actualizar `backend/app/resources/instructions/controller.md` para generar Jakarta REST / Quarkus REST (`@Path`, `@GET`, `@POST`, `@Produces`, `@Consumes`).
- [X] T004 [Backend] Actualizar `backend/app/resources/instructions/service.md` para generar servicios CDI con `@ApplicationScoped` y `@Transactional`.
- [X] T005 [Backend] Actualizar `backend/app/resources/instructions/test.md` para generar tests con `@QuarkusTest`, `quarkus-junit5`, REST-assured y `@InjectMock`.
- [X] T006 [Backend] Actualizar `backend/app/resources/dependency_allowlist.json` con dependencias oficiales del ecosistema Quarkus 3.x.

---

## Phase 2: Servicio de Requerimientos en Español y Cero Defaults
- [X] T007 [Backend] Modificar `backend/app/services/requirements_service.py` para requerir que las historias de usuario se generen en español (`Como... quiero... para...`) y los criterios BDD en español (`Dado... Cuando... Entonces...`).
- [X] T008 [Backend] Eliminar en `backend/app/services/requirements_service.py` el fallback automático de generación simulada con mocks predeterminados (`order-service`). Si el usuario solicita generación real y no hay LLM configurado, lanzar un error claro requiriendo credenciales.

---

## Phase 3: Servicios de Soporte Backend (Arquitectura, DevOps, Docker)
- [X] T009 [Backend] Actualizar `backend/app/services/architecture_service.py` para estructurar los proyectos en base al modelo Quarkus 3.x.
- [X] T010 [Backend] Actualizar `backend/app/services/devops_service.py` y `docker_service.py` para generar Dockerfiles multi-stage basados en Quarkus Fast-jar (`quarkus-app/quarkus-run.jar`).

---

## Phase 4: Frontend - Lienzo Limpio y Adaptación a Quarkus
- [X] T011 [Frontend] Modificar `frontend/src/context/StudioContext.tsx` para evitar la auto-selección de sesiones existentes al cargar la página (permitir arranque en lienzo limpio / Empty State).
- [X] T012 [Frontend] Modificar `frontend/src/context/LlmContext.tsx` y `apiClient.ts` para no fijar 'mock' como valor predeterminado si el usuario desea generación genuina con IA.
- [X] T013 [Frontend] Actualizar vistas (`RequirementsView.tsx`, `ArchitectureView.tsx`, `CodeExplorerView.tsx`, `DevOpsDeploymentView.tsx`, `StudioOverviewView.tsx`) para reemplazar las referencias de Spring Boot 3 por Quarkus 3.x y soportar BDD en español.

---

## Phase 5: Verificación y Pruebas
- [X] T014 Ejecutar pruebas de frontend y backend para comprobar que no existan regresiones y que el nuevo contrato funcione consistentemente.
