"""
Agente Analista (Lorena - Fábrica de Agentes Quarkus)
Responsabilidades:
1. Analizar el pedido y formular 3 a 5 preguntas de aclaración (Regla: 'Preguntar antes de construir').
   - Con LLM real (Gemini, Groq, OpenAI) si hay API Key.
   - Con generador dinámico de dominio adaptativo en modo offline/mock.
2. Formular Historias de Usuario con criterios de aceptación BDD (Given / When / Then).
3. Diseñar el Modelo Relacional de Base de Datos (Tablas, Columnas, PK/FK, Relaciones, Diagrama ER Mermaid y DDL SQL).
4. Redactar el Contrato OpenAPI 3.1 en YAML con esquemas rigurosos.
"""

from typing import List, Dict, Any, Tuple, Optional
import os
import json
import re
import yaml

from app.models.quarkus_factory import (
    FactoryOrder,
    ClarificationQuestion,
    ClarificationAnswerItem,
    OrderStatusEnum,
    UserStory,
    BddScenario,
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    DatabaseModelProposal
)
from app.services.llm_factory import LLMFactory


class AnalystAgent:

    @staticmethod
    def _extract_domain(order: FactoryOrder) -> Dict[str, Any]:
        """
        Extrae heurísticamente el dominio del pedido para respaldar generación dinámica
        cuando no haya conexión a internet o falle la llamada al LLM.
        """
        text = f"{order.basic_data.service_name} {order.business.description}".lower()

        # Detección de dominio común
        if any(w in text for w in ["cita", "medico", "paciente", "clinica", "hospital", "doctor", "salud", "odontolog"]):
            return {
                "domain": "Salud / Clínica",
                "main_singular": "Cita",
                "main_plural": "Citas",
                "main_table": "citas_medicas",
                "sub_singular": "Paciente",
                "sub_plural": "Pacientes",
                "sub_table": "pacientes",
                "detail_singular": "Diagnostico",
                "detail_table": "diagnosticos",
                "route": "/citas",
                "id_field": "citaId",
                "status_enum": ["AGENDADA", "CONFIRMADA", "ATENDIDA", "CANCELADA"]
            }
        elif any(w in text for w in ["factura", "pago", "cobro", "invoice", "tribut", "contab"]):
            return {
                "domain": "Facturación y Cobros",
                "main_singular": "Factura",
                "main_plural": "Facturas",
                "main_table": "facturas",
                "sub_singular": "Cliente",
                "sub_plural": "Clientes",
                "sub_table": "clientes",
                "detail_singular": "ItemFactura",
                "detail_table": "items_factura",
                "route": "/facturas",
                "id_field": "facturaId",
                "status_enum": ["EMITIDA", "PAGADA", "ANULADA", "VENCIDA"]
            }
        elif any(w in text for w in ["curso", "estudiante", "alumno", "profesor", "matricul", "aula", "escuela"]):
            return {
                "domain": "Educación y Matrículas",
                "main_singular": "Matricula",
                "main_plural": "Matriculas",
                "main_table": "matriculas",
                "sub_singular": "Estudiante",
                "sub_plural": "Estudiantes",
                "sub_table": "estudiantes",
                "detail_singular": "Curso",
                "detail_table": "cursos_inscritos",
                "route": "/matriculas",
                "id_field": "matriculaId",
                "status_enum": ["PENDIENTE", "ACTIVA", "COMPLETADA", "RETIRADA"]
            }
        elif any(w in text for w in ["hotel", "reserva", "habitacion", "huesped", "vuelo", "pasaje"]):
            return {
                "domain": "Reservas y Hotelería",
                "main_singular": "Reserva",
                "main_plural": "Reservas",
                "main_table": "reservas",
                "sub_singular": "Huesped",
                "sub_plural": "Huespedes",
                "sub_table": "huespedes",
                "detail_singular": "Habitacion",
                "detail_table": "habitaciones_reserva",
                "route": "/reservas",
                "id_field": "reservaId",
                "status_enum": ["SOLICITADA", "CONFIRMADA", "CHECKIN", "CANCELADA"]
            }
        elif any(w in text for w in ["veterinaria", "mascota", "perro", "gato", "animal"]):
            return {
                "domain": "Veterinaria y Mascotas",
                "main_singular": "AtencionVeterinaria",
                "main_plural": "Atenciones",
                "main_table": "atenciones_veterinarias",
                "sub_singular": "Mascota",
                "sub_plural": "Mascotas",
                "sub_table": "mascotas",
                "detail_singular": "Tratamiento",
                "detail_table": "tratamientos_aplicados",
                "route": "/atenciones",
                "id_field": "atencionId",
                "status_enum": ["PROGRAMADA", "EN_CURSO", "FINALIZADA", "CANCELADA"]
            }
        else:
            # Fallback natural basado en el nombre del servicio o "Pedidos"
            name_clean = order.basic_data.service_name.replace("-service", "").replace("_service", "").replace("-", " ").strip()
            entity_name = name_clean.title() if name_clean else "Registro"
            plural_name = entity_name + "s" if not entity_name.endswith("s") else entity_name
            return {
                "domain": entity_name,
                "main_singular": entity_name,
                "main_plural": plural_name,
                "main_table": entity_name.lower() + "s",
                "sub_singular": "Cliente",
                "sub_plural": "Clientes",
                "sub_table": "clientes",
                "detail_singular": "Item" + entity_name,
                "detail_table": "items_" + entity_name.lower(),
                "route": "/" + entity_name.lower() + "s",
                "id_field": "id",
                "status_enum": ["PENDIENTE", "PROCESANDO", "COMPLETADO", "CANCELADO"]
            }

    @staticmethod
    def generate_clarification_questions(
        order: FactoryOrder,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[List[ClarificationQuestion], int]:
        """
        Regla clave: Preguntar antes de construir.
        Formula preguntas de aclaración estructuradas a través de las 12 dimensiones clave de negocio:
        Objetivo, Necesidad, Usuarios, Funcionalidades, Información, Reglas de negocio, Validaciones,
        Flujo de trabajo, Notificaciones, Reportes, Integraciones y Prioridad.
        """
        # 1. Si hay API key disponible y no es modo mock, invocar al LLM real
        if not LLMFactory.is_mock(api_key, provider):
            try:
                chat_model = LLMFactory.get_chat_model(
                    api_key=api_key,
                    provider=provider,
                    model_name=model_name,
                    temperature=0.3
                )
                if chat_model:
                    from langchain_core.messages import SystemMessage, HumanMessage
                    sys_msg = SystemMessage(content=(
                        "Eres el Agente Analista experto de una fábrica de microservicios Quarkus 3.x / Java 21. "
                        "Aplica estrictamente la regla 'Preguntar antes de construir'. Analiza exhaustivamente el pedido del usuario "
                        "y genera entre 4 y 7 preguntas de aclaración de alto impacto técnico y de negocio. "
                        "Debes seleccionar y contextualizar las preguntas a partir del siguiente marco de 12 dimensiones:\n"
                        "1. Objetivo: ¿Qué problema específico de tu negocio deseas resolver?\n"
                        "2. Necesidad: ¿Qué proceso de negocio deseas automatizar o mejorar?\n"
                        "3. Usuarios: ¿Quiénes utilizarán el sistema? (Clientes, empleados, administradores, proveedores).\n"
                        "4. Funcionalidades: ¿Qué capacidades y operaciones indispensables debe proveer la API?\n"
                        "5. Información: ¿Qué datos, atributos y entidades necesitas registrar o administrar?\n"
                        "6. Reglas del negocio: ¿Qué condiciones, restricciones o políticas debe cumplir el proceso?\n"
                        "7. Validaciones: ¿Qué información es obligatoria y qué datos no deberían aceptarse jamás?\n"
                        "8. Flujo de trabajo: ¿Qué pasos y estados sigue el proceso desde que comienza hasta que termina?\n"
                        "9. Notificaciones: ¿Necesitas recibir alertas o avisos automáticos cuando ocurra algo?\n"
                        "10. Reportes: ¿Qué información, métricas o resultados necesitas consultar o filtrar?\n"
                        "11. Integraciones: ¿Necesitas que el sistema se conecte con otras herramientas, APIs o sistemas?\n"
                        "12. Prioridad: ¿Qué funcionalidades son indispensables (MVP) y cuáles podrían implementarse después?\n\n"
                        "Responde ÚNICAMENTE en JSON plano como array de objetos sin delimitadores ```json:\n"
                        "[\n"
                        "  {\n"
                        '    "id": "q1-dimension",\n'
                        '    "category": "Reglas del negocio",\n'
                        '    "question": "¿Pregunta precisa y técnica adaptada exactamente al negocio del usuario?",\n'
                        '    "context_or_reason": "Por qué esta aclaración es crítica para el contrato OpenAPI y la base de datos",\n'
                        '    "suggested_options": ["Opción A recomendada", "Opción B alternativa", "Opción C"]\n'
                        "  }\n"
                        "]"
                    ))
                    human_msg = HumanMessage(content=(
                        f"Servicio: {order.basic_data.service_name}\n"
                        f"Equipo: {order.basic_data.team}\n"
                        f"Descripción del Pedido de Negocio: {order.business.description}\n"
                        f"Motor de Base de Datos: {order.technical.database.value}\n"
                        f"Mecanismo de Seguridad: {order.technical.security.value}\n"
                        f"Kafka Habilitado: {order.technical.enable_kafka}"
                    ))
                    resp = chat_model.invoke([sys_msg, human_msg])
                    raw = resp.content if hasattr(resp, "content") else str(resp)
                    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
                    cleaned = re.sub(r"\s*```$", "", cleaned)
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list) and len(parsed) >= 3:
                        questions = [
                            ClarificationQuestion(
                                id=item.get("id", f"q{i+1}"),
                                category=item.get("category", "Negocio"),
                                question=item.get("question", ""),
                                context_or_reason=item.get("context_or_reason", ""),
                                suggested_options=item.get("suggested_options", [])
                            )
                            for i, item in enumerate(parsed[:7])
                        ]
                        return questions, 4200
            except Exception as e:
                print(f"[AnalystAgent] Error calling LLM for clarification questions: {e}")

        # 2. Generador Dinámico de Dominio (Adaptativo al marco de 12 dimensiones)
        dom = AnalystAgent._extract_domain(order)
        desc = order.business.description

        questions: List[ClarificationQuestion] = []

        questions.append(ClarificationQuestion(
            id=f"q1-{dom['main_table']}-workflow",
            category="Flujo de trabajo & Reglas de negocio",
            question=f"Flujo de trabajo: ¿Cuáles son los estados permitidos en el ciclo de vida de {dom['main_plural'].lower()} y bajo qué condiciones se puede cancelar o anular?",
            context_or_reason=f"Define la máquina de estados en el servicio Quarkus y las restricciones en base de datos para {dom['main_table']}.",
            suggested_options=[
                f"Estados: {', '.join(dom['status_enum'])}. Solo se permite cancelar en estado inicial '{dom['status_enum'][0]}'.",
                f"Permitir cancelación siempre que no esté en estado final ({dom['status_enum'][-2]}), registrando motivo de cancelación.",
                f"Flujo estricto: transición secuencial {' -> '.join(dom['status_enum'])} con auditoría de cambio de estado."
            ]
        ))

        questions.append(ClarificationQuestion(
            id=f"q2-{dom['sub_table']}-info",
            category="Información & Relaciones",
            question=f"Información: ¿Cómo se relaciona la entidad principal '{dom['main_singular']}' con '{dom['sub_singular']}' y qué datos deben ser obligatorios?",
            context_or_reason=f"Permite definir la clave foránea (FK) en la tabla relacional y las anotaciones @ManyToOne / @OneToMany en Panache.",
            suggested_options=[
                f"Relación 1 a N: Cada {dom['sub_singular']} puede tener múltiples {dom['main_plural']}. Se requiere ID de {dom['sub_singular']} y datos de contacto.",
                f"Relación directa embebida: Almacenar referencia {dom['sub_singular']}Id (UUID) con validación de existencia previa.",
                f"Esquema desacoplado con código externo/documento de identidad único."
            ]
        ))

        questions.append(ClarificationQuestion(
            id=f"q3-{dom['main_table']}-queries",
            category="Reportes & Consultas",
            question=f"Reportes y consultas: Al consultar {dom['main_plural'].lower()}, ¿qué filtros, ordenamiento y paginación se requieren?",
            context_or_reason="Determina los índices relacionales de base de datos y los query parameters del contrato OpenAPI.",
            suggested_options=[
                f"Filtro obligatorio por estado (?status=...) con paginación estándar (page=0, size=20) y orden cronológico descendente.",
                f"Búsqueda combinada por estado y por identificador de {dom['sub_singular']}, con soporte de conteo total.",
                f"Consulta paginada con rango de fechas de creación (startDate, endDate)."
            ]
        ))

        questions.append(ClarificationQuestion(
            id=f"q4-{dom['main_table']}-validation",
            category="Validaciones & Reglas del negocio",
            question="Validaciones: ¿Qué reglas de validación deben aplicarse para rechazar solicitudes con error HTTP 400 Bad Request o 409 Conflict?",
            context_or_reason="Establece los Jakarta Validation constraints (@NotNull, @Size, @DecimalMin) en los Java Records del contrato OpenAPI.",
            suggested_options=[
                "Validación estricta de campos obligatorios no vacíos, identificadores UUID válidos y montos mayores a cero.",
                "Validación de unicidad en identificadores externos y rechazo inmediato si ya existe duplicado (HTTP 409).",
                "Validación de formato de correo, números de teléfono y longitud mínima de descripción."
            ]
        ))

        if order.technical.security.value.startswith("JWT") or order.technical.security.value.startswith("OAuth2"):
            questions.append(ClarificationQuestion(
                id="q5-security-roles",
                category="Usuarios & Permisos",
                question=f"Usuarios: Para la seguridad {order.technical.security.value}, ¿qué roles o perfiles tienen permisos para crear y modificar {dom['main_plural'].lower()}?",
                context_or_reason="Configura las anotaciones Quarkus @RolesAllowed y la política de seguridad del contrato OpenAPI.",
                suggested_options=[
                    "Rol 'admin' con control total; rol 'operador' o 'cliente' solo consulta y creación de propios.",
                    "Cualquier token JWT válido corporativo con claim de usuario verificado.",
                    "Endpoints de consulta públicos; endpoints de creación y modificación restringidos a 'admin'."
                ]
            ))

        consumed_tokens = 3200 + (len(questions) * 350)
        return questions, consumed_tokens

    @staticmethod
    def synthesize_user_stories(
        order: FactoryOrder,
        answers_dict: Dict[str, str],
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[List[UserStory], int]:
        """
        Genera Historias de Usuario con formato ágil y escenarios BDD (Dado / Cuando / Entonces).
        Garantiza un mínimo de 10 Historias de Usuario para validar exhaustivamente el alcance del microservicio.
        """
        dom = AnalystAgent._extract_domain(order)

        # 1. Llamada a LLM real con Gemini o DeepSeek si hay API Key disponible o en entorno
        detected = LLMFactory.detect_provider(api_key, provider, model_name)
        effective_key = (api_key or "").strip()
        if not effective_key:
            if detected == "deepseek":
                effective_key = os.environ.get("DEEPSEEK_API_KEY")
            else:
                effective_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if detected != "mock" and effective_key:
            sys_msg_text = (
                "Eres el Agente Analista experto en metodologías ágiles y BDD en una fábrica de microservicios Quarkus 3.x. "
                "A partir del pedido de negocio y de las especificaciones, debes generar un catálogo exhaustivo "
                "de AL MENOS 10 Historias de Usuario ágiles (identificadas de HU-01 a HU-10 o más según la complejidad) con formato:\n"
                "'Como [rol], quiero [objetivo] para [beneficio]', cada una con 1 o 2 escenarios BDD formales (Given / When / Then).\n"
                "CRÍTICO: Las historias deben modelar FIELMENTE y de forma dinámica el dominio de negocio exacto especificado por el usuario, sin plantillas prefabricadas.\n"
                "Responde ÚNICAMENTE en JSON plano como array de objetos sin delimitadores ```json:\n"
                "[\n"
                "  {\n"
                '    "id": "HU-01",\n'
                '    "title": "Título descriptivo de la historia",\n'
                '    "role": "Como [rol específico]",\n'
                '    "goal": "quiero [acción concreta]",\n'
                '    "benefit": "para [valor de negocio]",\n'
                '    "scenarios": [\n'
                '      {\n'
                '        "title": "Escenario exitoso",\n'
                '        "given": "Dado que [precondición]",\n'
                '        "when": "Cuando [acción]",\n'
                '        "then": "Entonces [resultado esperado]"\n'
                '      }\n'
                '    ]\n'
                "  }\n"
                "]"
            )
            human_msg_text = (
                f"Servicio: {order.basic_data.service_name}\n"
                f"Equipo: {order.basic_data.team}\n"
                f"Descripción de negocio:\n{order.business.description}\n"
                f"Base de Datos: {order.technical.database.value}\n"
                f"Seguridad: {order.technical.security.value}\n"
                f"Aclaraciones acordadas:\n{json.dumps(answers_dict, ensure_ascii=False, indent=2)}"
            )
            try:
                raw = LLMFactory.call_chat(
                    prompt=human_msg_text,
                    system_prompt=sys_msg_text,
                    api_key=effective_key,
                    provider=detected,
                    model_name=model_name,
                    temperature=0.2,
                    max_tokens=8192,
                    response_mime_type="application/json"
                )
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) >= 2:
                    stories = [
                        UserStory(
                            id=item.get("id", f"HU-{i+1:02d}"),
                            title=item.get("title", f"Historia {i+1}"),
                            role=item.get("role", "Como usuario"),
                            goal=item.get("goal", "quiero operar el servicio"),
                            benefit=item.get("benefit", "para cumplir con el negocio"),
                            scenarios=[
                                BddScenario(
                                    title=sc.get("title", "Escenario"),
                                    given=sc.get("given", ""),
                                    when=sc.get("when", ""),
                                    then=sc.get("then", "")
                                )
                                for sc in item.get("scenarios", [])
                            ]
                        )
                        for i, item in enumerate(parsed)
                    ]
                    return stories, 4500
            except Exception as e:
                provider_label = "DeepSeek" if detected == "deepseek" else "Gemini"
                raise RuntimeError(f"Error en Requirements Agent / Historias de Usuario ({provider_label}): {str(e)}")

        # 2. Generador Determinista de 10 Historias de Usuario (Adaptativo al dominio solo si es mock explícito)
        main = dom["main_singular"]
        plural = dom["main_plural"]
        sub = dom["sub_singular"]
        status0 = dom["status_enum"][0]
        status_canc = dom["status_enum"][-1]

        stories = [
            UserStory(
                id="HU-01",
                title=f"Creación y registro de {plural}",
                role=f"Como operador o cliente del servicio",
                goal=f"quiero registrar un nuevo {main.lower()} con sus datos obligatorios y detalle asociado",
                benefit=f"para procesar la transacción y dejar constancia en la base de datos con estado {status0}",
                scenarios=[
                    BddScenario(
                        title=f"Registro exitoso de {main.lower()}",
                        given=f"Dado un cliente con datos de entrada válidos y detalles requeridos",
                        when=f"Cuando se envía un POST a {dom['route']} con el payload estructurado",
                        then=f"Entonces se persiste el registro en {dom['main_table']} con ID único, estado '{status0}' y retorna HTTP 201 Created"
                    )
                ]
            ),
            UserStory(
                id="HU-02",
                title=f"Consulta detallada de {main} por ID",
                role=f"Como usuario del sistema",
                goal=f"quiero obtener la información completa de un {main.lower()} mediante su identificador único",
                benefit=f"para verificar sus atributos, estados y relaciones asociadas",
                scenarios=[
                    BddScenario(
                        title=f"Consulta de {main.lower()} existente",
                        given=f"Dado un {main.lower()} registrado en el sistema con ID conocido",
                        when=f"Cuando se realiza una petición GET a {dom['route']}/{{id}}",
                        then=f"Entonces se retorna código HTTP 200 con el JSON completo del recurso"
                    ),
                    BddScenario(
                        title=f"Consulta de {main.lower()} no encontrado",
                        given=f"Dado un ID inexistente en la base de datos",
                        when=f"Cuando se realiza la petición GET",
                        then=f"Entonces el sistema responde con HTTP 404 Not Found y mensaje estructurado RFC 7807"
                    )
                ]
            ),
            UserStory(
                id="HU-03",
                title=f"Búsqueda y listado paginado de {plural}",
                role=f"Como usuario o administrador",
                goal=f"quiero consultar la lista de {plural.lower()} con soporte de filtros por estado y paginación",
                benefit=f"para navegar eficientemente por grandes volúmenes de registros",
                scenarios=[
                    BddScenario(
                        title=f"Listado paginado estándar",
                        given=f"Dado que existen registros en la base de datos",
                        when=f"Cuando se invoca GET a {dom['route']}?page=0&size=20",
                        then=f"Entonces se retorna HTTP 200 con los primeros 20 registros y cabeceras de paginación"
                    )
                ]
            ),
            UserStory(
                id="HU-04",
                title=f"Actualización parcial de datos de {main}",
                role=f"Como operador autorizado",
                goal=f"quiero modificar campos permitidos de un {main.lower()} en curso",
                benefit=f"para mantener la información actualizada ante cambios del cliente o del negocio",
                scenarios=[
                    BddScenario(
                        title=f"Actualización exitosa",
                        given=f"Dado un {main.lower()} en estado modificable",
                        when=f"Cuando se envía un PUT/PATCH a {dom['route']}/{{id}} con nuevos datos válidos",
                        then=f"Entonces el sistema actualiza la entidad, refresca updated_at y responde con HTTP 200"
                    )
                ]
            ),
            UserStory(
                id="HU-05",
                title=f"Transición de estados en el ciclo de vida de {main}",
                role=f"Como responsable operativo",
                goal=f"quiero avanzar el estado de {main.lower()} siguiendo las reglas de la máquina de estados",
                benefit=f"para reflejar el progreso del flujo de trabajo de negocio",
                scenarios=[
                    BddScenario(
                        title=f"Avance de estado válido",
                        given=f"Dado un {main.lower()} en estado inicial",
                        when=f"Cuando se ejecuta la acción de procesamiento correspondiente",
                        then=f"Entonces el sistema valida la transición y persiste el nuevo estado con HTTP 200"
                    )
                ]
            ),
            UserStory(
                id="HU-06",
                title=f"Cancelación o anulación controlada de {main}",
                role=f"Como usuario autorizado",
                goal=f"quiero cancelar o anular un {main.lower()} que aún no ha concluido su ciclo",
                benefit=f"para suspender el procesamiento y liberar compromisos de negocio",
                scenarios=[
                    BddScenario(
                        title=f"Cancelación exitosa en estado '{status0}'",
                        given=f"Dado un {main.lower()} en estado inicial '{status0}'",
                        when=f"Cuando se solicita la cancelación en {dom['route']}/{{id}}/cancel",
                        then=f"Entonces el estado cambia a '{status_canc}' y se retorna HTTP 200"
                    ),
                    BddScenario(
                        title=f"Rechazo de cancelación en estado finalizado",
                        given=f"Dado un {main.lower()} que ya completó su ciclo de vida",
                        when=f"Cuando se solicita la cancelación",
                        then=f"Entonces el sistema responde con HTTP 409 Conflict explicando la infracción de regla de negocio"
                    )
                ]
            ),
            UserStory(
                id="HU-07",
                title="Validación estricta de integridad y campos obligatorios",
                role="Como motor de validación del microservicio",
                goal="quiero rechazar solicitudes con payloads incompletos, tipos erróneos o valores fuera de rango",
                benefit="para evitar inconsistencias o corrupción de datos en la base de datos relacional",
                scenarios=[
                    BddScenario(
                        title="Rechazo por campos requeridos faltantes",
                        given="Dado un payload sin los atributos obligatorios especificados en el contrato OpenAPI",
                        when=f"Cuando se envía el POST a {dom['route']}",
                        then="Entonces el sistema responde con HTTP 400 Bad Request y detalle de errores Jakarta Validation"
                    )
                ]
            ),
            UserStory(
                id="HU-08",
                title="Control de acceso y autorización por roles (RBAC)",
                role="Como oficial de seguridad",
                goal="quiero que los endpoints críticos exijan autenticación válida y verifiquen roles de usuario",
                benefit="para prevenir accesos no autorizados o modificaciones indebidas de información",
                scenarios=[
                    BddScenario(
                        title="Acceso denegado sin credenciales",
                        given="Dado un cliente anónimo sin token de autenticación",
                        when=f"Cuando intenta realizar una operación protegida en {dom['route']}",
                        then="Entonces el sistema responde con HTTP 401 Unauthorized"
                    )
                ]
            ),
            UserStory(
                id="HU-09",
                title="Auditoría, trazabilidad y marcas temporales",
                role="Como auditor del sistema",
                goal=f"quiero que cada {main.lower()} registre automáticamente fechas de creación y actualización",
                benefit="para disponer de trazabilidad histórica fidedigna de todas las transacciones",
                scenarios=[
                    BddScenario(
                        title="Generación automática de campos de auditoría",
                        given=f"Dado un nuevo registro de {main.lower()}",
                        when="Cuando se persiste en la base de datos",
                        then="Entonces el sistema asigna created_at con timestamp UTC inmutable y updated_at sincronizado"
                    )
                ]
            ),
            UserStory(
                id="HU-10",
                title=f"Reportes operacionales y métricas agregadas de {plural}",
                role="Como líder de operaciones o supervisor",
                goal=f"quiero consultar métricas de totales, conteos por estado y resúmenes de {plural.lower()}",
                benefit="para supervisar el rendimiento y tomar decisiones operativas oportunas",
                scenarios=[
                    BddScenario(
                        title="Consulta exitosa de resumen de métricas",
                        given=f"Dado que existen transacciones registradas en el periodo",
                        when=f"Cuando se consulta el endpoint de métricas o resumen de {dom['route']}",
                        then="Entonces se retorna HTTP 200 con estadísticas de conteo agrupadas por estado"
                    )
                ]
            )
        ]
        return stories, 3200

    @staticmethod
    def synthesize_database_model(
        order: FactoryOrder,
        answers_dict: Dict[str, str],
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[DatabaseModelProposal, int]:
        """
        Diseña el Modelo de Base de Datos Relacional:
        Tablas, tipos de datos según motor (SQLite / SQL Server / Postgres), PKs, FKs,
        diagrama Mermaid erDiagram y DDL SQL.
        Permite al usuario validar las relaciones antes de la generación de código Panache.
        """
        engine = order.technical.database.value
        is_sql_server = "SQL Server" in engine or "Azure SQL" in engine
        dom = AnalystAgent._extract_domain(order)

        # 1. Llamada a LLM si está activo
        detected = LLMFactory.detect_provider(api_key, provider, model_name)
        effective_key = (api_key or "").strip()
        if not effective_key:
            if detected == "deepseek":
                effective_key = os.environ.get("DEEPSEEK_API_KEY")
            else:
                effective_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if detected != "mock" and effective_key:
            sys_msg_text = (
                f"Eres el Agente Arquitecto y Analista de Datos de una fábrica Quarkus 3.x / Java 21. "
                f"A partir del pedido de negocio y de TODAS las especificaciones proporcionadas por el usuario, "
                f"diseña el Modelo Relacional de Base de Datos completo y normalizado en 3FN para el motor {engine}. "
                "CRÍTICO: No utilices plantillas fijas. Modela EXACTAMENTE las entidades, campos y reglas del dominio del usuario. "
                "Deduce exhaustivamente todas las entidades necesarias del dominio (entidad principal, detalles/líneas, auditoría/historial, catálogos/estados), "
                "definiendo para cada tabla sus columnas con tipos de datos exactos (VARCHAR, UUID, DECIMAL, TIMESTAMP, INT, BOOLEAN), "
                "claves primarias PK (UUID), claves foráneas FK referenciadas, nulabilidad, relaciones relacionales (1:N, 1:1, N:M), "
                "código de diagrama Mermaid 'erDiagram' y script DDL SQL completo. "
                "Responde ÚNICAMENTE en JSON plano como un objeto sin bloques ```json:\n"
                "{\n"
                f'  "database_engine": "{engine}",\n'
                '  "tables": [\n'
                '    {\n'
                '      "name": "nombre_tabla",\n'
                '      "description": "Descripción de la entidad",\n'
                '      "columns": [\n'
                '        {"name": "id", "data_type": "VARCHAR(36)", "is_primary_key": true, "is_foreign_key": false, "is_nullable": false, "description": "PK UUID"}\n'
                '      ]\n'
                '    }\n'
                '  ],\n'
                '  "relationships": [\n'
                '    {"source_table": "tabla_a", "target_table": "tabla_b", "relation_type": "1:N", "description": "Una A contiene N B"}\n'
                '  ],\n'
                '  "mermaid_er_diagram": "erDiagram\\n  TABLA_A ||--o{ TABLA_B : contains",\n'
                '  "ddl_sql": "CREATE TABLE ...",\n'
                '  "validation_notes": ["Normalización 3FN verificada", "Integridad referencial y claves foráneas establecidas"]\n'
                "}"
            )
            human_msg_text = (
                f"Servicio: {order.basic_data.service_name}\n"
                f"Equipo Propietario: {order.basic_data.team}\n"
                f"Descripción de Negocio: {order.business.description}\n"
                f"Motor de Base de Datos: {engine}\n"
                f"Especificaciones adicionales:\n{json.dumps(answers_dict, ensure_ascii=False, indent=2)}"
            )
            try:
                raw = LLMFactory.call_chat(
                    prompt=human_msg_text,
                    system_prompt=sys_msg_text,
                    api_key=effective_key,
                    provider=detected,
                    model_name=model_name,
                    temperature=0.2,
                    max_tokens=8192,
                    response_mime_type="application/json"
                )
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "tables" in parsed and len(parsed["tables"]) >= 1:
                    proposal = DatabaseModelProposal(
                        database_engine=engine,
                        tables=[
                            TableDefinition(
                                name=t.get("name", "table"),
                                description=t.get("description", ""),
                                columns=[
                                    ColumnDefinition(
                                        name=c.get("name", "col"),
                                        data_type=c.get("data_type", "VARCHAR(100)"),
                                        is_primary_key=c.get("is_primary_key", False),
                                        is_foreign_key=c.get("is_foreign_key", False),
                                        references=c.get("references"),
                                        is_nullable=c.get("is_nullable", False),
                                        description=c.get("description", "")
                                    )
                                    for c in t.get("columns", [])
                                ]
                            )
                            for t in parsed.get("tables", [])
                        ],
                        relationships=[
                            RelationshipDefinition(
                                source_table=r.get("source_table", ""),
                                target_table=r.get("target_table", ""),
                                relation_type=r.get("relation_type", "1:N"),
                                description=r.get("description", "")
                            )
                            for r in parsed.get("relationships", [])
                        ],
                        mermaid_er_diagram=parsed.get("mermaid_er_diagram", ""),
                        ddl_sql=parsed.get("ddl_sql", ""),
                        validation_notes=parsed.get("validation_notes", [])
                    )
                    return proposal, 4000
            except Exception as e:
                provider_label = "DeepSeek" if detected == "deepseek" else "Gemini"
                raise RuntimeError(f"Error en Database Agent / Modelo Relacional ({provider_label}): {str(e)}")

        # 2. Generador Determinista de Modelo Relacional (Adaptado a motor)
        pk_type = "UNIQUEIDENTIFIER" if is_sql_server else "VARCHAR(36)"
        ts_type = "DATETIME2" if is_sql_server else "TIMESTAMP"
        dec_type = "DECIMAL(18,2)"

        t_main = dom["main_table"]
        t_sub = dom["sub_table"]
        t_det = dom["detail_table"]

        table_sub = TableDefinition(
            name=t_sub,
            description=f"Entidad que representa al {dom['sub_singular']} asociado a las operaciones.",
            columns=[
                ColumnDefinition(name="id", data_type=pk_type, is_primary_key=True, is_nullable=False, description="Identificador único (PK)"),
                ColumnDefinition(name="codigo_externo", data_type="VARCHAR(50)", is_nullable=False, description="Código de identificación o documento"),
                ColumnDefinition(name="nombre_completo", data_type="VARCHAR(150)", is_nullable=False, description="Nombre o razón social"),
                ColumnDefinition(name="email", data_type="VARCHAR(100)", is_nullable=True, description="Correo electrónico de contacto"),
                ColumnDefinition(name="created_at", data_type=ts_type, is_nullable=False, description="Fecha de registro")
            ]
        )

        table_main = TableDefinition(
            name=t_main,
            description=f"Tabla principal de {dom['main_plural']}, almacena cabecera y estado del ciclo de vida.",
            columns=[
                ColumnDefinition(name="id", data_type=pk_type, is_primary_key=True, is_nullable=False, description="Clave primaria UUID"),
                ColumnDefinition(name=f"{t_sub}_id", data_type=pk_type, is_foreign_key=True, references=f"{t_sub}(id)", is_nullable=False, description=f"FK hacia {t_sub}"),
                ColumnDefinition(name="estado", data_type="VARCHAR(30)", is_nullable=False, description=f"Estado: {', '.join(dom['status_enum'])}"),
                ColumnDefinition(name="monto_total", data_type=dec_type, is_nullable=False, description="Monto o valor total calculado"),
                ColumnDefinition(name="notas", data_type="VARCHAR(500)", is_nullable=True, description="Observaciones o notas de negocio"),
                ColumnDefinition(name="created_at", data_type=ts_type, is_nullable=False, description="Fecha y hora de creación"),
                ColumnDefinition(name="updated_at", data_type=ts_type, is_nullable=False, description="Fecha de última actualización")
            ]
        )

        table_det = TableDefinition(
            name=t_det,
            description=f"Detalle granular o ítems relacionados a cada registro de {dom['main_singular']}.",
            columns=[
                ColumnDefinition(name="id", data_type=pk_type, is_primary_key=True, is_nullable=False, description="Clave primaria"),
                ColumnDefinition(name=f"{t_main}_id", data_type=pk_type, is_foreign_key=True, references=f"{t_main}(id)", is_nullable=False, description=f"FK hacia {t_main}"),
                ColumnDefinition(name="codigo_item", data_type="VARCHAR(50)", is_nullable=False, description="Código de ítem, servicio o concepto"),
                ColumnDefinition(name="descripcion", data_type="VARCHAR(200)", is_nullable=False, description="Descripción detallada"),
                ColumnDefinition(name="cantidad", data_type="INTEGER", is_nullable=False, description="Cantidad (entero positivo)"),
                ColumnDefinition(name="precio_unitario", data_type=dec_type, is_nullable=False, description="Precio unitario aplicable"),
                ColumnDefinition(name="subtotal", data_type=dec_type, is_nullable=False, description="Subtotal = cantidad * precio")
            ]
        )

        relationships = [
            RelationshipDefinition(
                source_table=t_sub,
                target_table=t_main,
                relation_type="1:N",
                description=f"Un {dom['sub_singular']} puede originar múltiples {dom['main_plural']} a lo largo del tiempo."
            ),
            RelationshipDefinition(
                source_table=t_main,
                target_table=t_det,
                relation_type="1:N",
                description=f"Cada {dom['main_singular']} contiene uno o varios {dom['detail_singular']}s (composición estricta)."
            )
        ]

        mermaid_diag = f"""erDiagram
    {t_sub.upper()} ||--o{{ {t_main.upper()} : origina
    {t_main.upper()} ||--|{{ {t_det.upper()} : contiene

    {t_sub.upper()} {{
        string id PK
        string codigo_externo
        string nombre_completo
        string email
    }}

    {t_main.upper()} {{
        string id PK
        string {t_sub}_id FK
        string estado
        decimal monto_total
        datetime created_at
    }}

    {t_det.upper()} {{
        string id PK
        string {t_main}_id FK
        string codigo_item
        int cantidad
        decimal subtotal
    }}"""

        if is_sql_server:
            ddl_sql = f"""-- Script DDL para Microsoft SQL Server / Azure SQL
CREATE TABLE {t_sub} (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    codigo_externo VARCHAR(50) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    email VARCHAR(100) NULL,
    created_at DATETIME2 DEFAULT SYSDATETIME() NOT NULL
);

CREATE TABLE {t_main} (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    {t_sub}_id UNIQUEIDENTIFIER NOT NULL,
    estado VARCHAR(30) NOT NULL,
    monto_total DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    notas NVARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT SYSDATETIME() NOT NULL,
    updated_at DATETIME2 DEFAULT SYSDATETIME() NOT NULL,
    CONSTRAINT FK_{t_main}_{t_sub} FOREIGN KEY ({t_sub}_id) REFERENCES {t_sub}(id)
);

CREATE TABLE {t_det} (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    {t_main}_id UNIQUEIDENTIFIER NOT NULL,
    codigo_item VARCHAR(50) NOT NULL,
    descripcion NVARCHAR(200) NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario DECIMAL(18,2) NOT NULL,
    subtotal DECIMAL(18,2) NOT NULL,
    CONSTRAINT FK_{t_det}_{t_main} FOREIGN KEY ({t_main}_id) REFERENCES {t_main}(id) ON DELETE CASCADE
);

CREATE INDEX IX_{t_main}_estado ON {t_main}(estado);
CREATE INDEX IX_{t_main}_created ON {t_main}(created_at DESC);"""
        else:
            ddl_sql = f"""-- Script DDL para SQLite (Local portable) / PostgreSQL
CREATE TABLE {t_sub} (
    id TEXT PRIMARY KEY,
    codigo_externo TEXT NOT NULL,
    nombre_completo TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE {t_main} (
    id TEXT PRIMARY KEY,
    {t_sub}_id TEXT NOT NULL,
    estado TEXT NOT NULL,
    monto_total NUMERIC(18,2) NOT NULL DEFAULT 0.00,
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY ({t_sub}_id) REFERENCES {t_sub}(id)
);

CREATE TABLE {t_det} (
    id TEXT PRIMARY KEY,
    {t_main}_id TEXT NOT NULL,
    codigo_item TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(18,2) NOT NULL,
    subtotal NUMERIC(18,2) NOT NULL,
    FOREIGN KEY ({t_main}_id) REFERENCES {t_main}(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_{t_main}_estado ON {t_main}(estado);
CREATE INDEX IF NOT EXISTS idx_{t_main}_created ON {t_main}(created_at DESC);"""

        validation_notes = [
            f"Estructura normalizada en Tercera Forma Normal (3NF) entre {t_sub}, {t_main} y {t_det}.",
            f"Llaves primarias generadas con UUID/UNIQUEIDENTIFIER para alta escalabilidad sin colisiones distribuidas.",
            f"Integridad referencial asegurada con FKs y borrado en cascada en {t_det}.",
            f"Índice optimizado en columna 'estado' para acelerar consultas paginadas requeridas en el contrato OpenAPI."
        ]

        proposal = DatabaseModelProposal(
            database_engine=engine,
            tables=[table_sub, table_main, table_det],
            relationships=relationships,
            mermaid_er_diagram=mermaid_diag,
            ddl_sql=ddl_sql,
            validation_notes=validation_notes
        )
        return proposal, 2800

    @staticmethod
    def synthesize_openapi_contract(
        order: FactoryOrder,
        answers_dict: Dict[str, str],
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Sintetiza un contrato OpenAPI 3.1 en formato YAML completo a partir del pedido y las aclaraciones.
        Invoca al LLM si hay credenciales configuradas, o genera un contrato dinámico adaptado al dominio.
        """
        # 1. Si hay API key disponible, llamar al LLM real
        detected = LLMFactory.detect_provider(api_key, provider, model_name)
        effective_key = (api_key or "").strip()
        if not effective_key:
            if detected == "deepseek":
                effective_key = os.environ.get("DEEPSEEK_API_KEY")
            else:
                effective_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if detected != "mock" and effective_key:
            sys_msg_text = (
                "Eres el Agente Arquitecto y Analista de la Fábrica de Microservicios Quarkus 3.x / Java 21. "
                "Genera la especificación completa OpenAPI 3.1 en formato JSON para el microservicio solicitado. "
                "CRÍTICO: Modela FIELMENTE y de forma dinámica el dominio de negocio exacto especificado por el usuario, sin plantillas prefabricadas. "
                "Estructura la API de forma ágil y concisa: define entre 3 y 5 endpoints esenciales del microservicio "
                "(Creación POST, Listado con filtro GET, Detalle por ID GET, y Actualización/Cancelación PUT), con sus esquemas DTO centrales en components/schemas. "
                "Incluye openapi ('3.1.0'), info, servers, responses HTTP estándar (200, 201, 400, 404) y RFC 7807 ErrorResponse. "
                "Devuelve ÚNICAMENTE el objeto JSON válido de OpenAPI 3.1 sin delimitadores markdown ni explicaciones."
            )
            answers_summary = "\n".join([f"- {k}: {v}" for k, v in answers_dict.items()]) if answers_dict else "Diseñar a partir de la descripción y requerimientos del negocio."
            human_msg_text = (
                f"Servicio: {order.basic_data.service_name}\n"
                f"Equipo: {order.basic_data.team}\n"
                f"Descripción de Negocio:\n{order.business.description}\n"
                f"Detalles y especificaciones:\n{answers_summary}\n"
                f"Seguridad: {order.technical.security.value}\n"
                f"Base de datos: {order.technical.database.value}\n"
                f"Kafka: {order.technical.enable_kafka}"
            )
            try:
                raw_resp = LLMFactory.call_chat(
                    prompt=human_msg_text,
                    system_prompt=sys_msg_text,
                    api_key=effective_key,
                    provider=detected,
                    model_name=model_name,
                    temperature=0.2,
                    max_tokens=4096,
                    response_mime_type="application/json"
                )
                cleaned = re.sub(r"^```(?:json|yaml)?\s*", "", raw_resp.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()

                parsed_dict = None
                # 1. Intentar JSON directo
                try:
                    parsed_dict = json.loads(cleaned)
                except Exception:
                    # 2. Si fue cortado cerca del final, intentar cerrar llaves abiertas
                    for cut_idx in range(len(cleaned), max(0, len(cleaned) - 500), -20):
                        sub = cleaned[:cut_idx].rstrip().rstrip(",")
                        open_braces = sub.count("{") - sub.count("}")
                        open_brackets = sub.count("[") - sub.count("]")
                        candidate = sub + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
                        try:
                            repaired = json.loads(candidate)
                            if isinstance(repaired, dict) and "paths" in repaired:
                                parsed_dict = repaired
                                break
                        except Exception:
                            continue

                # 3. Si no fue JSON, intentar YAML
                if not parsed_dict:
                    try:
                        parsed_dict = yaml.safe_load(cleaned)
                    except Exception:
                        pass

                if isinstance(parsed_dict, dict) and "paths" in parsed_dict:
                    if "openapi" not in parsed_dict:
                        parsed_dict["openapi"] = "3.1.0"
                    yaml_contract = yaml.dump(parsed_dict, sort_keys=False, allow_unicode=True)
                    return yaml_contract, 5600
                elif isinstance(parsed_dict, dict):
                    if "openapi" not in parsed_dict:
                        parsed_dict["openapi"] = "3.1.0"
                    yaml_contract = yaml.dump(parsed_dict, sort_keys=False, allow_unicode=True)
                    return yaml_contract, 5600
                else:
                    provider_label = "DeepSeek" if detected == "deepseek" else "Gemini"
                    raise RuntimeError(f"El modelo {provider_label} no devolvió una estructura OpenAPI válida.")
            except Exception as e:
                provider_label = "DeepSeek" if detected == "deepseek" else "Gemini"
                raise RuntimeError(f"Error en Architecture Agent / OpenAPI ({provider_label}): {str(e)}")

        # 2. Generador Determinista Dinámico adaptado al Dominio
        dom = AnalystAgent._extract_domain(order)
        service_title = order.basic_data.service_name.replace("-", " ").title()
        route = dom["route"]
        main = dom["main_singular"]
        plural = dom["main_plural"]

        security_scheme = {}
        security_requirement = []
        if order.technical.security.value.startswith("JWT") or order.technical.security.value.startswith("OAuth2"):
            security_scheme = {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": f"Token JWT corporativo para Quarkus SmallRye JWT ({order.technical.security.value})"
                }
            }
            security_requirement = [{"bearerAuth": []}]

        openapi_dict = {
            "openapi": "3.1.0",
            "info": {
                "title": f"API Microservicio {service_title}",
                "version": "1.0.0",
                "description": (
                    f"Microservicio de {dom['domain']} generado por la Fábrica de Agentes Quarkus 3.x / Java 21. "
                    f"Equipo: {order.basic_data.team}. Pedido: {order.business.description}"
                ),
                "contact": {
                    "name": order.basic_data.team,
                    "email": f"{order.basic_data.team.lower().replace(' ', '')}@empresa.com"
                }
            },
            "servers": [
                {
                    "url": "http://localhost:8080/api/v1",
                    "description": "Entorno Local Quarkus Dev"
                }
            ],
            "tags": [
                {
                    "name": plural,
                    "description": f"Operaciones de ciclo de vida de {plural.lower()}"
                }
            ],
            "paths": {
                route: {
                    "post": {
                        "tags": [plural],
                        "summary": f"Registrar un nuevo {main.lower()}",
                        "description": f"Crea un {main.lower()} validando reglas de negocio, identificadores y detalles asociados.",
                        "operationId": f"create{main}",
                        "security": security_requirement,
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/Create{main}Request"}
                                }
                            }
                        },
                        "responses": {
                            "201": {
                                "description": f"{main} registrado exitosamente",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": f"#/components/schemas/{main}Response"}
                                    }
                                }
                            },
                            "400": {
                                "description": "Datos de entrada inválidos o reglas de negocio incumplidas",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                }
                            }
                        }
                    },
                    "get": {
                        "tags": [plural],
                        "summary": f"Consultar {plural.lower()} con filtros y paginación",
                        "description": f"Retorna lista paginada de {plural.lower()} filtrados por estado ({', '.join(dom['status_enum'])}).",
                        "operationId": f"list{plural}",
                        "security": security_requirement,
                        "parameters": [
                            {
                                "name": "status",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "enum": dom["status_enum"]
                                },
                                "description": "Filtrar por estado"
                            },
                            {
                                "name": "page",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 0},
                                "description": "Número de página (0-indexed)"
                            },
                            {
                                "name": "size",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 20},
                                "description": "Tamaño de página"
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": f"Lista paginada de {plural.lower()}",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": f"#/components/schemas/{main}Response"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                f"{route}/{{id}}": {
                    "get": {
                        "tags": [plural],
                        "summary": f"Consultar {main.lower()} por ID",
                        "operationId": f"get{main}ById",
                        "security": security_requirement,
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string", "format": "uuid"},
                                "description": "Identificador único"
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": f"Detalle de {main.lower()}",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": f"#/components/schemas/{main}Response"}
                                    }
                                }
                            },
                            "404": {
                                "description": "Registro no encontrado",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                }
                            }
                        }
                    }
                },
                f"{route}/{{id}}/cancel": {
                    "put": {
                        "tags": [plural],
                        "summary": f"Cancelar o anular {main.lower()}",
                        "description": f"Aplica regla de negocio: solo permite cancelar si se encuentra en estado inicial.",
                        "operationId": f"cancel{main}",
                        "security": security_requirement,
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string", "format": "uuid"}
                            }
                        ],
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/Cancel{main}Request"}
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Operación cancelada exitosamente",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": f"#/components/schemas/{main}Response"}
                                    }
                                }
                            },
                            "409": {
                                "description": "Conflicto: No es posible cancelar en el estado actual",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                }
                            },
                            "404": {
                                "description": "Registro no encontrado",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "securitySchemes": security_scheme,
                "schemas": {
                    f"Create{main}Request": {
                        "type": "object",
                        "required": ["codigoExterno", "nombreContacto", "items"],
                        "properties": {
                            "codigoExterno": {"type": "string", "example": "CLI-1029"},
                            "nombreContacto": {"type": "string", "example": "Juan Pérez"},
                            "email": {"type": "string", "format": "email", "example": "usuario@ejemplo.com"},
                            "notas": {"type": "string", "example": "Prioridad alta"},
                            "items": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": ["codigo", "descripcion", "cantidad", "precioUnitario"],
                                    "properties": {
                                        "codigo": {"type": "string", "example": "SRV-01"},
                                        "descripcion": {"type": "string", "example": "Atención general"},
                                        "cantidad": {"type": "integer", "minimum": 1, "example": 1},
                                        "precioUnitario": {"type": "number", "format": "double", "minimum": 0.01, "example": 50.00}
                                    }
                                }
                            }
                        }
                    },
                    f"Cancel{main}Request": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string", "example": "Cancelación solicitada por el usuario"}
                        }
                    },
                    f"{main}Response": {
                        "type": "object",
                        "required": ["id", "estado", "montoTotal", "createdAt"],
                        "properties": {
                            "id": {"type": "string", "format": "uuid", "example": "b5e8c1b2-1111-4444-9999-0123456789ab"},
                            "codigoExterno": {"type": "string", "example": "CLI-1029"},
                            "estado": {"type": "string", "enum": dom["status_enum"], "example": dom["status_enum"][0]},
                            "montoTotal": {"type": "number", "format": "double", "example": 100.00},
                            "createdAt": {"type": "string", "format": "date-time"},
                            "updatedAt": {"type": "string", "format": "date-time"}
                        }
                    },
                    "ErrorResponse": {
                        "type": "object",
                        "required": ["timestamp", "status", "error", "message"],
                        "properties": {
                            "timestamp": {"type": "string", "format": "date-time"},
                            "status": {"type": "integer", "example": 409},
                            "error": {"type": "string", "example": "Business Rule Violation"},
                            "message": {"type": "string", "example": "La operación solicitada no es válida en el estado actual."},
                            "path": {"type": "string", "example": f"/api/v1{route}/b5e8c1b2/cancel"}
                        }
                    }
                }
            }
        }

        yaml_content = yaml.dump(openapi_dict, sort_keys=False, allow_unicode=True)
        consumed_tokens = 4800
        return yaml_content, consumed_tokens
