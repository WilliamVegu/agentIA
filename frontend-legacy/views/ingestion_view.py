import json
import streamlit as st
import requests

def render_ingestion_view(backend_url: str):
    st.header("📥 Ingesta y Validación de Especificaciones")
    st.markdown(
        "Carga una especificación formal de microservicio (`spec.md`) generada por Spec Kit "
        "o proporciona un blueprint estructurado en formato JSON."
    )

    ingest_mode = st.radio("Método de Ingesta:", ["Cargar archivo spec.md (Markdown)", "Pegar Blueprint JSON"], horizontal=True)

    if ingest_mode == "Cargar archivo spec.md (Markdown)":
        uploaded_file = st.file_uploader("Selecciona archivo spec.md", type=["md", "markdown"])
        if uploaded_file is not None:
            if st.button("Validar y Procesar Archivo", key="btn_ingest_val_file", type="primary"):
                with st.spinner("Parseando y validando especificación..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/markdown")}
                        resp = requests.post(f"{backend_url}/api/v1/specifications/upload", files=files, timeout=10)
                        if resp.status_code == 201:
                            data = resp.json()
                            st.session_state.current_spec_id = data["specId"]
                            st.session_state.parsed_spec = data
                            st.success(f"✅ Especificación '{data['serviceName']}' validada exitosamente!")
                        else:
                            st.error(f"Error {resp.status_code}: {resp.text}")
                    except Exception as e:
                        st.error(f"Error conectando al backend: {e}")

    else:
        sample_json = {
            "serviceName": "payment-service",
            "packageName": "com.corp.payment",
            "basePort": 8080,
            "entities": [
                {
                    "name": "Payment",
                    "tableName": "payments",
                    "attributes": [
                        {"name": "id", "type": "UUID", "isPrimaryKey": True},
                        {"name": "customerEmail", "type": "String", "validationRules": ["@NotBlank", "@Email"]},
                        {"name": "amount", "type": "BigDecimal", "validationRules": ["@NotNull", "@Positive"]}
                    ]
                }
            ],
            "userStories": [
                {
                    "id": "US-1",
                    "priority": "P1",
                    "role": "Customer",
                    "intent": "submit payment",
                    "benefit": "complete order",
                    "scenarios": [
                        {
                            "scenarioId": "AC-1.1",
                            "given": "valid payment details",
                            "when": "POST /payments is invoked",
                            "then": "payment is saved with status SUCCESS and 201 returned"
                        }
                    ]
                }
            ]
        }
        json_input = st.text_area("Blueprint JSON:", value=json.dumps(sample_json, indent=2), height=300)
        if st.button("Validar Blueprint JSON", key="btn_ingest_val_json", type="primary"):
            with st.spinner("Validando JSON..."):
                try:
                    payload = json.loads(json_input)
                    resp = requests.post(f"{backend_url}/api/v1/specifications", json=payload, timeout=10)
                    if resp.status_code == 201:
                        data = resp.json()
                        st.session_state.current_spec_id = data["specId"]
                        st.session_state.parsed_spec = data
                        st.success(f"✅ Especificación '{data['serviceName']}' validada exitosamente!")
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")
                except json.JSONDecodeError as jde:
                    st.error(f"JSON inválido: {jde}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    # Display validated summary card if available
    if st.session_state.get("parsed_spec"):
        spec = st.session_state.parsed_spec
        st.markdown("---")
        st.subheader("📋 Resumen de la Especificación Activa")
        col1, col2, col3 = st.columns(3)
        col1.metric("Microservicio", spec.get("serviceName"))
        col2.metric("Entidades de Dominio", spec.get("entityCount"))
        col3.metric("Historias de Usuario", spec.get("storyCount"))
        st.info(f"Paquete Java configurado: `{spec.get('packageName')}` (Java 21 LTS / Spring Boot 3.x)")

        if st.button("➡️ Proceder a Generar Microservicio", key="btn_ingest_proceed_gen", type="secondary"):
            st.session_state["active_main_tab"] = "🚀 5. Generación & Logs"
            st.info("Pasa a la pestaña '🚀 5. Generación & Logs' para iniciar el proceso.")
            st.rerun()

