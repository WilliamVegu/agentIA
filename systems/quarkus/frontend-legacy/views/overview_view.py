import io
import json
import requests
import streamlit as st
from typing import Optional


def render_overview_view(backend_url: str, session_id: Optional[str] = None):
    """Renders the Project Overview Home View displaying executive metrics, visual pipeline, and launch modes."""
    st.subheader("🏠 Resumen del Proyecto y Control Central")

    if not session_id:
        # Quick-Start Hero Card for new microservices
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 22px; border-radius: 10px; color: white; margin-bottom: 20px;">
            <h2 style="margin:0; color:white;">⚡ Nuevo Microservicio (Inicio Rápido 1-Click)</h2>
            <p style="margin: 8px 0 0 0; opacity: 0.95; font-size: 1.02rem;">
                Crea un proyecto de microservicio completo con especificación, arquitectura 4 capas, entidades JPA, código Spring Boot 3 y suites de prueba Mockito con un solo clic.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("quick_start_form"):
            col_name, col_db = st.columns([2, 1])
            with col_name:
                service_name = st.text_input(
                    "Nombre del Microservicio",
                    value="order-service",
                    help="Identificador en minúsculas y guiones (ej. order-service, inventory-service)",
                )
            with col_db:
                db_engine = st.selectbox("Motor de Base de Datos", ["POSTGRESQL", "MYSQL", "H2"], index=0)

            prompt = st.text_area(
                "Descripción de Requisitos / Prompt del Negocio",
                value="Sistema de gestión de pedidos con clientes, items, control de estados de orden y procesamiento de pagos relacional",
                height=110,
                help="Describe el dominio de negocio, entidades principales y reglas para el microservicio",
            )

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                submit_auto = st.form_submit_button(
                    "⚡ Crear y Ejecutar Auto-Pilot Completo",
                    type="primary",
                    use_container_width=True,
                )
            with btn_col2:
                submit_step = st.form_submit_button(
                    "👣 Crear e Iniciar Modo Asistido",
                    use_container_width=True,
                )

        if submit_auto or submit_step:
            clean_name = service_name.strip() or "microservice"
            clean_prompt = prompt.strip() or f"Microservicio {clean_name}"
            is_auto = bool(submit_auto)
            try:
                with st.spinner("Creando sesión e inicializando especificación..."):
                    req_payload = {
                        "specName": clean_name,
                        "prompt": clean_prompt,
                        "databaseEngine": db_engine,
                        "autoRun": is_auto,
                    }
                    if st.session_state.get("api_key"):
                        req_payload["apiKey"] = st.session_state.get("api_key")
                    if st.session_state.get("llm_provider"):
                        req_payload["llmProvider"] = st.session_state.get("llm_provider")

                    resp = requests.post(
                        f"{backend_url}/api/v1/sessions/quick-start",
                        json=req_payload,
                        timeout=10.0,
                    )
                if resp.status_code in (200, 201, 202):
                    res_data = resp.json()
                    st.session_state.active_session_id = res_data["sessionId"]
                    st.session_state.current_spec_id = res_data.get("specId")
                    if is_auto:
                        st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                        st.success("🎉 ¡Microservicio creado y pipeline Auto-Pilot iniciado en segundo plano!")
                    else:
                        st.session_state["active_main_tab"] = "📝 1. Requisitos & Historias"
                        st.success("🎉 ¡Microservicio creado! Continúa con la revisión de requisitos.")
                    st.rerun()
                else:
                    err_msg = "Error al crear microservicio"
                    try:
                        err_payload = resp.json()
                        details = err_payload.get("details")
                        detail_text = "; ".join(details) if isinstance(details, list) else details
                        err_msg = (
                            err_payload.get("detail")
                            or err_payload.get("message")
                            or detail_text
                            or str(err_payload)
                        )
                    except Exception:
                        err_msg = resp.text or err_msg
                    st.error(f"Error ({resp.status_code}): {err_msg}")
            except Exception as e:
                st.error(f"Error de conexión con el backend: {e}")

        st.info("💡 También puedes redactar requisitos manualmente en la pestaña **'📝 1. Requisitos & Historias'** o cargar un JSON en **'📥 4. Ingesta de Especificación'**.")
        return

    try:
        resp = requests.get(f"{backend_url}/api/v1/orchestrator/sessions/{session_id}/overview", timeout=3.0)
        if resp.status_code != 200:
            st.error("No se pudo obtener el resumen de la sesión.")
            return
        overview = resp.json()
    except Exception as e:
        st.error(f"Error conectando con el orquestador: {e}")
        return

    lifecycle = overview.get("lifecycle", {})
    spec_name = overview.get("specName", "Microservicio")
    db_engine = overview.get("databaseEngine", "POSTGRESQL")
    stories_cnt = overview.get("userStoriesCount", 0)
    entities_cnt = overview.get("entitiesCount", 0)
    tests_passed = overview.get("testsPassed", False)
    sec_verdict = overview.get("securityAuditVerdict", "PENDING")
    deploy_status = overview.get("deploymentStatus", "IDLE")
    deploy_url = overview.get("deploymentUrl")
    pipeline_status = overview.get("pipelineStatus") or lifecycle.get("pipelineStatus", "IDLE")
    is_outdated = lifecycle.get("isOutdated", False)

    # Project Header Card
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">
        <h2 style="margin:0; color:white;">⚡ {spec_name}</h2>
        <p style="margin: 6px 0 0 0; opacity: 0.9;">
            Java 21 LTS &nbsp;|&nbsp; Spring Boot 3.x &nbsp;|&nbsp; Base de Datos: <strong>{db_engine}</strong> &nbsp;|&nbsp; Sesión: <code>{session_id}</code>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # In-Flight Pipeline Alerts & Quick Controls
    if pipeline_status == "RUNNING":
        st.info("⚡ **Pipeline Auto-Pilot en ejecución**: Las etapas se están generando de manera autónoma en segundo plano.")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("⏸️ Pausar Pipeline", key="ov_btn_pause", use_container_width=True):
                try:
                    requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/pause", json={"sessionId": session_id}, timeout=3.0)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        with col_p2:
            if st.button("⏹️ Cancelar Pipeline", key="ov_btn_cancel", use_container_width=True):
                try:
                    requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/cancel", json={"sessionId": session_id}, timeout=3.0)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    elif pipeline_status == "PAUSED":
        st.warning("⏸️ **Pipeline Auto-Pilot en Pausa**: La ejecución está suspendida temporalmente.")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("▶️ Reanudar Pipeline", key="ov_btn_resume", type="primary", use_container_width=True):
                try:
                    requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/resume", json={"sessionId": session_id}, timeout=3.0)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        with col_r2:
            if st.button("⏹️ Cancelar Pipeline", key="ov_btn_cancel_p", use_container_width=True):
                try:
                    requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/cancel", json={"sessionId": session_id}, timeout=3.0)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    if is_outdated:
        st.warning("⚠️ Se detectaron cambios en etapas anteriores. Algunas etapas downstream están desactualizadas.")
        if st.button("🔄 Re-sincronizar y Regenerar Fases Afectadas", key="ov_btn_resync", type="primary"):
            try:
                requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/run", json={"sessionId": session_id, "force": True}, timeout=3.0)
                st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    completion_pct = lifecycle.get("completionPercentage", 0.0)
    is_completed = (completion_pct >= 100.0 or pipeline_status == "COMPLETED")

    if is_completed:
        with st.container(border=True):
            st.success("🎉 **¡Microservicio completamente sintetizado y verificado con éxito!**")
            st.markdown(f"""
            Todos los artefactos para **`{spec_name}`** están listos y validados: historias de usuario BDD, arquitectura en 4 capas, esquema SQL relacional, código Java 21 / Spring Boot 3, pruebas unitarias Mockito, auditoría SAST con Quality Gate APROBADO y manifiestos Docker / Kubernetes.
            """)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔍 Explorar Código Fuente (Tab 6)", key="ov_btn_goto_tab6", use_container_width=True, type="primary"):
                    st.session_state["active_main_tab"] = "🔍 6. Código & Auto-Reparación"
                    st.rerun()
            with c2:
                if st.button("🛡️ Ver Quality Gate & SAST (Tab 7)", key="ov_btn_goto_tab7", use_container_width=True):
                    st.session_state["active_main_tab"] = "🛡️ 7. Seguridad & Calidad"
                    st.rerun()
            with c3:
                if st.button("📦 Descarga & Publicación Git (Tab 9)", key="ov_btn_goto_tab9", use_container_width=True):
                    st.session_state["active_main_tab"] = "📦 9. Exportación & Git"
                    st.rerun()

            with st.expander("🔄 ¿Deseas regenerar o re-ejecutar el pipeline completo?"):
                st.caption("Esto re-ejecutará todas las etapas del Auto-Pilot sobrescribiendo artefactos desactualizados.")
                if st.button("🚀 Re-ejecutar Auto-Pilot Completo", key="btn_ov_reexec", type="secondary"):
                    try:
                        r = requests.post(
                            f"{backend_url}/api/v1/orchestrator/pipeline/run",
                            json={
                                "sessionId": session_id,
                                "force": True,
                                "apiKey": st.session_state.get("api_key"),
                                "provider": st.session_state.get("llm_provider"),
                            },
                            timeout=3.0,
                        )
                        if r.status_code == 202:
                            st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Error al reiniciar pipeline"))
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        # Mode Selector Hero Section
        st.markdown("### 🎯 Selecciona tu Modo de Generación")
        col_auto, col_step = st.columns(2)

        with col_auto:
            st.markdown("""
            <div style="border: 2px solid #3B82F6; border-radius: 8px; padding: 16px; height: 100%;">
                <h4 style="margin:0; color: #1E3A8A;">🚀 Ejecutar Flujo Completo (Auto-Pilot)</h4>
                <p style="font-size: 0.9rem; color: #4B5563; margin-top: 6px;">
                    Genera el microservicio de principio a fin de forma 100% desatendida. Sintetiza historias, arquitectura, persistencia SQL, código Java, pruebas Mockito, auditoría SAST y contenedores Docker.
                </p>
            </div>
            """, unsafe_allow_html=True)

            cur_key = (st.session_state.get("api_key") or "").strip()
            if not cur_key or cur_key in ("mock-key", "test-key", "mock"):
                engine_desc = "⚪ Motor Mock (Offline / Sin llamadas a red)"
            elif cur_key.startswith("AIza") or cur_key.startswith("AQ."):
                engine_desc = "🟢 Google Gemini (gemini-3.6-flash)"
            elif cur_key.startswith("gsk_"):
                engine_desc = "🟢 Groq Cloud (qwen/qwen3.8-27b)"
            elif cur_key.startswith("sk-"):
                engine_desc = "🟢 OpenAI (gpt-4o-mini)"
            else:
                engine_desc = f"🟡 Proveedor ({st.session_state.get('llm_provider') or 'Autodetect'})"

            st.caption(f"🧠 Motor configurado: **{engine_desc}**")

            if st.button(
                "🚀 Iniciar Auto-Pilot Ahora",
                key="ov_btn_start_autopilot",
                type="primary",
                use_container_width=True,
                disabled=(pipeline_status == "RUNNING"),
            ):
                try:
                    r = requests.post(
                        f"{backend_url}/api/v1/orchestrator/pipeline/run",
                        json={
                            "sessionId": session_id,
                            "apiKey": st.session_state.get("api_key"),
                            "provider": st.session_state.get("llm_provider"),
                        },
                        timeout=3.0,
                    )
                    if r.status_code == 202:
                        st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                        st.success("🎉 ¡Auto-Pilot en ejecución! Redirigiendo a Generación & Logs...")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Error al iniciar Auto-Pilot"))
                except Exception as e:
                    st.error(f"Error: {e}")

        with col_step:
            st.markdown("""
            <div style="border: 2px solid #10B981; border-radius: 8px; padding: 16px; height: 100%;">
                <h4 style="margin:0; color: #065F46;">👣 Modo Paso a Paso (Asistido)</h4>
                <p style="font-size: 0.9rem; color: #4B5563; margin-top: 6px;">
                    Avanza etapa por etapa revisando y aprobando cada artefacto de diseño antes de continuar. Ideal si deseas ajustar historias de usuario, diagramas de arquitectura o esquemas relacionales.
                </p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("👣 Continuar en Modo Asistido", key="ov_btn_continue_assisted", use_container_width=True):
                next_target = lifecycle.get("nextTargetPhase") or "SPECIFICATION"
                tab_map = {
                    "SPECIFICATION": "📝 1. Requisitos & Historias",
                    "ARCHITECTURE": "🏗️ 2. Diseño Arquitectónico",
                    "DATA_MODEL": "💾 3. Modelos & SQL",
                    "CODE_GENERATION": "🚀 5. Generación & Logs",
                    "SECURITY_AUDIT": "🛡️ 7. Seguridad & Calidad",
                    "DEPLOYMENT": "🚀 8. DevOps & Despliegue",
                    "VERIFIED": "📦 9. Exportación & Git",
                }
                target_tab = tab_map.get(next_target, "📝 1. Requisitos & Historias")
                st.session_state["active_main_tab"] = target_tab
                st.rerun()

    st.markdown("---")

    # Milestone Metrics Grid
    st.markdown("### 📊 Métricas Clave del Microservicio")
    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        st.metric("Historias BDD", f"{stories_cnt}", help="Historias de usuario sintetizadas")
    with m2:
        st.metric("Entidades SQL", f"{entities_cnt}", help="Tablas y entidades relacionales")
    with m3:
        test_badge = "✅ Aprobadas" if tests_passed else "⏳ Pendiente"
        st.metric("Suites de Tests", test_badge)
    with m4:
        gate_badge = "✅ APROBADO" if sec_verdict == "PASS" else ("🛑 BLOQUEADO" if sec_verdict == "BLOCKED" else "⏳ PENDIENTE")
        st.metric("Quality Gate", gate_badge)
    with m5:
        st.metric("Despliegue", str(deploy_status))

    if deploy_url:
        st.success(f"🔗 Contenedor activo: [{deploy_url}]({deploy_url})")

    st.markdown("---")

    # One-Click Full Bundle Export
    st.markdown("### 📦 Descarga de Entregables")
    st.markdown("Descarga el paquete de entrega completo con especificación, código fuente Spring Boot, suites de prueba, esquemas SQL, Dockerfile, Compose, CI/CD y manifiestos de Kubernetes en un único archivo ZIP estructurado.")

    try:
        export_resp = requests.get(f"{backend_url}/api/v1/orchestrator/sessions/{session_id}/export-bundle", timeout=5.0)
        if export_resp.status_code == 200:
            st.download_button(
                label="📦 Descargar Bundle Completo (ZIP)",
                key="ov_dl_bundle_zip",
                data=export_resp.content,
                file_name=f"{spec_name.lower()}-complete-bundle.zip",
                mime="application/zip",
                type="secondary",
            )
        else:
            st.button("📦 Descargar Bundle Completo (ZIP)", key="ov_btn_bundle_dis_1", disabled=True)
    except Exception:
        st.button("📦 Descargar Bundle Completo (ZIP)", key="ov_btn_bundle_dis_2", disabled=True)

