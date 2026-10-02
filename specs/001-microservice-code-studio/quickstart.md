# Guía de Inicio Rápido y Validación: Fábrica de Agentes Quarkus ⚡

**Característica**: `001-quarkus-agent-factory` | **Iniciativa**: Pedido 2 de Lorena | **Fecha**: 2026-10-01

Esta guía describe los pasos para levantar el entorno completo y validar el flujo de 8 pasos con el caso de uso oficial **`orders-service`**.

---

## 1. Requisitos Previos

* **Python**: 3.11 o 3.12 (`python --version`)
* **Node.js**: 20+ (`node --version`) y npm (`npm --version`)
* **Java** (opcional, para compilar el ZIP exportado): Java 21 LTS (`java -version`)

---

## 2. Puesta en Marcha en 2 Pasos

### Opción A: Script Automático (Recomendado)
Ejecuta el script unificado en la raíz del proyecto:
```cmd
run_all.bat
```
Esto abrirá dos terminales:
1. **Backend FastAPI**: `http://localhost:8000` (Swagger docs: `http://localhost:8000/docs`).
2. **Frontend React Vite**: `http://localhost:3000`.

---

### Opción B: Arranque Manual

**Terminal 1 - Backend FastAPI:**
```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend React:**
```bash
cd frontend
npm run dev
```

---

## 3. Escenario de Validación End-to-End (`orders-service`)

Sigue este recorrido paso a paso en tu navegador en `http://localhost:3000`:

1. **Paso 1: Entrada del Pedido (5 Bloques):**
   * Servicio: `orders-service` | Equipo: `Ventas` | Java: `21` | Herramienta: `Maven`
   * Lógica de Negocio: *"registrar pedidos con cliente e ítems, consultarlos por estado y cancelarlos si aún no fueron despachados."*
   * Técnico: Base de datos `SQLite (Demo local portable)`, Seguridad `JWT (SmallRye JWT)`, sin Kafka.
   * Modo de IA: `Medio` (Rango estimado: 100k - 200k tokens).
   * Clic en: **"Ingresar Pedido y Consultar al Agente Analista"**.

2. **Paso 2: Aclaración Previa:**
   * El Agente Analista presenta entre 3 y 5 preguntas concretas sobre el manejo de estados de cancelación, esquema de ítems y reglas de inventario.
   * Selecciona las opciones recomendadas y pulsa **"Enviar Respuestas y Redactar Contrato OpenAPI 3.1"**.

3. **Paso 3: Control Humano 1 (Aprobación y Congelamiento):**
   * Revisa los endpoints generados (`POST /orders`, `GET /orders`, `GET /orders/{id}`, `PUT /orders/{id}/cancel`).
   * Visualiza el contrato en YAML.
   * Pulsa **"Aprobar y Congelar Contrato"**. El contrato queda inmutable y se activa el Agente Arquitecto.

4. **Paso 4: Arquitectura & Previsualizador de Arquetipo:**
   * Selecciona la arquitectura (Capas Estándar, Hexagonal o Reactiva).
   * **Examina el Previsualizador de Arquetipo**: Alterna entre **Maven (`pom.xml`)** y **Gradle (`build.gradle`)** para ver las dependencias oficiales de Quarkus, el plugin y la estructura de carpetas antes de generar.
   * Pulsa **"Confirmar y Generar Esqueleto Automático ⚡"**.

5. **Paso 5: Construcción & Tracking:**
   * Observa la barra de estados en tiempo real (`Generando` → `Probando`).
   * Pulsa **"Construir Lógica de Negocio y Ejecutar Pruebas QA ⚡"**.
   * Verifica los resultados de `@QuarkusTest`: 5/5 pruebas aprobadas (100%), cobertura de código al 94.8% y tiempo de ejecución de ~1.4s.

6. **Paso 6: Documentación:**
   * Examina los 5 documentos generados oficialmente: `README.md`, `DOCUMENTACION_API.md`, `ADR_001`, `GUIA_PRUEBAS_COBERTURA.md` y `GUIA_OPERACION_SERVICIO.md`.

7. **Paso 7: Control Humano 2 (Revisión Final):**
   * Explora el árbol de código Java generado (`Order.java`, `OrderService.java`, `OrderResource.java`, etc.).
   * Audita la tabla de tokens reales consumidos por cada agente comparada contra el rango estimado.
   * Pulsa **"Aprobar Entrega a Git y Activar Agente DevOps"**.

8. **Paso 8: Entrega DevOps & Descarga:**
   * Examina el `Jenkinsfile` corporativo y el `Dockerfile.jvm`.
   * Pulsa el botón **"Descargar .ZIP Completo"**.
   * Descomprime el archivo y abre el microservicio en tu IDE preferido. ¡Listo para ejecutar `./mvnw quarkus:dev`!
