import streamlit as st
import requests

def render_export_view(backend_url: str, active_session_id: str):
    st.header("📦 Exportación de Entregables y Publicación en Git")
    st.markdown("Descarga el proyecto Maven completo o publica un commit atómico en una rama de características de Git.")

    if not active_session_id:
        st.info("ℹ️ No hay ninguna sesión activa. Inicia y completa una generación para exportar los entregables.")
        return

    # Check session status
    spec_name = "microservice"
    try:
        sess_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}", timeout=5)
        if sess_resp.status_code == 200:
            sess_data = sess_resp.json()
            spec_name = sess_data.get("specName") or "microservice"
            status = sess_data.get("status")
            if status != "COMPLETED":
                st.warning(f"⚠️ La sesión actual tiene estado `{status}`. Se recomienda exportar únicamente sesiones con estado `COMPLETED`.")
    except Exception:
        pass

    col_zip, col_git = st.columns([1, 1], gap="large")

    # --- 1. ZIP Download Section ---
    with col_zip:
        st.subheader("📁 Descarga de Archivo ZIP")
        st.markdown(
            "Descarga el código fuente completo, estructura Maven (`pom.xml`), configuración y suite de pruebas unitarias "
            "como un paquete limpio e independiente."
        )

        try:
            export_url = f"{backend_url}/api/v1/sessions/{active_session_id}/export"
            zip_resp = requests.get(export_url, timeout=15)
            if zip_resp.status_code == 200:
                zip_data = zip_resp.content
                st.download_button(
                    label=f"⬇️ Descargar {spec_name}.zip ({len(zip_data) // 1024} KB)",
                    key="dl_export_zip",
                    data=zip_data,
                    file_name=f"{spec_name}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )
                st.success("✅ Archivo ZIP generado en memoria y listo para descarga.")
            else:
                st.error(f"Error preparando archivo ZIP: {zip_resp.status_code} - {zip_resp.text}")
        except Exception as e:
            st.error(f"Error al conectar con el backend: {e}")

        st.caption("Estructura incluida: Java 21, Spring Boot 3.x, Records DTOs, @RestControllerAdvice y Pruebas Mockito.")

    # --- 2. Git Feature Branch Publication ---
    with col_git:
        st.subheader("🐙 Publicación a Rama Git")
        st.markdown(
            "Crea y sube un commit atómico a una rama de características dedicada utilizando credenciales efímeras en memoria."
        )

        with st.form("git_publish_form"):
            repo_url = st.text_input("URL del Repositorio Remoto:", placeholder="https://github.com/organization/repo.git")
            default_branch = f"feature/{spec_name}"
            branch_name = st.text_input("Nombre de la Rama Git:", value=default_branch)
            git_token = st.text_input("Personal Access Token (PAT):", type="password", help="Utilizado en memoria exclusivamente para el push.")
            commit_msg = st.text_input(
                "Mensaje de Commit:",
                value=f"feat({spec_name}): initial autonomous generation and verified test suite"
            )

            st.caption("🔒 Principio Constitucional VI: El token se procesa únicamente en memoria y jamás se persiste.")
            submit_btn = st.form_submit_button("🚀 Publicar a Rama Git", type="primary", use_container_width=True)

        if submit_btn:
            if not repo_url or not branch_name:
                st.error("Por favor especifica la URL del repositorio y el nombre de la rama.")
            else:
                with st.spinner("Creando commit atómico y realizando push..."):
                    try:
                        publish_payload = {
                            "repositoryUrl": repo_url,
                            "branchName": branch_name,
                            "gitToken": git_token if git_token else None,
                            "commitMessage": commit_msg
                        }
                        p_resp = requests.post(
                            f"{backend_url}/api/v1/sessions/{active_session_id}/publish",
                            json=publish_payload,
                            timeout=30
                        )
                        if p_resp.status_code == 200:
                            p_data = p_resp.json()
                            st.success(f"🎉 ¡Publicado exitosamente en `{p_data.get('branchName')}`!")
                            st.markdown(f"- **Hash de Commit**: `{p_data.get('commitHash')[:8]}`")
                            st.markdown(f"- **Enlace a la Rama**: [{p_data.get('branchUrl')}]({p_data.get('branchUrl')})")
                            if p_data.get("pullRequestUrl"):
                                st.markdown(f"- **Crear Pull Request**: [{p_data.get('pullRequestUrl')}]({p_data.get('pullRequestUrl')})")
                        else:
                            st.error(f"Fallo en publicación Git: {p_resp.status_code} - {p_resp.text}")
                    except Exception as ex:
                        st.error(f"Error conectando al backend: {ex}")

