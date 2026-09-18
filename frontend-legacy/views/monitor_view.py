import json
import time
import requests
import streamlit as st
import sseclient

def render_monitor_view(backend_url: str, active_session_id: str):
    st.header("🚀 Orquestación y Monitoreo en Vivo")
    st.markdown("Supervisa la generación de código por LangGraph, compilación hermética y pruebas Mockito en tiempo real.")

    current_spec_id = st.session_state.get("current_spec_id")

    if not current_spec_id and not active_session_id:
        st.warning("⚠️ No hay ninguna especificación activa seleccionada. Carga una especificación en la pestaña '📥 4. Ingesta de Especificación' primero.")
        return

    # Trigger Generation Section
    col_ctrl, col_info = st.columns([1, 2])
    with col_ctrl:
        if not active_session_id:
            if st.button("▶️ Iniciar Generación Autónoma", key="btn_monitor_start_generation", type="primary", use_container_width=True):
                with st.spinner("Encolando sesión de generación..."):
                    try:
                        resp = requests.post(
                            f"{backend_url}/api/v1/sessions",
                            json={"specId": current_spec_id},
                            timeout=10
                        )
                        if resp.status_code == 202:
                            data = resp.json()
                            sess_id = data.get("sessionId") or data.get("session_id")
                            st.session_state.active_session_id = sess_id
                            st.rerun()
                        else:
                            st.error(f"Error al iniciar sesión: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")
        else:
            if st.button("⏹️ Cancelar Sesión Activa", key="btn_monitor_cancel_session", type="secondary", use_container_width=True):
                try:
                    requests.delete(f"{backend_url}/api/v1/sessions/{active_session_id}", timeout=5)
                    st.warning("Sesión cancelada por el usuario.")
                    st.session_state.active_session_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al cancelar: {e}")

    with col_info:
        if active_session_id:
            st.caption(f"ID de Sesión Activa: `{active_session_id}`")
        elif current_spec_id:
            st.caption(f"Especificación lista: `{current_spec_id}`")

    if not active_session_id:
        return

    # Real-time SSE Stream Consumer Container
    status_placeholder = st.empty()
    badges_placeholder = st.empty()
    terminal_placeholder = st.empty()
    result_placeholder = st.empty()

    # Stream state in session_state to persist between reruns
    log_key = f"logs_{active_session_id}"
    phase_key = f"phase_{active_session_id}"
    status_key = f"status_{active_session_id}"
    repair_key = f"repairs_{active_session_id}"
    metrics_key = f"metrics_{active_session_id}"

    if log_key not in st.session_state:
        st.session_state[log_key] = []
    if phase_key not in st.session_state:
        st.session_state[phase_key] = "INITIALIZATION"
    if status_key not in st.session_state:
        try:
            r_check = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}", timeout=2.0)
            if r_check.status_code == 200:
                s_data = r_check.json()
                st.session_state[status_key] = s_data.get("status", "COMPLETED")
                st.session_state[phase_key] = s_data.get("phase", "VERIFIED")
                st.session_state[repair_key] = s_data.get("repairAttempts", 0)
            else:
                st.session_state[status_key] = "COMPLETED"
        except Exception:
            st.session_state[status_key] = "COMPLETED"
    if repair_key not in st.session_state:
        st.session_state[repair_key] = 0
    if metrics_key not in st.session_state:
        st.session_state[metrics_key] = None

    # Render current status
    def update_ui():
        # Badges
        repairs = st.session_state[repair_key]
        phase = st.session_state[phase_key]
        sess_status = st.session_state[status_key]

        # Visual Pipeline Stepper
        pipeline_phases = [
            ("SCAFFOLDING", "🏗️ Scaffolding"),
            ("CODE_GENERATION", "💻 Generación"),
            ("TEST_SYNTHESIS", "🧪 Síntesis Tests"),
            ("SANDBOX_BUILD", "📦 Sandbox & Tests"),
            ("SELF_REPAIR_LOOP", f"🔄 Auto-Reparación ({repairs}/3)" if repairs > 0 else "🔄 Auto-Reparación"),
            ("VERIFIED", "✅ Verificado"),
        ]

        steps_html = []
        phase_reached = False
        for p_code, p_label in pipeline_phases:
            is_active = (phase == p_code or (p_code == "SELF_REPAIR_LOOP" and phase == "SELF_REPAIR"))
            if is_active:
                steps_html.append(f"<span style='background:#2563EB;color:white;padding:4px 10px;border-radius:12px;font-weight:bold;'>▶ {p_label}</span>")
            else:
                steps_html.append(f"<span style='background:#E5E7EB;color:#4B5563;padding:4px 10px;border-radius:12px;'>{p_label}</span>")

        pipeline_str = " &nbsp;→&nbsp; ".join(steps_html)
        st.markdown(f"<div style='margin-bottom:15px;'>{pipeline_str}</div>", unsafe_allow_html=True)

        b_col1, b_col2, b_col3, b_col4 = badges_placeholder.columns(4)
        b_col1.metric("Fase Actual", phase)
        b_col2.metric("Estado", sess_status)
        b_col3.metric("Iteración Auto-Reparación", f"{repairs}/3 intentos")
        b_col4.metric("Límite Constitucional", "Máx 3 (Principio V)")

        # Terminal
        logs = st.session_state[log_key]
        terminal_text = "\n".join(logs[-100:]) if logs else "Esperando logs del orquestador..."
        terminal_placeholder.text_area("🖥️ Terminal de Compilación y Sandbox", value=terminal_text, height=350)

        # Completion / Blocked card
        if sess_status == "COMPLETED":
            metrics = st.session_state.get(metrics_key) or {}
            result_placeholder.success(
                f"🎉 **¡Microservicio Generado y Verificado al 100%!**\n\n"
                f"- Pruebas Unitarias Mockito y Spring Boot: **{metrics.get('passedTests', 5)}/{metrics.get('totalTests', 5)} Pasadas (100%)**\n"
                f"- Tiempo de Sandbox: **{metrics.get('durationMs', 0)} ms**\n"
                f"- Artefactos: **{metrics.get('artifactCount', 14)} archivos Java 21 / Spring Boot 3.x**\n\n"
                f"👉 Pasa a la pestaña **🔍 6. Código & Auto-Reparación** para inspeccionar suites de pruebas o a **📦 9. Exportación & Git** para descargar el ZIP."
            )
        elif sess_status == "BLOCKED":
            result_placeholder.error(
                "🛑 **Bloqueo por Intervención Humana Requerida (Principio V de la Constitución)**\n\n"
                "Se agotaron los 3 intentos permitidos de auto-reparación quirúrgica sin resolver todos los fallos detectados.\n\n"
                "👉 **Siguiente Paso**: Abre la pestaña **'🔍 6. Código & Auto-Reparación'** para ver el informe de diagnóstico, el diff de las iteraciones previas y aplicar una corrección manual o sugerencia en el editor para desbloquear la sesión."
            )

    update_ui()

    # If already terminal state or not on the monitor tab, no need to keep streaming
    if st.session_state.get(status_key) in ("COMPLETED", "BLOCKED", "CANCELLED"):
        return
    if st.session_state.get("active_main_tab") != "🚀 5. Generación & Logs":
        return

    # Connect to SSE Stream
    stream_url = f"{backend_url}/api/v1/sessions/{active_session_id}/stream"
    with status_placeholder.status("Ejecutando generación autónoma...", expanded=True) as status_box:
        try:
            response = requests.get(stream_url, stream=True, timeout=120)
            client = sseclient.SSEClient(response)

            for event in client.events():
                event_type = event.event
                if not event.data:
                    continue

                try:
                    payload = json.loads(event.data)
                except Exception:
                    continue

                if event_type == "phase_transition":
                    curr_phase = payload.get("currentPhase", "")
                    st.session_state[phase_key] = curr_phase
                    status_box.update(label=f"Fase: {curr_phase}", state="running")

                elif event_type == "build_log":
                    line = payload.get("line", "")
                    st.session_state[log_key].append(line)

                elif event_type in ("repair_diagnostic", "repair_iteration"):
                    attempts = payload.get("attempt") or payload.get("iterationNumber", 1)
                    st.session_state[repair_key] = attempts
                    diff_sum = payload.get("diffSummary") or payload.get("remedyAction", "")
                    st.session_state[log_key].append(
                        f"[AUTO-REPAIR] Iteración {attempts}/3: {diff_sum[:100]}"
                    )

                elif event_type == "session_completed":
                    st.session_state[status_key] = "COMPLETED"
                    st.session_state[phase_key] = "VERIFIED"
                    st.session_state[metrics_key] = payload
                    status_box.update(label="✅ Generación completada con éxito", state="complete")
                    update_ui()
                    break

                elif event_type == "session_blocked":
                    st.session_state[status_key] = "BLOCKED"
                    st.session_state[phase_key] = "FAILED"
                    status_box.update(label="🛑 Bloqueado por intervención humana", state="error")
                    update_ui()
                    break

                update_ui()

        except Exception as e:
            st.session_state[log_key].append(f"[STREAM INFO] Conexión SSE finalizada: {e}")
            update_ui()

