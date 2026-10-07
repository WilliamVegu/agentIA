import json
import time
import requests
import streamlit as st


def render_devops_view(backend_url: str, active_session_id: str):
    st.header("🚀 DevOps, Contenerización & Despliegue")
    st.markdown(
        "Generación y orquestación de despliegue para microservicios Java 21 / Spring Boot 3: Dockerfile multi-stage hermético, "
        "docker-compose.yml con base de datos, pipelines de CI/CD (GitHub Actions / GitLab CI), Server-Sent Events (SSE) y Kubernetes."
    )

    if not active_session_id:
        st.info("ℹ️ No hay ninguna sesión activa. Inicia o selecciona una sesión para gestionar DevOps y Despliegues.")
        return

    # 1. Fetch Current Deployment Status
    status_data = {}
    try:
        s_resp = requests.get(f"{backend_url}/api/v1/devops/{active_session_id}/status", timeout=5)
        if s_resp.status_code == 200:
            status_data = s_resp.json()
    except Exception:
        pass

    current_status = status_data.get("status", "IDLE")
    host_port = status_data.get("hostPort", 8080)
    test_url = status_data.get("testUrl")
    error_msg = status_data.get("errorMessage")

    # 2. Status Banner & Metrics
    col_s1, col_s2, col_s3, col_s4 = st.columns([3, 1, 1, 1])

    with col_s1:
        if current_status == "HEALTHY":
            st.success(f"🟢 **Contenedor en Línea y Saludable** (Puerto: `{host_port}`)")
            if test_url:
                st.markdown(f"🌐 **URL de Prueba Activa**: [{test_url}]({test_url})")
        elif current_status in ("BUILDING", "RUNNING"):
            st.info(f"🔵 **Estado: {current_status}** — Orquestando contenedores en el daemon local...")
        elif current_status == "DOCKER_UNAVAILABLE":
            st.warning("⚠️ **Docker Daemon No Disponible (Modo Export-Only)**: El daemon local no responde. Puedes generar y exportar todos los artefactos para ejecutarlos externamente.")
        elif current_status == "FAILED":
            st.error(f"🔴 **Despliegue Fallido**: {error_msg or 'Consulte los logs de ejecución'}")
        else:
            st.caption(f"⚪ Estado Actual: `{current_status}`")

    with col_s2:
        st.metric("Puerto Mapeado", f"{host_port}:8080")
    with col_s3:
        st.metric("Estado Actuator", status_data.get("healthStatus") or "N/A")
    with col_s4:
        st.write("")
        if st.button("🔄 Refrescar", key="btn_devops_refresh_status", use_container_width=True):
            st.rerun()

    st.markdown("---")

    # 3. Action Controls
    st.markdown("### 🛠️ Controles de Despliegue & Orquestación")
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

    is_docker_unavailable = current_status == "DOCKER_UNAVAILABLE"
    is_running = current_status in ("RUNNING", "HEALTHY")

    with col_btn1:
        if st.button("⚙️ Generar Manifiestos DevOps", key="btn_devops_gen_manifests", use_container_width=True, type="secondary"):
            with st.spinner("Generando Dockerfile, Compose, CI/CD y Kubernetes..."):
                try:
                    g_resp = requests.post(
                        f"{backend_url}/api/v1/devops/{active_session_id}/generate",
                        params={"host_port": host_port},
                        timeout=10,
                    )
                    if g_resp.status_code == 200:
                        st.success("✅ Manifiestos DevOps generados exitosamente.")
                        st.rerun()
                    elif g_resp.status_code == 403:
                        st.error(f"⛔ Bloqueado por Quality Gate: {g_resp.json().get('detail')}")
                    else:
                        st.error(f"Error: {g_resp.status_code} - {g_resp.text}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    with col_btn2:
        if st.button("🚀 Desplegar Localmente", key="btn_devops_deploy_local", use_container_width=True, type="primary", disabled=is_docker_unavailable):
            with st.spinner("Iniciando build y orquestación con Docker daemon..."):
                try:
                    d_resp = requests.post(
                        f"{backend_url}/api/v1/devops/{active_session_id}/deploy",
                        json={"hostPort": host_port, "rebuild": True},
                        timeout=10,
                    )
                    if d_resp.status_code == 200:
                        st.info("🚀 Despliegue iniciado. Monitoreando terminal...")
                        st.rerun()
                    elif d_resp.status_code == 403:
                        st.error(f"⛔ Bloqueado por Quality Gate: {d_resp.json().get('detail')}")
                    else:
                        st.error(f"Error: {d_resp.status_code} - {d_resp.text}")
                except Exception as e:
                    st.error(f"Error conectando con daemon: {e}")

    with col_btn3:
        if st.button("🛑 Detener Contenedores", key="btn_devops_stop_containers", use_container_width=True, disabled=not is_running):
            with st.spinner("Deteniendo contenedores y redes..."):
                try:
                    stop_resp = requests.post(f"{backend_url}/api/v1/devops/{active_session_id}/stop", timeout=10)
                    if stop_resp.status_code == 200:
                        st.success("Contenedores detenidos.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with col_btn4:
        if st.button("🧪 Ejecutar Smoke Test", key="btn_devops_smoke_test", use_container_width=True, disabled=not is_running):
            with st.spinner("Consultando /actuator/health..."):
                try:
                    smk_resp = requests.post(
                        f"{backend_url}/api/v1/devops/{active_session_id}/smoke-test",
                        params={"host_port": host_port},
                        timeout=15,
                    )
                    if smk_resp.status_code == 200:
                        res = smk_resp.json()
                        if res.get("passed"):
                            st.success(f"✅ Smoke Test APROBADO: Status UP en {res.get('latencyMs')}ms")
                        else:
                            st.error(f"❌ Smoke Test FALLIDO: {res.get('details')}")
                        st.json(res.get("statusPayload", {}))
                except Exception as e:
                    st.error(f"Error ejecutando smoke test: {e}")

    st.markdown("---")

    # 3.5. Interactive API & Database Playground (when running/healthy)
    if is_running:
        st.markdown("### 🎮 Probador Visual de API & Base de Datos (Live Playground)")
        st.caption("Interactúa visualmente con los contenedores desplegados (Spring Boot + PostgreSQL) directamente desde esta pantalla.")

        tab_play1, tab_play2 = st.tabs(["📋 Gestor Visual de Órdenes (CRUD en PostgreSQL)", "🧪 Consola de Peticiones REST (Estilo Postman/Swagger)"])

        with tab_play1:
            col_form, col_table = st.columns([1, 2], gap="medium")

            with col_form:
                st.subheader("➕ Crear Nueva Orden")
                with st.form("form_create_order"):
                    c_email = st.text_input("Email del Cliente", value="cliente@ejemplo.com")
                    c_amount = st.number_input("Monto Total ($)", min_value=0.01, value=99.99, step=10.0, format="%.2f")
                    btn_submit = st.form_submit_button("💾 Guardar en PostgreSQL", use_container_width=True, type="primary")

                    if btn_submit:
                        try:
                            post_resp = requests.post(
                                f"http://localhost:{host_port}/api/v1/orders",
                                json={"customerEmail": c_email, "totalAmount": c_amount},
                                timeout=5,
                            )
                            if post_resp.status_code in (200, 201):
                                st.success(f"✅ ¡Guardado con éxito! ID generado: {post_resp.json().get('id')}")
                                st.rerun()
                            else:
                                st.error(f"Error {post_resp.status_code}: {post_resp.text}")
                        except Exception as ex:
                            st.error(f"Error conectando al microservicio: {ex}")

            with col_table:
                st.subheader("📦 Órdenes Registradas en Base de Datos")
                try:
                    get_resp = requests.get(f"http://localhost:{host_port}/api/v1/orders", timeout=5)
                    if get_resp.status_code == 200:
                        orders_data = get_resp.json()
                        if orders_data:
                            st.dataframe(orders_data, use_container_width=True)
                            st.caption(f"Total de registros en PostgreSQL: **{len(orders_data)}**")
                        else:
                            st.info("La tabla está vacía. ¡Crea tu primera orden en el formulario a la izquierda!")
                    else:
                        st.warning(f"No se pudieron cargar las órdenes (HTTP {get_resp.status_code})")
                except Exception as ex:
                    st.error(f"Error leyendo de la base de datos: {ex}")

        with tab_play2:
            st.subheader("🧪 Enviar Petición Personalizada")
            col_m, col_ep = st.columns([1, 3])
            with col_m:
                req_method = st.selectbox("Método HTTP", ["GET", "POST", "DELETE"])
            with col_ep:
                req_endpoint = st.text_input("Endpoint", value="/api/v1/orders")

            req_body = ""
            if req_method == "POST":
                req_body = st.text_area("Cuerpo JSON (Request Body)", value='{\n  "customerEmail": "demo@corp.com",\n  "totalAmount": 149.50\n}', height=120)

            if st.button("🚀 Enviar Petición", key="btn_send_custom_rest", type="primary"):
                req_url = f"http://localhost:{host_port}{req_endpoint}" if req_endpoint.startswith("/") else f"http://localhost:{host_port}/{req_endpoint}"
                t_start = time.time()
                try:
                    if req_method == "GET":
                        r = requests.get(req_url, timeout=5)
                    elif req_method == "POST":
                        headers = {"Content-Type": "application/json"}
                        r = requests.post(req_url, data=req_body.encode('utf-8'), headers=headers, timeout=5)
                    elif req_method == "DELETE":
                        r = requests.delete(req_url, timeout=5)

                    lat_ms = (time.time() - t_start) * 1000.0

                    badge_color = "green" if r.status_code < 300 else ("orange" if r.status_code < 500 else "red")
                    st.markdown(f"**Resultado:** :{badge_color}[HTTP {r.status_code}] | **Latencia:** `{lat_ms:.1f} ms`")
                    try:
                        st.json(r.json())
                    except Exception:
                        st.code(r.text)
                except Exception as ex:
                    st.error(f"Error al enviar petición: {ex}")

        st.markdown("---")

    # 4. Live Terminal View (Logs)
    st.markdown("### 💻 Terminal de Despliegue en Vivo (Logs)")
    terminal_container = st.empty()

    try:
        l_resp = requests.get(f"{backend_url}/api/v1/devops/{active_session_id}/logs", timeout=2)
        if l_resp.status_code == 200:
            log_lines = l_resp.json().get("logs", [])
            if log_lines:
                terminal_container.code("\n".join(log_lines[-100:]), language="bash")
            else:
                terminal_container.info("Aún no hay logs generados. Haz clic en 'Desplegar Localmente' para iniciar el proceso.")
        else:
            terminal_container.caption("Esperando logs de ejecución...")
    except Exception:
        terminal_container.caption("Consola en espera...")

    st.markdown("---")

    # 5. Manifest Inspector Accordion Tabs
    st.markdown("### 📄 Inspección de Manifiestos Generados")
    tab_m_docker, tab_m_compose, tab_m_cicd, tab_m_k8s = st.tabs([
        "🐳 Dockerfile & Ignore",
        "🐙 Docker Compose (Multi-Contenedor)",
        "🔄 CI/CD Pipelines (GitHub & GitLab)",
        "☸️ Manifiestos Kubernetes (Producción)",
    ])

    # Fetch existing files
    try:
        art_resp = requests.get(f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts", timeout=5)
        artifacts = art_resp.json() if art_resp.status_code == 200 else []
        art_paths = {a["relativePath"]: a for a in artifacts}
    except Exception:
        art_paths = {}

    def _render_code(rel_path: str, lang: str):
        try:
            c_resp = requests.get(
                f"{backend_url}/api/v1/sessions/{active_session_id}/artifacts/content",
                params={"path": rel_path},
                timeout=5,
            )
            if c_resp.status_code == 200:
                st.code(c_resp.text, language=lang, line_numbers=True)
            else:
                st.info(f"El archivo `{rel_path}` aún no ha sido generado. Pulsa 'Generar Manifiestos DevOps' arriba.")
        except Exception:
            st.info(f"Pendiente de generación: `{rel_path}`")

    with tab_m_docker:
        st.subheader("Dockerfile Multi-Stage (Eclipse Temurin JRE 21 LTS)")
        st.markdown(
            "- **Extractor**: `java -Djarmode=layertools -jar application.jar extract`\n"
            "- **Seguridad**: Ejecución con usuario no-root `appuser:10001` (Principio VI)\n"
            "- **JVM Flags**: `-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC`"
        )
        _render_code("Dockerfile", "dockerfile")
        st.subheader(".dockerignore")
        _render_code(".dockerignore", "text")

    with tab_m_compose:
        st.subheader("docker-compose.yml (Orquestación con Base de Datos)")
        st.markdown(
            "- Red bridge aislada `app-network`\n"
            "- Inicialización DDL montando `schema.sql` en `/docker-entrypoint-initdb.d/`\n"
            "- Healthcheck de base de datos con `depends_on: condition: service_healthy`"
        )
        _render_code("docker-compose.yml", "yaml")

    with tab_m_cicd:
        st.subheader("GitHub Actions (.github/workflows/ci-cd.yml)")
        _render_code(".github/workflows/ci-cd.yml", "yaml")
        st.subheader("GitLab CI (.gitlab-ci.yml)")
        _render_code(".gitlab-ci.yml", "yaml")

    with tab_m_k8s:
        st.subheader("Manifiestos Kubernetes para Producción")
        st.markdown("Configurados con probes HTTP liveness/readiness de Spring Boot Actuator y NGINX Ingress.")
        sub_k1, sub_k2, sub_k3, sub_k4 = st.tabs(["deployment.yaml", "service.yaml", "configmap.yaml", "ingress.yaml"])
        with sub_k1:
            _render_code("k8s/deployment.yaml", "yaml")
        with sub_k2:
            _render_code("k8s/service.yaml", "yaml")
        with sub_k3:
            _render_code("k8s/configmap.yaml", "yaml")
        with sub_k4:
            _render_code("k8s/ingress.yaml", "yaml")

