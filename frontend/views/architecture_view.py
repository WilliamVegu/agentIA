import json
import requests
import streamlit as st

def render_architecture_view(backend_url: str, openai_key: str = None, provider: str = None):
    st.header("🏗️ 2. Diseño Arquitectónico & Catálogo de Componentes")
    st.markdown(
        "Inspecciona y ajusta la arquitectura en 4 capas estrictas (**Controller** ➔ **Service** ➔ **Repository** ➔ **Model**), "
        "los componentes transversales de soporte (`GlobalExceptionHandler`), los contratos de endpoints REST (Java Records inmutables) "
        "y el diagrama direccional de dependencias libre de ciclos."
    )

    active_api_key = openai_key or st.session_state.get("api_key") or st.session_state.get("openai_key")
    active_provider = provider or st.session_state.get("llm_provider")

    if "architecture_design" not in st.session_state:
        st.session_state.architecture_design = None

    design = st.session_state.get("architecture_design")
    draft = st.session_state.get("draft_spec")

    # If no design has been synthesized yet
    if not design:
        if draft:
            st.info("💡 Tienes una especificación de requisitos activa. Genera el diseño arquitectónico inicial para visualizar los componentes:")
            if st.button("🏗️ Generar Diseño Arquitectónico y Componentes con IA", key="btn_arch_generate_ai", type="primary", use_container_width=True, disabled=not active_api_key):
                with st.spinner("Sintetizando topología en 4 capas, endpoints y diagrama Mermaid..."):
                    payload = {
                        "draft": draft,
                        "apiKey": active_api_key,
                        "provider": active_provider,
                    }
                    try:
                        headers = {}
                        if active_api_key:
                            headers["X-LLM-API-Key"] = active_api_key
                        if active_provider:
                            headers["X-LLM-Provider"] = active_provider
                        resp = requests.post(f"{backend_url}/api/v1/architecture/design", json=payload, headers=headers, timeout=45)
                        if resp.status_code == 200:
                            st.session_state.architecture_design = resp.json()
                            st.success("✅ ¡Arquitectura y componentes diseñados exitosamente!")
                            st.rerun()
                        else:
                            st.error(f"Error {resp.status_code}: {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")
        else:
            st.warning("⚠️ No hay ninguna especificación activa. Primero redacta o transforma requisitos en la pestaña **'📝 1. Requisitos & Historias'**.")
        return

    # Section 1: Mermaid Architecture Flowchart
    st.subheader("📊 1. Diagrama Direccional de Capas y Componentes (Mermaid)")
    st.caption("Visualización de dependencias unidireccionales (Principios Constitucionales I, II y III):")
    
    mermaid_code = design.get("mermaidDiagram", "")
    if mermaid_code:
        st.markdown(f"```mermaid\n{mermaid_code}\n```")
    else:
        st.info("Diagrama Mermaid no disponible.")

    # Section 2: Component Catalog by Layer
    st.markdown("---")
    st.subheader("🏛️ 2. Catálogo Jerárquico de Componentes")

    components = design.get("components", [])
    layers = {
        "controller": "Capa Controlador (REST / HTTP)",
        "service": "Capa Servicio (Lógica de Negocio)",
        "repository": "Capa Repositorio (Persistencia Spring Data JPA)",
        "model": "Capa Dominio & Modelos",
        "infrastructure": "Componentes Transversales & Infraestructura (@RestControllerAdvice)",
    }

    for layer_key, layer_label in layers.items():
        layer_comps = [c for c in components if c.get("layer") == layer_key]
        with st.expander(f"📁 {layer_label} ({len(layer_comps)})", expanded=(layer_key in ("controller", "service", "infrastructure"))):
            if not layer_comps:
                st.caption("No hay componentes en esta capa.")
            for c_idx, comp in enumerate(layer_comps):
                st.markdown(f"#### `{comp.get('name')}` — *{comp.get('stereotype')}*")
                col_c1, col_c2 = st.columns([3, 2])
                with col_c1:
                    comp["packageName"] = st.text_input(
                        "Paquete Java:",
                        value=comp.get("packageName", ""),
                        key=f"pkg_{layer_key}_{c_idx}",
                    )
                    resp_list = comp.get("responsibilities", [])
                    st.markdown("**Responsabilidades:**")
                    for r in resp_list:
                        st.markdown(f"- {r}")
                with col_c2:
                    st.markdown(f"**Dependencias de salida:** `{', '.join(comp.get('dependencies', [])) or 'Ninguna'}`")
                    st.markdown(f"**Historias mapeadas:** `{', '.join(comp.get('mappedStories', [])) or '—'}`")
                st.markdown("---")

    # Section 3: Derived REST Endpoint Catalog
    st.markdown("---")
    st.subheader("🌐 3. Catálogo de Endpoints REST & Contratos DTO")
    st.caption("Contratos inmutables de API derivados directamente de los escenarios Given/When/Then:")

    endpoints = design.get("endpoints", [])
    if endpoints:
        for ep_idx, ep in enumerate(endpoints):
            col_m, col_p, col_req, col_res, col_sc = st.columns([1, 3, 2, 2, 2])
            with col_m:
                method = ep.get("method")
                color = "green" if method == "GET" else "blue" if method == "POST" else "orange" if method in ("PUT", "PATCH") else "red"
                st.markdown(f":{color}[**{method}**]")
            with col_p:
                st.code(ep.get("path"), language=None)
                st.caption(ep.get("summary", ""))
            with col_req:
                req_dto = ep.get("requestDto")
                st.markdown(f"**Request DTO:** `{req_dto or '—'}`")
            with col_res:
                res_dto = ep.get("responseDto")
                st.markdown(f"**Response DTO:** `{res_dto or '—'}`")
            with col_sc:
                st.markdown(f"**Éxito:** `{ep.get('successStatus')}` | **Error:** `{', '.join(map(str, ep.get('errorStatuses', [])))}`")
                if ep.get("mappedScenarioId"):
                    st.caption(f"Criterio BDD: `{ep.get('mappedScenarioId')}`")

    # Section 4: Architecture Refinement Loop
    st.markdown("---")
    st.subheader("🔄 4. Asistente de Refinamiento Arquitectónico con IA")
    st.caption("Envía instrucciones para agregar componentes, reasignar dependencias o extraer servicios:")

    ref_col1, ref_col2, ref_col3 = st.columns([3, 1, 1])
    with ref_col1:
        arch_prompt = st.text_input(
            "Sugerencia o ajuste arquitectónico:",
            placeholder="Ej: Añade un componente de servicio AuditLogService para registrar eventos",
        )
    with ref_col2:
        comp_names = ["GLOBAL"] + [c.get("name") for c in components]
        target_comp = st.selectbox("Componente objetivo:", comp_names)
    with ref_col3:
        st.write("")
        refine_arch_btn = st.button("🔄 Refinar Arquitectura", key="btn_arch_refine_ai", type="secondary", use_container_width=True, disabled=not active_api_key)

    if refine_arch_btn:
        if not arch_prompt or len(arch_prompt.strip()) < 3:
            st.error("Ingresa una sugerencia clara de refinamiento arquitectónico.")
        else:
            with st.spinner("Aplicando ajustes arquitectónicos con IA..."):
                payload = {
                    "currentDesign": design,
                    "feedbackPrompt": arch_prompt.strip(),
                    "targetComponent": None if target_comp == "GLOBAL" else target_comp,
                    "apiKey": active_api_key,
                }
                try:
                    headers = {"X-LLM-API-Key": active_api_key} if active_api_key else {}
                    resp = requests.post(f"{backend_url}/api/v1/architecture/refine", json=payload, headers=headers, timeout=45)
                    if resp.status_code == 200:
                        st.session_state.architecture_design = resp.json()
                        st.success("✅ ¡Diseño arquitectónico refinado exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")
                except Exception as e:
                    st.error(f"Error conectando con el backend: {e}")

    # Section 5: Export Artifacts and Pipeline Handoff
    st.markdown("---")
    st.subheader("🚀 5. Exportación de Documentación y Transferencia al Generador")

    down_col1, down_col2 = st.columns([1, 1])

    with down_col1:
        openapi_yaml = design.get("openapiYaml", "")
        st.download_button(
            label="📥 Descargar openapi.yaml",
            data=openapi_yaml.encode("utf-8"),
            file_name=f"openapi-{design.get('serviceName', 'service')}.yaml",
            mime="application/x-yaml",
            use_container_width=True,
            key="dl_openapi_yaml",
        )

    with down_col2:
        arch_md = design.get("architectureMarkdown", "")
        st.download_button(
            label="📥 Descargar architecture.md",
            data=arch_md.encode("utf-8"),
            file_name=f"architecture-{design.get('serviceName', 'service')}.md",
            mime="text/markdown",
            use_container_width=True,
            key="dl_architecture_md",
        )

    st.markdown("#### 🔄 Flujo de Trabajo")
    col_workflow1, col_workflow2 = st.columns([1, 1])

    with col_workflow1:
        if st.button("💾 Diseñar Modelos & SQL (Recomendado)", key="btn_arch_goto_models_sql", type="primary", use_container_width=True):
            with st.spinner("Sintetizando modelos de dominio JPA, esquema SQL y diagrama ER..."):
                draft_dict = st.session_state.get("draft_spec")
                if not draft_dict:
                    draft_dict = {
                        "serviceName": design.get("serviceName"),
                        "packageName": design.get("packageName"),
                        "basePort": design.get("basePort", 8080),
                        "entities": design.get("entities", []),
                        "userStories": design.get("userStories", []),
                    }
                headers = {}
                if active_api_key:
                    headers["X-LLM-API-Key"] = active_api_key
                if active_provider:
                    headers["X-LLM-Provider"] = active_provider
                payload = {
                    "draft": draft_dict,
                    "apiKey": active_api_key,
                    "provider": active_provider,
                }
                try:
                    resp = requests.post(f"{backend_url}/api/v1/models/generate", json=payload, headers=headers, timeout=60)
                    if resp.status_code == 200:
                        st.session_state.data_model_design = resp.json()
                        st.success("🎉 ¡Modelos de dominio y esquema SQL generados exitosamente!")
                        st.info("👉 Pasa a la pestaña **'💾 3. Modelos & SQL'** para inspeccionar entidades, diagramas ER y scripts SQL.")
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")
                except Exception as e:
                    st.error(f"Error conectando con el backend: {e}")

    with col_workflow2:
        if st.button("➡️ Transferir Directo a Generación", key="btn_arch_transfer_direct", use_container_width=True):
            with st.spinner("Compilando blueprint arquitectónico y transfiriendo al generador..."):
                blueprint_payload = {
                    "serviceName": design.get("serviceName"),
                    "packageName": design.get("packageName"),
                    "basePort": design.get("basePort", 8080),
                    "entities": design.get("entities", []),
                    "userStories": design.get("userStories", []),
                }
                try:
                    resp = requests.post(f"{backend_url}/api/v1/specifications", json=blueprint_payload, timeout=10)
                    if resp.status_code == 201:
                        data = resp.json()
                        st.session_state.current_spec_id = data["specId"]
                        st.session_state.parsed_spec = data
                        st.success(f"🎉 ¡Arquitectura del microservicio '{data['serviceName']}' transferida exitosamente!")
                        st.info("👉 Pasa a la pestaña **'🚀 5. Generación & Logs'** para iniciar la compilación y pruebas autónomas.")
                    else:
                        st.error(f"Error al transferir: {resp.status_code} - {resp.text}")
                except Exception as e:
                    st.error(f"Error conectando con el backend: {e}")

