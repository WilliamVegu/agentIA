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
_META_TERMS = (
    "api", "endpoint", "rest", "servicio", "service", "microservicio", "microservice",
)

_DOMAIN_TERMS = (
    # structure and artifacts
    *_META_TERMS,
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

_SUBSTANTIVE_TERMS = tuple(t for t in _DOMAIN_TERMS if t not in _META_TERMS)

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
        return {
            "error": "UNLIKELY_SPECIFICATION",
            "field": self.field,
            "message": str(self),
            **self.assessment.to_dict(),
        }


def assess_specification(text: str) -> SpecAssessment:
    """Judge whether `text` plausibly describes a service to build.

    Returns the signals either way, so a caller can log why something was refused rather
    than reporting a bare rejection.
    """
    raw = text or ""
    stripped = raw.strip()

    words = len(re.findall(r"\w+", stripped))
    lowered = stripped.lower()
    substantive_terms = sum(1 for term in _SUBSTANTIVE_TERMS if term in lowered)
    meta_terms = sum(1 for term in _META_TERMS if term in lowered)
    terms = substantive_terms + meta_terms
    structure = len(_STRUCTURE_MARKERS.findall(raw))
    is_question = bool(stripped.endswith("?")) or bool(_INTERROGATIVE_START.match(raw))

    signals = {
        "words": words,
        "domainTerms": terms,
        "substantiveTerms": substantive_terms,
        "metaTerms": meta_terms,
        "structureMarkers": structure,
        "readsAsQuestion": int(is_question),
    }

    if not stripped:
        return SpecAssessment(False, ["the text is empty"], signals)

    # A solitary meta-term like "servicio" or "service" without any substantive operations,
    # domain entities, or specification structure is not a specification (e.g. "como servicio quiero que me sirvas un pollito a la brasa").
    if substantive_terms == 0 and structure == 0 and words < MIN_WORDS:
        reasons = []
        if is_question:
            reasons.append(
                "it reads as a question or conversational request rather than a description of a service to build"
            )
        reasons.append(
            "it names no entities, operations or fields, and has no structure (headings, "
            "lists, Given/When/Then)"
        )
        reasons.append(f"it is {words} word(s) long")
        return SpecAssessment(False, reasons, signals)

    # Substantive domain vocabulary, specification structure, or sufficient prose length
    if substantive_terms > 0 or structure > 0 or words >= MIN_WORDS:
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
