# Quickstart Validation Guide: Test Generation, Code Analysis & Iterative Self-Repair

**Feature**: `005-automated-tests-analysis`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides end-to-end runnable validation scenarios demonstrating autonomous test generation, compiler/assertion failure diagnostics, surgical self-repair iterations, and the human-in-the-loop blocked state override.

---

## 1. Prerequisites

- **FastAPI Backend running on port 8000**:
  ```bash
  python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
  ```
- **Streamlit Web Studio running on port 8501**:
  ```bash
  python -m streamlit run frontend/app.py --server.port 8501
  ```
- **Docker Engine running** (for hermetic `--network none` execution) or mock sandbox testing mode.
- **Ephemeral OpenAI API Key** configured in the sidebar or via header `X-LLM-API-Key`.

---

## 2. Validation Scenarios

### Scenario 1: Hybrid Test Suite Generation & Initial Verification
**Goal**: Verify that the system automatically authors unit tests (Mockito) and integration tests (`@SpringBootTest` with H2 PostgreSQL mode) matching all Given/When/Then acceptance scenarios.

1. In Streamlit Tab 4 (`🚀 4. Generación & Logs en Vivo`), trigger generation for an ingested specification (e.g. `order-service`).
2. Observe the generation phases advance:
   `SCAFFOLDING` ➔ `CODE_GENERATION` ➔ `TEST_SYNTHESIS` ➔ `SANDBOX_BUILD` ➔ `TEST_EXECUTION` ➔ `VERIFIED`.
3. In Tab 5 (`🔍 5. Explorador de Código & Tests`):
   - Verify that test files are generated under `src/test/java/...`:
     - `OrderServiceTest.java` (Unit tests mocking `OrderRepository`)
     - `OrderControllerTest.java` (Web layer tests verifying HTTP status codes)
     - `OrderIntegrationTest.java` (Context tests running against H2 `MODE=PostgreSQL`)
   - Verify 100% Mockito & JUnit test pass rate.

---

### Scenario 2: Autonomous Detection & Surgical Self-Repair of a Compilation Error
**Goal**: Verify that when a compiler error occurs (e.g. missing import or type mismatch), the repair agent isolates the error and applies a surgical method/block patch without rewriting the file.

1. Trigger a generation session where a service has a missing import or type discrepancy.
2. In the terminal logs, observe the failure:
   `[ERROR] OrderServiceImpl.java:[42,18] cannot find symbol: class BigDecimal`
3. **Expected Autonomous Action**:
   - The diagnostic engine parses `FailureDiagnostic`: file `OrderServiceImpl.java`, line 42, category `COMPILATION_ERROR`.
   - Iteration 1 starts: the repair agent generates a `CodeRepairPatch` of type `IMPORT_ADD` adding `import java.math.BigDecimal;`.
   - Patch is applied surgically.
   - Sandbox re-compiles and re-executes tests.
   - Status transitions to `VERIFIED`.

---

### Scenario 3: Autonomous Diagnosis & Repair of a Test Assertion Failure
**Goal**: Verify that when a business logic assertion fails, the repair engine analyzes the expected vs. actual values, corrects the defective calculation in the `@Service`, and passes the test.

1. Consider a service method where discount calculation returns `90.00` instead of `80.00`.
2. Observe test failure:
   `ComparisonFailure: expected:<[80.00]> but was:<[90.00]>`
3. **Expected Autonomous Action**:
   - The diagnostic engine extracts: method `shouldCalculateOrderDiscount`, expected `80.00`, actual `90.00`.
   - Iteration 1 starts: repair agent inspects the enclosing calculation method in `OrderServiceImpl.java`.
   - Agent outputs a `METHOD_REPLACE` patch correcting the calculation formula.
   - Sandbox re-runs tests: all tests pass.
   - Session transitions to `VERIFIED` with unified diff recorded in session history.

---

### Scenario 4: Exhaustion of 3 Repair Iterations & Human-in-the-Loop Override
**Goal**: Verify that when errors persist after 3 attempts, the system enforces the constitutional limit (halt), transitions to `BLOCKED`, and allows the developer to resolve the defect via an in-browser code editor.

1. Inject an intractable compilation defect or contradictory constraint.
2. Observe autonomous repair attempts:
   - Iteration 1: FAILED_CONTINUE
   - Iteration 2: FAILED_CONTINUE
   - Iteration 3: FAILED_BLOCKED
3. **Expected Outcome**:
   - The session halts immediately and status becomes `BLOCKED`.
   - Tab 5 displays the **"⚠️ Sesión Bloqueada: Intervención Humana Requerida"** panel.
   - The exact compiler error and line number are highlighted.
   - An in-browser code editor displays the defective source file with a pre-filled fix suggestion.
   - The developer edits line 35 and clicks `"🔄 Aplicar Corrección y Reintentar"`.
   - The system triggers `POST /api/v1/sessions/{id}/manual-repair`, re-runs the sandbox, and achieves `VERIFIED`.

---

### Scenario 5: Visual Inspection of Repair Diff History
**Goal**: Verify that the developer can audit every modification made across repair iterations.

1. In Tab 5 (`🔍 5. Explorador de Código & Tests`), navigate to the **"🔄 Historial de Auto-Reparaciones"** subtab.
2. Select Iteration 1: view the diagnostic summary, before/after code snippet, and unified diff.
3. Select Iteration 2: view the secondary patch applied.
4. Verify that total duration and test count delta are clearly documented.

