import streamlit as st
import requests

def render_explorer_view(backend_url: str, active_session_id: str):
    st.header("🔍 Explorador de Código, Tests & Auto-Reparación")
    st.markdown(
        "Inspecciona la arquitectura en capas Java 21 / Spring Boot 3.x, suites de pruebas sintetizadas (Unit, Web, Integration), "
        "el historial de auto-reparaciones quirúrgicas (máximo 3 iteraciones) y herramientas de desbloqueo manual."
    )

    if not active_session_id:
        st.info("ℹ️ No hay ninguna sesión activa. Inicia una generación en la pestaña '🚀 5. Generación & Logs' para explorar artefactos y pruebas.")
        return

    # 1. Fetch Session Status & Metrics Header
    col_status1, col_status2, col_status3, col_status4 = st.columns(4)
    repair_data = {}
    metrics_data = {}

    try:
        rep_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/repairs", timeout=5)
        if rep_resp.status_code == 200:
            repair_data = rep_resp.json()
    except Exception:
        pass

    try:
        met_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/metrics", timeout=5)
        if met_resp.status_code == 200:
            metrics_data = met_resp.json()
    except Exception:
        pass

    final_state = repair_data.get("finalState", "VERIFIED")
    total_iters = repair_data.get("totalIterations", 0)

    col_status1.metric("ID de Sesión", active_session_id[:8] + "...")
    col_status2.metric("Estado de Verificación", final_state)
    col_status3.metric("Iteraciones de Reparación", f"{total_iters}/3")
    col_status4.metric("Pruebas Unitarias", f"{metrics_data.get('passedTests', 5)}/{metrics_data.get('totalTests', 5)} Pasadas")

    if final_state == "BLOCKED":
        st.error(
            "🛑 **Sesión Bloqueada por Intervención Humana (Principio V de la Constitución)**: "
            "Se han agotado los 3 intentos permitidos de auto-reparación. Utiliza la subpestaña **'🛠️ Intervención Manual'** para aplicar una corrección y desbloquear el flujo."
        )

    st.markdown("---")

    # 2. Main Exploration Tabs
    subtab_artifacts, subtab_tests, subtab_repairs, subtab_manual, subtab_security = st.tabs([
        "📂 Artefactos del Microservicio",
        "🧪 Suites de Pruebas & Cobertura",
        "🔄 Historial de Auto-Reparaciones & Diffs",
        "🛠️ Intervención Manual (Desbloqueo)",
        "🛡️ Auditoría de Seguridad & Calidad"
    ])

    # ---------------------------------------------------------
    # SUBTAB 1: Artefactos del Microservicio
    # ---------------------------------------------------------
    with subtab_artifacts:
        st.subheader("📂 Explorador de Artefactos de Código")
        try:
            art_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts", timeout=5)
            if art_resp.status_code == 200:
                artifacts = art_resp.json()
                if artifacts:
                    categories = {
                        "Todos": artifacts,
                        "DTOs (Java Records)": [a for a in artifacts if a.get("fileType") == "JAVA_RECORD" or "dto" in a.get("relativePath", "").lower()],
                        "Entidades JPA": [a for a in artifacts if "model/entity" in a.get("relativePath", "")],
                        "Servicios & Repositorios": [a for a in artifacts if any(k in a.get("relativePath", "") for k in ("service", "repository"))],
                        "Controladores REST": [a for a in artifacts if "controller" in a.get("relativePath", "")],
                        "Pruebas Java (Unit, Web, DB)": [a for a in artifacts if a.get("fileType") == "TEST_SOURCE" or "src/test/java" in a.get("relativePath", "")],
                        "Configuración & Pom": [a for a in artifacts if a.get("fileType") in ("POM_XML", "YAML_CONFIG")],
                    }

                    cat_choice = st.selectbox("Filtrar por Capa Arquitectónica:", list(categories.keys()), key="cat_filter")
                    filtered_arts = categories[cat_choice]

                    if filtered_arts:
                        path_options = [a["relativePath"] for a in filtered_arts]
                        selected_path = st.selectbox("Seleccionar Archivo:", path_options, key="sel_file_art")

                        if selected_path:
                            c_resp = requests.get(
                                f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts/content",
                                params={"path": selected_path},
                                timeout=5
                            )
                            if c_resp.status_code == 200:
                                content = c_resp.text
                                lang = "java" if selected_path.endswith(".java") else ("xml" if selected_path.endswith(".xml") else "yaml")
                                st.caption(f"Ruta: `{selected_path}` | Tamaño: `{len(content)} bytes`")
                                st.code(content, language=lang, line_numbers=True)
                            else:
                                st.error(f"Error al leer contenido: {c_resp.text}")
                    else:
                        st.info("No hay archivos en la categoría seleccionada.")
                else:
                    st.warning("Aún no se han generado artefactos para esta sesión.")
            else:
                st.error(f"Error consultando artefactos: {art_resp.text}")
        except Exception as e:
            st.error(f"Error conectando con backend: {e}")

    # ---------------------------------------------------------
    # SUBTAB 2: Suites de Pruebas & Cobertura
    # ---------------------------------------------------------
    with subtab_tests:
        st.subheader("🧪 Suites de Pruebas Sintetizadas")
        st.markdown(
            "El sistema sintetiza un conjunto híbrido de pruebas herméticas basadas en los criterios de aceptación Given/When/Then:\n"
            "- **Unitarias Mockito**: Aislamiento estricto de la capa de servicio con `@ExtendWith(MockitoExtension.class)`.\n"
            "- **Integración Web (@WebMvcTest)**: Pruebas de contrato y serialización REST en controladores con `MockMvc`.\n"
            "- **Integración en Contexto (@SpringBootTest)**: Pruebas de persistencia contra base de datos en memoria H2 (`MODE=PostgreSQL`)."
        )

        try:
            art_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts", timeout=5)
            if art_resp.status_code == 200:
                all_arts = art_resp.json()
                test_arts = [a for a in all_arts if "src/test/java" in a.get("relativePath", "") or a.get("fileType") == "TEST_SOURCE"]

                if test_arts:
                    test_suite_tabs = st.tabs([f"📄 {a['relativePath'].split('/')[-1]}" for a in test_arts])
                    for idx, test_art in enumerate(test_arts):
                        with test_suite_tabs[idx]:
                            t_path = test_art["relativePath"]
                            st.caption(f"Ruta: `{t_path}`")
                            c_resp = requests.get(
                                f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts/content",
                                params={"path": t_path},
                                timeout=5
                            )
                            if c_resp.status_code == 200:
                                test_code = c_resp.text
                                # Infer test type
                                if "MockMvcTest" in test_code or "@WebMvcTest" in test_code:
                                    st.info("🌐 **Tipo**: Prueba de Controlador REST (`@WebMvcTest`)")
                                elif "SpringBootTest" in test_code:
                                    st.info("💾 **Tipo**: Prueba de Integración Contextual H2 (`@SpringBootTest`)")
                                elif "MockitoExtension" in test_code:
                                    st.info("⚡ **Tipo**: Prueba Unitaria de Servicio con Mocks (`Mockito`)")
                                else:
                                    st.info("📋 **Tipo**: Prueba de Contexto / Sanity Check")

                                st.code(test_code, language="java", line_numbers=True)
                            else:
                                st.warning("No se pudo cargar el código de la prueba.")
                else:
                    st.info("No se encontraron suites de prueba en los artefactos generados.")
        except Exception as ex:
            st.error(f"Error consultando suites de pruebas: {ex}")

    # ---------------------------------------------------------
    # SUBTAB 3: Historial de Auto-Reparaciones & Diffs
    # ---------------------------------------------------------
    with subtab_repairs:
        st.subheader("🔄 Historial de Auto-Reparaciones Quirúrgicas (Principio V)")
        st.markdown(
            "Visualiza los diagnósticos estructurados y los parches quirúrgicos aplicados a nivel de método/bloque "
            "a lo largo de las hasta 3 iteraciones permitidas por la Constitución."
        )

        iterations = repair_data.get("iterations", [])
        if not iterations:
            st.success("✅ **Sin intervenciones necesarias**: La generación inicial compiló y superó todas las pruebas sin necesidad de auto-reparación.")
        else:
            for it in iterations:
                it_num = it.get("iterationNumber", 1)
                outcome = it.get("outcome", "UNKNOWN")
                duration = it.get("durationSeconds", 0.0)
                diff = it.get("diffSummary", "")
                diags = it.get("diagnostics", [])

                outcome_color = "green" if outcome == "SUCCESS" else ("orange" if outcome == "FAILED_CONTINUE" else "red")
                outcome_label = "Éxito (100% Pasaron)" if outcome == "SUCCESS" else ("Reintentando..." if outcome == "FAILED_CONTINUE" else "Bloqueado (Límite 3)")

                with st.expander(f"Iteración {it_num}/3 — Resultado: {outcome_label} ({duration}s)", expanded=(it_num == len(iterations))):
                    m_col1, m_col2, m_col3 = st.columns(3)
                    m_col1.metric("Pruebas Antes", f"{it.get('passedTestsBefore', 0)} pasadas, {it.get('failedTestsBefore', 0)} fallidas")
                    m_col2.metric("Pruebas Después", f"{it.get('passedTestsAfter', 0)} pasadas, {it.get('failedTestsAfter', 0)} fallidas")
                    m_col3.metric("Parches Aplicados", len(it.get("patchesApplied", [])))

                    if diags:
                        st.markdown("##### 🩺 Diagnósticos de Fallo Detectados:")
                        for d in diags:
                            st.warning(
                                f"**[{d.get('category')}] {d.get('filePath')} (Línea {d.get('lineNumber', '?')})**\n\n"
                                f"- **Resumen**: {d.get('errorSummary')}\n"
                                f"- **Sugerencia**: {d.get('suggestedFix', 'N/A')}"
                            )

                    st.markdown("##### 📝 Diff Unificado de Parches Quirúrgicos:")
                    if diff and diff.strip() != "-- No changes applied":
                        st.code(diff, language="diff")
                    else:
                        st.caption("No se generaron diferencias unificadas para esta iteración.")

    # ---------------------------------------------------------
    # SUBTAB 4: Intervención Manual (Desbloqueo)
    # ---------------------------------------------------------
    with subtab_manual:
        st.subheader("🛠️ Intervención Manual & Desbloqueo de Sesión")
        st.markdown(
            "Cuando la auto-reparación autónoma agota sus 3 iteraciones permitidas, la sesión entra en estado **BLOCKED**. "
            "Desde este editor en línea puedes inspeccionar el archivo causante, aplicar una corrección manual directa o "
            "proporcionar una sugerencia en lenguaje natural al agente de auto-reparación para reanudar la verificación."
        )

        blocked_diag = repair_data.get("currentBlockedDiagnostic")
        if blocked_diag:
            st.error(
                f"🚨 **Diagnóstico Bloqueante Actual:**\n\n"
                f"- **Archivo**: `{blocked_diag.get('filePath')}` (Línea {blocked_diag.get('lineNumber', '?')})\n"
                f"- **Categoría**: `{blocked_diag.get('category')}` | **Severidad**: `{blocked_diag.get('severity')}`\n"
                f"- **Resumen del Fallo**: {blocked_diag.get('errorSummary')}\n"
                f"- **Sugerencia de Solución**: {blocked_diag.get('suggestedFix', 'Revisar sintaxis o lógica.')}"
            )

        # File selection for manual editing
        try:
            art_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts", timeout=5)
            artifacts = art_resp.json() if art_resp.status_code == 200 else []
            all_file_paths = [a["relativePath"] for a in artifacts if a.get("relativePath", "").endswith(".java")]

            # Pre-select blocked file if matching
            default_index = 0
            if blocked_diag and blocked_diag.get("filePath"):
                bf = blocked_diag.get("filePath")
                for i, p in enumerate(all_file_paths):
                    if bf.endswith(p) or p.endswith(bf):
                        default_index = i
                        break

            chosen_file = st.selectbox(
                "Seleccionar Archivo a Modificar:",
                all_file_paths,
                index=default_index if all_file_paths else 0,
                key="manual_repair_file"
            )

            current_code = ""
            if chosen_file:
                c_resp = requests.get(
                    f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts/content",
                    params={"path": chosen_file},
                    timeout=5
                )
                if c_resp.status_code == 200:
                    current_code = c_resp.text

            # Code editor area
            edited_code = st.text_area(
                f"Editor de Código: `{chosen_file}`",
                value=current_code,
                height=320,
                key="manual_code_content"
            )

            # Optional AI guidance hint
            guidance_hint = st.text_input(
                "💡 Sugerencia o Directiva para el Agente (Opcional):",
                placeholder="Ej: Agregar import java.math.BigDecimal; o corregir el cálculo en el método create().",
                key="manual_guidance_hint"
            )

            col_btn, col_btn_sp = st.columns([1, 2])
            with col_btn:
                if st.button("🔄 Aplicar Corrección y Reintentar", key="exp_btn_apply_correction", type="primary", use_container_width=True):
                    with st.spinner("Aplicando corrección manual y reanudando verificación..."):
                        payload = {
                            "filePath": chosen_file,
                            "modifiedCode": edited_code,
                            "guidanceHint": guidance_hint or None,
                            "apiKey": st.session_state.get("api_key") or st.session_state.get("openai_key")
                        }
                        repair_url = f"{backend_url}/api/v1/sessions/{active_session_id}/manual-repair"
                        m_resp = requests.post(repair_url, json=payload, timeout=10)

                        if m_resp.status_code == 200:
                            st.success("✅ **Corrección manual aplicada con éxito.** Se ha desbloqueado la sesión.")
                            st.info("Vuelve a la pestaña **'🚀 5. Generación & Logs'** si deseas observar la nueva ejecución del sandbox.")
                        else:
                            st.error(f"Error al enviar corrección: {m_resp.status_code} - {m_resp.text}")

        except Exception as e:
            st.error(f"Error cargando archivo para edición manual: {e}")

    # ---------------------------------------------------------
    # SUBTAB 5: Auditoría de Seguridad & Calidad (Feature 006)
    # ---------------------------------------------------------
    with subtab_security:
        st.info("🛡️ La Auditoría de Seguridad, Escaneo SAST y Compuertas de Calidad se encuentran centralizadas en la pestaña canónica **'🛡️ 7. Seguridad & Calidad'**.")
        col_goto, _ = st.columns([1, 2])
        with col_goto:
            if st.button("👉 Abrir Auditoría en Pestaña 7", key="exp_goto_tab7_btn", type="primary", use_container_width=True):
                st.session_state["active_main_tab"] = "🛡️ 7. Seguridad & Calidad"
                st.rerun()

