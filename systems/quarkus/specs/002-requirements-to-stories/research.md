# Technical Research: Requirements to Stories & Criteria Transformation

**Feature**: `002-requirements-to-stories`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Structured Extraction via Pydantic & LangChain

### Context & Goal
Transforming unstructured natural language text into strictly typed, hierarchical data models (`ArchitectureBlueprint`, `UserStoryRecord`, `AcceptanceScenarioRecord`, `DomainEntity`) requires deterministic parsing without schema hallucination or formatting defects.

### Decision
Use `langchain_openai.ChatOpenAI` (or compatible OpenAI-compatible chat client) configured with `.with_structured_output(SpecificationDraftResponse)`.

### Rationale
- **Deterministic Schema Compliance**: Guarantees that every generated user story has `role`, `intent`, `benefit`, `priority`, and an array of `AcceptanceScenarioRecord`s containing `scenarioId`, `given`, `when`, `then`.
- **Seamless Serialization**: Pydantic models directly match the schemas already established in `backend/app/models/blueprint.py`, eliminating conversion layers.
- **Error Handling**: Pydantic automatically validates constraints (e.g. minimum scenario length, non-empty fields) upon receiving LLM outputs.

### Alternatives Evaluated
- *Raw text parsing with regular expressions*: Highly fragile against varied phrasing, bullet styles, and languages. Rejected.
- *Unstructured Markdown generation + regex*: Requires complex AST parsing and frequently produces broken Given/When/Then blocks. Rejected.

---

## 2. Interactive Refinement Engine (Human-in-the-Loop)

### Context & Goal
Per clarification 5, the user must be able to make manual adjustments or submit natural language suggestions (e.g., *"regenerate US-2 to focus on token expiry"* or *"add a scenario for concurrent balance deduction"*).

### Decision
Implement a dedicated refinement endpoint `POST /api/v1/requirements/refine` that accepts:
1. The current `SpecificationDraft`
2. A natural language `feedbackPrompt` (or specific target `storyId`)

The prompt instructs the LLM to apply delta modifications to the existing draft, preserving unaffected entities and stories while updating the targeted requirements.

### Rationale
- Allows incremental refinement without discarding user edits.
- Maintains fast turn-around times since the model performs focused delta adjustments.

---

## 3. Ephemeral Key Management (Constitution Principle VI)

### Context & Goal
Constitution Principle VI states: **Zero Hardcoded Secrets**. User API keys for LLMs must never be written to disk, SQLite databases, or commit logs.

### Decision
- The Streamlit frontend captures the optional `openai_api_key` in `st.session_state` (stored only in browser session memory).
- When invoking `POST /api/v1/requirements/transform` or `/refine`, the key is forwarded in the `X-LLM-API-Key` HTTP header (or in the request payload).
- If the header is absent, FastAPI checks the environment variable `OPENAI_API_KEY`.
- If neither is present, the endpoint rejects the request with HTTP 401 and an unambiguous message prompting the user to supply their key in the settings sidebar.
- The backend never logs, caches, or persists the key.

### Alternatives Evaluated
- *Persisting key in `studio.db`*: Explicit violation of Constitution Principle VI. Rejected.

---

## 4. Direct Pipeline Handoff into Feature 001

### Context & Goal
Eliminate friction between specifying requirements and autonomous microservice generation.

### Decision
When the user clicks **"➡️ Transferir a Generación de Microservicio"**:
1. The frontend invokes `POST /api/v1/specifications` with the validated blueprint payload.
2. The backend validates and registers the specification in `SPECIFICATIONS_STORE`, returning `specId`.
3. The frontend updates `st.session_state.current_spec_id = specId` and sets the active tab in `st.session_state` to Tab 1 / Tab 2.
4. The user sees the green validation badge in Tab 1 and can immediately launch code generation in Tab 2.

### Rationale
Completely eliminates the need to download `spec.md` and re-upload it, while still retaining the "Descargar spec.md" button for users who want the offline document.

