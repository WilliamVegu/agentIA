import os
import sys
from pathlib import Path
import requests
import streamlit as st

# Ensure frontend root and app directory are accessible
_FRONTEND_ROOT = Path(__file__).resolve().parent
if str(_FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_ROOT))

from utils.ui import load_css, render_header, render_status_badge

st.set_page_config(
    page_title="AgentIA | Microservice Code Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Load TalentIA-based SaaS Stylesheet
load_css()

# 2. Sidebar Branding & Configuration
with st.sidebar:
    logo_path = _FRONTEND_ROOT / "assets" / "logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=190)
    st.markdown(
        """
        <div class="sidebar-brand-box">
            <div>
                <div class="sidebar-brand-title">AgentIA Studio</div>
                <div class="sidebar-brand-subtitle">Autonomous Microservice Architect</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()


    st.markdown("##### ⚙️ Configuración del Sistema")
    backend_url = st.text_input(
        "URL del Backend FastAPI",
        value=st.session_state.get("backend_url", "http://localhost:8000"),
        help="Servidor de orquestación y sandbox hermético",
    )
    st.divider()


# Session State & Active Session Selector
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "current_spec_id" not in st.session_state:
    st.session_state.current_spec_id = None
if "parsed_spec" not in st.session_state:
    st.session_state.parsed_spec = None
if "backend_url" not in st.session_state:
    st.session_state.backend_url = backend_url
else:
    st.session_state.backend_url = backend_url

TAB_LABELS = [
    "🏠 0. Resumen del Proyecto",
    "📝 1. Requisitos & Historias",
    "🏗️ 2. Diseño Arquitectónico",
    "💾 3. Modelos & SQL",
    "📥 4. Ingesta de Especificación",
    "🚀 5. Generación & Logs",
    "🔍 6. Código & Auto-Reparación",
    "🛡️ 7. Seguridad & Calidad",
    "🚀 8. DevOps & Despliegue",
    "📦 9. Exportación & Git",
]
if "active_main_tab" not in st.session_state:
    st.session_state.active_main_tab = TAB_LABELS[0]

# Sidebar Session Selector
st.sidebar.subheader("📂 Sesión del Microservicio")
session_options = ["✨ + Nuevo Microservicio (Crear)"]
session_id_map = {"✨ + Nuevo Microservicio (Crear)": None}

try:
    s_resp = requests.get(f"{backend_url}/api/v1/sessions", timeout=2.0)
    if s_resp.status_code == 200:
        sess_items = s_resp.json()
        for s in sess_items:
            sid = s.get("sessionId", "")
            sname = s.get("specName", "microservice")
            sstatus = s.get("status", "")
            pct = s.get("completionPercentage", 0.0)
            label = f"⚡ {sname} ({sid[:8]}...) [{sstatus} {int(pct)}%]"
            session_options.append(label)
            session_id_map[label] = sid
except Exception:
    pass

curr_idx = 0
current_sid = st.session_state.get("active_session_id")
if current_sid:
    for idx, opt in enumerate(session_options):
        if session_id_map.get(opt) == current_sid:
            curr_idx = idx
            break

selected_session_label = st.sidebar.selectbox(
    "Seleccionar Sesión Activa",
    session_options,
    index=curr_idx,
    help="Elige un microservicio generado previamente o crea uno nuevo",
)
chosen_sid = session_id_map.get(selected_session_label)
st.session_state.active_session_id = chosen_sid

if st.sidebar.button("🔄 Refrescar Lista de Sesiones", key="sidebar_btn_refresh_sessions", use_container_width=True):
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.subheader("🤖 Proveedor de IA (Nivel Gratuito)")
provider_options = [
    "Detección Automática",
    "Google Gemini (100% Gratis)",
    "Groq Cloud (100% Gratis)",
    "OpenAI",
    "Modo Mock (Offline / Sin Costo)",
]
selected_provider_label = st.sidebar.selectbox("Motor LLM", provider_options, index=0)

provider_mapping = {
    "Detección Automática": None,
    "Google Gemini (100% Gratis)": "gemini",
    "Groq Cloud (100% Gratis)": "groq",
    "OpenAI": "openai",
    "Modo Mock (Offline / Sin Costo)": "mock",
}
selected_provider = provider_mapping[selected_provider_label]

st.sidebar.subheader("🔒 Credenciales Efímeras")
if selected_provider == "mock":
    api_key_input = "mock-key"
    st.sidebar.success("✅ Modo Mock activo: Cero costo, sin llamadas a internet.")
else:
    api_key_input = st.sidebar.text_input(
        "API Key Efímera",
        type="password",
        help="Introduce tu API Key gratuita de Gemini (AIza...), Groq (gsk_...) o OpenAI (sk-...). Se procesa estrictamente en memoria.",
    )
    clean_key = (api_key_input or "").strip()
    if not clean_key or clean_key in ("mock-key", "test-key", "mock"):
        detected_engine_badge = "⚪ Modo Offline (Mock Engine)"
    elif clean_key.startswith("AIza") or clean_key.startswith("AQ."):
        detected_engine_badge = "🟢 Google Gemini (gemini-3.6-flash)"
    elif clean_key.startswith("gsk_"):
        detected_engine_badge = "🟢 Groq Cloud (llama-3.3-70b-versatile)"
    elif clean_key.startswith("sk-"):
        detected_engine_badge = "🟢 OpenAI (gpt-4o-mini)"
    else:
        detected_engine_badge = f"🟡 Proveedor Personalizado ({selected_provider or 'Autodetect'})"

    active_prov = selected_provider
    if not active_prov:
        if clean_key.startswith("AIza") or clean_key.startswith("AQ."):
            active_prov = "gemini"
        elif clean_key.startswith("gsk_"):
            active_prov = "groq"
        elif clean_key.startswith("sk-"):
            active_prov = "openai"
        else:
            active_prov = "mock"

    model_options_map = {
        "gemini": [
            "gemini-3.6-flash (Recomendado / Alta Inteligencia)",
            "gemini-3.5-flash-lite (Ultra Rápido / Liviano)",
            "gemini-3.1-pro-preview (Avanzado)",
            "Personalizado / Escribir otro...",
        ],
        "groq": [
            "llama-3.3-70b-versatile (Recomendado)",
            "llama-3.1-8b-instant (Rápido)",
            "mixtral-8x7b-32768",
            "Personalizado / Escribir otro...",
        ],
        "openai": [
            "gpt-4o-mini (Recomendado)",
            "gpt-4o (Avanzado)",
            "Personalizado / Escribir otro...",
        ],
        "mock": ["offline-mock"],
    }

    selected_model_name = None
    if active_prov in model_options_map and active_prov != "mock":
        chosen_opt = st.sidebar.selectbox("Modelo Específico", model_options_map[active_prov], index=0)
        if "Personalizado" in chosen_opt:
            selected_model_name = st.sidebar.text_input("Nombre del Modelo", placeholder="ej. gemini-3.6-flash")
        else:
            selected_model_name = chosen_opt.split(" ")[0]

    st.sidebar.markdown(f"**Motor Detectado:** `{detected_engine_badge}`")

    if st.sidebar.button("🧪 Probar Conexión con IA", key="sidebar_btn_test_ai_conn", use_container_width=True):
        with st.sidebar:
            with st.spinner("Probando conexión con el motor de IA..."):
                try:
                    verify_resp = requests.post(
                        f"{st.session_state.backend_url}/api/v1/llm/verify",
                        json={
                            "apiKey": api_key_input,
                            "provider": selected_provider,
                            "model": selected_model_name,
                        },
                        timeout=12.0,
                    )
                    if verify_resp.status_code == 200:
                        st.session_state["llm_verify_result"] = verify_resp.json()
                    else:
                        st.session_state["llm_verify_result"] = {
                            "status": "ERROR",
                            "message": f"Error del servidor (HTTP {verify_resp.status_code})",
                        }
                except Exception as e:
                    st.session_state["llm_verify_result"] = {
                        "status": "ERROR",
                        "message": f"Error de red: {e}",
                    }

    if "llm_verify_result" in st.session_state:
        v_res = st.session_state["llm_verify_result"]
        if v_res.get("status") == "CONNECTED":
            st.sidebar.success(
                f"✅ **¡Conectado a {v_res.get('provider', '').upper()}!**\n\n"
                f"• **Modelo**: `{v_res.get('model')}`\n"
                f"• **Latencia**: `{v_res.get('latencyMs')} ms`\n\n"
                f"⚡ Las próximas etapas usarán este motor de IA."
            )
        elif v_res.get("status") == "READY":
            st.sidebar.info(
                f"⚪ **Modo Offline Activo**\n\n"
                f"{v_res.get('message')}"
            )
        else:
            st.sidebar.error(
                f"❌ **Error de Conexión**\n\n"
                f"{v_res.get('message')}"
            )

    with st.sidebar.expander("💡 Obtener Claves 100% Gratuitas"):
        st.markdown("""
        - **Google Gemini (Gratis)**: [aistudio.google.com](https://aistudio.google.com/) *(sin tarjeta, 1.500 req/día)*
        - **Groq Cloud (Gratis)**: [console.groq.com](https://console.groq.com/keys) *(sin tarjeta, ultra rápido)*
        - **Mock Offline**: Escribe `mock-key` para usar el generador sin internet.
        """)

st.sidebar.caption("Constitución v1.1.0: Cero secretos persistidos.")

# Session state initialization
st.session_state.api_key = api_key_input
st.session_state.openai_key = api_key_input  # Retrocompatibilidad
st.session_state.llm_provider = selected_provider
st.session_state.llm_model = selected_model_name

# Header (Hero Banner TalentIA Style)
render_header(
    title="⚡ AgentIA Microservice Code Studio",
    subtitle="Plataforma de generación autónoma, diseño arquitectónico y verificación hermética de microservicios Java 21 / Spring Boot 3.x",
    badge="v1.1.0 • Java 21 LTS • Spring Boot 3.x • Sandbox Hermético",
)


# Global Persistent Stepper
try:
    from views.lifecycle_stepper import render_lifecycle_stepper
    render_lifecycle_stepper(st.session_state.backend_url, st.session_state.active_session_id)
except Exception:
    pass

# Main Navigation Tabs (Canonical 10 Tabs)
tab_overview, tab_reqs, tab_arch, tab_models, tab_ingest, tab_monitor, tab_explorer, tab_security, tab_devops, tab_export = st.tabs(
    TAB_LABELS,
    default=st.session_state.get("active_main_tab", TAB_LABELS[0]),
)

with tab_overview:
    try:
        from views.overview_view import render_overview_view
        render_overview_view(st.session_state.backend_url, st.session_state.active_session_id)
    except Exception as e:
        st.info(f"Vista de Resumen en construcción... ({e})")

with tab_reqs:
    try:
        from views.requirements_view import render_requirements_view
        render_requirements_view(
            st.session_state.backend_url,
            st.session_state.get("api_key"),
            st.session_state.get("llm_provider"),
            session_id=st.session_state.active_session_id,
        )
    except ImportError:
        st.info("Vista de Requisitos en construcción...")

with tab_arch:
    try:
        from views.architecture_view import render_architecture_view
        render_architecture_view(
            st.session_state.backend_url,
            st.session_state.get("api_key"),
            st.session_state.get("llm_provider"),
        )
    except ImportError:
        st.info("Vista de Diseño Arquitectónico en construcción...")

with tab_models:
    try:
        from views.models_sql_view import render_models_sql_view
        render_models_sql_view(
            st.session_state.backend_url,
            st.session_state.get("api_key"),
            st.session_state.get("llm_provider"),
        )
    except ImportError:
        st.info("Vista de Modelos de Dominio & Esquema SQL en construcción...")

with tab_ingest:
    try:
        from views.ingestion_view import render_ingestion_view
        render_ingestion_view(st.session_state.backend_url)
    except ImportError:
        st.info("Vista de Ingesta en construcción...")

with tab_monitor:
    try:
        from views.monitor_view import render_monitor_view
        render_monitor_view(st.session_state.backend_url, st.session_state.active_session_id)
    except ImportError:
        st.info("Vista de Monitoreo en vivo en construcción...")

with tab_explorer:
    try:
        from views.explorer_view import render_explorer_view
        render_explorer_view(st.session_state.backend_url, st.session_state.active_session_id)
    except ImportError:
        st.info("Vista de Explorador de Código en construcción...")

with tab_security:
    try:
        from views.security_view import render_security_view
        render_security_view(st.session_state.backend_url, st.session_state.active_session_id, key_prefix="tab7_")
    except ImportError:
        st.info("Vista de Seguridad & Calidad en construcción...")

with tab_devops:
    try:
        from views.devops_view import render_devops_view
        render_devops_view(st.session_state.backend_url, st.session_state.active_session_id)
    except ImportError:
        st.info("Vista de DevOps & Despliegue en construcción...")

with tab_export:
    try:
        from views.export_view import render_export_view
        render_export_view(st.session_state.backend_url, st.session_state.active_session_id)
    except ImportError:
        st.info("Vista de Exportación en construcción...")



