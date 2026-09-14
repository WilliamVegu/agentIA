import requests
import streamlit as st
from typing import Optional

PHASE_TO_TAB = {
    "SPECIFICATION": "📝 1. Requisitos & Historias",
    "ARCHITECTURE": "🏗️ 2. Diseño Arquitectónico",
    "DATA_MODEL": "💾 3. Modelos & SQL",
    "CODE_GENERATION": "🚀 5. Generación & Logs",
    "SECURITY_AUDIT": "🛡️ 7. Seguridad & Calidad",
    "DEPLOYMENT": "🚀 8. DevOps & Despliegue",
    "VERIFIED": "📦 9. Exportación & Git",
}

def render_lifecycle_stepper(backend_url: str, session_id: Optional[str] = None):
    """Renders a persistent global lifecycle stepper and contextual Next Action Bar at the top of the Studio."""
    if not session_id:
        return

    try:
        resp = requests.get(f"{backend_url}/api/v1/orchestrator/sessions/{session_id}/lifecycle", timeout=2.0)
        if resp.status_code != 200:
            return
        lifecycle = resp.json()
    except Exception:
        return

    completion_pct = lifecycle.get("completionPercentage", 0.0)
    phases = lifecycle.get("phases", [])
    next_action = lifecycle.get("nextRecommendedAction", "Continuar con la siguiente etapa")
    is_outdated = lifecycle.get("isOutdated", False)
    active_mode = lifecycle.get("activeMode", "GUIDED_STEP")
    can_advance = lifecycle.get("canAdvance", True)
    pipeline_status = lifecycle.get("pipelineStatus", "IDLE")
    next_target = lifecycle.get("nextTargetPhase")

    status_labels = {
        "IDLE": "💤 En Reposo",
        "RUNNING": "⚡ Ejecutando Auto-Pilot",
        "PAUSED": "⏸️ En Pausa",
        "COMPLETED": "✅ Completado",
        "FAILED": "❌ Fallido",
        "CANCELLED": "⏹️ Cancelado",
    }
    pipeline_badge = status_labels.get(pipeline_status, pipeline_status)

    with st.container(border=True):
        col_title, col_prog = st.columns([3, 1])
        with col_title:
            mode_badge = "🚀 Auto-Pilot" if active_mode == "AUTO_PILOT" else "👣 Modo Paso a Paso"
            st.markdown(
                f"**⚡ Flujo del Microservicio** &nbsp;|&nbsp; Modo: `{mode_badge}` &nbsp;|&nbsp; "
                f"Estado: `{pipeline_badge}` &nbsp;|&nbsp; Sesión: `{session_id[:8]}...`"
            )
        with col_prog:
            st.progress(min(max(completion_pct / 100.0, 0.0), 1.0))
            st.caption(f"Progreso Global: **{completion_pct}%**")

        # 7 Interactive Phase Indicators
        cols = st.columns(len(phases) if phases else 1)
        for i, p in enumerate(phases):
            status = p.get("status", "NOT_STARTED")
            phase_name = p.get("phase", "")
            title = p.get("title", f"Fase {i+1}")
            clean_title = title.split(".")[1].strip() if "." in title else title
            is_unlocked = p.get("isUnlocked", False) or status in ("COMPLETED", "IN_PROGRESS", "OUTDATED")

            icon = "🔒"
            if status == "COMPLETED":
                icon = "✅"
            elif status == "IN_PROGRESS":
                icon = "⏳"
            elif status == "OUTDATED":
                icon = "⚠️"
            elif status == "BLOCKED":
                icon = "🛑"

            with cols[i]:
                if is_unlocked:
                    is_current = (status == "IN_PROGRESS")
                    btn_type = "primary" if is_current else "secondary"
                    btn_label = f"{icon} {clean_title}"
                    if st.button(
                        btn_label,
                        key=f"stepper_phase_btn_{i}_{phase_name}",
                        type=btn_type,
                        use_container_width=True,
                        help=f"{p.get('description', '')} (Estado: {status})",
                    ):
                        target_tab = PHASE_TO_TAB.get(phase_name)
                        if target_tab:
                            st.session_state["active_main_tab"] = target_tab
                            st.rerun()
                else:
                    st.button(
                        f"🔒 {clean_title}",
                        key=f"stepper_phase_locked_{i}_{phase_name}",
                        disabled=True,
                        use_container_width=True,
                        help="Bloqueado: completa las fases previas para desbloquear.",
                    )

        # Amber banner if downstream phases are outdated
        if is_outdated:
            st.warning("⚠️ Se detectaron modificaciones en etapas previas. Las etapas posteriores están marcadas como desactualizadas.")
            if st.button("🔄 Re-sincronizar y Regenerar etapas afectadas", key="btn_stepper_resync", type="primary"):
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
                        st.success("¡Re-sincronización iniciada en segundo plano!")
                        st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "No se pudo iniciar re-sincronización"))
                except Exception as e:
                    st.error(f"Error: {e}")

        # In-Flight Pipeline Controls & Next Action Bar
        col_action_msg, col_action_btns = st.columns([3, 2])
        with col_action_msg:
            if pipeline_status == "RUNNING":
                st.info("⚡ **Auto-Pilot Activo**: El orquestador está ejecutando etapas en segundo plano. Puedes pausar o cancelar en cualquier momento.")
            elif pipeline_status == "PAUSED":
                st.warning("⏸️ **Auto-Pilot en Pausa**: La ejecución está suspendida. Puedes inspeccionar los artefactos generados o reanudar el flujo.")
            else:
                st.info(f"👉 **Acción Recomendada**: {next_action}")

        with col_action_btns:
            if pipeline_status == "RUNNING":
                btn_pause, btn_cancel = st.columns(2)
                with btn_pause:
                    if st.button("⏸️ Pausar", key="btn_stepper_pause", use_container_width=True):
                        try:
                            r = requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/pause", json={"sessionId": session_id}, timeout=3.0)
                            if r.status_code == 200:
                                st.toast("Auto-Pilot pausado")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error al pausar"))
                        except Exception as e:
                            st.error(f"Error: {e}")
                with btn_cancel:
                    if st.button("⏹️ Cancelar", key="btn_stepper_cancel", use_container_width=True):
                        try:
                            r = requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/cancel", json={"sessionId": session_id}, timeout=3.0)
                            if r.status_code == 200:
                                st.toast("Auto-Pilot cancelado")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error al cancelar"))
                        except Exception as e:
                            st.error(f"Error: {e}")
            elif pipeline_status == "PAUSED":
                btn_resume, btn_cancel = st.columns(2)
                with btn_resume:
                    if st.button("▶️ Reanudar", key="btn_stepper_resume", type="primary", use_container_width=True):
                        try:
                            r = requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/resume", json={"sessionId": session_id}, timeout=3.0)
                            if r.status_code == 200:
                                st.toast("Auto-Pilot reanudado")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error al reanudar"))
                        except Exception as e:
                            st.error(f"Error: {e}")
                with btn_cancel:
                    if st.button("⏹️ Cancelar", key="btn_stepper_cancel_paused", use_container_width=True):
                        try:
                            r = requests.post(f"{backend_url}/api/v1/orchestrator/pipeline/cancel", json={"sessionId": session_id}, timeout=3.0)
                            if r.status_code == 200:
                                st.toast("Auto-Pilot cancelado")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error al cancelar"))
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("🚀 Auto-Pilot", key="btn_stepper_autopilot", help="Ejecutar todas las etapas en segundo plano", use_container_width=True):
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
                                st.success("¡Pipeline Auto-Pilot iniciado en segundo plano!")
                                st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "No se pudo iniciar Auto-Pilot"))
                        except Exception as e:
                            st.error(f"Error conectando con backend: {e}")

                with btn_col2:
                    if next_target and next_target != "COMPLETED":
                        if st.button("👉 Siguiente Paso", key="btn_stepper_next", disabled=not can_advance, use_container_width=True):
                            try:
                                r = requests.post(f"{backend_url}/api/v1/orchestrator/sessions/{session_id}/transition", json={"targetPhase": next_target}, timeout=3.0)
                                if r.status_code == 200:
                                    target_tab = PHASE_TO_TAB.get(next_target)
                                    if target_tab:
                                        st.session_state["active_main_tab"] = target_tab
                                    st.rerun()
                                else:
                                    st.error(r.json().get("detail", "Error en transición"))
                            except Exception as e:
                                st.error(f"Error: {e}")
                    else:
                        st.caption("✅ Flujo Completo")
