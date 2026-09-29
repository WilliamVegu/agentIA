"""Prompt-injection guardrails for untrusted input.

**What is untrusted.** Everything a user submits: the requirements narrative, the
markdown spec, and every string field inside a JSON blueprint — entity names,
attribute names, `validationRules`, story text, Given/When/Then clauses and
assumptions. All of it is rendered into a stage request that a language model reads.

**Why this is not paranoia on this platform specifically.** Two properties make
injection worse here than in a chat product:

1. **The model's output becomes files.** A steered stage does not just say something
   wrong, it writes code that is then built and run. The blast radius is the
   workspace, not a conversation.
2. **Output feeds later model calls.** The reflector is shown recorded session
   evidence — artifact paths and rule findings produced by an earlier run. Content
   that reaches an artifact can therefore reach a *future* prompt as an instruction.
   That is the indirect channel, and it is the one a self-improving loop must not
   leave open.

**What containment already exists**, and this module is not a substitute for it: a
stage can only persist paths inside its own declared scope
(``runner.out_of_scope_violations``), only relative paths without traversal
(``_is_safe_relative_path``), only allowlisted dependencies
(``compliance.check_dependency_allowlist``), and no credentials
(``check_artifact_credentials``). Those bound the *blast radius*. This module bounds
the *steering*, and ``render_stage_request`` labels the payload as data so the model
has less reason to obey it.

**Deliberately not a blocklist of magic words.** A detector that fires on "ignore"
would reject a legitimate spec saying "ignore previous versions of an order". The
patterns below therefore require an *instruction-shaped* object — an override aimed
at a reader, not ordinary domain language — and only HIGH-confidence matches are
rejected. Everything else is reported as a warning and the request proceeds, because
a guardrail that blocks valid work gets switched off, and then it guards nothing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple

#: A finding that must stop the request before a model sees it.
SEVERITY_HIGH = "HIGH"
#: A finding worth telling the operator about, but not worth refusing the request.
SEVERITY_MEDIUM = "MEDIUM"

RULE_INSTRUCTION_OVERRIDE = "INSTRUCTION_OVERRIDE"
RULE_ROLE_HIJACK = "ROLE_HIJACK"
RULE_POLICY_EVASION = "POLICY_EVASION"
RULE_HIDDEN_TEXT = "HIDDEN_TEXT"
RULE_ENCODED_PAYLOAD = "ENCODED_PAYLOAD"

#: Cap on how much of a finding is echoed back, so a rejection cannot itself become a
#: channel for a large injected blob.
_EXCERPT_CHARS = 120


@dataclass(frozen=True)
class InjectionFinding:
    rule_id: str
    severity: str
    field: str
    excerpt: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "ruleId": self.rule_id,
            "severity": self.severity,
            "field": self.field,
            "excerpt": self.excerpt,
            "message": self.message,
        }


def _excerpt(text: str, match: "re.Match[str]") -> str:
    start = max(0, match.start() - 20)
    snippet = text[start:match.end() + 20]
    snippet = " ".join(snippet.split())
    return snippet[:_EXCERPT_CHARS]


#: Instruction override. The object must be an instruction-like noun, so "ignore
#: previous orders" and "ignore previous versions" do not match.
#:
#: Spanish is covered with the same care as English, and not as a courtesy: the
#: product's own UI, prompts and operators write Spanish, so an English-only detector
#: would be blind to an attack written in the language the users actually use. A first
#: version of this module missed "Ignora las instrucciones anteriores" for exactly
#: that reason. Accents are written as optional classes because both spellings appear
#: in practice and either one is an attack.
_OVERRIDE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:ignore|disregard|forget|discard)\s+(?:all\s+|any\s+|the\s+|your\s+|these\s+)*"
        r"(?:previous|prior|above|earlier|foregoing|preceding)?\s*"
        r"(?:instructions?|prompts?|rules?|directions?|guidelines?|context)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ignora|ignoren|olvida|olviden|descarta|descarten|omite|omitan|desestima)\w*\s+"
        r"(?:todas?\s+|las?\s+|estas?\s+|esas?\s+|tus\s+|sus\s+)*"
        r"(?:instrucciones|indicaciones|reglas|directrices|[óo]rdenes|prompts?|contexto)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:new|updated|real|actual|true)\s+instructions?\s*[:\-]", re.IGNORECASE),
    re.compile(r"\b(?:nuevas?|nuevos?)\s+(?:instrucciones|indicaciones|reglas)\s*[:\-]", re.IGNORECASE),
    re.compile(r"\b(?:overrid|bypass|circumvent)\w*\s+(?:the\s+)?(?:rules?|instructions?|guardrails?|restrictions?|polic\w+|gate|validation)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:anula|anule|elude|eluda|evita|evite|salta|salte|soslaya)\w*\s+(?:las?\s+|los\s+)?"
        r"(?:reglas?|instrucciones|restricciones|pol[íi]ticas?|validaci[óo]n|filtros?|controles?)\b",
        re.IGNORECASE,
    ),
)

#: Role hijack: attempts to become the system, or to address the model as one.
_ROLE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\byou\s+are\s+(?:now|no\s+longer)\b", re.IGNORECASE),
    re.compile(r"\bahora\s+(?:eres|ser[áa]s)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(?:a\s+|an\s+|the\s+)?(?:system|developer|admin|root|assistant)\b", re.IGNORECASE),
    re.compile(r"\bact[úu]a\s+como\s+(?:un|una|el|la)?\s*(?:sistema|desarrollador|administrador|root|asistente)\b", re.IGNORECASE),
    re.compile(r"\b(?:system|developer)\s*(?:prompt|message|instruction)\s*[:\-]", re.IGNORECASE),
    re.compile(r"<\|?\s*(?:system|im_start|im_end|endoftext)\s*\|?>", re.IGNORECASE),
    re.compile(r"^\s*(?:SYSTEM|ASSISTANT|DEVELOPER)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:SISTEMA|ASISTENTE)\s*:", re.IGNORECASE | re.MULTILINE),
)

#: Policy evasion aimed at this pipeline's own controls.
_POLICY_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:do\s+not|don'?t|never)\s+(?:follow|obey|apply|enforce)\s+(?:the\s+)?(?:rules?|instructions?|gate|policy|policies|constitution)\b", re.IGNORECASE),
    re.compile(r"\bno\s+sigas?\s+(?:las?\s+)?(?:reglas?|instrucciones|pol[íi]ticas?|restricciones)\b", re.IGNORECASE),
    re.compile(r"\bskip\s+(?:the\s+)?(?:quality\s+gate|compliance|validation|audit|review)\b", re.IGNORECASE),
    re.compile(r"\bsalta(?:te|r)?\s+(?:el\s+)?(?:quality\s*gate|control\s+de\s+calidad|validaci[óo]n|auditor[íi]a|revisi[óo]n)\b", re.IGNORECASE),
    re.compile(r"\b(?:reveal|print|output|repeat)\s+(?:your\s+)?(?:system\s+prompt|instructions?|api\s*key|credentials?|token)\b", re.IGNORECASE),
    re.compile(r"\b(?:revela|muestra|imprime|repite|dime)\s+(?:tu\s+|el\s+|las?\s+)?(?:prompt|instrucciones|clave|credenciales|token)\b", re.IGNORECASE),
)

_FENCED_SYSTEM = re.compile(r"```\s*(?:system|instructions?|sistema|instrucciones)\b", re.IGNORECASE)

#: A long uninterrupted base64/hex run: an instruction can be smuggled past a reader.
_ENCODED_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")

#: Characters that render as nothing (or as something else) to a human reviewer.
_HIDDEN_CATEGORIES = {"Cf", "Cc"}


def _hidden_characters(text: str) -> List[str]:
    """Zero-width, bidi-override and control characters, excluding normal whitespace."""
    found = []
    for char in text:
        if char in "\t\n\r":
            continue
        if unicodedata.category(char) in _HIDDEN_CATEGORIES:
            found.append(char)
    return found


def scan_text(text: Any, field: str) -> List[InjectionFinding]:
    """Injection findings for one untrusted string. Order is stable for a given input."""
    if not isinstance(text, str) or not text.strip():
        return []

    findings: List[InjectionFinding] = []

    for rule_id, patterns, severity, message in (
        (RULE_INSTRUCTION_OVERRIDE, _OVERRIDE_PATTERNS, SEVERITY_HIGH,
         "Text tries to override the instructions given to the model."),
        (RULE_ROLE_HIJACK, _ROLE_PATTERNS, SEVERITY_HIGH,
         "Text tries to take over the model's role or impersonate a system message."),
        (RULE_POLICY_EVASION, _POLICY_PATTERNS, SEVERITY_HIGH,
         "Text tries to disable this pipeline's own controls."),
    ):
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                findings.append(InjectionFinding(
                    rule_id=rule_id, severity=severity, field=field,
                    excerpt=_excerpt(text, match), message=message,
                ))
                break                      # one finding per rule per field

    if _FENCED_SYSTEM.search(text):
        findings.append(InjectionFinding(
            rule_id=RULE_ROLE_HIJACK, severity=SEVERITY_HIGH, field=field,
            excerpt="```system", message="A fenced block is labelled as system content.",
        ))

    hidden = _hidden_characters(text)
    if hidden:
        names = sorted({unicodedata.name(c, hex(ord(c))) for c in hidden})
        findings.append(InjectionFinding(
            rule_id=RULE_HIDDEN_TEXT, severity=SEVERITY_MEDIUM, field=field,
            excerpt=f"{len(hidden)} hidden character(s): {', '.join(names[:3])}",
            message=(
                "Text contains invisible or direction-overriding characters, which let "
                "a human reviewer see different content from the model."
            ),
        ))

    blob = _ENCODED_BLOB.search(text)
    if blob:
        findings.append(InjectionFinding(
            rule_id=RULE_ENCODED_PAYLOAD, severity=SEVERITY_MEDIUM, field=field,
            excerpt=f"{len(blob.group(0))} characters of encoded data",
            message="A long encoded blob is embedded in a field that should hold prose.",
        ))

    return findings


#: Fields of a blueprint or draft that carry free text. Anything not listed is either
#: an identifier the schema constrains or a value the pipeline generates itself.
_FREE_TEXT_KEYS = frozenset({
    "rawText", "raw_text", "prompt", "markdownSpec", "assumption", "assumptions",
    "intent", "benefit", "role", "given", "when", "then", "title", "description",
    "validationRules", "validation_rules", "rationale", "notes", "feedbackPrompt",
})


def _walk(node: Any, path: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(field_path, text)`` for every string in a nested payload."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, Mapping):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield from _walk(value, child)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


def scan_document(document: Any, *, only_free_text: bool = False) -> List[InjectionFinding]:
    """Scan every untrusted string in a submitted document.

    ``only_free_text=True`` restricts the scan to fields that are *meant* to hold
    prose. Entity and attribute names are still scanned by default, because a name is
    a string the model reads and the schema does not make it safe -- but a caller that
    wants to minimise false positives can narrow it.
    """
    findings: List[InjectionFinding] = []
    for field, text in _walk(document, ""):
        if only_free_text:
            leaf = field.rsplit(".", 1)[-1].split("[", 1)[0]
            if leaf not in _FREE_TEXT_KEYS:
                continue
        findings.extend(scan_text(text, field))
    return findings


def has_blocking_finding(findings: Iterable[InjectionFinding]) -> bool:
    """Whether any finding is severe enough to refuse the request."""
    return any(finding.severity == SEVERITY_HIGH for finding in findings)
