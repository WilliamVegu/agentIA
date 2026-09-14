import json
import uuid
import requests
import streamlit as st

def render_requirements_view(backend_url: str, openai_key: str = None, provider: str = None, session_id: str = None):
    st.header("📝 Redacción y Asistente de Requisitos con IA")
    st.markdown(
        "El asistente descompone los requisitos en **Historias de Usuario canonicales**, "
        "criterios de aceptación **Given/When/Then** (éxito + validación de error) "
        "y **Entidades del Dominio** fuertemente tipadas. Puedes generarlas con IA con un solo clic y luego revisarlas y ajustarlas a tu gusto."
    )

    active_session_id = session_id or st.session_state.get("active_session_id")

    # Resolve ephemeral API key, provider and model
    active_api_key = openai_key or st.session_state.get("api_key") or st.session_state.get("openai_key")
    active_provider = provider or st.session_state.get("llm_provider")
    active_model = st.session_state.get("llm_model")

    # Constitution Principle VI Guard
    if not active_api_key:
        st.warning(
            "🔒 **Clave de API requerida**: Ingresa tu API Key (Gemini, Groq u OpenAI) en la barra lateral "
            "(`Credenciales Efímeras`). "
            "\n*Nota: ¡Puedes usar **Google Gemini** o **Groq** 100% gratis sin tarjeta de crédito, o ingresar `mock-key` para modo local sin internet!*"
        )

    # Initialize draft state
    if "draft_spec" not in st.session_state:
        st.session_state.draft_spec = None

    # Auto-load session requirements / prompt if available
    session_prompt = ""
    session_service_name = "order-service"
    if active_session_id:
        try:
            req_info_resp = requests.get(f"{backend_url}/api/v1/requirements/sessions/{active_session_id}", timeout=3.0)
            if req_info_resp.status_code == 200:
                s_data = req_info_resp.json()
                session_service_name = s_data.get("serviceName", "order-service")
                raw_p = s_data.get("rawPrompt", "")
                if raw_p:
                    # Clean markdown header if present
                    lines = [l for l in raw_p.split("\n") if not l.startswith("#")]
                    session_prompt = "\n".join(lines).strip()
                if s_data.get("hasDraft") and st.session_state.draft_spec is None:
                    st.session_state.draft_spec = s_data.get("draft")
        except Exception:
            pass

    # Step 1: Requirements Ingestion / Generation Section
    if st.session_state.draft_spec is None:
        st.markdown(f"""
        <div style="background-color: #1E293B; border: 1px solid #3B82F6; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h4 style="margin: 0 0 8px 0; color: #60A5FA;">✨ Generación Inteligente de Historias (Modo Asistido)</h4>
            <p style="margin: 0 0 12px 0; font-size: 0.95rem; color: #CBD5E1;">
                Microservicio activo: <b><code>{session_service_name}</code></b>.<br/>
                Pulsa el botón a continuación para que la IA sintetice automáticamente todas las historias de usuario y entidades de dominio basándose en tu requerimiento.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if session_prompt:
            btn_quick_generate = st.button(
                f"✨ Generar Historias y Criterios BDD con IA ({active_model or 'Gemini 3.6'})",
                type="primary",
                use_container_width=True,
                disabled=not active_api_key,
                key="btn_quick_gen_reqs",
            )
            if btn_quick_generate:
                with st.spinner("Generando historias de usuario, criterios Given/When/Then y entidades con IA..."):
                    payload = {
                        "rawText": session_prompt,
                        "serviceName": session_service_name,
                        "packageName": f"com.corp.{session_service_name.lower().replace('-', '.')}",
                        "apiKey": active_api_key,
                        "provider": active_provider,
                        "modelName": active_model,
                    }
                    try:
                        resp = requests.post(f"{backend_url}/api/v1/requirements/transform", json=payload, timeout=45)
                        if resp.status_code == 200:
                            st.session_state.draft_spec = resp.json()
                            if active_session_id:
                                requests.post(f"{backend_url}/api/v1/requirements/sessions/{active_session_id}/save", json=st.session_state.draft_spec)
                            st.success("🎉 ¡Historias y entidades generadas! Ahora revísalas y modifícalas abajo.")
                            st.rerun()
                        else:
                            st.error(f"Error ({resp.status_code}): {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con backend: {e}")

    with st.expander("📝 Editor / Entrada Manual de Requisitos", expanded=(st.session_state.draft_spec is None and not session_prompt)):
        col_text, col_meta = st.columns([3, 1])
        with col_text:
            raw_text = st.text_area(
                "Describe las capacidades y reglas del microservicio:",
                value=session_prompt,
                height=180,
                placeholder=(
                    "Ejemplo:\n"
                    "- El cliente debe poder consultar y registrar órdenes de compra con su email y lista de productos.\n"
                    "- Cada orden debe tener un monto total en BigDecimal y estado PENDING o APPROVED.\n"
                    "- No se permiten órdenes con monto cero o negativo.\n"
                    "- Debe emitir un error 400 cuando el email sea inválido."
                ),
            )
        with col_meta:
            service_name_input = st.text_input(
                "Nombre sugerido (Opcional):",
                value=session_service_name,
                placeholder="order-service",
                help="Formato kebab-case, e.g. billing-service",
            )
            package_name_input = st.text_input(
                "Paquete Java (Opcional):",
                value=f"com.corp.{session_service_name.lower().replace('-', '.')}",
                placeholder="com.corp.order",
                help="e.g. com.corp.billing",
            )

            transform_clicked = st.button(
                "✨ Transformar a Historias",
                type="primary",
                use_container_width=True,
                disabled=not active_api_key,
                key="btn_req_transform_manual",
            )

        if transform_clicked:
            if not raw_text or len(raw_text.strip()) < 10:
                st.error("Por favor ingresa al menos 10 caracteres describiendo los requisitos.")
            else:
                with st.spinner("Descomponiendo requisitos en Historias y Criterios Given/When/Then..."):
                    payload = {
                        "rawText": raw_text.strip(),
                        "serviceName": service_name_input.strip() if service_name_input else None,
                        "packageName": package_name_input.strip() if package_name_input else None,
                        "apiKey": active_api_key,
                        "provider": active_provider,
                        "modelName": active_model,
                    }
                    try:
                        headers = {}
                        if active_api_key:
                            headers["X-LLM-API-Key"] = active_api_key
                        if active_provider:
                            headers["X-LLM-Provider"] = active_provider
                        resp = requests.post(
                            f"{backend_url}/api/v1/requirements/transform",
                            json=payload,
                            headers=headers,
                            timeout=45,
                        )
                        if resp.status_code == 200:
                            st.session_state.draft_spec = resp.json()
                            if active_session_id:
                                requests.post(f"{backend_url}/api/v1/requirements/sessions/{active_session_id}/save", json=st.session_state.draft_spec)
                            st.success("✅ Requisitos transformados con éxito! Revisa y ajusta abajo.")
                            st.rerun()
                        elif resp.status_code == 401:
                            st.error("❌ Error 401: Clave de API no válida o ausente.")
                        else:
                            st.error(f"Error {resp.status_code}: {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")

    # If draft is available, show review and editing controls
    if st.session_state.draft_spec:
        draft = st.session_state.draft_spec

        st.markdown("---")
        st.subheader("📋 2. Revisión y Ajustes de la Especificación")

        # Metadata summary
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            draft["serviceName"] = st.text_input("Nombre del Microservicio:", value=draft.get("serviceName", "app-service"))
        with m_col2:
            draft["packageName"] = st.text_input("Paquete Base Java:", value=draft.get("packageName", "com.corp.app"))
        with m_col3:
            draft["basePort"] = st.number_input("Puerto Base:", value=int(draft.get("basePort", 8080)), min_value=1024, max_value=65535)

        # Domain Entities Section
        with st.expander(f"🏛️ Entidades del Dominio Extraídas ({len(draft.get('entities', []))})", expanded=True):
            entities = draft.get("entities", [])
            for ent_idx, ent in enumerate(entities):
                st.markdown(f"#### Entidad: `{ent.get('name')}` (Tabla: `{ent.get('tableName')}`)")
                attrs = ent.get("attributes", [])
                
                # Attribute display & edits
                for a_idx, attr in enumerate(attrs):
                    a_col1, a_col2, a_col3, a_col4 = st.columns([3, 3, 2, 2])
                    with a_col1:
                        attr["name"] = st.text_input(f"Atributo #{a_idx+1}", value=attr.get("name", ""), key=f"ent_{ent_idx}_attr_name_{a_idx}")
                    with a_col2:
                        type_options = ["String", "Long", "BigDecimal", "Boolean", "DateTime", "UUID", "Integer"]
                        cur_type = attr.get("type", "String")
                        idx_type = type_options.index(cur_type) if cur_type in type_options else 0
                        attr["type"] = st.selectbox(f"Tipo #{a_idx+1}", type_options, index=idx_type, key=f"ent_{ent_idx}_attr_type_{a_idx}")
                    with a_col3:
                        attr["isPrimaryKey"] = st.checkbox("PK (Clave)", value=attr.get("isPrimaryKey", False), key=f"ent_{ent_idx}_pk_{a_idx}")
                    with a_col4:
                        attr["nullable"] = st.checkbox("Nullable", value=attr.get("nullable", False), key=f"ent_{ent_idx}_null_{a_idx}")

                if st.button(f"➕ Agregar Atributo a {ent.get('name')}", key=f"btn_add_attr_{ent_idx}"):
                    attrs.append({"name": "nuevoCampo", "type": "String", "nullable": False, "isPrimaryKey": False, "validationRules": []})
                    st.rerun()

        # User Stories & Acceptance Criteria Section
        with st.expander(f"📖 Historias de Usuario & Criterios BDD ({len(draft.get('userStories', []))})", expanded=True):
            user_stories = draft.get("userStories", [])
            stories_to_delete = []

            for s_idx, story in enumerate(user_stories):
                st.markdown(f"### {story.get('id', f'US-{s_idx+1}')}: Como {story.get('role')} quiero {story.get('intent')}")
                st_col1, st_col2, st_col3, st_col4 = st.columns([2, 4, 4, 2])
                with st_col1:
                    story["priority"] = st.selectbox(
                        "Prioridad:",
                        ["P1", "P2", "P3"],
                        index=["P1", "P2", "P3"].index(story.get("priority", "P1")),
                        key=f"st_prio_{s_idx}"
                    )
                with st_col2:
                    story["role"] = st.text_input("Como (Rol):", value=story.get("role", ""), key=f"st_role_{s_idx}")
                with st_col3:
                    story["intent"] = st.text_input("Quiero (Acción):", value=story.get("intent", ""), key=f"st_intent_{s_idx}")
                with st_col4:
                    story["benefit"] = st.text_input("Para (Beneficio):", value=story.get("benefit", ""), key=f"st_benefit_{s_idx}")

                st.markdown("**Escenarios Given/When/Then:**")
                scenarios = story.get("scenarios", [])
                sc_to_delete = []
                for sc_idx, sc in enumerate(scenarios):
                    sc_col1, sc_col2, sc_col3, sc_col4 = st.columns([4, 4, 4, 1])
                    with sc_col1:
                        sc["given"] = st.text_input(f"Given ({sc.get('scenarioId')}):", value=sc.get("given", ""), key=f"given_{s_idx}_{sc_idx}")
                    with sc_col2:
                        sc["when"] = st.text_input("When:", value=sc.get("when", ""), key=f"when_{s_idx}_{sc_idx}")
                    with sc_col3:
                        sc["then"] = st.text_input("Then:", value=sc.get("then", ""), key=f"then_{s_idx}_{sc_idx}")
                    with sc_col4:
                        st.write("")
                        if st.button("🗑️", key=f"del_sc_{s_idx}_{sc_idx}", help="Eliminar escenario"):
                            sc_to_delete.append(sc_idx)

                for del_sc in reversed(sc_to_delete):
                    if len(scenarios) > 1:
                        scenarios.pop(del_sc)
                        st.rerun()
                    else:
                        st.warning("Cada historia debe conservar al menos 1 escenario de aceptación.")

                b_col1, b_col2 = st.columns([1, 4])
                with b_col1:
                    if st.button(f"➕ Escenario a {story.get('id')}", key=f"btn_add_sc_{s_idx}"):
                        new_sc_id = f"AC-{s_idx+1}.{len(scenarios)+1}"
                        scenarios.append({
                            "scenarioId": new_sc_id,
                            "given": "precondición válida",
                            "when": "acción del usuario",
                            "then": "resultado esperado",
                        })
                        st.rerun()
                with b_col2:
                    if st.button(f"🗑️ Eliminar Historia {story.get('id')}", key=f"btn_del_story_{s_idx}"):
                        stories_to_delete.append(s_idx)

                st.markdown("---")

            for del_st in reversed(stories_to_delete):
                user_stories.pop(del_st)
                st.rerun()

            if st.button("➕ Agregar Nueva Historia de Usuario", key="btn_req_add_story"):
                new_idx = len(user_stories) + 1
                user_stories.append({
                    "id": f"US-{new_idx}",
                    "priority": "P2",
                    "role": "Usuario",
                    "intent": "realizar una acción",
                    "benefit": "obtener un beneficio",
                    "scenarios": [
                        {"scenarioId": f"AC-{new_idx}.1", "given": "estado inicial", "when": "evento", "then": "resultado exitoso"},
                        {"scenarioId": f"AC-{new_idx}.2", "given": "condición inválida", "when": "evento", "then": "error manejado"}
                    ]
                })
                st.rerun()

        # Step 3: Natural Language Refinement Section (US2)
        st.markdown("---")
        st.subheader("🔄 3. Asistente de Refinamiento Iterativo con IA")
        st.caption("Envía instrucciones en lenguaje natural para que el LLM refine o agregue criterios específicos.")

        refine_col_prompt, refine_col_target, refine_col_btn = st.columns([3, 1, 1])
        with refine_col_prompt:
            refine_prompt = st.text_input(
                "Sugerencia de cambio o refinamiento:",
                placeholder="Ej: Agrega un escenario de error cuando el saldo sea insuficiente para US-1",
            )
        with refine_col_target:
            story_options = ["Todas"] + [s.get("id") for s in draft.get("userStories", [])]
            target_story = st.selectbox("Historia objetivo:", story_options)
        with refine_col_btn:
            st.write("")
            refine_clicked = st.button("🔄 Refinar con IA", key="btn_req_refine_with_ai", type="secondary", use_container_width=True, disabled=not active_api_key)

        if refine_clicked:
            if not refine_prompt or len(refine_prompt.strip()) < 3:
                st.error("Por favor escribe una instrucción de refinamiento clara.")
            else:
                with st.spinner("Refinando especificación con IA..."):
                    refine_payload = {
                        "currentDraft": draft,
                        "feedbackPrompt": refine_prompt.strip(),
                        "targetStoryId": None if target_story == "Todas" else target_story,
                        "apiKey": active_api_key,
                    }
                    try:
                        headers = {"X-LLM-API-Key": active_api_key} if active_api_key else {}
                        resp = requests.post(
                            f"{backend_url}/api/v1/requirements/refine",
                            json=refine_payload,
                            headers=headers,
                            timeout=45,
                        )
                        if resp.status_code == 200:
                            st.session_state.draft_spec = resp.json()
                            st.success("✅ Especificación refinada con éxito!")
                            st.rerun()
                        else:
                            st.error(f"Error al refinar: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")

        # Step 4: Export and Pipeline Handoff Section (US4)
        st.markdown("---")
        st.subheader("🚀 4. Flujo de Arquitectura, Exportación y Transferencia")
        st.caption("Avanza al diseño arquitectónico formal de 4 capas y endpoints, o descarga y transfiere directamente.")

        out_col_arch, out_col_dl, out_col_gen = st.columns([2, 1, 2])
        with out_col_arch:
            if st.button("🏗️ Aprobar y Diseñar Arquitectura (Fase 2)", key="btn_req_approve_design_arch", type="primary", use_container_width=True, disabled=not active_api_key):
                with st.spinner("Sintetizando topología en 4 capas, endpoints y diagrama Mermaid con IA..."):
                    payload = {
                        "draft": draft,
                        "apiKey": active_api_key,
                        "provider": active_provider,
                    }
                    try:
                        headers = {"X-LLM-API-Key": active_api_key} if active_api_key else {}
                        resp = requests.post(
                            f"{backend_url}/api/v1/architecture/design",
                            json=payload,
                            headers=headers,
                            timeout=45,
                        )
                        if resp.status_code == 200:
                            st.session_state.architecture_design = resp.json()
                            if active_session_id:
                                requests.post(f"{backend_url}/api/v1/requirements/sessions/{active_session_id}/save", json=draft)
                                requests.post(f"{backend_url}/api/v1/orchestrator/sessions/{active_session_id}/transition", json={"targetPhase": "ARCHITECTURE"})
                            st.success("✅ ¡Historias aprobadas y arquitectura diseñada exitosamente!")
                            st.session_state["active_main_tab"] = "🏗️ 2. Diseño Arquitectónico"
                            st.rerun()
                        else:
                            st.error(f"Error al diseñar arquitectura: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")

        with out_col_dl:
            # Re-render markdown if needed
            markdown_content = draft.get("markdownSpec", "")
            st.download_button(
                label="📥 Descargar spec.md (Spec Kit)",
                key="dl_req_spec_md",
                data=markdown_content.encode("utf-8"),
                file_name=f"spec-{draft.get('serviceName', 'service')}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with out_col_gen:
            if st.button("➡️ Transferir Directo a Generación", key="btn_req_transfer_direct", type="secondary", use_container_width=True):
                with st.spinner("Transfiriendo especificación al motor de generación..."):
                    blueprint_payload = {
                        "serviceName": draft.get("serviceName"),
                        "packageName": draft.get("packageName"),
                        "basePort": draft.get("basePort", 8080),
                        "entities": draft.get("entities", []),
                        "userStories": draft.get("userStories", []),
                    }
                    try:
                        resp = requests.post(
                            f"{backend_url}/api/v1/specifications",
                            json=blueprint_payload,
                            timeout=10,
                        )
                        if resp.status_code == 201:
                            data = resp.json()
                            st.session_state.current_spec_id = data["specId"]
                            st.session_state.parsed_spec = data
                            st.success(f"🎉 ¡Especificación '{data['serviceName']}' transferida exitosamente!")
                            st.info("👉 Pasa a la pestaña **'🚀 5. Generación & Logs'** para iniciar la compilación y pruebas autónomas.")
                        else:
                            st.error(f"Error al transferir: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")

