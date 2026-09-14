import requests
import streamlit as st


def render_security_view(backend_url: str, active_session_id: str, key_prefix: str = ""):
    """Renders the dedicated Security & Quality Gate Audit view (Spec 006)."""
    st.header("🛡️ 7. Auditoría de Seguridad, SAST & Compuertas de Calidad")
    st.markdown(
        "Evaluación estática de vulnerabilidades de código fuente (**SAST**), fuga de secretos o credenciales efímeras (**Principio VI**), "
        "composición de software y base de datos CVE offline (**Principio IV**), verificación de reglas arquitectónicas de la Constitución "
        "y compuerta de exportación (**Quality Gate** estilo SonarQube)."
    )

    if not active_session_id:
        st.info("ℹ️ No hay ninguna sesión activa. Inicia una sesión desde la **Pestaña 0 (Resumen)** o genera el código para auditar el microservicio.")
        return

    col_refresh, col_space = st.columns([1, 4])
    with col_refresh:
        st.button("🔄 Actualizar Auditoría", key=f"{key_prefix}btn_sec_view_refresh", use_container_width=True)

    audit_report = None
    try:
        with st.spinner("Ejecutando escaneo estático SAST, análisis de secretos y reglas arquitectónicas..."):
            audit_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/audit", timeout=12)
            if audit_resp.status_code == 200:
                audit_report = audit_resp.json()
            elif audit_resp.status_code == 404:
                st.info("ℹ️ No se ha generado el código fuente para esta sesión aún. Ejecuta la generación en las etapas previas.")
                return
            else:
                st.error(f"Error al obtener reporte de auditoría: {audit_resp.status_code} - {audit_resp.text}")
                return
    except Exception as e:
        st.error(f"Error comunicando con el servicio de seguridad: {e}")
        return

    if not audit_report:
        return

    qg = audit_report.get("qualityGate", {})
    metrics = audit_report.get("metrics", {})
    vulns = audit_report.get("vulnerabilities", [])
    viols = audit_report.get("violations", [])

    qg_status = qg.get("status", "PASS")
    score = qg.get("score", 100)
    can_export = qg.get("canExport", True)
    summary_msg = qg.get("summaryMessage", "")

    # 1. Quality Gate Verdict Banner
    st.markdown("---")
    if qg_status == "BLOCKED":
        st.error(f"🛑 **Quality Gate: BLOQUEADO (Puntaje: {score}/100)**\n\n{summary_msg}")
        st.warning("⛔ **Exportación ZIP y Publicación Git Bloqueadas**: Debes resolver las vulnerabilidades Críticas/Altas para habilitar el release.")
    elif qg_status == "WARNING":
        st.warning(f"⚠️ **Quality Gate: ADVERTENCIA (Puntaje: {score}/100)**\n\n{summary_msg}")
    else:
        st.success(f"✅ **Quality Gate: APROBADO (Puntaje: {score}/100)**\n\n{summary_msg}")

    # 2. Executive Metric Badges
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    rating = "A" if score >= 90 else ("B" if score >= 75 else ("C" if score >= 60 else "F"))
    col_m1.metric("Rating de Seguridad", f"Nivel {rating}", f"{score}/100 pts")
    col_m2.metric("Vulnerabilidades", f"{len(vulns)} Total", f"{qg.get('criticalCount', 0)} Críticas | {qg.get('highCount', 0)} Altas")
    col_m3.metric("Violaciones Constitucionales", f"{len(viols)} Reglas", "Principios I-VI")
    col_m4.metric("Complejidad Ciclomática", f"CC {metrics.get('averageCyclomaticComplexity', 1.0)}", f"Máx: {metrics.get('maxCyclomaticComplexity', 1)}")

    st.markdown("---")

    # 3. Categorized Vulnerabilities Section
    st.subheader("🚨 Vulnerabilidades de Seguridad (SAST, Secretos & CVEs)")
    if vulns:
        for idx, v in enumerate(vulns):
            sev = v.get("severity", "HIGH")
            color_icon = "🔴" if sev == "CRITICAL" else ("🟠" if sev == "HIGH" else "🟡")
            with st.expander(f"{color_icon} [{sev}] {v.get('title')} — `{v.get('filePath')}:{v.get('lineNumber')}`", expanded=(sev in ("CRITICAL", "HIGH"))):
                st.markdown(f"**Categoría**: `{v.get('category')}` | **CWE**: `{v.get('cweId')}` | **OWASP**: `{v.get('owaspCategory')}`")
                st.markdown(f"**Descripción**: {v.get('description')}")
                st.code(v.get("codeSnippet", ""), language="java")
                st.info(f"💡 **Remediación**: {v.get('remediationGuidance')}")

                if v.get("autoFixAvailable"):
                    if st.button(f"⚡ Auto-Reparar Quirúrgicamente (1-Click)", key=f"{key_prefix}sec_view_fix_vuln_{idx}"):
                        with st.spinner("Aplicando parche quirúrgico determinista..."):
                            rem_payload = {
                                "findingId": v.get("id"),
                                "filePath": v.get("filePath"),
                            }
                            rem_resp = requests.post(f"{backend_url}/api/v1/security/remediate", json=rem_payload, timeout=10)
                            if rem_resp.status_code == 200:
                                rem_data = rem_resp.json()
                                st.success("✅ **Parche aplicado exitosamente.**")
                                if rem_data.get("diff"):
                                    st.markdown("**Diff unificado aplicado:**")
                                    st.code(rem_data.get("diff"), language="diff")
                                st.rerun()
                            else:
                                st.error(f"Error aplicando auto-reparación: {rem_resp.text}")
    else:
        st.success("🎉 Cero vulnerabilidades de seguridad detectadas. Código conforme a OWASP Top 10.")

    st.markdown("---")

    # 4. Constitutional & Architectural Standards Section
    st.subheader("🏛️ Cumplimiento de Estándares & Constitución")
    if viols:
        for idx, viol in enumerate(viols):
            v_sev = viol.get("severity", "HIGH")
            v_icon = "🛑" if v_sev == "CRITICAL" or v_sev == "HIGH" else "⚠️"
            with st.expander(f"{v_icon} [{viol.get('principle')}] {viol.get('offendingElement')} (`{viol.get('filePath')}`)", expanded=True):
                st.markdown(f"**Regla Violada**: {viol.get('ruleDescription')}")
                st.markdown(f"**Corrección Sugerida**: {viol.get('suggestedFix')}")

                if viol.get("autoFixAvailable"):
                    if st.button(f"⚡ Convertir / Corregir Automáticamente", key=f"{key_prefix}sec_view_fix_viol_{idx}"):
                        with st.spinner("Aplicando corrección constitucional..."):
                            rem_payload = {
                                "findingId": viol.get("id"),
                                "filePath": viol.get("filePath"),
                            }
                            rem_resp = requests.post(f"{backend_url}/api/v1/security/remediate", json=rem_payload, timeout=10)
                            if rem_resp.status_code == 200:
                                rem_data = rem_resp.json()
                                st.success("✅ **Corrección aplicada exitosamente.**")
                                if rem_data.get("diff"):
                                    st.code(rem_data.get("diff"), language="diff")
                                st.rerun()
                            else:
                                st.error(f"Error aplicando corrección: {rem_resp.text}")
    else:
        st.success("🎉 Cumplimiento 100% con los Principios I, II, III, IV, V y VI de la Constitución.")

    st.markdown("---")

    # 5. Clean Code Maintainability Metrics
    st.subheader("📊 Métricas de Mantenibilidad (Clean Code / SonarQube)")
    col_met1, col_met2, col_met3 = st.columns(3)
    col_met1.write(f"**Líneas de Código (LOC)**: `{metrics.get('totalLinesOfCode', 0)}`")
    col_met1.write(f"**Total Métodos Evaluados**: `{metrics.get('totalMethodsAudited', 0)}`")
    col_met2.write(f"**Métodos Excediendo Umbral (CC > 10)**: `{metrics.get('methodsExceedingThreshold', 0)}`")
    col_met2.write(f"**Porcentaje de Duplicación**: `{metrics.get('duplicationPercentage', 0.0)}%` (Umbral $\\le$ 3%)")
    col_met3.write(f"**Densidad de Aserciones**: `{metrics.get('testAssertionDensity', 0.0)} / test`")
    col_met3.write(f"**Code Smells Totales**: `{metrics.get('totalCodeSmells', 0)}`")

