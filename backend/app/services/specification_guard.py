"""Is this text a specification at all?

**Why this exists, separately from `injection_guard`.** That module answers "does this text
try to redirect the model?". It correctly found nothing wrong with:

    # Feature Specification: mock-test

    que dia es hoy?

Nothing in that is an attack. It is simply *not a specification*, and the pipeline designed
a whole domain around it: three entities (`DateInquiry`, `CalendarDay`, `AuditEvent`), a
persistence model, and two BDD stories about resolving "the current date" through an
inquiry table. Model calls were spent, artifacts were written, and the result looked like
output. Asked a question, the system produced an API.

That is the failure this module addresses: a generator with no notion of scope will answer
anything, and the answer is indistinguishable from a real result.

**What this is, and is not.** A *plausibility* heuristic, not comprehension. It looks for
the surface features every specification has -- domain nouns, operations, structure -- and
refuses when there are none and the text reads as a question or a fragment. It cannot tell
a good specification from a bad one; it can tell that "que dia es hoy?" is neither.

**Deliberately conservative.** Blocking a legitimate specification is worse than allowing a
silly one: the first stops work, the second wastes a model call. Every threshold is set so a
terse but real request ("Customer CRUD with email and tier") passes, and only input with
*no* domain vocabulary, *no* structure, and a conversational shape is refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

#: Below this, and without any domain vocabulary or structure, the text is a fragment.
MIN_WORDS = 15

#: Domain nouns and operations, Spanish and English. Words a person describing a service
#: almost always uses, and that small talk almost never does. Deliberately excludes generic
#: computing words like "application" or "system", which appear in questions too
#: ("I need it for my application") and would defeat the check.
_DOMAIN_TERMS = (
    # structure and artifacts
    "api", "endpoint", "rest", "servicio", "service", "microservicio", "microservice",
    "entidad", "entity", "modelo", "model", "tabla", "table", "columna", "column",
    "campo", "field", "atributo", "attribute", "esquema", "schema", "base de datos",
    "database", "repositorio", "repository", "persistencia", "persistence", "crud",
    "dto", "controller", "controlador", "migración", "migration",
    # operations
    "crear", "create", "leer", "read", "actualizar", "update", "eliminar", "delete",
    "borrar", "listar", "list", "registrar", "register", "gestionar", "manage",
    "almacenar", "store", "persistir", "persist", "consultar", "filtrar", "filter",
    "validar", "validate", "paginación", "pagination",
    # domain nouns
    "cliente", "customer", "usuario", "user", "pedido", "order", "producto", "product",
    "factura", "invoice", "pago", "payment", "cuenta", "account", "ticket", "reserva",
    "booking", "cita", "appointment", "empleado", "employee", "proveedor", "supplier",
    "inventario", "inventory", "transacción", "transaction", "préstamo", "loan",
    "tarjeta", "card", "saldo", "balance", "producto", "suscripción", "subscription",
    # specification vocabulary
    "requisito", "requirement", "historia", "story", "caso de uso", "use case",
    "criterio", "acceptance", "given", "when", "then", "dado", "cuando", "entonces",
    "validación", "validation", "estado", "status", "rol", "role", "permiso",
    "permission", "autenticación", "authentication", "seguridad", "security",
)

#: A question, or small talk, rather than a description of something to build.
_INTERROGATIVE_START = re.compile(
    r"^\s*(?:#+[^\n]*\n\s*)*"  # tolerate a markdown heading above the line
    r"(qu[eé]|c[oó]mo|c[uá]l(?:es)?|cu[aá]ndo|d[oó]nde|qui[eé]n|por qu[eé]|"
    r"what|how|when|where|who|why|which|is|are|do|does|can|could|should|would|"
    r"hola|hi|hello|hey|buenas)\b",
    re.IGNORECASE,
)

#: The shape a specification arrives in: enumerated content, not just a title.
#:
#: Headings are deliberately **excluded**. An early version counted `#` and was defeated by
#: the very case it was written for -- "# Feature Specification: mock-test" -- because the
#: title alone supplied a structure marker while the body was the question "que dia es
#: hoy?". A heading is a label; a bullet list or acceptance criteria is content.
_STRUCTURE_MARKERS = re.compile(
    r"(?m)^\s*(?:[-*+•]\s|\d+[.)]\s|"
    r"(?:given|when|then|dado|cuando|entonces)\b)",
    re.IGNORECASE,
)

#: Explicit out-of-scope patterns: requests that describe culinary tasks, cooking recipes,
#: creative entertainment (jokes, poems), or everyday non-software physical chores.
#: An enterprise microservice generator must not attempt to fabricate an API or domain model
#: around these.
_OUT_OF_SCOPE_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    # Culinary / Food / Recipe actions (cooking, baking, preparing dishes)
    (
        re.compile(
            r"\b(?:haga|hacer|haz(?:me)?|prepar(?:ar|a|ame)?|cocin(?:ar|a|ame)?|elaborar|sirv(?:a|e|eme)?)\s+"
            r"(?:un|una|el|la|los|las|de|me\s+un)?\s*"
            r"(?:ceviche|comida|receta|almuerzo|cena|desayuno|café|postre|pizza|tacos|sopa|pastel|arroz|plato|hamburguesa|sándwich|sandwich)\b",
            re.IGNORECASE,
        ),
        "solicitud culinaria o preparación física de alimentos ('hacer/cocinar/preparar comida')",
    ),
    (
        re.compile(
            r"\b(?:receta|ingredientes|como\s+cocinar|como\s+preparar)\s+de\b",
            re.IGNORECASE,
        ),
        "solicitud de receta gastronómica",
    ),
    (
        re.compile(
            r"\b(?:make|cook|prepare|bake|brew)\s+(?:me\s+)?(?:a|an|the|some)?\s*"
            r"(?:ceviche|coffee|meal|food|lunch|dinner|breakfast|dish|pizza|soup|cake|burger|sandwich|recipe)\b",
            re.IGNORECASE,
        ),
        "culinary or food preparation command",
    ),
    # Creative writing, entertainment, humor
    (
        re.compile(
            r"\b(?:cu[ée]nta(?:me)?|dime|escribe|escr[íi]beme|genera|canta)\s+(?:un|una|el|la)?\s*"
            r"(?:chiste|broma|poema|poes[íi]a|canci[óo]n|cuento|historia\s+de\s+terror|adivinanza)\b",
            re.IGNORECASE,
        ),
        "solicitud de entretenimiento o escritura creativa ('chistes, poemas o canciones')",
    ),
    (
        re.compile(
            r"\b(?:tell|write|sing)\s+(?:me\s+)?(?:a\s+)?(?:joke|poem|story|song|riddle)\b",
            re.IGNORECASE,
        ),
        "creative entertainment request ('joke, poem or song')",
    ),
    # Physical / household chores / personal tasks
    (
        re.compile(
            r"\b(?:limpi(?:a|ar|ame)|lav(?:a|ar|ame)|conduc(?:ir|e)|manej(?:ar|a))\s+(?:la|el|mi|tu|los|las)\b",
            re.IGNORECASE,
        ),
        "solicitud de tarea física del mundo real",
    ),
    # General trivia or personal queries with no software/business context
    (
        re.compile(
            r"\b(?:dame\s+un\s+consejo\s+de\s+amor|c[óo]mo\s+conquistar|rutina\s+de\s+ejercicios?)\b",
            re.IGNORECASE,
        ),
        "consulta personal fuera del ámbito de software",
    ),
)


@dataclass(frozen=True)
class SpecAssessment:
    """The signals found, and whether they amount to a specification."""

    plausible: bool
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "plausible": self.plausible,
            "reasons": list(self.reasons),
            "signals": dict(self.signals),
        }


class UnlikelySpecificationError(ValueError):
    """The text is not a specification, so no model call was made.

    A `ValueError` so the existing route handlers, which already translate that to 400,
    behave correctly without each of them learning about this.
    """

    def __init__(self, assessment: SpecAssessment, field: str = "rawText") -> None:
        self.assessment = assessment
        self.field = field
        joined = "; ".join(assessment.reasons) or "the text does not describe a service"
        super().__init__(f"{field} does not look like a specification: {joined}")

    def to_dict(self) -> Dict[str, object]:
        friendly_message = (
            "La solicitud no describe un requerimiento de microservicio o arquitectura de software válido. "
            "Por favor, describa un objetivo de negocio o funcionalidad backend "
            "(ej. gestión de pedidos, clientes, inventario, procesamiento de pagos o catálogo de productos)."
        )
        if self.assessment.reasons:
            friendly_message += f" Motivo detectado: {'; '.join(self.assessment.reasons)}."

        return {
            "error": "UNLIKELY_SPECIFICATION",
            "field": self.field,
            "message": friendly_message,
            "detailMessage": str(self),
            **self.assessment.to_dict(),
        }


def assess_specification(text: str) -> SpecAssessment:
    """Judge whether `text` plausibly describes a service to build.

    Returns the signals either way, so a caller can log why something was refused rather
    than reporting a bare rejection.
    """
    raw = text or ""
    stripped = raw.strip()

    # Strip synthetic markdown headers (e.g. "# Feature Specification: app-service")
    # so that labels prepended by internal templates do not fool domain term checks with "servicio" or "service".
    clean_text = re.sub(
        r"^\s*#+\s*(?:Feature\s+)?Specification:[^\n]*\n?",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    content_to_check = clean_text if clean_text else stripped

    words = len(re.findall(r"\w+", content_to_check))
    lowered = content_to_check.lower()
    terms = sum(1 for term in _DOMAIN_TERMS if term in lowered)
    structure = len(_STRUCTURE_MARKERS.findall(raw))
    is_question = bool(content_to_check.endswith("?")) or bool(_INTERROGATIVE_START.match(content_to_check))

    out_of_scope_reasons: List[str] = []
    for pattern, desc in _OUT_OF_SCOPE_PATTERNS:
        match = pattern.search(content_to_check)
        if match:
            out_of_scope_reasons.append(f"{desc} ('{match.group(0)}')")

    signals = {
        "words": words,
        "domainTerms": terms,
        "structureMarkers": structure,
        "readsAsQuestion": int(is_question),
        "outOfScopeMatches": len(out_of_scope_reasons),
    }

    if not stripped or not content_to_check:
        return SpecAssessment(False, ["the text is empty"], signals)

    # 1. Out-of-scope triggers (culinary, entertainment, physical chores):
    # Unless formal BDD structure and technical domain operations are present, reject immediately.
    if out_of_scope_reasons and structure == 0:
        reasons = list(out_of_scope_reasons)
        reasons.append(
            "it names no entities, operations or fields, and has no structure (headings, lists, Given/When/Then)"
        )
        return SpecAssessment(False, reasons, signals)

    # 2. Positive domain vocabulary or structure markers
    if terms > 0 or structure > 0:
        return SpecAssessment(True, [], signals)

    # 3. Text without domain vocabulary or structure:
    # If conversational or a question, refuse:
    if words >= MIN_WORDS and not is_question and not out_of_scope_reasons:
        return SpecAssessment(True, [], signals)

    reasons = []
    if is_question:
        reasons.append(
            "it reads as a question rather than a description of a service to build"
        )
    reasons.append(
        "it names no entities, operations or fields, and has no structure (headings, "
        "lists, Given/When/Then)"
    )
    reasons.append(f"it is {words} word(s) long")
    return SpecAssessment(False, reasons, signals)


def assert_looks_like_specification(text: str, field: str = "rawText") -> SpecAssessment:
    """Raise `UnlikelySpecificationError` unless `text` plausibly describes a service.

    Called before the model, not after: the point is to not spend a call, and to not write
    artifacts, for input that was never a specification.
    """
    assessment = assess_specification(text)
    if not assessment.plausible:
        raise UnlikelySpecificationError(assessment, field=field)
    return assessment


def verify_domain_relevance_llm(
    text: str,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Fast semantic check using the active LLM if available, to catch subtle out-of-scope requests."""
    try:
        from app.services.llm_factory import LLMFactory
        if not api_key or LLMFactory.is_mock(api_key, provider):
            return True, None

        llm = LLMFactory.get_chat_model(
            api_key=api_key,
            provider=provider,
            model_name=model_name,
            temperature=0.0,
        )
        if not llm:
            return True, None

        from langchain_core.messages import SystemMessage, HumanMessage
        import json

        sys_msg = SystemMessage(
            content=(
                "You are an enterprise software domain gatekeeper for a Spring Boot 3 microservice studio. "
                "Evaluate whether the user's input describes a legitimate software system, microservice, "
                "REST API, database entity model, or business transactional domain (e.g. e-commerce, banking, logistics, reservations). "
                "Reject requests that are out-of-scope: cooking recipes, preparing food, casual chitchat, jokes, poems, "
                "physical tasks, or absurd non-software requests.\n"
                "Respond ONLY with a JSON object: {\"valid\": true/false, \"reason\": \"Explicación breve en español\"}"
            )
        )
        usr_msg = HumanMessage(content=f"Requerimiento del usuario:\n{text.strip()}")

        response = llm.invoke([sys_msg, usr_msg])
        content = getattr(response, "content", "") or ""
        clean_json = content.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```", 1)[1].split("```", 1)[0].strip()

        data = json.loads(clean_json)
        is_valid = bool(data.get("valid", True))
        reason = data.get("reason", "")
        return is_valid, reason
    except Exception:
        # Fail-open if the external LLM check times out so network latency doesn't disrupt valid workflows
        return True, None
