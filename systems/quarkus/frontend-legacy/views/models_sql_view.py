import io
import json
import zipfile
from typing import Optional
import requests
import streamlit as st

def render_models_sql_view(backend_url: str, openai_key: Optional[str] = None, provider: Optional[str] = None):
    st.header("💾 3. Modelos de Dominio JPA & Esquema SQL Relacional")
    st.markdown(
        "Inspecciona y afina las entidades de dominio JPA fuertemente tipadas, "
        "las claves primarias autonuméricas (`Long id`), los campos de auditoría (`Instant createdAt`, `updatedAt`), "
        "el diagrama Entidad-Relación visual (Mermaid `erDiagram`) y los scripts relacionales sincronizados "
        "(`schema.sql` y `data.sql`) compatibles con PostgreSQL y H2 en memoria (`MODE=PostgreSQL`)."
    )

    active_api_key = openai_key or st.session_state.get("api_key") or st.session_state.get("openai_key")
    active_provider = provider or st.session_state.get("llm_provider")

    if "data_model_design" not in st.session_state:
        st.session_state.data_model_design = None

    design = st.session_state.get("data_model_design")
    draft = st.session_state.get("draft_spec")
    arch_design = st.session_state.get("architecture_design")

    # If no design has been synthesized yet
    if not design:
        if draft or arch_design:
            st.info("💡 Tienes una especificación activa. Sintetiza los modelos de dominio JPA, esquema SQL y diagrama ER:")
            if st.button("💾 Sintetizar Modelos de Dominio & Esquema SQL con IA", key="btn_sql_synthesize", type="primary", use_container_width=True):
                with st.spinner("Sintetizando entidades JPA, DDL relacional, datos semilla y diagrama ER..."):
                    draft_payload = draft
                    if not draft_payload and arch_design:
                        draft_payload = {
                            "serviceName": arch_design.get("serviceName"),
                            "packageName": arch_design.get("packageName"),
                            "basePort": arch_design.get("basePort", 8080),
                            "entities": arch_design.get("entities", []),
                            "userStories": arch_design.get("userStories", []),
                        }
                    payload = {
                        "draft": draft_payload,
                        "apiKey": active_api_key,
                        "provider": active_provider,
                    }
                    try:
                        headers = {}
                        if active_api_key:
                            headers["X-LLM-API-Key"] = active_api_key
                        if active_provider:
                            headers["X-LLM-Provider"] = active_provider
                        resp = requests.post(f"{backend_url}/api/v1/models/generate", json=payload, headers=headers, timeout=180)
                        if resp.status_code == 200:
                            st.session_state.data_model_design = resp.json()
                            st.success("✅ ¡Modelos de dominio y esquema SQL sintetizados exitosamente!")
                            st.rerun()
                        else:
                            st.error(f"Error {resp.status_code}: {resp.text}")
                    except requests.exceptions.Timeout:
                        st.error("⏱️ Tiempo de espera agotado al generar modelos de datos y esquema SQL con IA. Intenta nuevamente.")
                    except Exception as e:
                        st.error(f"Error conectando con el backend: {e}")
        else:
            st.warning("⚠️ No hay ninguna especificación activa. Primero redacta requisitos en **'📝 1. Requisitos & Historias'** o genera la arquitectura en **'🏗️ 2. Diseño Arquitectónico'**.")
        return

    # Overview metadata
    st.caption(
        f"Microservicio: **{design.get('serviceName', 'service')}** | "
        f"Paquete Base: `{design.get('packageName', 'com.example')}` | "
        f"Entidades: **{len(design.get('entities', []))}**"
    )

    # Section 1: Mermaid Entity-Relationship Diagram
    st.markdown("---")
    st.subheader("📊 1. Diagrama Entidad-Relación Visual (Mermaid erDiagram)")
    st.caption("Visualización de entidades, atributos, tipos SQL y cardinalidades relacionales:")

    mermaid_code = design.get("mermaidErDiagram", "")
    if mermaid_code:
        st.markdown(f"```mermaid\n{mermaid_code}\n```")
        with st.expander("🔍 Ver código fuente Mermaid erDiagram"):
            st.code(mermaid_code, language="mermaid")
    else:
        st.info("Diagrama ER Mermaid no disponible.")

    # Section 2: Interactive JPA Domain Entities
    st.markdown("---")
    st.subheader("🏛️ 2. Entidades de Dominio JPA & Atributos Tipados")
    st.caption("Inspecciona los atributos de cada entidad con sus mapeos a columnas SQL y tipos Java 21:")

    entities = design.get("entities", [])
    java_classes = design.get("javaEntityClasses", {})

    for idx, entity in enumerate(entities):
        ent_name = entity.get("name", f"Entity_{idx}")
        table_name = entity.get("tableName", ent_name.lower() + "s")
        desc = entity.get("description", "")

        with st.expander(f"📦 Entidad: {ent_name}  ➔  Tabla SQL: `{table_name}`", expanded=True):
            if desc:
                st.markdown(f"*{desc}*")

            # Attributes table
            attrs = entity.get("attributes", [])
            attr_rows = []
            for attr in attrs:
                pk_badge = "🔑 Sí" if attr.get("isPrimaryKey") else "No"
                null_badge = "Sí" if attr.get("nullable") else "🔒 Not Null"
                uniq_badge = "⭐ Único" if attr.get("unique") else "No"
                rules = ", ".join(attr.get("validationRules", [])) or "-"

                attr_rows.append({
                    "Campo (Java)": attr.get("name"),
                    "Columna (SQL)": attr.get("columnName"),
                    "Tipo Java": attr.get("javaType"),
                    "Tipo SQL": attr.get("sqlType"),
                    "PK": pk_badge,
                    "Nulabilidad": null_badge,
                    "Unicidad": uniq_badge,
                    "Validaciones": rules,
                })

            if attr_rows:
                st.dataframe(attr_rows, use_container_width=True)

            # Relationships
            rels = entity.get("relationships", [])
            if rels:
                st.markdown("**🔗 Relaciones de Dominio:**")
                for r in rels:
                    fk_info = f" (Columna FK: `{r.get('foreignKeyColumn')}`)" if r.get("foreignKeyColumn") else ""
                    join_info = f" [Tabla Unión: `{r.get('joinTableName')}`]" if r.get("joinTableName") else ""
                    st.markdown(f"- **{r.get('relationshipType')}** hacia `{r.get('targetEntity')}`{fk_info}{join_info}: {r.get('description', '')}")

            # Java source preview
            if ent_name in java_classes:
                with st.expander(f"☕ Ver Código Java JPA ({ent_name}.java)"):
                    st.code(java_classes[ent_name], language="java")

    # Section 3: Synchronized SQL Scripts
    st.markdown("---")
    st.subheader("📄 3. Scripts SQL Relacionales Sincronizados")
    st.caption("Dialecto ANSI SQL compatible con **PostgreSQL** y **H2** en memoria (`MODE=PostgreSQL`). Hermético y autónomo.")

    sql_schema = design.get("sqlSchema", {})
    sql_tab1, sql_tab2 = st.tabs(["📄 schema.sql (DDL de Tablas e Índices)", "🌱 data.sql (DML de Datos Semilla)"])

    with sql_tab1:
        st.caption("Estructura DDL ordenada topológicamente (padres antes que hijos) con claves foráneas:")
        st.code(sql_schema.get("schemaDdl", "-- Sin DDL generado"), language="sql")

    with sql_tab2:
        st.caption("Datos iniciales de prueba derivados de las precondiciones 'Given' de los escenarios de aceptación:")
        st.code(sql_schema.get("seedDml", "-- Sin DML generado"), language="sql")

    # Section 4: AI Model & SQL Refinement Assistant
    st.markdown("---")
    st.subheader("💬 4. Asistente IA de Refinamiento de Modelos & Esquema SQL")
    st.caption("Ajusta columnas, tipos de datos, índices únicos, restricciones de nulabilidad o añade nuevas relaciones mediante lenguaje natural:")

    col_target, _ = st.columns([1, 1])
    with col_target:
        entity_options = ["Todas las entidades"] + [e.get("name") for e in entities if e.get("name")]
        selected_target = st.selectbox("Entidad objetivo para el refinamiento:", entity_options)

    refine_prompt = st.text_area(
        "Instrucción de refinamiento:",
        placeholder="Ejemplo: 'Añade un campo trackingNumber de tipo String con restricción de unicidad en la entidad Order y regenera el DDL'",
        height=85
    )

    if st.button("✨ Refinar Modelos & Esquema SQL con IA", key="btn_sql_refine", type="primary", use_container_width=True):
        if not refine_prompt.strip():
            st.warning("Por favor escribe una instrucción de refinamiento antes de ejecutar.")
        else:
            with st.spinner("Refinando entidades de dominio, esquema SQL y diagrama ER con IA..."):
                target_arg = None if selected_target == "Todas las entidades" else selected_target
                payload = {
                    "currentResponse": design,
                    "feedbackPrompt": refine_prompt.strip(),
                    "targetEntity": target_arg,
                    "apiKey": active_api_key,
                }
                try:
                    headers = {"X-LLM-API-Key": active_api_key} if active_api_key else {}
                    resp = requests.post(f"{backend_url}/api/v1/models/refine", json=payload, headers=headers, timeout=180)
                    if resp.status_code == 200:
                        st.session_state.data_model_design = resp.json()
                        st.success("✅ ¡Modelos y esquema SQL refinados exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")
                except requests.exceptions.Timeout:
                    st.error("⏱️ Tiempo de espera agotado al refinar modelos y esquema SQL con IA. Intenta nuevamente.")
                except Exception as e:
                    st.error(f"Error conectando con el backend: {e}")

    # Section 5: Downloads & Pipeline Handoff
    st.markdown("---")
    st.subheader("🚀 5. Exportación de Artefactos y Transferencia al Motor de Generación")

    down_col1, down_col2, down_col3 = st.columns(3)

    with down_col1:
        st.download_button(
            label="📥 Descargar schema.sql",
            key="dl_sql_schema",
            data=sql_schema.get("schemaDdl", "").encode("utf-8"),
            file_name=f"schema-{design.get('serviceName', 'service')}.sql",
            mime="application/sql",
            use_container_width=True,
        )

    with down_col2:
        st.download_button(
            label="📥 Descargar data.sql",
            key="dl_sql_data",
            data=sql_schema.get("seedDml", "").encode("utf-8"),
            file_name=f"data-{design.get('serviceName', 'service')}.sql",
            mime="application/sql",
            use_container_width=True,
        )

    with down_col3:
        # Create in-memory zip archive with all Java entity classes + SQL files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("schema.sql", sql_schema.get("schemaDdl", ""))
            zf.writestr("data.sql", sql_schema.get("seedDml", ""))
            for cls_name, cls_source in java_classes.items():
                zf.writestr(f"model/{cls_name}.java", cls_source)
        zip_data = zip_buffer.getvalue()

        st.download_button(
            label="📥 Descargar Clases Java (.zip)",
            key="dl_sql_java_entities_zip",
            data=zip_data,
            file_name=f"domain-entities-{design.get('serviceName', 'service')}.zip",
            mime="application/zip",
            use_container_width=True,
        )

    st.markdown("#### 🔄 Transferencia al Motor de Generación")
    if st.button("➡️ Transferir al Motor de Generación de Código", key="btn_sql_transfer_gen", type="primary", use_container_width=True):
        with st.spinner("Compilando blueprint de especificación enriquecido y transfiriendo al generador..."):
            # Map design entities to blueprint format
            blueprint_entities = [
                {
                    "name": e["name"],
                    "tableName": e.get("tableName", e["name"].lower() + "s"),
                    "attributes": [
                        {
                            "name": a["name"],
                            "type": a.get("javaType", "String"),
                            "nullable": a.get("nullable", False),
                            "isPrimaryKey": a.get("isPrimaryKey", False),
                            "validationRules": a.get("validationRules", [])
                        }
                        for a in e.get("attributes", [])
                    ]
                }
                for e in design.get("entities", [])
            ]

            user_stories = (
                (st.session_state.get("draft_spec") or {}).get("userStories")
                or (st.session_state.get("architecture_design") or {}).get("userStories")
                or []
            )

            blueprint_payload = {
                "serviceName": design.get("serviceName"),
                "packageName": design.get("packageName"),
                "basePort": design.get("basePort", 8080),
                "entities": blueprint_entities,
                "userStories": user_stories,
            }

            try:
                resp = requests.post(f"{backend_url}/api/v1/specifications", json=blueprint_payload, timeout=10)
                if resp.status_code == 201:
                    data = resp.json()
                    st.session_state.current_spec_id = data["specId"]
                    st.session_state.parsed_spec = data
                    st.success(f"🎉 ¡Modelos de dominio del microservicio '{data['serviceName']}' transferidos exitosamente!")
                    st.info("👉 Pasa a la pestaña **'🚀 5. Generación & Logs'** para iniciar la compilación y pruebas autónomas.")
                else:
                    st.error(f"Error al transferir: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"Error conectando con el backend: {e}")

